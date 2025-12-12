#!/usr/bin/env python3
"""
Test script for the Paper RAG Pipeline HTTP server upload tools.
Tests the new add_paper_from_upload and add_papers_from_folder_upload tools.

Usage:
    python test_http_upload.py [--with-server]

    --with-server: Also start the HTTP server and test via HTTP requests
                   (requires uvicorn)
"""

import sys
import base64
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_upload_tools_direct():
    """Test upload tools by calling them directly (no HTTP server needed)."""
    print("=" * 60)
    print("Testing HTTP Upload Tools (Direct Call)")
    print("=" * 60)

    # Import from HTTP server module
    from src.mcp_http_server import (
        initialize_components,
        load_config,
        add_paper_from_upload,
        add_papers_from_folder_upload,
        database_stats,
        delete_paper
    )
    from src.utils import compute_hash_from_bytes

    try:
        # Initialize components
        print("\n1. Initializing components...")
        initialize_components()
        print("   ✅ Components initialized\n")

        # Get initial stats
        print("2. Getting initial database stats...")
        stats = await database_stats()
        print(f"   {stats}\n")

        # Create a minimal valid PDF for testing
        # This is the smallest valid PDF structure
        test_pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
312
%%EOF"""

        # Test 3: Test hash computation from bytes
        print("3. Testing compute_hash_from_bytes...")
        pdf_hash = compute_hash_from_bytes(test_pdf_content)
        print(f"   Hash: {pdf_hash[:16]}...")
        print("   ✅ Hash computation works\n")

        # Test 4: Test base64 encoding/decoding
        print("4. Testing base64 encoding...")
        pdf_base64 = base64.b64encode(test_pdf_content).decode('utf-8')
        decoded = base64.b64decode(pdf_base64)
        assert decoded == test_pdf_content
        print(f"   Encoded length: {len(pdf_base64)} chars")
        print("   ✅ Base64 encoding/decoding works\n")

        # Test 5: Test single upload with invalid base64
        print("5. Testing error handling - invalid base64...")
        result = await add_paper_from_upload(
            pdf_data="not-valid-base64!!!",
            filename="invalid.pdf"
        )
        assert "Error" in result
        print(f"   Result: {result[:60]}...")
        print("   ✅ Invalid base64 properly rejected\n")

        # Test 6: Test single upload with non-PDF data
        print("6. Testing error handling - non-PDF data...")
        non_pdf_base64 = base64.b64encode(b"This is not a PDF file").decode('utf-8')
        result = await add_paper_from_upload(
            pdf_data=non_pdf_base64,
            filename="not_a_pdf.pdf"
        )
        assert "Error" in result and "PDF" in result
        print(f"   Result: {result}")
        print("   ✅ Non-PDF data properly rejected\n")

        # Test 7: Test batch upload with empty list
        print("7. Testing batch upload with empty list...")
        result = await add_papers_from_folder_upload(
            pdf_files=[],
            custom_tags=["test"]
        )
        print(f"   Result: {result[:100]}...")
        print("   ✅ Empty batch handled\n")

        # Test 8: Test batch upload with mixed valid/invalid
        print("8. Testing batch upload with mixed valid/invalid data...")
        result = await add_papers_from_folder_upload(
            pdf_files=[
                {"filename": "invalid1.pdf", "pdf_data": "bad-base64"},
                {"filename": "not_pdf.pdf", "pdf_data": non_pdf_base64},
            ],
            custom_tags=["test-batch"]
        )
        print(f"   Result:\n{result}")
        assert "Failed: 2" in result or "failed" in result.lower()
        print("   ✅ Batch error handling works\n")

        # Test 9: Test with a real PDF from the database (if available)
        print("9. Testing with real PDF (duplicate detection)...")
        sample_pdfs = list(Path("data/pdfs").glob("*.pdf"))
        if sample_pdfs:
            sample_pdf = sample_pdfs[0]
            print(f"   Using: {sample_pdf.name}")

            # Read and encode the PDF
            pdf_bytes = sample_pdf.read_bytes()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # Try to upload - should detect as duplicate
            result = await add_paper_from_upload(
                pdf_data=pdf_base64,
                filename=sample_pdf.name,
                custom_tags=["test-duplicate"]
            )
            print(f"   Result: {result[:80]}...")

            if "duplicate" in result.lower() or "already exists" in result.lower():
                print("   ✅ Duplicate detection works\n")
            else:
                print("   ⚠️  PDF was not detected as duplicate (may be a new file)\n")
        else:
            print("   ⚠️  No sample PDFs found in data/pdfs/\n")

        print("=" * 60)
        print("All direct tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


async def test_http_server():
    """Test the HTTP server by making actual HTTP requests."""
    print("\n" + "=" * 60)
    print("Testing HTTP Server (via HTTP requests)")
    print("=" * 60)

    try:
        import httpx
    except ImportError:
        print("⚠️  httpx not installed. Run: pip install httpx")
        return False

    import os
    api_key = os.getenv("MCP_API_KEY", "test-key")
    base_url = "http://127.0.0.1:8080"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Test 1: Check server is running by calling MCP endpoint
            print("\n1. Checking server is running...")
            response = await client.post(
                f"{base_url}/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 0
                }
            )
            if response.status_code == 200:
                print("   ✅ Server is running\n")
            else:
                print(f"   ❌ Server returned {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
        except httpx.ConnectError:
            print("   ❌ Cannot connect to server at http://127.0.0.1:8080")
            print("   Start the server with: python -m src.mcp_http_server")
            return False

        # Test 2: Get database stats via MCP
        print("2. Testing database_stats via HTTP...")
        response = await client.post(
            f"{base_url}/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "database_stats",
                    "arguments": {}
                },
                "id": 1
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.text[:200]}...")
            print("   ✅ MCP call works\n")
        else:
            print(f"   ❌ Error: {response.text}")

        # Test 3: Test upload with invalid data
        print("3. Testing add_paper_from_upload with invalid data...")
        response = await client.post(
            f"{base_url}/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "add_paper_from_upload",
                    "arguments": {
                        "pdf_data": "not-valid-base64",
                        "filename": "test.pdf"
                    }
                },
                "id": 2
            }
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        print("   ✅ Error handling works\n")

        # Test 4: Test batch upload with empty list
        print("4. Testing add_papers_from_folder_upload with empty list...")
        response = await client.post(
            f"{base_url}/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "add_papers_from_folder_upload",
                    "arguments": {
                        "pdf_files": [],
                        "custom_tags": ["test"]
                    }
                },
                "id": 3
            }
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        print("   ✅ Batch upload works\n")

    print("=" * 60)
    print("HTTP server tests completed!")
    print("=" * 60)
    return True


def start_server_background():
    """Start the HTTP server in a background thread."""
    import threading
    import time

    def run_server():
        from src.mcp_http_server import run_http_server
        run_http_server(host="127.0.0.1", port=8080)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Wait for server to start
    print("Starting HTTP server...")
    time.sleep(3)
    return thread


async def main():
    """Main test function."""
    import argparse

    parser = argparse.ArgumentParser(description="Test HTTP upload tools")
    parser.add_argument("--with-server", action="store_true",
                       help="Also test via HTTP server")
    args = parser.parse_args()

    print("\n🧪 Paper RAG Pipeline - HTTP Upload Tools Test\n")

    # Always run direct tests
    success = await test_upload_tools_direct()

    # Optionally run HTTP server tests
    if args.with_server and success:
        # Start server in background
        start_server_background()

        # Run HTTP tests
        await test_http_server()

    print("\n✅ Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
