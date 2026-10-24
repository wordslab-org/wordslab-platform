"""The canary's routes — the deterministic surface it owns.

Handlers are thin: validate the request, return the contract body. Business
logic of a real capability lives here in the same shape (a real capability
would also own its SQLModel tables — the canary's interaction record is a
bounded in-memory store, just enough to prove the consent contract).

The consent contract rides the canary (ticket #72, ADR-0026 §1/§2): every
input carries the consent flag; the extraction surface applies the base
consent gate — the private/secret exclusion is never bypassable.

The export/restore contract rides the canary too (ticket #269, ADR-0021 §3):
every record carries its user+role attribution (an input without an explicit
owner/role belongs to the machine's local user identity), and the canary
wires the base export/restore surface against this store — the template's
demonstration that a service's storage can extract one user+role's data as a
self-contained unit and replay full + true-incremental deltas onto it.
"""

from __future__ import annotations

from collections import deque

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from contract.base.consent import consent_gate, input_consent
from contract.base.errors import invalid_request, request_too_large
from contract.base.export_restore import (
    DEFAULT_OWNER,
    DEFAULT_ROLE,
    export_restore_routes,
    resolve_owner_role,
)
from contract.base.pagination import paginate

MAX_ECHO_BYTES = 64 * 1024  # the canary echoes small JSON objects only
MAX_INTERACTIONS = 128  # the canary's bounded interaction record


class InteractionStore:
    """The canary's in-memory interaction record — per-app state (created by
    `app.py`, handed to the routes), bounded so the template stays a
    skeleton: `deque(maxlen=...)` evicts the oldest interaction over the
    cap. Each record carries a monotonic `seq` — the unique, order-stable
    key the item-5 cursor anchors on — and its user+role attribution
    (ticket #269, ADR-0021 §1/§3), which is what makes the per-user
    export/restore contract demonstrable on the canary. A real capability
    records its traces durably (its own SQLModel tables).

    The store also implements the export/restore store protocol
    (`contract/base/export_restore.py`): `records` / `high_water` /
    `apply_full` / `apply_delta` over the user+role attribution."""

    def __init__(self, *, max_interactions: int = MAX_INTERACTIONS) -> None:
        self._interactions: deque = deque(maxlen=max_interactions)
        self._seq = 0

    def record(
        self,
        *,
        text: str,
        consent: str,
        owner: str = DEFAULT_OWNER,
        role: str = DEFAULT_ROLE,
    ) -> dict:
        self._seq += 1
        interaction = {
            "seq": self._seq,
            "owner": owner,
            "role": role,
            "text": text,
            "consent": consent,
        }
        self._interactions.append(interaction)
        return interaction

    def all(self) -> list[dict]:
        return list(self._interactions)

    # --- the export/restore store protocol (contract/base/export_restore.py)

    def records(self, owner: str, role: str, *, after_seq: int = 0) -> list[dict]:
        """The user+role's records with `seq > after_seq`, in seq order —
        the per-user extraction ADR-0021 §3 mandates (a full export passes
        `after_seq=0`, a true-incremental delta the last backed-up seq)."""
        return [
            dict(i)
            for i in self._interactions
            if i["owner"] == owner and i["role"] == role and i["seq"] > after_seq
        ]

    def high_water(self, owner: str, role: str) -> int:
        """The highest seq stored for that user+role (0 when none) — the
        seq a delta chains from (ADR-0021 §5)."""
        return max(
            (i["seq"] for i in self._interactions if i["owner"] == owner and i["role"] == role),
            default=0,
        )

    def apply_full(self, owner: str, role: str, items: list[dict]) -> None:
        """Replace the user+role's records with the export unit's items —
        the restore of a full export (ADR-0021 §7)."""
        kept = [i for i in self._interactions if not (i["owner"] == owner and i["role"] == role)]
        self._interactions = deque(kept, maxlen=self._interactions.maxlen)
        for item in items:
            self._append_attributed(item)

    def apply_delta(self, owner: str, role: str, items: list[dict]) -> None:
        """Append the export unit's items — the true-incremental replay
        (ADR-0021 §5)."""
        for item in items:
            self._append_attributed(item)

    def _append_attributed(self, item: dict) -> None:
        """Re-record one restored item under its ORIGINAL attribution: the
        export unit's items carry their own owner/role, and a restore must
        not renumber or re-attribute them (the unit is self-contained,
        ADR-0021 §3)."""
        self._interactions.append(dict(item))
        self._seq = max(self._seq, int(item["seq"]))


async def ping(request: Request) -> JSONResponse:
    """GET /v1/echo/ping — returns pong."""
    return JSONResponse({"pong": True})


def routes(interactions: InteractionStore, *, service_name: str, version: str) -> list[Route]:
    """The canary's routes, closed over the per-app interaction store (the
    app's assembly in `app.py` creates the store and hands it here). The
    base export/restore surface rides the canary too (ticket #269): the
    canary's store implements the store protocol, so the template's proof
    capability demonstrably passes the per-user export/restore contract."""

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
        try:
            consent = input_consent(parsed)
        except ValueError as error:
            raise invalid_request(str(error)) from None
        # The user+role attribution rides every recorded interaction (ticket
        # #269, ADR-0021 §1/§3): an ABSENT attribution belongs to the
        # machine's local user identity; a DECLARED one outside the closed
        # role vocabulary — or an empty owner — is 400 invalid_request.
        try:
            owner, role = resolve_owner_role(
                parsed.get("owner", DEFAULT_OWNER), parsed.get("role", DEFAULT_ROLE)
            )
        except ValueError as error:
            raise invalid_request(str(error)) from None
        interactions.record(text=text, consent=consent, owner=owner, role=role)
        return JSONResponse(parsed)

    async def extract(request: Request) -> JSONResponse:
        """GET /v1/echo/extract — the canary's extraction surface: the
        recorded interactions through the base consent gate (ADR-0026 §2
        pass 1), with the exclusions reported. The gate is eligibility over
        the WHOLE record; the base item-5 pagination slices the eligible
        list, and the exclusion report rides every page."""
        eligible, excluded = consent_gate(interactions.all())
        return paginate(
            request, eligible, key_fn=lambda item: item["seq"], extra={"excluded": excluded}
        )

    return [
        Route("/v1/echo", echo, methods=["POST"]),
        Route("/v1/echo/extract", extract, methods=["GET"]),
        Route("/v1/echo/ping", ping, methods=["GET"]),
        # The per-user export/restore surface (ticket #269, ADR-0021 §3):
        # the base contract module's routes, wired against this store — the
        # canary is the template's demonstration that a service passes the
        # contract.
        *export_restore_routes(interactions, service_name=service_name, version=version),
    ]
