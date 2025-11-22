"""CSRF protection middleware using the double-submit cookie pattern."""
from __future__ import annotations

import logging
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate CSRF tokens on state-changing requests that include auth cookies."""

    def __init__(self, app, settings=None, exempt_paths: Iterable[str] | None = None):
        super().__init__(app)
        self.settings = settings or get_settings()
        self.safe_methods = {"GET", "HEAD", "OPTIONS", "TRACE"}
        self.exempt_paths = tuple(exempt_paths or self.settings.csrf_exempt_paths)

    async def dispatch(self, request: Request, call_next):
        if not self.settings.csrf_protection_enabled:
            return await call_next(request)

        if request.method.upper() in self.safe_methods:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.exempt_paths):
            return await call_next(request)

        auth_cookie = request.cookies.get(self.settings.auth_cookie_name)
        if not auth_cookie:
            # Without an auth cookie there is no ambient credential to protect.
            return await call_next(request)

        csrf_cookie = request.cookies.get(self.settings.csrf_cookie_name)
        header_name = self.settings.csrf_header_name
        csrf_header = request.headers.get(header_name)

        logger.info(f"CSRF check {request.method} {path}: cookie={csrf_cookie[:8] if csrf_cookie else 'None'}..., header={csrf_header[:8] if csrf_header else 'None'}...")

        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            logger.warning(f"CSRF failed: cookie_present={bool(csrf_cookie)}, header_present={bool(csrf_header)}, match={csrf_cookie == csrf_header if csrf_cookie and csrf_header else False}")
            return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})

        return await call_next(request)
