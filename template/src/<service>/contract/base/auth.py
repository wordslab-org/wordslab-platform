"""Base contract item 2 — Auth (ADR-0001 §Base contract.2).

`Authorization: Bearer ***` only, per-service API keys validated by the
service itself (no central round-trip). 401 `authentication_failed` when
absent/invalid. No user accounts inside services.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .errors import authentication_failed


class AuthMiddleware(BaseHTTPMiddleware):
    """Bearer-key check. Unauthenticated paths: `/health` only — the
    monitoring/dashboard surface must read health without a key (ADR-0001
    items 2 and 6); everything else, including all `/v1/...` paths and the
    later `/mcp` surface, requires the key on every request."""

    def __init__(self, app, api_keys: frozenset[str]) -> None:
        super().__init__(app)
        self.api_keys = api_keys

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health",):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        scheme, _, key = auth.partition(" ")
        if scheme.lower() != "bearer" or not key or key not in self.api_keys:
            error = authentication_failed()
            return JSONResponse(error.body(request.state.request_id), status_code=error.status)
        return await call_next(request)
