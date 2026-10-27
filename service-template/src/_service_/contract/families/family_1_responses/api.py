"""Family 1 — the OpenAPI fragment for `POST /v1/responses`.

A capability that implements family 1 merges this fragment into the service's
document (base item 1's `/openapi.json`, assembled by
`contract/base/openapi.openapi_document`). Because the `/mcp` tools are
auto-generated from that same document — the request body schema becoming the
tool's `inputSchema` — this fragment is written INLINE, like the canary's: a
`$ref` in a request body hands an agent a dangling reference instead of
parameters. Merging the fragment is therefore what makes the inference
capability agent-callable, with no separate MCP code (base item 9).

The item-4 error body is NOT defined here: it is contract-wide and supplied
once by `contract/base/openapi.py`, so its responses `$ref` it.

The schemas describe the contract this module enforces (see `shapes.py`); the
engine implementations vary behind it (ADR-0004), which is what the support
matrix documents (`support.py`, `docs/family-1-responses.md`).
"""

from __future__ import annotations

from .shapes import (
    ANNOTATION_TYPES,
    CONTENT_PART_TYPES,
    INPUT_MESSAGE_ROLES,
    INPUT_PART_TYPES,
    ITEM_STATUSES,
    OUTPUT_ITEM_TYPES,
    RESPONSE_STATUSES,
    TEXT_FORMAT_TYPES,
    TOOL_TYPES,
)

_USAGE = {
    "type": "object",
    "required": ["input_tokens", "output_tokens", "total_tokens"],
    "properties": {
        "input_tokens": {"type": "integer", "minimum": 0},
        "output_tokens": {"type": "integer", "minimum": 0},
        "total_tokens": {
            "type": "integer",
            "minimum": 0,
            "description": "input_tokens + output_tokens (base item 8: usage on every resource-consuming operation; family 1's unit is tokens).",
        },
    },
}

_INPUT_PART = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            # the enum IS the module's vocabulary — one source, no drift
            "enum": sorted(INPUT_PART_TYPES),
            "description": (
                "Multimodal input is in (ADR-0001 §Families.1); generation output is "
                "text or structured. `function_call_output` returns a tool call's "
                "result — it is what closes a tool loop."
            ),
        },
        "text": {"type": "string", "description": "input_text"},
        "image_url": {
            "type": ["string", "object"],
            "description": "input_image — a URL string, or an object carrying `url`.",
        },
        "input_audio": {
            "type": "object",
            "description": "input_audio — {data, format}.",
            "properties": {"data": {"type": "string"}, "format": {"type": "string"}},
        },
        "call_id": {"type": "string", "description": "function_call_output — the call it answers."},
        "output": {
            "type": ["string", "array"],
            "description": "function_call_output — the tool's result.",
        },
    },
}

_INPUT_MESSAGE = {
    "type": "object",
    "required": ["role", "content"],
    "description": (
        "A role-tagged message. `role` is a closed enum (upstream's "
        "EasyInputMessage); `content` is a string or a list of input parts."
    ),
    "properties": {
        "role": {"type": "string", "enum": sorted(INPUT_MESSAGE_ROLES)},
        "content": {
            "type": ["string", "array"],
            "items": _INPUT_PART,
        },
    },
}

_OUTPUT_ITEM = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "enum": sorted(OUTPUT_ITEM_TYPES),
        },
        "id": {"type": "string"},
        "status": {"type": "string", "enum": sorted(ITEM_STATUSES)},
        "role": {"type": "string", "description": "message"},
        "content": {
            "type": "array",
            "description": "message — content parts.",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string", "enum": sorted(CONTENT_PART_TYPES)},
                    "text": {"type": "string"},
                    "refusal": {"type": "string"},
                    "annotations": {
                        "type": "array",
                        "description": "Citations ride the output_text part.",
                        "items": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "type": {"type": "string", "enum": sorted(ANNOTATION_TYPES)}
                            },
                        },
                    },
                },
            },
        },
        "name": {"type": "string", "description": "function_call / mcp_call"},
        "arguments": {"type": "string", "description": "function_call / mcp_call — a JSON string."},
        "call_id": {"type": "string", "description": "function_call"},
        "summary": {
            "type": "array",
            "description": "reasoning — summary parts.",
            "items": {
                "type": "object",
                "required": ["type", "text"],
                "properties": {"type": {"const": "summary_text"}, "text": {"type": "string"}},
            },
        },
        "server_label": {"type": "string", "description": "mcp_call / mcp_list_tools"},
        "tools": {"type": "array", "description": "mcp_list_tools"},
    },
}

_REQUEST = {
    "type": "object",
    "required": ["model", "input"],
    "properties": {
        "model": {"type": "string", "description": "The model id, resolved by the owning capability's catalog."},
        "input": {
            "type": ["string", "array"],
            "description": "A string (one input_text part), or a list of input items: a typed input part, or a role-tagged message carrying a content list.",
            "items": {"anyOf": [_INPUT_PART, _INPUT_MESSAGE]},
        },
        "instructions": {"type": "string"},
        "tools": {
            "type": "array",
            "description": "Function tools and MCP servers (ADR-0001 §Families.1).",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string", "enum": sorted(TOOL_TYPES)},
                    "name": {"type": "string", "description": "function — required."},
                    "description": {"type": "string"},
                    "parameters": {"type": "object", "description": "function — the JSON schema."},
                    "server_label": {"type": "string", "description": "mcp — required."},
                    "server_url": {"type": "string", "description": "mcp"},
                },
            },
        },
        "text": {
            "type": "object",
            "description": "Structured outputs: text.format {type: text|json_schema}.",
            "properties": {
                "format": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {"type": "string", "enum": sorted(TEXT_FORMAT_TYPES)},
                        "name": {"type": "string", "description": "json_schema — required."},
                        "schema": {"type": "object", "description": "json_schema — required."},
                    },
                }
            },
        },
        "stream": {
            "type": "boolean",
            "default": False,
            "description": "SSE with the typed Responses event vocabulary (family 1's events module).",
        },
        "max_output_tokens": {"type": "integer", "minimum": 1},
    },
    "additionalProperties": True,
}

_RESPONSE = {
    "type": "object",
    "required": ["id", "object", "created_at", "status", "model", "output", "usage"],
    "properties": {
        "id": {"type": "string", "pattern": "^resp_"},
        "object": {"const": "response"},
        "created_at": {"type": "integer"},
        "status": {"type": "string", "enum": sorted(RESPONSE_STATUSES)},
        "model": {"type": "string"},
        "instructions": {"type": "string", "description": "Echoed when the request carried it."},
        "output": {"type": "array", "items": _OUTPUT_ITEM},
        "usage": _USAGE,
    },
}

openapi_fragment = {
    # No `components`: the item-4 `error` schema is supplied once by
    # `contract/base/openapi.py`, and the payload schemas are inline so the
    # auto-generated MCP tool carries real parameters instead of a $ref.
    "paths": {
        "/v1/responses": {
            "post": {
                "operationId": "responses",
                "summary": "One model turn on the Responses API (family 1).",
                "description": (
                    "The OpenAI Responses API by reference (ADR-0001 §Families.1): "
                    "typed streaming events, tool calling (function tools + MCP "
                    "servers), structured outputs, citations, reasoning items, "
                    "refusals, and `usage` in tokens. Multimodal input is in. "
                    "Background responses are the async-jobs family, not this one."
                ),
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": _REQUEST}},
                },
                "responses": {
                    "200": {
                        "description": (
                            "The response body, or — with `stream: true` — an SSE "
                            "stream of typed events ending in `response.completed`."
                        ),
                        "content": {
                            "application/json": {"schema": _RESPONSE},
                            "text/event-stream": {
                                "schema": {
                                    "type": "string",
                                    "description": "`event: <type>` + `data: <json>` frames, sequence_number ordered.",
                                }
                            },
                        },
                    },
                    "400": {
                        "description": "Malformed request, an unknown input part or tool type, or a feature the selected implementation does not support.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "401": {
                        "description": "Missing or invalid Bearer key.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "413": {
                        "description": "Request body over the family's size limit.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "429": {
                        "description": "resource_exhausted — vram/ram/disk/gpu/cloud-spend (ADR-0005).",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "503": {
                        "description": "busy or unavailable — the engine cannot serve right now.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                },
            }
        }
    },
}
