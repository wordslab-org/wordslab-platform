"""The agent surface — stateless MCP at `/mcp` (ADR-0001 §Base contract.9;
ADR-0002 §3; contract family 3 semantics).

`/mcp` is a base-contract surface on EVERY service: stateless MCP
(JSON-RPC 2.0, no sessions, per-request Bearer — the auth middleware gates
this mount like every non-`/health` path). Tools are **auto-generated from
the OpenAPI document** — zero drift by construction: the MCP surface IS the
API, machine-translated. The FastMCP reference SDK (`mcp`, pinned by
ADR-0001 item 9) carries the protocol: its stateless streamable-HTTP
transport was verified at template build time (spec 2026-07-28 posture).

Dispatch: a tools/call re-enters the SAME Starlette app over the in-process
ASGI stack with the caller's Bearer key — the MCP surface executes the
deterministic surface's own routes, so there is exactly one behavior to
keep in sync, not two.

Author overrides (`@tool` definitions where the machine API needs an
English-friendly interface) are a future template ticket — the override
mechanism lands with its first real use, not speculatively.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any

import httpx
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import (
    StreamableHTTPASGIApp,
    StreamableHTTPSessionManager,
)
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Mount

# The outer request's Bearer key, carried into tools/call's inner dispatch.
# Set by the ASGI endpoint before the session manager's task group runs;
# anyio copies the current context into spawned tasks, so the call_tool
# handler reads it there.
_bearer_cvar: ContextVar[str] = ContextVar("mcp_bearer", default="")

_BODY_METHODS = frozenset({"post", "put", "patch"})
_HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def tools_from_openapi(doc: dict) -> dict[str, tuple[str, str, dict | None]]:
    """operationId → (http method, path, request-body schema | None)."""
    tools: dict[str, tuple[str, str, dict | None]] = {}
    for path, item in doc.get("paths", {}).items():
        for method in _HTTP_METHODS:
            operation = item.get(method)
            if not operation:
                continue
            name = operation.get("operationId")
            if not name:
                continue  # an operation without an operationId is not a tool
            schema = None
            if method in _BODY_METHODS:
                schema = (
                    operation.get("requestBody", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
            tools[name] = (method.upper(), path, schema)
    return tools


def _operation_descriptions(doc: dict) -> dict[str, str]:
    """operationId → the tool's description (summary + description)."""
    descriptions: dict[str, str] = {}
    for path, item in doc.get("paths", {}).items():
        for method in _HTTP_METHODS:
            operation = item.get(method)
            if not operation or not operation.get("operationId"):
                continue
            summary = operation.get("summary") or f"{method.upper()} {path}"
            description = operation.get("description")
            descriptions[operation["operationId"]] = (
                f"{summary} — {description}" if description else summary
            )
    return descriptions


class McpSurface:
    """The `/mcp` mount: a stateless MCP server over the service app.

    Built from the assembled OpenAPI document; `dispatch_app` is the service
    app itself (tools re-enter it). `run()` must be driven by the service's
    lifespan — the session manager runs per-request sessions in stateless
    mode and needs a running manager.
    """

    def __init__(
        self,
        *,
        openapi_doc: dict,
        dispatch_app,
        server_name: str,
        server_version: str,
        instructions: str | None = None,
    ) -> None:
        self._dispatch_app = dispatch_app
        self._operations = tools_from_openapi(openapi_doc)
        self._descriptions = _operation_descriptions(openapi_doc)
        self._server = Server(
            server_name,
            version=server_version,
            instructions=instructions,
            on_list_tools=self._list_tools,
            on_call_tool=self._call_tool,
        )
        # Bearer auth (the middleware outside) is the control; the SDK's
        # DNS-rebinding protection is a browser-origin control that does not
        # apply to a Bearer-gated, LAN-hosted JSON endpoint.
        no_rebinding = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        self._manager = StreamableHTTPSessionManager(
            app=self._server,
            json_response=True,
            stateless=True,
            security_settings=no_rebinding,
        )
        self.asgi = StreamableHTTPASGIApp(self._manager)

    def mount(self) -> Mount:
        """The `/mcp` mount for the service app's route table. The endpoint
        wrapper first copies the caller's Bearer key into a contextvar (the
        session manager's spawned tasks inherit the context) so tools/call's
        in-process dispatch re-authenticates exactly as the outer request
        did."""
        sdk_asgi = self.asgi

        async def endpoint(scope, receive, send):
            for key, value in scope.get("headers") or []:
                if key == b"authorization":
                    auth = value.decode("latin-1")
                    if auth[:7].lower() == "bearer ":
                        _bearer_cvar.set(auth[7:])
            await sdk_asgi(scope, receive, send)

        return Mount("/mcp", app=endpoint, name="mcp")

    def run(self):
        """The lifespan entry (async context manager) driving the manager."""
        return self._manager.run()

    # --- tool generation from the OpenAPI document ------------------------

    async def _list_tools(self, ctx, params) -> types.ListToolsResult:
        tools = [
            types.Tool(
                name=name,
                description=self._descriptions.get(name, name),
                inputSchema=schema or {"type": "object", "properties": {}},
            )
            for name, (_method, _path, schema) in self._operations.items()
        ]
        return types.ListToolsResult(tools=tools)

    # --- dispatch ----------------------------------------------------------

    async def _call_tool(self, ctx, params) -> types.CallToolResult:
        name = params.name
        if name not in self._operations:
            return types.CallToolResult(
                is_error=True,
                content=[
                    types.TextContent(
                        type="text",
                        text=(
                            f"Unknown tool {name!r} — not an operationId of "
                            "this service's OpenAPI document."
                        ),
                    )
                ],
            )
        method, path, _schema = self._operations[name]
        arguments = dict(params.arguments or {})
        try:
            status, body = await self._dispatch(method, path, arguments)
        except Exception as exc:  # noqa: BLE001 — surfaced as a tool error
            return types.CallToolResult(
                is_error=True,
                content=[types.TextContent(type="text", text=f"Dispatch failed: {exc}")],
            )
        if 200 <= status < 300:
            result = types.CallToolResult(
                content=[types.TextContent(type="text", text=_to_text(body))]
            )
            if isinstance(body, dict):
                result.structured_content = body
            return result
        return types.CallToolResult(
            is_error=True,
            content=[types.TextContent(type="text", text=_to_text(body))],
        )

    async def _dispatch(self, method: str, path: str, arguments: dict) -> tuple[int, Any]:
        bearer = _bearer_cvar.get()
        headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
        transport = httpx.ASGITransport(app=self._dispatch_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://in-process") as client:
            response = await client.request(
                method, path, json=arguments or None, headers=headers
            )
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, response.text


def _to_text(body: Any) -> str:
    if isinstance(body, str):
        return body
    return json.dumps(body)
