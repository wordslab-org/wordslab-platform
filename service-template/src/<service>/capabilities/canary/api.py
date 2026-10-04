"""The canary's OpenAPI fragment — the capability's API self-description.

The fragment uses the FULL contract paths (`/v1/...`) and is merged into the
service's document by `contract.base.openapi.openapi_document`; the `/mcp`
tools are then auto-generated from the merged document. Authoring rule:
describe the API the way a client drives it — schema per request body,
`operationId` per operation (it becomes the MCP tool's name).
"""

from __future__ import annotations

openapi_fragment = {
    "components": {
        "schemas": {
            # The item-4 error body, as every endpoint's error responses
            # reference it ($ref below).
            "error": {
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
            },
        }
    },
    "paths": {
        "/v1/echo": {
            "post": {
                "operationId": "echo",
                "summary": "Echo the request body back.",
                "description": "Returns the JSON object received, unchanged.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                # The consent flag rides every user input
                                # (ADR-0026 §1, ticket #72): two states, the
                                # `may_use` default. The MCP surface inherits
                                # this schema — zero drift by construction.
                                "properties": {
                                    "consent": {
                                        "type": "string",
                                        "enum": ["may_use", "private_secret"],
                                        "default": "may_use",
                                        "description": (
                                            "The interaction's consent state (ADR-0026 §1): "
                                            "'may_use' (the default — eligible for improvement "
                                            "extraction) or 'private_secret' — do not use."
                                        ),
                                    },
                                },
                                "additionalProperties": True,
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "The echoed request body.",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "additionalProperties": True}
                            }
                        },
                    },
                    # The error taxonomy is contract-wide (item 4: one JSON
                    # shape, fixed 11 codes) — the fragments document the
                    # per-operation codes a client can hit here.
                    "400": {
                        "description": "Missing, non-object, malformed, or oversized body.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "401": {
                        "description": "Missing or invalid Bearer key.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "413": {
                        "description": "Body over the canary's echo limit.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                },
            }
        },
        "/v1/echo/extract": {
            "get": {
                "operationId": "echo.extract",
                "summary": "Extract the canary's interactions through the consent gate.",
                "description": (
                    "The canary's extraction surface (ticket #72, ADR-0026 §2 pass 1): "
                    "only 'may_use' interactions are eligible to pass; private/secret "
                    "and unset interactions are excluded and reported, never bypassed."
                ),
                "responses": {
                    "200": {
                        "description": "The eligible interactions and the exclusion report.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["interactions", "excluded"],
                                    "properties": {
                                        "interactions": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["text", "consent"],
                                                "properties": {
                                                    "text": {},
                                                    "consent": {
                                                        "type": "string",
                                                        "enum": ["may_use"],
                                                    },
                                                },
                                            },
                                        },
                                        "excluded": {
                                            "type": "object",
                                            "description": (
                                                "Excluded-interaction counts by consent "
                                                "state ('private_secret' / 'unset')."
                                            ),
                                            "additionalProperties": {"type": "integer"},
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "401": {
                        "description": "Missing or invalid Bearer key.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                },
            }
        },
        "/v1/echo/ping": {
            "get": {
                "operationId": "echo.ping",
                "summary": "Ping the canary.",
                "description": "Returns pong — a liveness probe for the canary capability.",
                "responses": {
                    "200": {
                        "description": "Pong.",
                        "content": {
                            "application/json": {"schema": {"type": "object", "required": ["pong"], "properties": {"pong": {"type": "boolean"}}}}
                        },
                    },
                    "401": {
                        "description": "Missing or invalid Bearer key.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                },
            }
        },
    }
}
