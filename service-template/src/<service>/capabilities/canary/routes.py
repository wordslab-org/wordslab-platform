"""The canary's routes — the deterministic surface it owns.

Handlers are thin: validate the request, return the contract body. Business
logic of a real capability lives here in the same shape (a real capability
would also own its SQLModel tables — the canary is stateless by design).
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from contract.base.errors import invalid_request, request_too_large

MAX_ECHO_BYTES = 64 * 1024  # the canary echoes small JSON objects only


async def echo(request: Request) -> JSONResponse:
    """POST /v1/echo — returns the request body."""
    body = await request.body()
    if not body:
        raise invalid_request("POST /v1/echo expects a JSON object request body.")
    if len(body) > MAX_ECHO_BYTES:
        raise request_too_large(f"Echo body exceeds the {MAX_ECHO_BYTES}-byte canary limit.")
    try:
        parsed = await request.json()
    except ValueError:  # malformed JSON is a CLIENT error (item 4 taxonomy),
        raise invalid_request(  # never an unhandled 500 internal_error
            "POST /v1/echo expects a JSON object request body."
        ) from None
    if not isinstance(parsed, dict):
        raise invalid_request("POST /v1/echo expects a JSON object request body.")
    return JSONResponse(parsed)


async def ping(request: Request) -> JSONResponse:
    """GET /v1/echo/ping — returns pong."""
    return JSONResponse({"pong": True})


routes = [
    Route("/v1/echo", echo, methods=["POST"]),
    Route("/v1/echo/ping", ping, methods=["GET"]),
]
