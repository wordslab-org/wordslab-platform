"""Family 1 — LLM & agents inference (ADR-0001 §Families.1).

The OpenAI Responses API by reference at `POST /v1/responses`: request, typed
streaming events, tool calling (function tools + MCP servers), structured
outputs, citations, reasoning items, refusals, `usage` in tokens, multimodal
input.

Four pieces, one per concern:

- `shapes` — the vocabulary + `parse_request` / `normalize_response`: what a
  request may carry and what a response body must look like;
- `events` — the typed streaming vocabulary + `events_for` / `sse_frames`:
  SSE frames ending in a terminal `response.completed` (no `[DONE]` sentinel);
- `support` — the per-implementation `SupportMatrix` (ADR-0004: the capability
  API is the union of its variants, and the variance is declared, not guessed);
- `api` — the OpenAPI fragment a capability merges into the service document,
  from which the `/mcp` tools are auto-generated (base item 9).

`routes.responses_routes(engine, …)` mounts the surface for one engine. A
service that does not implement inference deletes this whole directory
(CONTRIBUTING.md step 5 keeps only what the service exercises).

Scope fence: no engine adapters (Ollama / vLLM / sglang / cloud gateway — the
Inference service's implementation tickets), no model catalog or
download/load lifecycle (family 5, #80), no background/async responses
(family 5 again — rejected with a precise message).
"""

from .api import openapi_fragment
from .events import EVENT_TYPES, TERMINAL_EVENT_TYPES, events_for, sse_frames
from .routes import DEFAULT_MAX_REQUEST_BYTES, ResponsesEngine, responses_routes
from .shapes import (
    ANNOTATION_TYPES,
    CONTENT_PART_TYPES,
    INPUT_PART_TYPES,
    OUTPUT_ITEM_TYPES,
    TOOL_TYPES,
    normalize_response,
    parse_request,
)
from .support import FEATURES, SupportMatrix, ensure_supported, required_features

__all__ = [
    "ANNOTATION_TYPES",
    "CONTENT_PART_TYPES",
    "DEFAULT_MAX_REQUEST_BYTES",
    "EVENT_TYPES",
    "FEATURES",
    "INPUT_PART_TYPES",
    "OUTPUT_ITEM_TYPES",
    "ResponsesEngine",
    "SupportMatrix",
    "TERMINAL_EVENT_TYPES",
    "TOOL_TYPES",
    "ensure_supported",
    "events_for",
    "normalize_response",
    "openapi_fragment",
    "parse_request",
    "required_features",
    "responses_routes",
    "sse_frames",
]
