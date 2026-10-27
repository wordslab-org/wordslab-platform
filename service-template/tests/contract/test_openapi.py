"""The assembled OpenAPI document (base item 1) — its contract-wide parts.

One schema is NOT a capability's to define: the item-4 error body. It is
supplied once by `openapi_document()` from `base/errors.py` (next to
`ApiError.body()`, which builds the same shape at runtime), so a service with
several capabilities publishes it exactly once and every fragment `$ref`s it. A
fragment that redefines it is a composition error — before this rule existed,
the canary and the first family fragment each shipped a copy and the service
crashed at startup.

These are BASE guarantees, so they belong in the always-run block: a copied
service inherits them and catches the drift itself.
"""

import pytest

from contract.base.errors import ERROR_SCHEMA, ApiError
from contract.base.openapi import openapi_document


def test_the_document_always_carries_the_item_4_error_schema():
    document = openapi_document(title="probe", version="0.0.1")
    assert document["components"]["schemas"]["error"] == ERROR_SCHEMA


def test_a_fragment_that_redefines_the_error_schema_fails_loudly():
    fragment = {"paths": {}, "components": {"schemas": {"error": {"type": "object"}}}}
    with pytest.raises(ValueError, match="redefines the contract-wide"):
        openapi_document(title="probe", version="0.0.1", fragments=[fragment])


def test_the_published_error_schema_matches_the_runtime_body():
    """The document and the wire are one shape: if `ApiError.body()` gains a
    field, this test is what tells the published schema to follow."""
    body = ApiError("resource_exhausted", "no vram left", resource="vram").body("req-1")
    assert set(body) == set(ERROR_SCHEMA["required"])
    error_schema = ERROR_SCHEMA["properties"]["error"]
    assert set(ERROR_SCHEMA["properties"]["error"]["required"]) <= set(body["error"])
    assert set(body["error"]) <= set(error_schema["properties"])


def test_an_injected_schema_is_a_copy_so_a_caller_cannot_mutate_the_constant():
    served = openapi_document(title="probe", version="0.0.1")
    served["components"]["schemas"]["error"]["properties"].clear()
    assert ERROR_SCHEMA["properties"]  # the module constant is untouched
