"""Family 1 — the OpenAPI fragment for `POST /v1/responses`.

A capability that implements family 1 merges this fragment into the service's
document (base item 1's `/openapi.json`, assembled by
`contract/base/openapi.openapi_document`). Because the `/mcp` tools are
auto-generated from that same document, merging the fragment is what makes the
inference capability agent-callable — no separate MCP code (base item 9).

The schemas describe the contract this module enforces (see `shapes.py`); the
engine implementations vary behind it (ADR-0004), which is what the support
matrix documents (`support.py`, `docs/family-1-responses.md`).
"""

from __future__ import annotations

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

_ERROR = {
    "type": "object",
    "required": ["error", "request_id"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["type", "message"],
            "properties": {
                "type": {"type": "string"},
                "message": {"type": "string"},
                "resource": {"type": "string"},
            },
        },
        "request_id": {"type": "string"},
    },
}

_INPUT_PART = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "enum": ["input_text", "input_image", "input_audio"],
            "description": "Multimodal input is in (ADR-0001 §Families.1); generation output is text or structured.",
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
    },
}

_OUTPUT_ITEM = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "enum": ["message", "function_call", "reasoning", "mcp_call", "mcp_list_tools"],
        },
        "role": {"type": "string", "description": "message"},
        "content": {
            "type": "array",
            "description": "message — content parts.",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string", "enum": ["output_text", "refusal"]},
                    "text": {"type": "string"},
                    "refusal": {"type": "string"},
                    "annotations": {
                        "type": "array",
                        "description": "Citations ride the output_text part.",
                        "items": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "type": {"type": "string", "enum": ["url_citation", "file_citation"]}
                            },
                        },
                    },
                },
            },
        },
        "name": {"type": "string", "description": "function_call / mcp_call"},
        "arguments": {"type": "string", "description": "function_call — a JSON string."},
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
            "description": "A string (one input_text part), or a list of input parts / role-tagged message objects.",
            "items": _INPUT_PART,
        },
        "instructions": {"type": "string"},
        "tools": {
            "type": "array",
            "description": "Function tools and MCP servers (ADR-0001 §Families.1).",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"type": "string", "enum": ["function", "mcp"]},
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
                        "type": {"type": "string", "enum": ["text", "json_schema"]},
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
        "status": {"type": "string", "enum": ["completed", "incomplete", "failed"]},
        "model": {"type": "string"},
        "output": {"type": "array", "items": _OUTPUT_ITEM},
        "usage": _USAGE,
    },
}

openapi_fragment = {
    "components": {
        "schemas": {
            "error": _ERROR,
            "responses_request": _REQUEST,
            "responses_response": _RESPONSE,
            "responses_usage": _USAGE,
        }
    },
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
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/responses_request"}}},
                },
                "responses": {
                    "200": {
                        "description": (
                            "The response body, or — with `stream: true` — an SSE "
                            "stream of typed events ending in `response.completed`."
                        ),
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/responses_response"}},
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
