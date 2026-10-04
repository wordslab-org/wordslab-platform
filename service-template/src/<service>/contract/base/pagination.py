"""Base contract item 5 — Pagination (ADR-0001 §Base contract.5).

Cursor-based only: `?limit` (default 50, max 200) + `?cursor`; responses
`{"items": [...], "next_cursor": "<opaque>"}`. No page numbers, no offset;
cursors never parsed by clients — the token is opaque (JSON + HMAC, so a
tampered cursor is a 400 `invalid_request`, not a decoding crash).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets

from starlette.requests import Request
from starlette.responses import JSONResponse

from .errors import invalid_request

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

# Per-process signing secret. Cursors are short-lived navigation tokens, not
# stored state; a restart invalidating old cursors is acceptable (a client
# re-lists from the start — there are no offsets to resume).
_SECRET = os.environ.get("WORDSLAB_CURSOR_SECRET") or secrets.token_hex(32)


def _sign(payload: bytes) -> str:
    return hmac.new(_SECRET.encode(), payload, hashlib.sha256).hexdigest()[:32]


def encode_cursor(last_key: str) -> str:
    """Encode an opaque cursor carrying the last-seen item key."""
    payload = json.dumps({"k": last_key}, separators=(",", ":")).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{token}.{_sign(payload)}"


def decode_cursor(cursor: str) -> str:
    """Return the last-seen key, or raise `invalid_request` on any
    malformed/tampered cursor."""
    try:
        token, _, signature = cursor.partition(".")
        payload = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        if not hmac.compare_digest(_sign(payload), signature):
            raise ValueError("signature mismatch")
        return json.loads(payload)["k"]
    except Exception as exc:
        raise invalid_request("Malformed cursor.") from exc


def parse_limit(request: Request) -> int:
    raw = request.query_params.get("limit")
    if raw is None:
        return DEFAULT_LIMIT
    try:
        limit = int(raw)
    except ValueError as exc:
        raise invalid_request("limit must be an integer.") from exc
    if limit < 1:
        raise invalid_request("limit must be >= 1.")
    return min(limit, MAX_LIMIT)


def paginate(request: Request, items: list, key_fn) -> JSONResponse:
    """Slice `items` for this request and return the contract envelope.

    `items` must be in their stable order; `key_fn(item)` gives each item's
    unique, order-stable key (the cursor's anchor).
    """
    limit = parse_limit(request)
    cursor = request.query_params.get("cursor")
    if cursor:
        last_key = decode_cursor(cursor)
        start = next(
            (i + 1 for i, item in enumerate(items) if str(key_fn(item)) == last_key), None
        )
        if start is None:
            raise invalid_request("Unknown cursor: the item it anchors no longer exists.")
    else:
        start = 0
    page = items[start : start + limit]
    has_more = start + limit < len(items)
    next_cursor = encode_cursor(str(key_fn(page[-1]))) if has_more else ""
    return JSONResponse({"items": page, "next_cursor": next_cursor})
