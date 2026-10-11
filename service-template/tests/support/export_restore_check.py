"""The per-user export/restore compliance checker (ticket #269) — the
test-side, cross-cutting assertions that keep ADR-0021 §3's storage contract
checkable *from the first service* (the build order's testability rule;
spec #65).

Vocabulary note: this is a **compliance checker / test harness**. In an
agentic platform "harness" alone reads as the *AI agent harness* (ADR-0017
§6) — so the module, its functions, and its docs always say **compliance
checker** or **test harness**, never bare "harness".

Unlike the sibling placement checkers (#275 security-controls, #285
consent-controls — plain-data maps), this contract is a SHIPPED surface
(`contract/base/export_restore.py`), so the checker asserts it over the one
HTTP seam: it stands up a **controlled stub service** — a base-contract–
conforming service exposing its per-user export/restore surface, standing in
for Inference/Document/… — and probes it:

1. **the whole-DB export is not expressible** — an export request without
   the user+role context is rejected, never served (ADR-0021 §3's forbidden
   shape);
2. **per-user isolation** — each expected user+role's export contains that
   user+role's records and NO other user's (the isolation a whole-DB backup
   defeats);
3. **the unit is self-contained** — the closed unit shape, the service
   identity it was exported from, a consistent seq chain (ADR-0021 §3/§7);
4. **the true-incremental delta** — `since` yields exactly the records above
   that seq (ADR-0021 §5);
5. **the restore shape gate** — a malformed unit is a 400, never applied;
6. **the delta chain is enforced** — a delta that does not chain onto the
   current high-water seq is a 409, never silently applied;
7. **full + delta replay** — restoring the chain onto a fresh target service
   reproduces the source's state exactly (ADR-0021 §3/§5/§7);
8. **determinism** — the same export answers identically twice (no clock,
   no randomness — the cadence itself is #270's, not this checker's).

A service failing the contract (e.g. a whole-DB-only export) is CAUGHT: the
probes report findings, they do not raise — the sweeper prints what is wrong
rather than crashing on it. `WholeDbExportService` below is the fixture that
proves it (#269 AC 3).

The sweep entry point (`check_export_restore`) is what the test-harness
sweeper (#68/#85) calls to re-verify the contract per service as each lands
from #47 on, and the seam the end-stage backup orchestration tickets
(#270–#272) call when the `backup` machinery is deepened. #85 does not exist
yet, so the entry point is explicit and documented, proven by this ticket's
own tests against the canary (#46) — not an integration with a sweeper that
isn't there.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from contract.base.app import create_service_app
from contract.base.export_restore import (
    UNIT_KEYS,
    build_export_unit,
    export_restore_routes,
)

from tests.support.stubs import stub_api_key

__all__ = [
    "ContractReport",
    "StubExportRestoreService",
    "WholeDbExportService",
    "check_export_restore",
    "contract_findings",
]

# The checker's controlled dataset: two physical users across two spheres —
# alice (user + builder) and bob (user). Per-user isolation is only
# assertable when more than one identity has data.
ALICE, BOB = "alice", "bob"
CONTROLLED_RECORDS: tuple[tuple[str, str, str], ...] = (
    (ALICE, "user", "alice-user-1"),
    (ALICE, "user", "alice-user-2"),
    (ALICE, "builder", "alice-builder-1"),
    (BOB, "user", "bob-user-1"),
)
#: (owner, role, record count) — what a service seeded with
#: CONTROLLED_RECORDS must export per user+role.
CONTROLLED_EXPECTED: tuple[tuple[str, str, int], ...] = (
    (ALICE, "user", 2),
    (ALICE, "builder", 1),
    (BOB, "user", 1),
)


class StubAttributedStore:
    """The controlled stub store: an attributed in-memory record store that
    implements the export/restore store protocol
    (`contract/base/export_restore.py`) — the storage shape a real service's
    own store realizes, stood up for the checker so it never depends on the
    canary (a copied service may delete the canary; the checker stays)."""

    def __init__(self) -> None:
        self._records: list[dict] = []
        self._seq = 0

    def record(self, *, text: str, consent: str, owner: str, role: str) -> dict:
        self._seq += 1
        record = {"seq": self._seq, "owner": owner, "role": role, "text": text, "consent": consent}
        self._records.append(record)
        return record

    # --- the export/restore store protocol

    def records(self, owner: str, role: str, *, after_seq: int = 0) -> list[dict]:
        return [
            dict(r)
            for r in self._records
            if r["owner"] == owner and r["role"] == role and r["seq"] > after_seq
        ]

    def all(self) -> list[dict]:
        return [dict(r) for r in self._records]

    def high_water(self, owner: str, role: str) -> int:
        return max(
            (r["seq"] for r in self._records if r["owner"] == owner and r["role"] == role),
            default=0,
        )

    def apply_full(self, owner: str, role: str, items: list[dict]) -> None:
        self._records = [r for r in self._records if not (r["owner"] == owner and r["role"] == role)]
        for item in items:
            self._append_attributed(item)

    def apply_delta(self, owner: str, role: str, items: list[dict]) -> None:
        for item in items:
            self._append_attributed(item)

    def _append_attributed(self, item: dict) -> None:
        self._records.append(dict(item))
        self._seq = max(self._seq, int(item["seq"]))


def _seed_store(store) -> None:
    """Seed a store with the controlled dataset through its own `record`
    (the service's input shape, not a back door)."""
    for owner, role, text in CONTROLLED_RECORDS:
        store.record(text=text, consent="may_use", owner=owner, role=role)


class StubExportRestoreService:
    """The controlled stub service (ticket #269 AC 2): a base-contract–
    conforming service exposing its per-user export/restore surface,
    standing in for Inference/Document/… Stood up through the repo's single
    stub pattern — `InProcessService` + the single stub-factory's key + the
    base contract's `export_restore_routes` over a `StubAttributedStore` —
    never a hand-rolled mock, never a real service.

    `fresh()` builds another instance with the SAME service identity: the
    restore target of the replay probe (ADR-0021 §7's portability shape —
    the target provides the same service)."""

    def __init__(
        self,
        *,
        store=None,
        service_name: str = "stub-export-restore",
        version: str = "0.0.1",
        routes: list[Route] | None = None,
    ) -> None:
        self.store = store if store is not None else StubAttributedStore()
        self.service_name = service_name
        self.version = version
        # The base factory directly, not `InProcessService`: the template
        # app always mounts the canary, whose own /v1/export would shadow
        # the surface under test. The base factory is the SAME HTTP seam —
        # the full base-contract middleware + routing stack over the
        # in-process ASGI transport — minus the canary, which is exactly
        # the shape a real service (Inference, Document, ...) has.
        self._key = stub_api_key()
        self._app = create_service_app(
            service_name=service_name,
            version=version,
            api_keys=[self._key],
            extra_routes=(
                routes
                if routes is not None
                else export_restore_routes(
                    self.store, service_name=service_name, version=version
                )
            ),
        )
        self._client = TestClient(self._app, raise_server_exceptions=False)

    def client(self):
        """The authorized client over the one HTTP seam (enter as a context
        manager)."""
        self._client.headers["Authorization"] = f"Bearer {self._key}"
        return self._client

    def close(self) -> None:
        self._client.close()

    def fresh(self) -> "StubExportRestoreService":
        """A fresh store, the same service identity — the restore target."""
        return StubExportRestoreService(
            service_name=self.service_name, version=self.version
        )


class WholeDbExportService:
    """The AC-3 negative fixture: a service whose export is WHOLE-DB — it
    serves every user's records at once, ignores the user+role context, and
    applies any restore unconditionally. Exactly the shape ADR-0021 §3
    forbids ("a database's builtin whole-DB backup — that would capture
    every user at once and defeat the per-user encryption and per-user
    restore"). The checker must CATCH it, asserted."""

    def __init__(self, *, service_name: str = "whole-db-service", version: str = "0.0.1") -> None:
        self._stub = StubExportRestoreService(
            service_name=service_name, version=version, routes=self._routes()
        )
        self.store = self._stub.store
        _seed_store(self.store)
        self.service_name = service_name

    def _routes(self) -> list[Route]:
        def _unit(items: list[dict]) -> JSONResponse:
            return JSONResponse(
                build_export_unit(
                    service=self.service_name,
                    version="0.0.1",
                    owner="*",  # the whole-DB tell: no user+role context
                    role="user",
                    kind="full",
                    since=None,
                    through=max((i["seq"] for i in items), default=0),
                    items=items,
                )
            )

        async def export(request) -> JSONResponse:
            # whole-DB: the user+role context is ignored — every user's
            # records come back at once (the forbidden shape).
            return _unit(self.store.all())

        async def restore(request) -> JSONResponse:
            # no shape gate, no chain check: any body is applied.
            body = await request.json()
            self.store.apply_delta("*", "user", body.get("items", []))
            return JSONResponse({"restored": True})

        return [
            Route("/v1/export", export, methods=["GET"]),
            Route("/v1/restore", restore, methods=["POST"]),
        ]

    def client(self):
        return self._stub.client()

    def close(self) -> None:
        self._stub.close()


@dataclass(frozen=True)
class ContractReport:
    """The checker's answer for one service: what it probed and what it
    found.

    `findings` is empty exactly when the service passes the per-user
    export/restore contract — the sweeper prints the report's `render()`
    line per service, so "the contract holds" is a fact read off the
    surface, not a promise.
    """

    findings: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    service: str = ""

    @property
    def green(self) -> bool:
        """The contract holds: no probe found a breach."""
        return not self.findings

    def render(self) -> str:
        """One pass/fail line for the sweeper's per-service output."""
        state = "green" if self.green else f"RED ({len(self.findings)} findings)"
        line = (
            f"export/restore contract {state}: service {self.service!r}, "
            f"{len(self.checks)} probes"
        )
        if self.green:
            return line
        return "\n".join([line, *(f"  - {finding}" for finding in self.findings)])


def _unit_violations(unit: object, *, service: str, owner: str, role: str) -> list[str]:
    """Violations of one export response body against the closed unit shape
    (ADR-0021 §3/§7): the keys, the identity, the context, the chain."""
    problems: list[str] = []
    if not isinstance(unit, dict):
        return [f"the export body is not a JSON object (unit shape, ADR-0021 §3)"]
    unknown = sorted(set(unit) - UNIT_KEYS)
    missing = sorted(UNIT_KEYS - set(unit))
    if unknown or missing:
        problems.append(
            f"the export unit shape drifted (unknown {unknown}, missing {missing}) "
            "— the unit is self-contained (ADR-0021 §3)"
        )
        return problems
    if unit.get("service") != service:
        problems.append(
            f"the export unit names service {unit.get('service')!r}, not {service!r} "
            "— the unit carries the service identity it was exported from (ADR-0021 §7)"
        )
    if unit.get("owner") != owner or unit.get("role") != role:
        problems.append(
            f"the export unit is attributed to {unit.get('owner')!r}/{unit.get('role')!r}, "
            f"not the requested {owner!r}/{role!r} — the export is per user+role (ADR-0021 §3)"
        )
    items = unit.get("items")
    if not isinstance(items, list):
        problems.append("the export unit's `items` is not a list (ADR-0021 §3)")
        return problems
    if unit.get("kind") == "full" and unit.get("since") is not None:
        problems.append("a full export unit carries a non-null `since` (ADR-0021 §5)")
    seqs = [i.get("seq") for i in items if isinstance(i, dict)]
    if any(not isinstance(s, int) for s in seqs):
        problems.append("an exported record has no integer `seq` (the chain anchor, ADR-0021 §5)")
    elif seqs != sorted(seqs):
        problems.append("the exported records are not in seq order (the chain, ADR-0021 §5)")
    return problems


def contract_findings(
    client,
    *,
    target_factory: Callable[[], object],
    expected: tuple[tuple[str, str, int], ...],
    service: str,
) -> tuple[list[str], list[str]]:
    """The contract findings AND the passed probe names for one service's
    export/restore surface, probed over the one HTTP seam with an authorized
    client — findings empty when the contract holds.

    `target_factory` builds a fresh service with the SAME identity (the
    replay probe's restore target); `expected` is the (owner, role, count)
    census of the dataset the service was seeded with."""
    findings: list[str] = []
    passed: list[str] = []

    # (1) the whole-DB export is NOT expressible (ADR-0021 §3).
    r = client.get("/v1/export")
    if r.status_code == 200:
        findings.append(
            "GET /v1/export without the user+role context returns 200 — the "
            "whole-DB export is expressible, the exact shape ADR-0021 §3 "
            "forbids (it captures every user at once)"
        )
    else:
        passed.append("whole-db-export-not-expressible")

    # (2)+(3) per-user isolation + the self-contained unit, per user+role.
    for owner, role, count in expected:
        r = client.get("/v1/export", params={"owner": owner, "role": role})
        if r.status_code != 200:
            findings.append(
                f"GET /v1/export?owner={owner}&role={role} returned "
                f"{r.status_code} — the per-user export surface is missing or "
                "rejects a valid user+role context (ADR-0021 §3)"
            )
            continue
        unit = r.json()
        problems = _unit_violations(unit, service=service, owner=owner, role=role)
        items = unit.get("items") if isinstance(unit.get("items"), list) else []
        foreign = [
            i for i in items
            if isinstance(i, dict) and (i.get("owner"), i.get("role")) != (owner, role)
        ]
        if foreign:
            problems.append(
                f"the export for {owner!r}/{role} contains {len(foreign)} record(s) "
                f"attributed to other identities — per-user isolation breached; a "
                "whole-DB capture defeats per-user encryption and restore (ADR-0021 §3)"
            )
        if len(items) != count:
            problems.append(
                f"the export for {owner!r}/{role} holds {len(items)} record(s), "
                f"expected {count} — the unit is not the user+role's complete data "
                "(self-contained unit, ADR-0021 §3)"
            )
        if problems:
            findings.extend(problems)
        else:
            passed.append(f"per-user-export:{owner}/{role}")

    # (4) the true-incremental delta: since = the high-water seq yields
    # exactly nothing new (ADR-0021 §5).
    if expected:
        owner, role, _ = expected[0]
        full = client.get("/v1/export", params={"owner": owner, "role": role}).json()
        through = full.get("through")
        r = client.get("/v1/export", params={"owner": owner, "role": role, "since": through})
        problems: list[str] = []
        if r.status_code != 200:
            problems.append(
                f"GET /v1/export?since={through} returned {r.status_code} — the "
                "true-incremental delta surface is missing (ADR-0021 §5)"
            )
        else:
            delta = r.json()
            problems += _unit_violations(delta, service=service, owner=owner, role=role)
            if delta.get("kind") != "delta" or delta.get("since") != through:
                problems.append(
                    "the `since` export is not a delta unit chaining from the requested "
                    f"seq (kind {delta.get('kind')!r}, since {delta.get('since')!r}) "
                    "— true-incremental semantics (ADR-0021 §5)"
                )
            if delta.get("items") != []:
                problems.append(
                    "the delta since the high-water seq is not empty — the delta "
                    "re-captures already-backed-up records (ADR-0021 §5)"
                )
        if problems:
            findings.extend(problems)
        else:
            passed.append("true-incremental-delta")

    # (5) the restore shape gate: a malformed unit is rejected, never applied.
    r = client.post("/v1/restore", json={"items": []})
    if r.status_code != 400:
        findings.append(
            f"POST /v1/restore with a malformed unit returned {r.status_code}, not "
            "400 — the restore applies units it cannot verify (ADR-0021 §7)"
        )
    else:
        passed.append("restore-shape-gate")

    # (6) the delta chain is enforced: a delta that does not chain onto the
    # current high-water seq is refused, never silently applied.
    if expected:
        owner, role, _ = expected[0]
        bogus = build_export_unit(
            service=service,
            version="0",
            owner=owner,
            role=role,
            kind="delta",
            since=10**9,
            through=10**9,
            items=[{"seq": 10**9 + 1, "owner": owner, "role": role, "text": "bogus-delta", "consent": "may_use"}],
        )
        r = client.post("/v1/restore", json=bogus)
        if r.status_code != 409:
            findings.append(
                f"POST /v1/restore with a delta chaining from seq 1000000000 returned "
                f"{r.status_code}, not 409 — the incremental chain is not enforced; a "
                "corrupt chain would silently corrupt the restore (ADR-0021 §5)"
            )
        else:
            passed.append("delta-chain-enforced")

    # (7) full + delta replay: the chain the cadence builds — a FULL export
    # taken at an earlier point (the items up to a mid seq), then the
    # true-incremental delta above it (fetched live from the surface with
    # `since` = that point) — restored onto a fresh target. The target's
    # state equals the source's (ADR-0021 §3/§5/§7).
    if expected:
        owner, role, count = expected[0]
        full = client.get("/v1/export", params={"owner": owner, "role": role}).json()
        half = count // 2
        mid_seq = full["items"][half - 1]["seq"] if half else 0
        full_at_mid = {**full, "through": mid_seq, "items": full["items"][:half]}
        delta = client.get(
            "/v1/export", params={"owner": owner, "role": role, "since": mid_seq}
        ).json()
        target = target_factory()
        try:
            with target.client() as tc:
                r_full = tc.post("/v1/restore", json=full_at_mid)
                r_delta = tc.post("/v1/restore", json=delta)
                if r_full.status_code != 200 or r_delta.status_code != 200:
                    findings.append(
                        f"the target rejected the full+delta chain "
                        f"({r_full.status_code}/{r_delta.status_code}) — full + delta "
                        "restore must apply (ADR-0021 §5/§7)"
                    )
                else:
                    replayed = tc.get(
                        "/v1/export", params={"owner": owner, "role": role}
                    ).json()
                    if replayed.get("items") != full["items"]:
                        findings.append(
                            f"full + delta replay on the target does not reproduce the "
                            f"source's {owner!r}/{role} state — the chain is not "
                            "self-contained (ADR-0021 §3)"
                        )
            passed.append("full-plus-delta-replay")
        finally:
            target.close()

    # (8) determinism: the same export answers identically twice (no clock,
    # no randomness in the contract machinery).
    if expected:
        owner, role, _ = expected[0]
        first = client.get("/v1/export", params={"owner": owner, "role": role}).json()
        second = client.get("/v1/export", params={"owner": owner, "role": role}).json()
        if first != second:
            findings.append(
                "the same export answered differently twice — the contract surface "
                "is not deterministic (no clock/randomness allowed)"
            )
        else:
            passed.append("determinism")

    return findings, passed


def check_export_restore(
    client,
    *,
    target_factory: Callable[[], object],
    expected: tuple[tuple[str, str, int], ...] = CONTROLLED_EXPECTED,
    service: str,
) -> ContractReport:
    """Probe one service's export/restore surface (the sweeper-consumable
    entry point, #269 AC 4/5).

    `client` is an AUTHORIZED client over the one HTTP seam (the sweeper
    boots each real service and passes its client); `target_factory` builds
    a fresh same-identity service for the replay probe; `expected` is the
    census of the dataset the service was seeded with. Contract drift is
    REPORTED as findings, never raised — the sweeper prints what is wrong
    rather than crashing on it."""
    findings, passed = contract_findings(
        client, target_factory=target_factory, expected=expected, service=service
    )
    return ContractReport(findings=tuple(findings), checks=tuple(passed), service=service)
