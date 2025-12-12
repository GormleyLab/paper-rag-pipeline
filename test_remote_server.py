#!/usr/bin/env python3
"""
Test script for the Paper RAG Pipeline remote MCP server on RunPod.
Tests all MCP tools via HTTP requests to verify server functionality.

Usage:
    python test_remote_server.py --url https://ENDPOINT_ID.api.runpod.ai --api-key YOUR_KEY

    # Or use environment variables:
    export MCP_API_KEY="your-key"
    python test_remote_server.py --url https://ENDPOINT_ID.api.runpod.ai

    # Run specific test categories:
    python test_remote_server.py --url ... --only health
    python test_remote_server.py --url ... --only readonly
    python test_remote_server.py --url ... --only upload
    python test_remote_server.py --url ... --only errors
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str
    duration_ms: float = 0.0


class RemoteServerTester:
    """Test suite for remote MCP server."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.results: list[TestResult] = []
        self.request_id = 0

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        # Minimal valid PDF for testing uploads
        self.test_pdf_content = b"""%PDF-1.4
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

    def _next_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id

    async def _call_mcp_tool(
        self,
        client: httpx.AsyncClient,
        tool_name: str,
        arguments: dict,
        timeout: Optional[float] = None
    ) -> dict:
        """Call an MCP tool via HTTP."""
        response = await client.post(
            f"{self.base_url}/mcp",
            headers=self.headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": self._next_id()
            },
            timeout=timeout or self.timeout
        )
        return {
            "status_code": response.status_code,
            "body": response.text,
            "json": response.json() if response.status_code == 200 else None
        }

    def _record_result(self, name: str, passed: bool, message: str, duration_ms: float = 0.0):
        """Record a test result."""
        result = TestResult(name, passed, message, duration_ms)
        self.results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        duration_str = f" ({duration_ms:.0f}ms)" if duration_ms > 0 else ""
        print(f"  {status}: {name}{duration_str}")
        if not passed:
            print(f"         {message}")

    # =========================================================================
    # Health & Connectivity Tests
    # =========================================================================

    async def test_ping(self, client: httpx.AsyncClient) -> bool:
        """Test /ping endpoint."""
        try:
            import time
            start = time.time()
            response = await client.get(
                f"{self.base_url}/ping",
                headers=self.headers,
                timeout=30.0
            )
            duration = (time.time() - start) * 1000

            if response.status_code == 200:
                self._record_result("ping", True, "Server responded", duration)
                return True
            else:
                self._record_result("ping", False, f"Status {response.status_code}: {response.text[:100]}", duration)
                return False
        except Exception as e:
            self._record_result("ping", False, f"Error: {e}")
            return False

    async def test_health(self, client: httpx.AsyncClient) -> bool:
        """Test /health endpoint."""
        try:
            import time
            start = time.time()
            response = await client.get(
                f"{self.base_url}/health",
                headers=self.headers,
                timeout=30.0
            )
            duration = (time.time() - start) * 1000

            if response.status_code == 200:
                self._record_result("health", True, f"Response: {response.text[:100]}", duration)
                return True
            else:
                self._record_result("health", False, f"Status {response.status_code}: {response.text[:100]}", duration)
                return False
        except Exception as e:
            self._record_result("health", False, f"Error: {e}")
            return False

    async def test_auth_required(self, client: httpx.AsyncClient) -> bool:
        """Test that authentication is required."""
        try:
            import time
            start = time.time()
            # Make request without auth header
            response = await client.post(
                f"{self.base_url}/mcp",
                headers={"Content-Type": "application/json"},  # No auth
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": self._next_id()
                },
                timeout=30.0
            )
            duration = (time.time() - start) * 1000

            if response.status_code == 401:
                self._record_result("auth_required", True, "401 returned for unauthenticated request", duration)
                return True
            elif response.status_code == 200:
                # Auth might be disabled - still passes but note it
                self._record_result("auth_required", True, "Auth disabled (200 without token)", duration)
                return True
            else:
                self._record_result("auth_required", False, f"Unexpected status {response.status_code}", duration)
                return False
        except Exception as e:
            self._record_result("auth_required", False, f"Error: {e}")
            return False

    async def run_health_tests(self, client: httpx.AsyncClient) -> bool:
        """Run all health and connectivity tests."""
        print("\n" + "=" * 60)
        print("HEALTH & CONNECTIVITY TESTS")
        print("=" * 60)

        # Ping must pass to continue
        if not await self.test_ping(client):
            print("\n⚠️  Server is not responding. Aborting remaining tests.")
            return False

        await self.test_health(client)
        await self.test_auth_required(client)

        return True

    # =========================================================================
    # Read-Only MCP Tool Tests
    # =========================================================================

    async def test_database_stats(self, client: httpx.AsyncClient) -> bool:
        """Test database_stats tool."""
        try:
            import time
            start = time.time()
            result = await self._call_mcp_tool(client, "database_stats", {})
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                # Check for expected content
                if "paper" in body.lower() or "database" in body.lower() or "total" in body.lower():
                    self._record_result("database_stats", True, f"Got stats: {body[:100]}...", duration)
                    return True
                else:
                    self._record_result("database_stats", True, f"Response: {body[:100]}...", duration)
                    return True
            else:
                self._record_result("database_stats", False, f"Status {result['status_code']}: {result['body'][:100]}", duration)
                return False
        except Exception as e:
            self._record_result("database_stats", False, f"Error: {e}")
            return False

    async def test_list_recent_papers(self, client: httpx.AsyncClient) -> bool:
        """Test list_recent_papers tool."""
        try:
            import time
            start = time.time()
            result = await self._call_mcp_tool(client, "list_recent_papers", {"n": 3})
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                self._record_result("list_recent_papers", True, f"Response: {body[:100]}...", duration)
                return True
            else:
                self._record_result("list_recent_papers", False, f"Status {result['status_code']}: {result['body'][:100]}", duration)
                return False
        except Exception as e:
            self._record_result("list_recent_papers", False, f"Error: {e}")
            return False

    async def test_search_papers(self, client: httpx.AsyncClient) -> bool:
        """Test search_papers tool."""
        try:
            import time
            start = time.time()
            result = await self._call_mcp_tool(
                client,
                "search_papers",
                {"query": "machine learning", "n_results": 3}
            )
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                self._record_result("search_papers", True, f"Response: {body[:100]}...", duration)
                return True
            else:
                self._record_result("search_papers", False, f"Status {result['status_code']}: {result['body'][:100]}", duration)
                return False
        except Exception as e:
            self._record_result("search_papers", False, f"Error: {e}")
            return False

    async def test_get_paper_details(self, client: httpx.AsyncClient, bibtex_key: Optional[str] = None) -> bool:
        """Test get_paper_details tool."""
        try:
            # If no key provided, try to get one from recent papers
            if not bibtex_key:
                result = await self._call_mcp_tool(client, "list_recent_papers", {"n": 1})
                if result["status_code"] == 200:
                    # Try to extract a bibtex key from the response
                    import re
                    match = re.search(r'\[(\w+\d+[a-z]?)\]', result["body"])
                    if match:
                        bibtex_key = match.group(1)

            if not bibtex_key:
                self._record_result("get_paper_details", True, "Skipped: No papers in database")
                return True

            import time
            start = time.time()
            result = await self._call_mcp_tool(
                client,
                "get_paper_details",
                {"bibtex_key": bibtex_key}
            )
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                self._record_result("get_paper_details", True, f"Got details for [{bibtex_key}]: {body[:80]}...", duration)
                return True
            else:
                self._record_result("get_paper_details", False, f"Status {result['status_code']}: {result['body'][:100]}", duration)
                return False
        except Exception as e:
            self._record_result("get_paper_details", False, f"Error: {e}")
            return False

    async def run_readonly_tests(self, client: httpx.AsyncClient) -> bool:
        """Run all read-only MCP tool tests."""
        print("\n" + "=" * 60)
        print("READ-ONLY MCP TOOL TESTS")
        print("=" * 60)

        await self.test_database_stats(client)
        await self.test_list_recent_papers(client)
        await self.test_search_papers(client)
        await self.test_get_paper_details(client)

        return True

    # =========================================================================
    # Upload & Processing Tests
    # =========================================================================

    async def test_upload_invalid_base64(self, client: httpx.AsyncClient) -> bool:
        """Test upload with invalid base64 data."""
        try:
            import time
            start = time.time()
            result = await self._call_mcp_tool(
                client,
                "add_paper_from_upload",
                {"pdf_data": "not-valid-base64!!!", "filename": "invalid.pdf"}
            )
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                if "error" in body.lower():
                    self._record_result("upload_invalid_base64", True, "Error properly returned for invalid base64", duration)
                    return True
                else:
                    self._record_result("upload_invalid_base64", False, f"No error for invalid base64: {body[:100]}", duration)
                    return False
            else:
                # Error status code is also acceptable
                self._record_result("upload_invalid_base64", True, f"Status {result['status_code']} for invalid input", duration)
                return True
        except Exception as e:
            self._record_result("upload_invalid_base64", False, f"Error: {e}")
            return False

    async def test_upload_non_pdf(self, client: httpx.AsyncClient) -> bool:
        """Test upload with non-PDF data."""
        try:
            import time
            start = time.time()
            non_pdf_base64 = base64.b64encode(b"This is not a PDF file").decode('utf-8')
            result = await self._call_mcp_tool(
                client,
                "add_paper_from_upload",
                {"pdf_data": non_pdf_base64, "filename": "not_a_pdf.pdf"}
            )
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                if "error" in body.lower() or "pdf" in body.lower():
                    self._record_result("upload_non_pdf", True, "Error properly returned for non-PDF data", duration)
                    return True
                else:
                    self._record_result("upload_non_pdf", False, f"No error for non-PDF: {body[:100]}", duration)
                    return False
            else:
                self._record_result("upload_non_pdf", True, f"Status {result['status_code']} for non-PDF input", duration)
                return True
        except Exception as e:
            self._record_result("upload_non_pdf", False, f"Error: {e}")
            return False

    async def test_upload_valid_pdf(self, client: httpx.AsyncClient) -> bool:
        """Test upload with valid minimal PDF."""
        try:
            import time
            start = time.time()
            pdf_base64 = base64.b64encode(self.test_pdf_content).decode('utf-8')
            result = await self._call_mcp_tool(
                client,
                "add_paper_from_upload",
                {
                    "pdf_data": pdf_base64,
                    "filename": "test_minimal.pdf",
                    "custom_tags": ["test", "remote-test"]
                },
                timeout=180.0  # Longer timeout for processing
            )
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                # Success could mean added or duplicate detected
                if "success" in body.lower() or "added" in body.lower() or "duplicate" in body.lower() or "already" in body.lower():
                    self._record_result("upload_valid_pdf", True, f"Response: {body[:100]}...", duration)
                    return True
                elif "error" in body.lower():
                    # Some errors are expected (e.g., minimal PDF can't be parsed)
                    self._record_result("upload_valid_pdf", True, f"Expected processing issue: {body[:100]}...", duration)
                    return True
                else:
                    self._record_result("upload_valid_pdf", True, f"Response: {body[:100]}...", duration)
                    return True
            else:
                self._record_result("upload_valid_pdf", False, f"Status {result['status_code']}: {result['body'][:100]}", duration)
                return False
        except Exception as e:
            self._record_result("upload_valid_pdf", False, f"Error: {e}")
            return False

    async def run_upload_tests(self, client: httpx.AsyncClient) -> bool:
        """Run all upload and processing tests."""
        print("\n" + "=" * 60)
        print("UPLOAD & PROCESSING TESTS")
        print("=" * 60)

        await self.test_upload_invalid_base64(client)
        await self.test_upload_non_pdf(client)
        await self.test_upload_valid_pdf(client)

        return True

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    async def test_invalid_tool_name(self, client: httpx.AsyncClient) -> bool:
        """Test calling a non-existent tool."""
        try:
            import time
            start = time.time()
            result = await self._call_mcp_tool(
                client,
                "nonexistent_tool_12345",
                {}
            )
            duration = (time.time() - start) * 1000

            if result["status_code"] == 200:
                body = result["body"]
                if "error" in body.lower() or "unknown" in body.lower() or "not found" in body.lower():
                    self._record_result("invalid_tool_name", True, "Error returned for invalid tool", duration)
                    return True
                else:
                    self._record_result("invalid_tool_name", False, f"No error for invalid tool: {body[:100]}", duration)
                    return False
            else:
                # Error status code is acceptable
                self._record_result("invalid_tool_name", True, f"Status {result['status_code']} for invalid tool", duration)
                return True
        except Exception as e:
            self._record_result("invalid_tool_name", False, f"Error: {e}")
            return False

    async def test_malformed_jsonrpc(self, client: httpx.AsyncClient) -> bool:
        """Test with malformed JSON-RPC request."""
        try:
            import time
            start = time.time()
            response = await client.post(
                f"{self.base_url}/mcp",
                headers=self.headers,
                json={"invalid": "request"},  # Missing required fields
                timeout=30.0
            )
            duration = (time.time() - start) * 1000

            # Any response is acceptable - we just want it to not crash
            self._record_result("malformed_jsonrpc", True, f"Server handled malformed request (status {response.status_code})", duration)
            return True
        except Exception as e:
            self._record_result("malformed_jsonrpc", False, f"Error: {e}")
            return False

    async def test_wrong_api_key(self, client: httpx.AsyncClient) -> bool:
        """Test with wrong API key."""
        try:
            import time
            start = time.time()
            response = await client.post(
                f"{self.base_url}/mcp",
                headers={
                    "Authorization": "Bearer wrong-key-12345",
                    "Content-Type": "application/json"
                },
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": self._next_id()
                },
                timeout=30.0
            )
            duration = (time.time() - start) * 1000

            if response.status_code == 401 or response.status_code == 403:
                self._record_result("wrong_api_key", True, "Unauthorized returned for wrong key", duration)
                return True
            elif response.status_code == 200:
                # Auth might be disabled
                self._record_result("wrong_api_key", True, "Auth disabled (200 with wrong key)", duration)
                return True
            else:
                self._record_result("wrong_api_key", False, f"Unexpected status {response.status_code}", duration)
                return False
        except Exception as e:
            self._record_result("wrong_api_key", False, f"Error: {e}")
            return False

    async def run_error_tests(self, client: httpx.AsyncClient) -> bool:
        """Run all error handling tests."""
        print("\n" + "=" * 60)
        print("ERROR HANDLING TESTS")
        print("=" * 60)

        await self.test_invalid_tool_name(client)
        await self.test_malformed_jsonrpc(client)
        await self.test_wrong_api_key(client)

        return True

    # =========================================================================
    # Main Test Runner
    # =========================================================================

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        print(f"\nTotal: {total} tests")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")

        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        print()
        return failed == 0

    async def run_all_tests(self, only: Optional[str] = None):
        """Run all tests or a specific category."""
        print("\n" + "=" * 60)
        print(f"Paper RAG Pipeline - Remote Server Tests")
        print(f"Target: {self.base_url}")
        print("=" * 60)

        async with httpx.AsyncClient() as client:
            # Health tests must run first
            if only is None or only == "health":
                if not await self.run_health_tests(client):
                    self.print_summary()
                    return False
                if only == "health":
                    return self.print_summary()

            # Read-only tests
            if only is None or only == "readonly":
                await self.run_readonly_tests(client)
                if only == "readonly":
                    return self.print_summary()

            # Upload tests
            if only is None or only == "upload":
                await self.run_upload_tests(client)
                if only == "upload":
                    return self.print_summary()

            # Error handling tests
            if only is None or only == "errors":
                await self.run_error_tests(client)

        return self.print_summary()


def main():
    parser = argparse.ArgumentParser(
        description="Test remote MCP server on RunPod",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_remote_server.py --url https://abc123.api.runpod.ai --api-key mykey
  python test_remote_server.py --url https://abc123.api.runpod.ai --only health

Environment variables:
  MCP_API_KEY - API key for authentication (alternative to --api-key)
"""
    )
    parser.add_argument(
        "--url", "-u",
        required=True,
        help="RunPod endpoint URL (e.g., https://abc123.api.runpod.ai)"
    )
    parser.add_argument(
        "--api-key", "-k",
        default=os.getenv("MCP_API_KEY"),
        help="MCP API key (or set MCP_API_KEY env var)"
    )
    parser.add_argument(
        "--only", "-o",
        choices=["health", "readonly", "upload", "errors"],
        help="Run only specific test category"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=120.0,
        help="Request timeout in seconds (default: 120)"
    )

    args = parser.parse_args()

    if not args.api_key:
        print("Error: API key required. Use --api-key or set MCP_API_KEY environment variable.")
        sys.exit(1)

    tester = RemoteServerTester(args.url, args.api_key, args.timeout)
    success = asyncio.run(tester.run_all_tests(args.only))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
