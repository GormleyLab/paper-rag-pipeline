"""
Root-level MCP server wrapper for AWS AgentCore compatibility.
This matches the file structure shown in AWS documentation.
"""
import sys
print("=== MCP SERVER STARTING ===", file=sys.stdout, flush=True)
print(f"Python version: {sys.version}", file=sys.stdout, flush=True)
print(f"Python executable: {sys.executable}", file=sys.stdout, flush=True)

try:
    print("Importing src.mcp_http_server...", file=sys.stdout, flush=True)
    # Import and run the actual MCP server from src/
    from src.mcp_http_server import mcp
    print("Import successful!", file=sys.stdout, flush=True)
except Exception as e:
    print(f"IMPORT ERROR: {e}", file=sys.stdout, flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("Starting MCP server with streamable-http transport...", file=sys.stdout, flush=True)
    try:
        mcp.run(transport="streamable-http")
    except Exception as e:
        print(f"SERVER ERROR: {e}", file=sys.stdout, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
