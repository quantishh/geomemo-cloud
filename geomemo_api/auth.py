"""
GeoMemo — HTTP Basic Auth + Security Headers Middleware
Protects the admin dashboard and all write operations.

When ADMIN_PASSWORD is set in .env:
  - /admin/* requires authentication (browser shows native login popup)
  - All POST/PUT/DELETE/PATCH requests require authentication
  - GET requests to API endpoints remain public (read-only)

When ADMIN_PASSWORD is empty:
  - Auth is disabled (development mode)

If your reverse proxy (e.g. nginx) already handles authentication,
leave ADMIN_PASSWORD empty to avoid double-prompting.
"""
import os
import base64
import secrets
import logging

from starlette.responses import Response

logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Paths that NEVER require auth (public endpoints)
_PUBLIC_EXACT = frozenset({
    "/api/health",
    "/api/subscribe",
    "/subscribe",
    "/docs",
    "/openapi.json",
    "/redoc",
})

# Path prefixes that never require auth
_PUBLIC_PREFIXES = ("/uploads/",)


def _requires_auth(path: str, method: str) -> bool:
    """Decide whether this request must be authenticated."""
    # OPTIONS (CORS preflight) — always pass through
    if method == "OPTIONS":
        return False

    # Exact public paths
    if path in _PUBLIC_EXACT:
        return False

    # Public prefix paths (uploaded images, etc.)
    for prefix in _PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return False

    # Admin dashboard — always requires auth (any method)
    if path.startswith("/admin"):
        return True

    # All write operations require auth
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        return True

    # GET/HEAD to API endpoints — public (read-only)
    return False


def _check_credentials(auth_header: str) -> bool:
    """Validate an HTTP Basic Authorization header value."""
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return False
    return (
        secrets.compare_digest(username.encode(), ADMIN_USERNAME.encode())
        and secrets.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
    )


# ─── Pure ASGI Middleware ─────────────────────────────────────────────
# Using raw ASGI instead of BaseHTTPMiddleware to avoid
# request-body buffering issues with file uploads.

class BasicAuthMiddleware:
    """HTTP Basic Auth — triggers native browser login popup."""

    def __init__(self, app):
        self.app = app
        if ADMIN_PASSWORD:
            logger.info("HTTP Basic Auth enabled for admin endpoints")
        else:
            logger.warning("ADMIN_PASSWORD not set — auth DISABLED (dev mode)")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Auth disabled if no password configured
        if not ADMIN_PASSWORD:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        if not _requires_auth(path, method):
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        auth_value = ""
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                auth_value = value.decode("utf-8")
                break

        if _check_credentials(auth_value):
            await self.app(scope, receive, send)
            return

        # 401 — browser will show native login popup
        response = Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="GeoMemo Admin"'},
            content="Authentication required",
        )
        await response(scope, receive, send)


class SecurityHeadersMiddleware:
    """Inject standard security headers into every HTTP response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"SAMEORIGIN"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ])
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
