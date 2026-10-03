"""Base contract machinery (ADR-0001 base items 1–9, vendored per ADR-0002).

This package is the `contract/base/` of the service template: it is **always
kept, never edited** (ADR-0002 §The template.1). Every module implements one
base-contract item; the item wording lives in ADR-0001 — cite it, don't
restate it in new definitions.
"""

from .errors import ApiError, ERROR_TAXONOMY
from .pagination import decode_cursor, encode_cursor, paginate
from .app import create_service_app

__all__ = [
    "ApiError",
    "ERROR_TAXONOMY",
    "create_service_app",
    "paginate",
    "encode_cursor",
    "decode_cursor",
]
