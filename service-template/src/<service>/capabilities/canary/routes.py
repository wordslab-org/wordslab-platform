"""The canary's routes — the deterministic surface it owns.

Handlers are thin: validate the request, return the contract body. Business
logic of a real capability lives here in the same shape (a real capability
would also own its SQLModel tables — the canary's interaction record is a
bounded in-memory store, just enough to prove the consent contract).

The consent contract rides the canary (ticket #72, ADR-0026 §1/§2): every
input carries the consent flag; the extraction surface applies the base
consent gate — the private/secret exclusion is never bypassable.
"""

from __future__ import annotations

import json
from collections import deque

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from contract.base.consent import DEFAULT_CONSENT, consent_gate, resolve_consent
from contract.base.errors import invalid_request, request_too_large
from contract.base.pagination import paginate

MAX_ECHO_BYTES = 64 * 1024  # the canary echoes small JSON objects only
MAX_INTERACTIONS = 128  # the canary's bounded interaction record


class InteractionStore:
    """The canary's in-memory interaction record — per-app state (created by
    `app.py`, handed to the routes), bounded so the template stays a
    skeleton: `deque(maxlen=...)` evicts the oldest interaction over the
    cap. Each record carries a monotonic `seq` — the unique, order-stable
    key the item-5 cursor anchors on. A real capability records its traces
    durably (its own SQLModel tables)."""

    def __init__(self, *, max_interactions: int = MAX_INTERACTIONS) -> None:
        self._interactions: deque = deque(maxlen=max_interactions)
        self._seq = 0

    def record(self, *, text: str, consent: str) -> dict:
        self._seq += 1
        interaction = {"seq": self._seq, "text": text, "consent": consent}
        self._interactions.append(interaction)
        return interaction

    def all(self) -> list[dict]:
        return list(self._interactions)


async def ping(request: Request) -> JSONResponse:
    """GET /v1/echo/ping — returns pong."""
    return JSONResponse({"pong": True})


def routes(interactions: InteractionStore) -> list[Route]:
    """The canary's routes, closed over the per-app interaction store (the
    app's assembly in `app.py` creates the store and hands it here)."""

    async def echo(request: Request) -> JSONResponse:
        """POST /v1/echo — returns the request body."""
        body = await request.body()
        if not body:
            raise invalid_request("POST /v1/echo expects a JSON object request body.")
        if len(body) > MAX_ECHO_BYTES:
            raise request_too_large(
                f"Echo body exceeds the {MAX_ECHO_BYTES}-byte canary limit."
            )
        try:
            parsed = await request.json()
        except ValueError:  # malformed JSON is a CLIENT error (item 4 taxonomy),
            raise invalid_request(  # never an unhandled 500 internal_error
                "POST /v1/echo expects a JSON object request body."
            ) from None
        if not isinstance(parsed, dict):
            raise invalid_request("POST /v1/echo expects a JSON object request body.")
        # The interaction's content is the `text` string (the OpenAPI schema
        # requires it) — a body without one has no interaction to record, so
        # it is a client error, not a silently degraded record.
        text = parsed.get("text")
        if not isinstance(text, str):
            raise invalid_request(
                "POST /v1/echo expects a string 'text' in the JSON object request body."
            )
        # The consent flag rides every user input (ADR-0026 §1, ticket #72):
        # an ABSENT flag takes the `may_use` default; a DECLARED mark that is
        # not one of the two states — an unknown value or an explicit null —
        # is 400 invalid_request, never a silent normalization.
        if "consent" in parsed:
            try:
                consent = resolve_consent(parsed["consent"])
            except ValueError as error:
                raise invalid_request(str(error)) from None
        else:
            consent = DEFAULT_CONSENT
        interactions.record(text=text, consent=consent)
        return JSONResponse(parsed)

    async def extract(request: Request) -> JSONResponse:
        """GET /v1/echo/extract — the canary's extraction surface: the
        recorded interactions through the base consent gate (ADR-0026 §2
        pass 1), with the exclusions reported. The gate is eligibility over
        the WHOLE record; the base item-5 pagination slices the eligible
        list, and the exclusion report rides every page."""
        eligible, excluded = consent_gate(interactions.all())
        response = paginate(request, eligible, key_fn=lambda item: item["seq"])
        payload = json.loads(bytes(response.body))
        payload["excluded"] = excluded
        return JSONResponse(payload, status_code=response.status_code)

    return [
        Route("/v1/echo", echo, methods=["POST"]),
        Route("/v1/echo/extract", extract, methods=["GET"]),
        Route("/v1/echo/ping", ping, methods=["GET"]),
    ]
