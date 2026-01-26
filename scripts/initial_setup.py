#!/usr/bin/env python3
"""
Initial setup script for Paper RAG Pipeline.
Processes all PDFs in a specified directory and populates the PostgreSQL vector database.
For AWS AgentCore deployment with PostgreSQL + pgvector.
"""

import asyncio
import os
import sys
from pathlib import Path
import warnings
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Suppress resource tracker warnings from multiprocessing (used internally by Docling)
warnings.filterwarnings('ignore', category=UserWarning, module='multiprocessing.resource_tracker')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.document_processor import DocumentProcessor
from src.metadata_extractor import MetadataExtractor
from src.embeddings import EmbeddingGenerator
from src.pg_vector_store import PGVectorStore
from src.services.s3_service import S3Service
from src.core.settings import get_settings
from src.core.database import init_db
from src.utils import setup_logger, find_pdf_files, compute_file_hash


console = Console()


async def initialize_database():
    """Initialize database and run migrations."""
    console.print("[bold blue]Initializing database...[/bold blue]")

    # Initialize database schema
    await init_db()

    # Run Alembic migrations
    try:
        import subprocess
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            console.print(f"[yellow]Migration warning: {result.stderr}[/yellow]")
        else:
            console.print("[green]✓[/green] Database migrations applied")
    except Exception as e:
        console.print(f"[yellow]Could not run migrations automatically: {e}[/yellow]")
        console.print("[yellow]Please run 'alembic upgrade head' manually[/yellow]")

    console.print("[green]✓[/green] Database initialized")


def initialize_components():
    """Initialize all pipeline components."""
    console.print("[bold blue]Initializing components...[/bold blue]")

    settings = get_settings()

    # Set up logging (stdout only for cloud compatibility)
    logger = setup_logger('initial_setup')

    # Validate required settings
    if not settings.openai_api_key:
        console.print("[bold red]Error: OPENAI_API_KEY not found![/bold red]")
        console.print("Set it in .env file or as environment variable")
        sys.exit(1)

    # Initialize document processor
    doc_processor = DocumentProcessor(
        max_chunk_tokens=settings.max_chunk_tokens,
        chunk_overlap=settings.chunk_overlap,
        embedding_model=settings.embedding_model
    )
    console.print("[green]✓[/green] Document processor initialized")

    # Initialize metadata extractor
    metadata_extractor = MetadataExtractor(
        crossref_email=settings.crossref_email
    )
    console.print("[green]✓[/green] Metadata extractor initialized")

    # Initialize embedding generator
    embedding_generator = EmbeddingGenerator(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
        dimensions=settings.vector_dimension,
        batch_size=settings.batch_size
    )
    console.print("[green]✓[/green] Embedding generator initialized")

    # Initialize PostgreSQL vector store
    vector_store = PGVectorStore(
        vector_dimension=settings.vector_dimension
    )
    console.print("[green]✓[/green] PostgreSQL vector store initialized")

    # Initialize S3 service
    s3_service = S3Service()
    console.print("[green]✓[/green] S3 service initialized")

    return doc_processor, metadata_extractor, embedding_generator, vector_store, s3_service, logger


async def process_pdf_library(
    pdf_library_path: Path,
    doc_processor,
    metadata_extractor,
    embedding_generator,
    vector_store,
    s3_service,
    logger
):
    """Process all PDFs in the library."""
    if not pdf_library_path.exists():
        console.print(f"[bold red]Error: PDF library path not found: {pdf_library_path}[/bold red]")
        sys.exit(1)

    # Find all PDFs
    console.print(f"\n[bold blue]Scanning for PDFs in: {pdf_library_path}[/bold blue]")
    pdf_files = find_pdf_files(pdf_library_path, recursive=True)

    if not pdf_files:
        console.print("[yellow]No PDF files found in the library directory.[/yellow]")
        return

    console.print(f"[green]Found {len(pdf_files)} PDF files[/green]\n")

    # Get existing keys to avoid collisions
    existing_keys = await vector_store.get_all_bibtex_keys()

    # Process each PDF
    processed = 0
    skipped = 0
    failed = 0
    total_cost = 0.0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:

        task = progress.add_task("[cyan]Processing PDFs...", total=len(pdf_files))

        for pdf_path in pdf_files:
            progress.update(task, description=f"[cyan]Processing: {pdf_path.name}")

            try:
                # Check for duplicates
                pdf_hash = compute_file_hash(pdf_path)
                if await vector_store.check_duplicate(pdf_hash):
                    logger.info(f"Skipping duplicate: {pdf_path.name}")
                    skipped += 1
                    progress.advance(task)
                    continue

                # Process PDF
                doc, chunks = doc_processor.process_pdf(pdf_path)

                # Extract metadata
                first_pages_text = doc_processor.extract_text_from_first_pages(pdf_path)
                metadata = metadata_extractor.extract_metadata(
                    pdf_path,
                    first_pages_text=first_pages_text,
                    existing_keys=existing_keys
                )

                # Add key to existing set
                existing_keys.add(metadata.bibtex_key)

                # Generate embeddings
                chunk_texts = [chunk.text for chunk in chunks]
                embedding_results = embedding_generator.generate_embeddings_batch(chunk_texts)
                embeddings = [result.embedding for result in embedding_results]

                # Track cost
                stats = embedding_generator.get_embedding_stats(embedding_results)
                total_cost += stats['estimated_cost_usd']

                # Upload PDF to S3
                try:
                    s3_key = await s3_service.upload_pdf_from_file(
                        file_path=pdf_path,
                        bibtex_key=metadata.bibtex_key
                    )
                    logger.info(f"Uploaded PDF to S3: {s3_key}")
                except Exception as e:
                    logger.error(f"Failed to upload PDF to S3 for {pdf_path.name}: {e}")
                    failed += 1
                    progress.advance(task)
                    continue

                # Add to vector store
                await vector_store.add_paper(
                    metadata=metadata,
                    chunks=chunks,
                    embeddings=embeddings,
                    s3_key=s3_key,
                    pdf_hash=pdf_hash
                )

                processed += 1
                logger.info(f"Successfully processed: {pdf_path.name} ({metadata.bibtex_key})")

            except Exception as e:
                logger.error(f"Failed to process {pdf_path.name}: {e}", exc_info=True)
                failed += 1

            progress.advance(task)

    # Print summary
    console.print("\n[bold green]Processing Complete![/bold green]\n")
    console.print(f"[green]✓[/green] Successfully processed: {processed} papers")
    if skipped > 0:
        console.print(f"[yellow]⊘[/yellow] Skipped (duplicates): {skipped} papers")
    if failed > 0:
        console.print(f"[red]✗[/red] Failed: {failed} papers")

    console.print(f"\n[bold]Total estimated cost:[/bold] ${total_cost:.4f}")

    # Show database stats
    stats = await vector_store.get_statistics()
    console.print(f"\n[bold]Database Statistics:[/bold]")
    console.print(f"  Total papers: {stats['total_papers']}")
    console.print(f"  Total chunks: {stats['total_chunks']}")
    console.print(f"  Backend: {stats['database_type']}")


async def main():
    """Main setup function."""
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]  Paper RAG Pipeline - Initial Setup[/bold cyan]")
    console.print("[bold cyan]  AWS AgentCore (PostgreSQL + pgvector + S3)[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]\n")

    # Load environment variables
    load_dotenv()

    # Get PDF library path from command line or prompt
    if len(sys.argv) > 1:
        pdf_library_path = Path(sys.argv[1])
    else:
        console.print("[bold]Enter the path to your PDF library:[/bold]")
        pdf_path_str = input("> ").strip()
        if not pdf_path_str:
            console.print("[bold red]Error: No path provided![/bold red]")
            sys.exit(1)
        pdf_library_path = Path(pdf_path_str)

    # Initialize database
    await initialize_database()

    # Initialize components
    doc_processor, metadata_extractor, embedding_generator, vector_store, s3_service, logger = initialize_components()

    try:
        # Process PDF library
        await process_pdf_library(
            pdf_library_path,
            doc_processor,
            metadata_extractor,
            embedding_generator,
            vector_store,
            s3_service,
            logger
        )

        console.print("\n[bold green]Setup complete! The MCP server is ready to use.[/bold green]\n")
        console.print("To start the server, run:")
        console.print("  python src/mcp_http_server.py")
    finally:
        # Explicit cleanup
        logger.info("Cleaning up resources...")


if __name__ == "__main__":
    asyncio.run(main())
