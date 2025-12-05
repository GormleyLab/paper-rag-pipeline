"""
RunPod Serverless Handler for Academic RAG Pipeline.

This handler provides two modes of operation:
1. HTTP Server Mode: Starts a persistent HTTP server for MCP protocol (default)
2. Job Mode: Processes individual jobs for batch operations

For MCP clients, use HTTP Server Mode which runs the FastMCP server.
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Configure logging for RunPod
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("runpod-handler")


# Pre-load heavy components at module level for cold start optimization
logger.info("Pre-loading components...")

try:
    # Pre-load Docling (heavy import)
    from docling.document_converter import DocumentConverter
    logger.info("Docling loaded")
except Exception as e:
    logger.warning(f"Failed to pre-load Docling: {e}")

try:
    # Pre-load transformers tokenizer
    import tiktoken
    tiktoken.get_encoding("cl100k_base")
    logger.info("Tokenizer loaded")
except Exception as e:
    logger.warning(f"Failed to pre-load tokenizer: {e}")

try:
    # Pre-load LanceDB
    import lancedb
    logger.info("LanceDB loaded")
except Exception as e:
    logger.warning(f"Failed to pre-load LanceDB: {e}")

logger.info("Pre-loading complete")


def ensure_directories():
    """Ensure all required directories exist on the network volume."""
    if os.path.exists('/runpod-volume'):
        dirs = [
            '/runpod-volume/data/lancedb',
            '/runpod-volume/data/pdfs',
            '/runpod-volume/data/bibs',
            '/runpod-volume/data/logs',
            '/runpod-volume/cache/huggingface',
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {dir_path}")


def run_http_server():
    """Run the MCP HTTP server for handling MCP protocol requests."""
    from src.mcp_http_server import create_app

    import uvicorn

    # Ensure directories exist
    ensure_directories()

    # Get configuration
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", "8080"))

    logger.info(f"Starting MCP HTTP server on {host}:{port}")

    # Create and run the app
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


def handler(job):
    """
    RunPod serverless handler for job-based processing.

    This handler supports two types of requests:
    1. HTTP server start (default): Starts the MCP HTTP server
    2. Direct tool calls: Execute MCP tools directly without HTTP

    Args:
        job: RunPod job dictionary with 'input' containing request data

    Returns:
        Job result dictionary
    """
    try:
        job_input = job.get("input", {})

        # Check if this is a request to start the HTTP server
        mode = job_input.get("mode", "http_server")

        if mode == "http_server":
            # This will block and run the HTTP server
            # RunPod will keep the worker alive while the server runs
            run_http_server()
            return {"status": "server_stopped"}

        elif mode == "tool_call":
            # Direct tool call mode for batch processing
            return asyncio.run(handle_tool_call(job_input))

        elif mode == "health_check":
            # Health check mode
            return {
                "status": "healthy",
                "version": "1.0.0",
                "mode": "runpod_serverless"
            }

        else:
            return {"error": f"Unknown mode: {mode}"}

    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return {"error": str(e)}


async def handle_tool_call(job_input: dict) -> dict:
    """
    Handle direct tool calls without going through HTTP.

    Useful for batch processing or direct API integration.

    Args:
        job_input: Dictionary with 'tool' name and 'arguments'

    Returns:
        Tool execution result
    """
    from src.mcp_http_server import (
        search_papers,
        add_paper_from_file,
        generate_bibliography,
        get_paper_details,
        database_stats,
        list_recent_papers,
        delete_paper
    )

    tool_name = job_input.get("tool")
    arguments = job_input.get("arguments", {})

    logger.info(f"Executing tool: {tool_name} with args: {arguments}")

    # Map tool names to functions
    tools = {
        "search_papers": search_papers,
        "add_paper_from_file": add_paper_from_file,
        "generate_bibliography": generate_bibliography,
        "get_paper_details": get_paper_details,
        "database_stats": database_stats,
        "list_recent_papers": list_recent_papers,
        "delete_paper": delete_paper,
    }

    if tool_name not in tools:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        result = await tools[tool_name](**arguments)
        return {"result": result}
    except Exception as e:
        logger.error(f"Tool execution error: {e}", exc_info=True)
        return {"error": str(e)}


# Entry point for RunPod serverless
if __name__ == "__main__":
    import runpod

    # Check if we should start in HTTP server mode directly
    # This is useful for testing or when RunPod is configured for HTTP endpoints
    if os.environ.get("START_HTTP_SERVER", "false").lower() == "true":
        logger.info("Starting in HTTP server mode (START_HTTP_SERVER=true)")
        run_http_server()
    else:
        # Standard RunPod serverless handler
        logger.info("Starting RunPod serverless handler")
        runpod.serverless.start({"handler": handler})
