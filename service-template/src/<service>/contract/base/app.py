"""The service app factory — wires the base contract (ADR-0001) into one
Starlette application (ADR-0002 §The template: one `/health`, one auth, one
`/mcp`, one OpenAPI; the MCP/OpenAPI surfaces are later stage-0 tickets —
#73's stub patterns and #70's suite build on this seam).

Vendored, never edited (ADR-0002 §1): services add capabilities via
`extra_routes` (mounted under the `/v1` prefix, base item 3) — they do not
modify this file.
"""

from __future__ import annotations

from typing import Any, Callable

from starlette.applications import Starlette
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.routing import Router

from .auth import AuthMiddleware
from .errors import ApiError
from .health import health_endpoint
from .idempotency import IdempotencyMiddleware, InMemoryIdempotencyStore
from .request_id import RequestIdMiddleware


def _under_v1(routes: list) -> list:
    """Mount `extra_routes` under the `/v1` prefix (base item 3). Services
    declare full contract paths (`/v1/...`); the prefix is stripped here
    because the Mount already supplies it (Route compiles its regex at
    construction, so the route is rebuilt, not mutated)."""
    from starlette.routing import Route

    stripped = []
    for route in routes:
        if isinstance(route, Route) and route.path.startswith("/v1/"):
            route = Route(
                route.path[len("/v1"):],
                route.endpoint,
                methods=route.methods,
                name=route.name,
            )
        stripped.append(route)
    return stripped


def create_service_app(
    *,
    service_name: str,
    version: str,
    api_keys: list[str],
    health_status: str = "ready",
    resources: dict | None = None,
    models: dict | None = None,
    extra_routes: list[Route | Mount] | None = None,
    idempotency_store=None,
) -> Starlette:
    """Build the template service app embodying the base contract.

    - items 2/4/7: auth, error taxonomy, idempotency via middleware
    - item 3: `extra_routes` mount at `/v1`
    - item 6: `/health` from the given status/resources/models
    """

    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body(request.state.request_id), status_code=exc.status)

    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Starlette's own 404s carry the contract `not_found` body (base item
        # 4: one JSON shape, fixed taxonomy). Any other Starlette-raised code
        # (405 method-not-allowed, …) is not a v1 code, so it comes back as
        # 400 `invalid_request` — every response's (status, type) pair must
        # be inside the fixed 11-code taxonomy.
        from .errors import invalid_request, not_found

        error = not_found() if exc.status_code == 404 else invalid_request(str(exc.detail))
        return JSONResponse(error.body(request.state.request_id), status_code=error.status)

    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        from .errors import internal_error

        return JSONResponse(
            internal_error().body(request.state.request_id), status_code=500
        )

    return Starlette(
        routes=[
            Route(
                "/health",
                health_endpoint(
                    service_name,
                    version,
                    get_status=lambda: health_status,
                    get_resources=lambda: resources or {},
                    get_models=(lambda: models) if models is not None else None,
                ),
                methods=["GET"],
            ),
            Mount("/v1", Router(routes=_under_v1(extra_routes or []))),
        ],
        middleware=[
            Middleware(RequestIdMiddleware),
            Middleware(AuthMiddleware, api_keys=frozenset(api_keys)),
            Middleware(
                IdempotencyMiddleware, store=idempotency_store or InMemoryIdempotencyStore()
            ),
        ],
        exception_handlers={
            ApiError: api_error_handler,
            StarletteHTTPException: http_exception_handler,
            Exception: unhandled_error_handler,
        },
    )
