"""Family 1 — the `POST /v1/responses` route factory and the engine seam.

A model-backed capability mounts this surface by wiring an ENGINE behind it:

    routes = responses_routes(engine, support=adapter.SUPPORT, implementation="ollama")

The split is deliberate and is the whole point of a family module:
**this module owns the contract** (validation, the response shape, the typed
streaming events, the support gate) and the **engine owns the model** (the
output items and token counts). An engine adapter therefore never re-derives
the contract, and the conformance block proves the contract against a
deterministic stub engine instead of a real model.

The engine seam is one synchronous operation, `responses(request) -> dict`,
where `request` is the PARSED request (`shapes.parse_request`) and the reply is
a LooseResponse: `{"output": [...], "usage": {...}}`, plus optional `id` /
`status` / `created_at`. Anything the engine returns that breaks the seam is
500 `internal_error` — the implementation is at fault, never the caller. An
engine that cannot serve (model not loaded, cloud refused) raises the base
taxonomy's error (`busy` / `unavailable` / `resource_exhausted`) and the app's
handler turns it into the contract body. Async adapters expose a sync facade;
native token-by-token streaming is an adapter concern (the Inference service's
implementation tickets) — this module derives the typed event sequence from the
completed body, so the client contract is identical either way.
"""

from __future__ import annotations

from typing import Protocol

from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from ...base.errors import invalid_request, request_too_large
from .events import events_for, sse_frames
from .shapes import normalize_response, parse_request
from .support import SupportMatrix, ensure_supported

# Request bodies are capped because multimodal input arrives base64-inline
# (input_image / input_audio); over the cap is 413 `request_too_large` (base
# item 4), never a silent truncation. Implementations may lower it; raising it
# is a deliberate service decision, so it is a parameter.
DEFAULT_MAX_REQUEST_BYTES = 4 * 1024 * 1024


class ResponsesEngine(Protocol):
    """The engine seam: what a model implementation must provide.

    `request` is the parsed request from `parse_request` (its `input` is a list
    of typed input parts, `tools` a list, `text` a `{"format": …}` object); the
    reply carries `output` (family-1 output items) and `usage` (token counts).
    """

    def responses(self, request: dict) -> dict: ...


def responses_routes(
    engine: ResponsesEngine,
    *,
    support: SupportMatrix | None = None,
    implementation: str = "",
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
) -> list[Route]:
    """The family-1 route for one engine.

    `support` is the selected implementation's `SupportMatrix`; when given, a
    request that needs a feature the implementation lacks is refused with a
    message naming the feature (ADR-0004's documented-variance rule made
    operational). `implementation` is the name used in that message.
    """

    async def create_response(request: Request) -> JSONResponse | StreamingResponse:
        """POST /v1/responses — one model turn."""
        # A declared length over the cap is refused BEFORE the body is buffered:
        # the cap exists to bound memory for base64-inline multimodal input, and
        # buffering first would defeat it. The post-read check stays as the
        # fallback for a chunked (or lying) upload.
        declared = request.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_request_bytes:
            raise request_too_large(
                f"Request body exceeds the {max_request_bytes}-byte family-1 limit."
            )
        body = await request.body()
        if not body:
            raise invalid_request("POST /v1/responses expects a JSON object request body.")
        if len(body) > max_request_bytes:
            raise request_too_large(
                f"Request body exceeds the {max_request_bytes}-byte family-1 limit."
            )
        try:
            payload = await request.json()
        except ValueError:  # malformed JSON is a CLIENT error, never a 500
            raise invalid_request(
                "POST /v1/responses expects a JSON object request body."
            ) from None

        parsed = parse_request(payload)
        if support is not None:
            ensure_supported(parsed, support, implementation=implementation)

        response = normalize_response(parsed, engine.responses(parsed))

        if parsed["stream"]:
            # One chunk carrying the whole sequence: the module's contract is the
            # event ORDER, not the pacing — an adapter that emits natively serves
            # the identical frames incrementally.
            return StreamingResponse(
                iter([sse_frames(events_for(response))]),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )
        return JSONResponse(response)

    return [Route("/v1/responses", create_response, methods=["POST"])]
