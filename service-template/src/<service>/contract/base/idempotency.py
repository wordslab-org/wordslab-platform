"""Base contract item 7 — Idempotency (ADR-0001 §Base contract.7).

Optional `Idempotency-Key` header on mutating endpoints; the service dedupes
retries and returns the original result.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class InMemoryIdempotencyStore:
    """Process-local store; a service that must survive restarts swaps in its
    own SQLModel-backed implementation of the same two methods."""

    def __init__(self) -> None:
        self._entries: dict[str, object] = {}

    def get(self, key: str):
        return self._entries.get(key)

    def put(self, key: str, entry) -> None:
        self._entries[key] = entry


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, store) -> None:
        super().__init__(app)
        self.store = store

    async def dispatch(self, request: Request, call_next):
        if request.method not in MUTATING_METHODS:
            return await call_next(request)
        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)
        scope_key = f"{request.method} {request.url.path} {key}"
        cached = self.store.get(scope_key)
        if cached is not None:
            status, body_bytes, request_id = cached
            request.state.request_id = request_id  # replay = the original result
            return Response(
                content=body_bytes,
                status_code=status,
                media_type="application/json",
                headers={"X-Request-Id": request_id},
            )
        response = await call_next(request)
        if 200 <= response.status_code < 500:
            body_bytes = b""
            if hasattr(response, "body_iterator"):
                async for chunk in response.body_iterator:
                    body_bytes += chunk
            else:
                body_bytes = response.body
            entry = (response.status_code, body_bytes, getattr(request.state, "request_id", ""))
            self.store.put(scope_key, entry)
            # Rebuild the response: the original body iterator is consumed.
            response = Response(
                content=body_bytes,
                status_code=response.status_code,
                media_type=response.media_type,
            )
            response.headers["X-Request-Id"] = entry[2]
        return response
