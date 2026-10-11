"""Export/restore compliance-checker tests (ticket #269 AC 2/3/4/5).

The compliance checker (`tests/support/export_restore_check.py` — a TEST-side
checker; never the AI-agent harness) stands up a **controlled stub service**
(a base-contract–conforming service exposing its per-user export/restore
surface, standing in for Inference/Document/…) and probes it over the one
HTTP seam: the whole-DB export is not expressible, per-user isolation holds,
the unit is self-contained, the delta chains, the restore gates shapes and
chains, full + delta replay reproduces the state, and the surface is
deterministic.

The third acceptance criterion is the **required negative test**: a service
whose export is whole-DB (captures every user at once) must be CAUGHT by the
checker, with the specific finding — the breach is REPORTED, never raised,
so the sweeper prints what is wrong rather than crashing on it.

The fourth criterion is asserted against the canary (#46): the shipped
template app — the shape every copied service inherits — passes the same
checker entry point.
"""

from __future__ import annotations

from pathlib import Path

from tests.support.export_restore_check import (
    ALICE,
    BOB,
    CONTROLLED_EXPECTED,
    CONTROLLED_RECORDS,
    ContractReport,
    StubExportRestoreService,
    WholeDbExportService,
    check_export_restore,
    contract_findings,
)
from tests.support.test_server import InProcessService

# --------------------------------------------------- the controlled stub
# --------------------------------------------------- service passes (AC 2)


def _check_stub() -> ContractReport:
    stub = StubExportRestoreService()
    for owner, role, text in CONTROLLED_RECORDS:
        stub.store.record(text=text, consent="may_use", owner=owner, role=role)
    try:
        with stub.client() as client:
            return check_export_restore(
                client,
                target_factory=stub.fresh,
                expected=CONTROLLED_EXPECTED,
                service=stub.service_name,
            )
    finally:
        stub.close()


def test_the_controlled_stub_service_passes_the_contract():
    """#269 AC 2: the checker stands up a controlled stub service and
    asserts it passes the per-user-export + true-incremental contract —
    every probe green, deterministically."""
    report = _check_stub()
    assert report.green is True, report.findings
    assert report.render().startswith("export/restore contract green")
    # every probe ran: whole-DB not expressible, one per-user export per
    # expected identity, the delta, the shape gate, the chain, the replay,
    # determinism.
    assert len(report.checks) == 3 + 6  # 3 per-user exports + 6 shared probes


def test_the_checker_probes_are_deterministic():
    """AC 2's determinism clause: two runs of the whole sweep over two
    identically-seeded stubs agree — no clock, no network, no randomness."""
    first, second = _check_stub(), _check_stub()
    assert first.findings == second.findings == ()
    assert first.checks == second.checks


# ------------------------------------------- the required negative (AC 3)


def test_a_whole_db_only_export_is_caught_by_the_checker():
    """#269 AC 3 (required): a service failing the contract — a whole-DB
    export that captures every user at once — is CAUGHT, with the specific
    finding. The breach is reported, never raised (the sweeper prints it)."""
    bad = WholeDbExportService()
    try:
        with bad.client() as client:
            report = check_export_restore(
                client,
                target_factory=lambda: WholeDbExportService(),
                expected=CONTROLLED_EXPECTED,
                service=bad.service_name,
            )
    finally:
        bad.close()
    assert report.green is False
    (finding,) = [f for f in report.findings if "whole-DB export is expressible" in f]
    assert "ADR-0021 §3" in finding
    # the isolation breach fires too: the whole-DB unit carries foreign
    # records in every per-user export
    assert any("per-user isolation" in f for f in report.findings)
    assert "RED" in report.render()


def test_the_whole_db_negative_fixture_is_the_forbidden_shape():
    """The fixture itself is the ADR's forbidden shape: an export with no
    user+role context answers 200 with EVERY user's records at once — the
    checker's finding is about a real breach, not a fixture artifact."""
    bad = WholeDbExportService()
    try:
        with bad.client() as client:
            r = client.get("/v1/export")
            assert r.status_code == 200
            owners = {i["owner"] for i in r.json()["items"]}
            assert owners == {ALICE, BOB}  # every user captured at once
    finally:
        bad.close()


# --------------------------------------- the canary passes the checker
# --------------------------------------- (AC 4: asserted against #46)


def test_the_canary_passes_the_export_restore_checker():
    """#269 AC 4: the checker entry point is asserted against the canary —
    the shipped template app (the shape every copied service inherits from
    #47 on) passes the per-user export/restore contract with no fixture
    meddling."""
    from contract.declaration import load_service_toml

    declaration = load_service_toml(Path(__file__).resolve().parents[2] / "service.toml")

    class _CanaryTarget:
        """The checker's target seam: `client()` + `close()`. The canary's
        InProcessService answers it through `authorized()`."""

        def __init__(self) -> None:
            self._svc = InProcessService(api_keys=["sk-target"])

        def client(self):
            return self._svc.authorized()

        def close(self) -> None:
            self._svc.close()

    svc = InProcessService(api_keys=["sk-correct"])
    try:
        with svc.authorized() as client:
            for owner, role, text in CONTROLLED_RECORDS:
                client.post("/v1/echo", json={"text": text, "owner": owner, "role": role})
            report = check_export_restore(
                client,
                target_factory=_CanaryTarget,
                expected=CONTROLLED_EXPECTED,
                service=declaration.name,
            )
    finally:
        svc.close()
    assert report.green is True, report.findings


def test_the_checker_entry_point_is_consumable_by_the_sweeper():
    """#269 AC 4/5: an explicit, documented entry point the sweeper
    (#68/#85) and the backup orchestration tickets (#270–#272) call — it
    takes an authorized client over the one HTTP seam and returns a report
    with `green` + `render()`, never raising on contract drift. #85 does not
    exist yet, so the proof is this ticket's tests — against the canary and
    the negative fixture."""
    report = _check_stub()
    assert isinstance(report, ContractReport)
    assert report.green is True
    lines = report.render().splitlines()
    assert lines == [
        f"export/restore contract green: service 'stub-export-restore', {len(report.checks)} probes"
    ]
    assert not any(line.startswith("  - ") for line in lines)


def test_contract_drift_is_reported_never_raised():
    """The rejection split for a contract surface: shape errors at the
    boundary are the SURFACE's 400/409 (asserted in test_export_restore.py);
    contract drift at the CHECKER is a finding, never an exception — the
    sweeper prints what is wrong instead of crashing on it."""
    bad = WholeDbExportService()
    try:
        with bad.client() as client:
            findings, passed = contract_findings(
                client,
                target_factory=lambda: WholeDbExportService(),
                expected=CONTROLLED_EXPECTED,
                service=bad.service_name,
            )
    finally:
        bad.close()
    assert findings  # the sweep REPORTS
    assert "whole-db-export-not-expressible" not in passed  # ... and names what passed
