"""
Authentication middleware for MCP HTTP Server.
Implements Bearer token authentication for remote access.
"""

import os
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates Bearer token authentication.

    Requires MCP_API_KEY environment variable to be set.
    Skips authentication for health check endpoints.
    """

    # Paths that don't require authentication
    EXEMPT_PATHS = {"/health", "/healthz", "/ready", "/"}

    async def dispatch(self, request: Request, call_next):
        """Process request and validate authentication."""

        # Skip auth for exempt paths (health checks, root)
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get expected API key from environment
        expected_key = os.environ.get("MCP_API_KEY", "")

        if not expected_key:
            logger.warning("MCP_API_KEY not set - authentication disabled")
            # Allow request if no key is configured (development mode)
            return await call_next(request)

        # Get Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            logger.warning(f"Missing Authorization header for {request.url.path}")
            return JSONResponse(
                {"error": "Missing Authorization header", "detail": "Bearer token required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Validate Bearer token format
        if not auth_header.startswith("Bearer "):
            logger.warning(f"Invalid Authorization format for {request.url.path}")
            return JSONResponse(
                {"error": "Invalid Authorization format", "detail": "Use 'Bearer <token>'"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Extract and validate token
        token = auth_header[7:]  # Remove "Bearer " prefix

        if token != expected_key:
            logger.warning(f"Invalid API key for {request.url.path}")
            return JSONResponse(
                {"error": "Invalid API key", "detail": "Authentication failed"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Authentication successful
        logger.debug(f"Authenticated request for {request.url.path}")
        return await call_next(request)


class CORSMiddleware:
    """
    Simple CORS middleware for cross-origin requests.

    Useful if browser-based clients need access to the API.
    """

    def __init__(self, app, allow_origins: list[str] = None):
        self.app = app
        self.allow_origins = allow_origins or ["*"]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Handle preflight OPTIONS request
        if scope["method"] == "OPTIONS":
            headers = [
                (b"access-control-allow-origin", b"*"),
                (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
                (b"access-control-allow-headers", b"Authorization, Content-Type, Mcp-Session-Id"),
                (b"access-control-max-age", b"86400"),
            ]
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": headers,
            })
            await send({
                "type": "http.response.body",
                "body": b"",
            })
            return

        # Add CORS headers to response
        async def send_with_cors(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", b"*"))
                headers.append((b"access-control-expose-headers", b"Mcp-Session-Id"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_cors)
