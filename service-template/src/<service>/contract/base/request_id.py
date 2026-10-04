"""Base contract item 4 — every response carries `X-Request-Id` (ADR-0001
§Base contract.4).

A pure-ASGI middleware placed outermost: it owns the request id — generated
per request (an incoming `X-Request-Id` is honored so chained calls can
propagate their chain id) — publishes it on `scope["state"]` for handlers and
inner middleware (`request.state.request_id`), and stamps the header on every
response, including idempotent replays and middleware-produced errors.
"""

from __future__ import annotations

import uuid

from starlette.datastructures import MutableHeaders


class RequestIdMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        headers = {}
        for k, v in scope.get("headers") or []:
            headers[k.decode("latin-1").lower()] = v.decode("latin-1")
        if not state.get("request_id"):
            state["request_id"] = headers.get("x-request-id") or uuid.uuid4().hex

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-Id"] = state["request_id"]
            await send(message)

        await self.app(scope, receive, send_with_request_id)
