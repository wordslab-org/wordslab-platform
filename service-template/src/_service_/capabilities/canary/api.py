"""The canary's OpenAPI fragment — the capability's API self-description.

The fragment uses the FULL contract paths (`/v1/...`) and is merged into the
service's document by `contract.base.openapi.openapi_document`; the `/mcp`
tools are then auto-generated from the merged document. Authoring rule:
describe the API the way a client drives it — schema per request body,
`operationId` per operation (it becomes the MCP tool's name).
"""

from __future__ import annotations

openapi_fragment = {
    # No `components.schemas.error` here: the item-4 error body is
    # contract-wide and supplied once by `contract/base/openapi.py`
    # (ERROR_SCHEMA) — a fragment that redefines it fails assembly loudly.
    # A capability's own schemas still live here (the canary needs none).
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
                                # The interaction's content is the `text`
                                # string; the consent flag rides every user
                                # input (ADR-0026 §1, ticket #72): two
                                # states, the `may_use` default. The MCP
                                # surface inherits this schema — zero drift
                                # by construction.
                                "required": ["text"],
                                "properties": {
                                    "text": {
                                        "type": "string",
                                        "description": "The interaction's content.",
                                    },
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
                                    "owner": {
                                        "type": "string",
                                        "default": "local",
                                        "description": (
                                            "The identity the interaction belongs to (ADR-0021 §1). "
                                            "Absent: the machine's local user identity — the "
                                            "attribution the per-user export/restore contract "
                                            "extracts on (ticket #269)."
                                        ),
                                    },
                                    "role": {
                                        "type": "string",
                                        "enum": ["user", "builder", "admin"],
                                        "default": "user",
                                        "description": (
                                            "The data sphere the interaction belongs to "
                                            "(ADR-0021 §1 — the three identities of a physical "
                                            "user)."
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
                    "and unset interactions are excluded and reported, never bypassed. "
                    "The gate is eligibility over the whole record; the item-5 "
                    "pagination (?limit/?cursor) slices the eligible list, and the "
                    "exclusion report rides every page."
                ),
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
                        "description": "Page size (base contract item 5).",
                    },
                    {
                        "name": "cursor",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "The opaque cursor from the previous page.",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "The eligible interactions (item-5 envelope) and the exclusion report.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["items", "next_cursor", "excluded"],
                                    "properties": {
                                        "items": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["seq", "owner", "role", "text", "consent"],
                                                "properties": {
                                                    "seq": {"type": "integer"},
                                                    "owner": {"type": "string"},
                                                    "role": {"type": "string", "enum": ["user", "builder", "admin"]},
                                                    "text": {"type": "string"},
                                                    "consent": {
                                                        "type": "string",
                                                        "enum": ["may_use"],
                                                    },
                                                },
                                            },
                                        },
                                        "next_cursor": {
                                            "type": "string",
                                            "description": "The opaque next-page cursor; empty on the last page.",
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
        # --- The per-user export/restore surface (ticket #269, ADR-0021
        # --- §3/§5/§7) — the base contract module's routes
        # --- (`contract/base/export_restore.py`), demonstrated on the
        # --- canary's interaction record. The core's `backup` capability
        # --- (ADR-0021 §8, `core.backup` — recorded as data, not built)
        # --- calls this shape at the end.
        "/v1/export": {
            "get": {
                "operationId": "export",
                "summary": "Export one user+role's data as a self-contained unit.",
                "description": (
                    "The per-user export surface (ADR-0021 §3): `owner` + `role` are "
                    "REQUIRED — a whole-DB export (no user+role context) is the shape "
                    "ADR-0021 §3 forbids. `since` selects a true-incremental delta "
                    "(records with seq > since); absent selects a full export. The unit "
                    "is deliberately NOT item-5 paginated: a paginated export is not a "
                    "self-contained unit."
                ),
                "parameters": [
                    {
                        "name": "owner",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The identity whose data is exported (ADR-0021 §1).",
                    },
                    {
                        "name": "role",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "enum": ["user", "builder", "admin"]},
                        "description": "The data sphere (ADR-0021 §1 — the three identities).",
                    },
                    {
                        "name": "since",
                        "in": "query",
                        "schema": {"type": "integer", "minimum": 0},
                        "description": "Export only records with seq > since — a true-incremental delta (ADR-0021 §5).",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "One self-contained export unit (ADR-0021 §3).",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["service", "version", "owner", "role", "kind", "since", "through", "items"],
                                    "properties": {
                                        "service": {"type": "string", "description": "The service identity the unit was exported from (ADR-0021 §7)."},
                                        "version": {"type": "string"},
                                        "owner": {"type": "string"},
                                        "role": {"type": "string", "enum": ["user", "builder", "admin"]},
                                        "kind": {"type": "string", "enum": ["full", "delta"]},
                                        "since": {
                                            "type": ["integer", "null"],
                                            "description": "null for a full export; the seq a delta chains from (ADR-0021 §5).",
                                        },
                                        "through": {"type": "integer", "description": "The highest seq this service holds for the user+role."},
                                        "items": {"type": "array", "items": {"type": "object"}},
                                    },
                                }
                            }
                        },
                    },
                    "400": {
                        "description": "Missing/empty owner, unknown role, or non-integer since.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "401": {
                        "description": "Missing or invalid Bearer key.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                },
            }
        },
        "/v1/restore": {
            "post": {
                "operationId": "restore",
                "summary": "Apply one export unit to this service.",
                "description": (
                    "The restore surface (ADR-0021 §3/§5/§7): a full unit replaces the "
                    "user+role's records; a delta must chain onto the current high-water "
                    "seq (else 409 conflict). The unit's service identity is verified "
                    "against this service before apply — the restore target must provide "
                    "the same service (ADR-0021 §7)."
                ),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["service", "version", "owner", "role", "kind", "since", "through", "items"],
                                "properties": {
                                    "service": {"type": "string"},
                                    "version": {"type": "string"},
                                    "owner": {"type": "string"},
                                    "role": {"type": "string", "enum": ["user", "builder", "admin"]},
                                    "kind": {"type": "string", "enum": ["full", "delta"]},
                                    "since": {"type": ["integer", "null"]},
                                    "through": {"type": "integer"},
                                    "items": {"type": "array", "items": {"type": "object"}},
                                },
                                "additionalProperties": False,
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "The unit was applied.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["restored", "owner", "role", "kind", "items"],
                                    "properties": {
                                        "restored": {"type": "boolean", "const": True},
                                        "owner": {"type": "string"},
                                        "role": {"type": "string"},
                                        "kind": {"type": "string", "enum": ["full", "delta"]},
                                        "items": {"type": "integer", "description": "The number of records applied."},
                                    },
                                }
                            }
                        },
                    },
                    "400": {
                        "description": "The body is not a valid export unit (closed shape — unknown/missing keys, bad vocabulary).",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "401": {
                        "description": "Missing or invalid Bearer key.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                    "409": {
                        "description": "The unit's service identity does not match, or a delta does not chain onto the current seq.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/error"}}},
                    },
                },
            }
        },
    },
}
