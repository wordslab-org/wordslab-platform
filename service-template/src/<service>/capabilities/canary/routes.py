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

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from contract.base.consent import consent_gate, resolve_consent
from contract.base.errors import invalid_request, request_too_large

MAX_ECHO_BYTES = 64 * 1024  # the canary echoes small JSON objects only
MAX_INTERACTIONS = 128  # the canary's bounded interaction record


class InteractionStore:
    """The canary's in-memory interaction record — per-app state (created by
    `app.py`, handed to the routes), bounded so the template stays a
    skeleton: over the cap the oldest interaction is evicted. A real
    capability records its traces durably (its own SQLModel tables)."""

    def __init__(self, *, max_interactions: int = MAX_INTERACTIONS) -> None:
        self._max = max_interactions
        self._interactions: list[dict] = []

    def record(self, *, text: object, consent: str) -> dict:
        interaction = {"text": text, "consent": consent}
        self._interactions.append(interaction)
        if len(self._interactions) > self._max:
            del self._interactions[: len(self._interactions) - self._max]
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
        # The consent flag rides every user input (ADR-0026 §1, ticket #72):
        # resolve it against the two states — absent → the `may_use` default,
        # an unknown mark → 400 invalid_request, never a silent normalization.
        try:
            consent = resolve_consent(parsed.get("consent"))
        except ValueError as error:
            raise invalid_request(str(error)) from None
        interactions.record(text=parsed.get("text"), consent=consent)
        return JSONResponse(parsed)

    async def extract(request: Request) -> JSONResponse:
        """GET /v1/echo/extract — the canary's extraction surface: the
        recorded interactions through the base consent gate (ADR-0026 §2
        pass 1), with the exclusions reported."""
        eligible, excluded = consent_gate(interactions.all())
        return JSONResponse({"interactions": eligible, "excluded": excluded})

    return [
        Route("/v1/echo", echo, methods=["POST"]),
        Route("/v1/echo/extract", extract, methods=["GET"]),
        Route("/v1/echo/ping", ping, methods=["GET"]),
    ]
