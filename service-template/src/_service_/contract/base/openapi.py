"""The deterministic surface — the service's OpenAPI 3.1 document
(ADR-0001 §Base contract.1: every service exposes its OpenAPI 3.1 doc at
`/openapi.json`).

The document is ASSEMBLED, not generated from code: each capability ships an
OpenAPI fragment (its paths, in full `/v1/...` contract paths) and the
service app merges them under the service identity. The MCP surface
(`contract/base/mcp.py`) is then auto-generated from this same document —
zero drift by construction: the OpenAPI doc IS the tool list's source.

One schema is NOT a capability's to define: the item-4 error body. It is
contract-wide, so it is supplied here, once, for every document — a fragment
that documents error responses `$ref`s it. (Two fragments each shipping their
own copy is a composition error the merge would raise anyway; naming the rule
here means a contributor reads why instead of debugging a duplicate.)
"""

from __future__ import annotations

# The item-4 error body, verbatim: `{"error": {"type", "message", "resource"?},
# "request_id"}` (ADR-0001 §Base contract.4). Every fragment's error responses
# `$ref` `#/components/schemas/error`.
ERROR_SCHEMA = {
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


def openapi_document(
    *,
    title: str,
    version: str,
    description: str = "",
    fragments: list[dict] | None = None,
) -> dict:
    """Merge capability OpenAPI fragments into one OpenAPI 3.1 document.

    A fragment is `{"paths": {...}, "components"?: {...}}` — the canary's is
    the pattern (capabilities/canary/api.py). Paths are keyed by their full
    contract paths (`/v1/...`); duplicate paths/operationIds across
    capabilities are a composition error and fail loudly at assembly, as is a
    fragment that redefines the contract-wide `error` schema.
    """
    paths: dict = {}
    operation_ids: set[str] = set()
    # The one contract-wide schema — supplied here, never by a fragment.
    components: dict = {"schemas": {"error": ERROR_SCHEMA}}
    for fragment in fragments or []:
        for path, item in fragment.get("paths", {}).items():
            if path in paths:
                raise ValueError(f"duplicate OpenAPI path across capabilities: {path}")
            for method, operation in item.items():
                op_id = operation.get("operationId")
                if op_id:
                    if op_id in operation_ids:
                        raise ValueError(f"duplicate operationId in OpenAPI fragments: {op_id}")
                    operation_ids.add(op_id)
            paths[path] = item
        for kind, definitions in fragment.get("components", {}).items():
            existing = components.setdefault(kind, {})
            for name, definition in definitions.items():
                if kind == "schemas" and name == "error":
                    raise ValueError(
                        "a fragment redefines the contract-wide `error` schema — "
                        "it is supplied once by openapi_document() (ADR-0001 base "
                        "item 4); $ref it instead"
                    )
                if name in existing:
                    raise ValueError(
                        f"duplicate OpenAPI component {kind}/{name} across capabilities"
                    )
                existing[name] = definition
    return {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version, "description": description},
        "paths": paths,
        "components": components,
    }
