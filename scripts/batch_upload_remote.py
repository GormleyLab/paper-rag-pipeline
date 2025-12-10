#!/usr/bin/env python3
"""
Batch upload PDFs to remote RunPod MCP server.

This script reads PDFs from a local folder, encodes them as base64,
and uploads them one at a time to the RunPod serverless MCP server.

Usage:
    # Dry run first to see what would be uploaded
    python scripts/batch_upload_remote.py /path/to/your/pdfs --dry-run

    # Actually upload
    python scripts/batch_upload_remote.py /path/to/your/pdfs

    # With recursive search and tags
    python scripts/batch_upload_remote.py /path/to/your/pdfs -r --tags neuroscience

    # Resume after interruption
    python scripts/batch_upload_remote.py /path/to/your/pdfs --resume

Environment variables required (set in .env):
    MCP_SERVER_URL: Your RunPod endpoint URL (e.g., https://api.runpod.ai/v2/ENDPOINT_ID)
    RUNPOD_API_KEY: Your RunPod API key

Optional environment variables:
    REQUEST_TIMEOUT: Timeout in seconds per PDF (default: 600)
    MAX_FILE_SIZE_MB: Maximum PDF file size in MB (default: 15, due to RunPod 20MB limit)

The script will:
    1. Upload PDFs one at a time using RunPod's /runsync endpoint (20MB limit)
    2. Skip files larger than 15MB (base64 encoding adds ~33% overhead)
    3. Poll for completion every 5 seconds
    4. Track progress and allow resuming if interrupted
    5. Retry failed uploads up to 3 times
"""

import os
import sys
import base64
import time
import argparse
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

console = Console()

# Configuration
DEFAULT_TIMEOUT = 600  # 10 minutes per PDF
DEFAULT_MAX_FILE_SIZE_MB = 15  # RunPod /runsync has 20MB limit, base64 adds ~33% overhead
MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds
POLL_INTERVAL = 5  # seconds between status checks


def get_config():
    """Load configuration from environment variables."""
    server_url = os.getenv("MCP_SERVER_URL")
    api_key = os.getenv("RUNPOD_API_KEY")

    if not server_url:
        console.print(
            "[bold red]Error: MCP_SERVER_URL environment variable not set[/bold red]"
        )
        console.print("Set it in your .env file:")
        console.print("  MCP_SERVER_URL=https://api.runpod.ai/v2/YOUR_ENDPOINT_ID")
        sys.exit(1)

    if not api_key:
        console.print(
            "[bold red]Error: RUNPOD_API_KEY environment variable not set[/bold red]"
        )
        console.print("Set it in your .env file:")
        console.print("  RUNPOD_API_KEY=your-runpod-api-key")
        sys.exit(1)

    # Ensure URL doesn't have trailing slash
    server_url = server_url.rstrip("/")

    return {
        "server_url": server_url,
        "api_key": api_key,
        "timeout": int(os.getenv("REQUEST_TIMEOUT", DEFAULT_TIMEOUT)),
        "max_file_size_mb": float(os.getenv("MAX_FILE_SIZE_MB", DEFAULT_MAX_FILE_SIZE_MB)),
    }


def find_pdf_files(folder_path: Path) -> list[Path]:
    """Find all PDF files in folder (non-recursive by default)."""
    pdf_files = sorted(folder_path.glob("*.pdf"))
    return pdf_files


def find_pdf_files_recursive(folder_path: Path) -> list[Path]:
    """Find all PDF files in folder and subfolders."""
    pdf_files = sorted(folder_path.rglob("*.pdf"))
    return pdf_files


def encode_pdf(pdf_path: Path) -> tuple[str, str]:
    """Read and base64-encode a PDF file."""
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    pdf_data = base64.b64encode(pdf_bytes).decode("utf-8")
    return pdf_path.name, pdf_data


def create_batch(pdf_paths: list[Path]) -> list[dict]:
    """Create a batch of encoded PDFs."""
    batch = []
    for pdf_path in pdf_paths:
        filename, pdf_data = encode_pdf(pdf_path)
        batch.append({"filename": filename, "pdf_data": pdf_data})
    return batch


def run_sync_job(
    client: httpx.Client,
    server_url: str,
    batch: list[dict],
    custom_tags: list[str],
    job_id: int,
    timeout: int,
) -> dict:
    """Run a synchronous job on RunPod using /runsync endpoint (20MB limit)."""

    # RunPod serverless input format wrapping MCP JSON-RPC
    payload = {
        "input": {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "add_papers_from_folder_upload",
                "arguments": {"pdf_files": batch, "custom_tags": custom_tags},
            },
            "id": job_id,
        }
    }

    # Use /runsync for synchronous execution (20MB payload limit vs 10MB for /run)
    response = client.post(f"{server_url}/runsync", json=payload, timeout=timeout)
    response.raise_for_status()

    return response.json()


def parse_runpod_response(status: dict) -> dict:
    """Parse RunPod job output and extract results."""
    output = status.get("output", {})

    # Handle error case
    if "error" in status:
        return {
            "success": False,
            "error": status["error"],
            "processed": 0,
            "skipped": 0,
            "failed": 0,
        }

    # The output contains the MCP response
    if isinstance(output, dict):
        # Check for MCP error
        if "error" in output:
            return {
                "success": False,
                "error": output["error"].get("message", "Unknown error"),
                "processed": 0,
                "skipped": 0,
                "failed": 0,
            }

        # Get the result from MCP response
        result = output.get("result", {})

        # Handle the nested content structure from MCP
        if isinstance(result, dict) and "content" in result:
            content_list = result.get("content", [])
            if content_list and isinstance(content_list[0], dict):
                text = content_list[0].get("text", "")
            else:
                text = str(content_list)
        else:
            text = str(result)
    else:
        text = str(output)

    # Parse the text response to extract counts
    processed = 0
    skipped = 0
    failed = 0

    for line in text.split("\n"):
        if "Processed:" in line:
            try:
                processed = int(line.split(":")[1].split()[0])
            except (ValueError, IndexError):
                pass
        elif "Skipped" in line and "duplicates" in line:
            try:
                skipped = int(line.split(":")[1].split()[0])
            except (ValueError, IndexError):
                pass
        elif "Failed:" in line:
            try:
                failed = int(line.split(":")[1].split()[0])
            except (ValueError, IndexError):
                pass

    return {
        "success": True,
        "text": text,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
    }


def load_progress(progress_file: Path) -> set[str]:
    """Load set of already-processed filenames from progress file."""
    if not progress_file.exists():
        return set()

    with open(progress_file, "r") as f:
        return set(line.strip() for line in f if line.strip())


def save_progress(progress_file: Path, filenames: list[str]):
    """Append processed filenames to progress file."""
    with open(progress_file, "a") as f:
        for filename in filenames:
            f.write(f"{filename}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Batch upload PDFs to remote RunPod MCP server"
    )
    parser.add_argument(
        "pdf_folder", type=str, help="Path to folder containing PDF files"
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Search for PDFs recursively in subfolders",
    )
    parser.add_argument(
        "--tags",
        "-t",
        type=str,
        nargs="*",
        default=[],
        help="Custom tags to apply to all uploaded papers",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous run (skip already-processed files)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )

    args = parser.parse_args()

    # Print banner
    console.print(
        "\n[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]"
    )
    console.print("[bold cyan]  Paper RAG Pipeline - Remote Batch Upload[/bold cyan]")
    console.print(
        "[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]\n"
    )

    # Load configuration
    config = get_config()
    console.print(f"[green]✓[/green] Server URL: {config['server_url']}")
    console.print(f"[green]✓[/green] Max file size: {config['max_file_size_mb']} MB")
    console.print(f"[green]✓[/green] Timeout: {config['timeout']} seconds per PDF")

    # Find PDF files
    pdf_folder = Path(args.pdf_folder).resolve()
    if not pdf_folder.exists():
        console.print(f"[bold red]Error: Folder not found: {pdf_folder}[/bold red]")
        sys.exit(1)

    console.print(f"\n[bold blue]Scanning for PDFs in: {pdf_folder}[/bold blue]")

    if args.recursive:
        pdf_files = find_pdf_files_recursive(pdf_folder)
        console.print("[dim](recursive search enabled)[/dim]")
    else:
        pdf_files = find_pdf_files(pdf_folder)

    if not pdf_files:
        console.print("[yellow]No PDF files found in the specified folder.[/yellow]")
        sys.exit(0)

    console.print(f"[green]Found {len(pdf_files)} PDF files[/green]")

    # Handle resume functionality
    progress_file = pdf_folder / ".upload_progress.txt"
    processed_files = set()

    if args.resume:
        processed_files = load_progress(progress_file)
        if processed_files:
            console.print(
                f"[yellow]Resuming: {len(processed_files)} files already processed[/yellow]"
            )
            pdf_files = [f for f in pdf_files if f.name not in processed_files]
            console.print(f"[green]Remaining: {len(pdf_files)} files to process[/green]")

    if not pdf_files:
        console.print("[green]All files already processed![/green]")
        sys.exit(0)

    # Filter out files that are too large
    max_size_bytes = config["max_file_size_mb"] * 1024 * 1024
    valid_files = []
    oversized_files = []

    for pdf_path in pdf_files:
        size_bytes = pdf_path.stat().st_size
        if size_bytes > max_size_bytes:
            oversized_files.append((pdf_path, size_bytes / (1024 * 1024)))
        else:
            valid_files.append(pdf_path)

    if oversized_files:
        console.print(
            f"\n[yellow]Warning: {len(oversized_files)} files exceed {config['max_file_size_mb']} MB limit and will be skipped:[/yellow]"
        )
        for pdf_path, size_mb in oversized_files:
            console.print(f"  - {pdf_path.name} ({size_mb:.1f} MB)")

    pdf_files = valid_files

    if not pdf_files:
        console.print("[yellow]No files within size limit to upload.[/yellow]")
        sys.exit(0)

    # Dry run - just show what would be uploaded
    if args.dry_run:
        console.print("\n[bold yellow]DRY RUN - No files will be uploaded[/bold yellow]\n")

        table = Table(title="Files to Upload")
        table.add_column("#", style="cyan")
        table.add_column("Filename", style="green")
        table.add_column("Size", style="dim")

        for i, pdf_path in enumerate(pdf_files, 1):
            size_mb = pdf_path.stat().st_size / (1024 * 1024)
            table.add_row(str(i), pdf_path.name, f"{size_mb:.1f} MB")

        console.print(table)

        console.print(f"\n[bold]Total:[/bold] {len(pdf_files)} files to upload (one at a time)")
        if oversized_files:
            console.print(f"[yellow]Skipped:[/yellow] {len(oversized_files)} oversized files")
        sys.exit(0)

    console.print(f"\n[bold]Processing {len(pdf_files)} PDFs (one at a time)[/bold]")
    if args.tags:
        console.print(f"[dim]Tags: {', '.join(args.tags)}[/dim]")

    # Initialize tracking
    total_processed = 0
    total_skipped = 0
    total_failed = 0
    failed_files = []
    start_time = time.time()

    # Create HTTP client with RunPod auth header
    with httpx.Client(
        headers={"Authorization": f"Bearer {config['api_key']}"},
        timeout=config["timeout"],
    ) as client:

        # Test connection first
        console.print("\n[bold blue]Testing connection...[/bold blue]")
        try:
            test_response = client.get(f"{config['server_url']}/health", timeout=10)
            if test_response.status_code == 200:
                console.print("[green]✓[/green] Connection successful\n")
            else:
                console.print(
                    f"[yellow]Warning: Health check returned status {test_response.status_code}[/yellow]\n"
                )
        except Exception as e:
            console.print(f"[yellow]Warning: Could not reach health endpoint: {e}[/yellow]")
            console.print("[dim]Continuing anyway (endpoint may still work)...[/dim]\n")

        # Process files one at a time with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            task = progress.add_task("[cyan]Uploading PDFs...", total=len(pdf_files))

            for file_num, pdf_file in enumerate(pdf_files, 1):
                progress.update(
                    task,
                    description=f"[cyan]{file_num}/{len(pdf_files)}: Encoding {pdf_file.name}...",
                )

                # Encode single PDF
                try:
                    batch_data = create_batch([pdf_file])
                except Exception as e:
                    console.print(f"\n[red]Error encoding {pdf_file.name}: {e}[/red]")
                    failed_files.append(pdf_file.name)
                    total_failed += 1
                    progress.advance(task)
                    continue

                progress.update(
                    task,
                    description=f"[cyan]{file_num}/{len(pdf_files)}: Processing {pdf_file.name}...",
                )

                # Submit and wait with retry logic
                success = False
                last_error = None

                for attempt in range(MAX_RETRIES):
                    try:
                        # Run synchronous job (uses /runsync with 20MB limit)
                        response = run_sync_job(
                            client=client,
                            server_url=config["server_url"],
                            batch=batch_data,
                            custom_tags=args.tags,
                            job_id=file_num,
                            timeout=config["timeout"],
                        )

                        result = parse_runpod_response(response)

                        if result["success"]:
                            total_processed += result["processed"]
                            total_skipped += result["skipped"]
                            total_failed += result["failed"]

                            # Save progress
                            save_progress(progress_file, [pdf_file.name])

                            success = True
                            break
                        else:
                            last_error = result.get("error", "Unknown error")
                            console.print(
                                f"\n[yellow]{pdf_file.name} error: {last_error}[/yellow]"
                            )

                    except TimeoutError as e:
                        last_error = str(e)
                        console.print(
                            f"\n[yellow]{pdf_file.name} timeout (attempt {attempt + 1}/{MAX_RETRIES})[/yellow]"
                        )
                        if attempt < MAX_RETRIES - 1:
                            console.print(f"[dim]Retrying in {RETRY_DELAY} seconds...[/dim]")
                            time.sleep(RETRY_DELAY)

                    except httpx.HTTPStatusError as e:
                        last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                        console.print(
                            f"\n[yellow]{pdf_file.name} HTTP error: {last_error}[/yellow]"
                        )
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY)

                    except Exception as e:
                        last_error = str(e)
                        console.print(f"\n[red]{pdf_file.name} error: {e}[/red]")
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY)

                if not success:
                    console.print(
                        f"[red]{pdf_file.name} failed after {MAX_RETRIES} attempts: {last_error}[/red]"
                    )
                    failed_files.append(pdf_file.name)
                    total_failed += 1

                progress.advance(task)

    # Print summary
    elapsed = time.time() - start_time
    elapsed_min = elapsed / 60

    console.print(
        "\n[bold green]═══════════════════════════════════════════════════════[/bold green]"
    )
    console.print("[bold green]  Upload Complete![/bold green]")
    console.print(
        "[bold green]═══════════════════════════════════════════════════════[/bold green]\n"
    )

    summary_table = Table(title="Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")

    summary_table.add_row("Successfully processed", str(total_processed))
    summary_table.add_row("Skipped (duplicates)", str(total_skipped))
    summary_table.add_row("Skipped (oversized)", str(len(oversized_files)))
    summary_table.add_row("Failed", str(total_failed))
    summary_table.add_row("Total time", f"{elapsed_min:.1f} minutes")

    if total_processed > 0:
        avg_time = elapsed / total_processed
        summary_table.add_row("Average time per paper", f"{avg_time:.1f} seconds")

    console.print(summary_table)

    if failed_files:
        console.print("\n[bold red]Failed files:[/bold red]")
        for filename in failed_files[:20]:
            console.print(f"  - {filename}")
        if len(failed_files) > 20:
            console.print(f"  ... and {len(failed_files) - 20} more")

        # Save failed files list
        failed_file = pdf_folder / ".upload_failed.txt"
        with open(failed_file, "w") as f:
            for filename in failed_files:
                f.write(f"{filename}\n")
        console.print(f"\n[dim]Failed files list saved to: {failed_file}[/dim]")

    if oversized_files:
        # Save oversized files list
        oversized_file = pdf_folder / ".upload_oversized.txt"
        with open(oversized_file, "w") as f:
            for pdf_path, size_mb in oversized_files:
                f.write(f"{pdf_path.name}\t{size_mb:.1f} MB\n")
        console.print(f"\n[dim]Oversized files list saved to: {oversized_file}[/dim]")
        console.print("[dim]These files need to be uploaded manually or compressed.[/dim]")

    if args.resume or total_processed > 0:
        console.print(f"\n[dim]Progress saved to: {progress_file}[/dim]")
        console.print("[dim]Use --resume to continue from where you left off[/dim]")


if __name__ == "__main__":
    main()
