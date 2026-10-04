"""The deterministic surface — the service's OpenAPI 3.1 document
(ADR-0001 §Base contract.1: every service exposes its OpenAPI 3.1 doc at
`/openapi.json`).

The document is ASSEMBLED, not generated from code: each capability ships an
OpenAPI fragment (its paths, in full `/v1/...` contract paths) and the
service app merges them under the service identity. The MCP surface
(`contract/base/mcp.py`) is then auto-generated from this same document —
zero drift by construction: the OpenAPI doc IS the tool list's source.
"""

from __future__ import annotations


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
    capabilities are a composition error and fail loudly at assembly.
    """
    paths: dict = {}
    operation_ids: set[str] = set()
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
    return {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version, "description": description},
        "paths": paths,
    }
