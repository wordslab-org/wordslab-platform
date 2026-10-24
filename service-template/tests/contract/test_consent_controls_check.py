"""Consent-controls compliance-checker tests (ticket #285 AC 2/3/4).

The compliance checker (`tests/support/consent_controls_check.py` — a
TEST-side checker; never the AI-agent harness) stands up a **stub
owning-home surface** per home and asserts the placement invariants against
the map: every declared ADR-0026 section places a control, every control is
homed, no control re-implemented in two places, every named home with a
surface, and every consent-bearing home carrying the flag + the
never-bypassable exclusion.

The third acceptance criterion is the **required negative test**: a map for
a consent-bearing surface WITHOUT the consent flag, or WITHOUT the
never-bypassable exclusion, must each be CAUGHT, with the specific finding —
and the map must still LOAD (the loader-vs-harness split: placement drift is
reported, never raised). The stubs are the repo's single stub-factory
(`StubCollaborator`), exercised over the one HTTP seam — never a mock of
internals, never a real service, never a second mocking framework.
"""

from __future__ import annotations

import pytest

from contract.consent_controls import (
    DEFAULT_MAP_PATH,
    HOMES,
    ConsentControlsMapError,
    load_consent_controls_map,
)

from tests.support.consent_controls_check import (
    CONSENT_BEARING_REQUIREMENTS,
    HOME_STUBS,
    ComplianceReport,
    build_home_stubs,
    check_consent_controls,
    compliance_findings,
)
from tests.support.consent_controls_fixtures import (
    CONTROL_ANONYMIZE,
    CONTROL_FLAG,
    CONTROL_GATE,
    SECTION_ONE,
    SECTION_TWO,
    good_map,
    write_map,
)
from tests.support.stubs import StubCollaborator
from tests.support.test_server import InProcessService

# --------------------------------------------------- the invariants, green


def test_a_good_map_is_green(tmp_path):
    controls_map = load_consent_controls_map(good_map(tmp_path))
    assert compliance_findings(controls_map) == []
    report = check_consent_controls(good_map(tmp_path))
    assert report.green is True
    assert report.findings == ()
    assert report.sections == ("1", "2")
    assert report.controls == (
        "consent-flag",
        "private-secret-exclusion",
        "core-anonymize-pass",
    )
    assert report.homes == ("core", "template")
    assert report.render().startswith("consent placement green")


def test_a_section_with_no_control_is_caught(tmp_path):
    """Invariant (1): every declared ADR-0026 section places >=1 control — a
    control-carrying section with nothing under it is an unplaced part of
    the model."""
    # section 2 is declared but no control cites it (CONTROL_GATE would
    # back it — the fixture deliberately omits it)
    path = write_map(tmp_path, SECTION_ONE + SECTION_TWO + CONTROL_FLAG)
    report = check_consent_controls(path)
    assert report.green is False
    assert any("`2`" in f and "places no control" in f for f in report.findings)
    assert "RED" in report.render()


# -------------------------------- the required negatives (AC 3): a consent-
# -------------------------------- bearing surface missing the flag / the
# -------------------------------- exclusion is flagged, specifically


def test_a_surface_without_the_consent_flag_is_flagged(tmp_path):
    """#285 AC 3 (required): a service/template that ships a consent-bearing
    surface WITHOUT the consent flag is flagged — and the map still LOADS
    (the drift is reported, never raised: assert both halves of the split)."""
    no_flag = CONTROL_GATE  # the template home keeps the exclusion, loses the flag
    path = write_map(tmp_path, SECTION_ONE + SECTION_TWO + no_flag + CONTROL_ANONYMIZE)
    controls_map = load_consent_controls_map(path)  # ... the map LOADS
    report = check_consent_controls(path)  # ... the sweep REPORTS
    assert report.green is False
    (finding,) = [f for f in report.findings if "consent-flag" in f]
    assert "`template`" in finding and "does not place" in finding
    # the exclusion itself is placed — only the missing flag fires
    assert not any("private-secret-exclusion" in f for f in report.findings)


def test_a_surface_without_the_never_bypassable_exclusion_is_flagged(tmp_path):
    """#285 AC 3 (required), the other half: WITHOUT the never-bypassable
    private/secret exclusion the surface is flagged."""
    no_exclusion = CONTROL_FLAG  # the template home keeps the flag, loses the gate
    report = check_consent_controls(
        write_map(tmp_path, SECTION_ONE + SECTION_TWO + no_exclusion + CONTROL_ANONYMIZE)
    )
    assert report.green is False
    (finding,) = [f for f in report.findings if "private-secret-exclusion" in f]
    assert "`template`" in finding and "does not place" in finding
    assert "never-bypassable" in finding or "ADR-0026" in finding


def test_a_HOMELESS_control_is_caught(tmp_path):
    """AC 2: a map with a homeless control is caught by the checker — a
    control the model names but never places."""
    homeless = CONTROL_GATE.replace('home = "template"\n', "")
    report = check_consent_controls(
        write_map(tmp_path, SECTION_ONE + SECTION_TWO + CONTROL_FLAG + homeless + CONTROL_ANONYMIZE)
    )
    assert report.green is False
    assert any(
        "private-secret-exclusion" in finding and "homeless" in finding
        for finding in report.findings
    ), report.findings
    # the required-pair check fires too (the home no longer places it) —
    # both are true statements about the same drift, and neither hides the other
    assert any("does not place" in f for f in report.findings)


def test_a_DOUBLE_HOMED_control_is_caught(tmp_path):
    """AC 2: a map that re-implements a control in two places is caught. The
    drift's shape — the model names ONE control, and the map lands it in two
    places."""
    twin = CONTROL_FLAG.replace('home = "template"', 'home = "core"')
    report = check_consent_controls(
        write_map(tmp_path, SECTION_ONE + SECTION_TWO + CONTROL_FLAG + twin + CONTROL_GATE + CONTROL_ANONYMIZE)
    )
    assert report.green is False
    (finding,) = [f for f in report.findings if "re-implemented" in f]
    assert "`consent-flag`" in finding and "landed in 2 places" in finding


def test_two_distinct_controls_sharing_one_home_is_legal():
    """The template legitimately hosts several DISTINCT controls (flag,
    exclusion, extraction surface, data-shape declaration) — the invariant
    checks a control's identity, never a count per home. The shipped map
    proves it: six controls homed `template`, still green."""
    controls_map = load_consent_controls_map(DEFAULT_MAP_PATH)
    template_controls = [c.id for c in controls_map.controls if c.home == "template"]
    assert len(template_controls) == 6, template_controls
    report = check_consent_controls(DEFAULT_MAP_PATH)
    assert report.green is True, report.findings


def test_a_control_whose_home_has_no_surface_is_caught(tmp_path):
    """Invariant (4): every home a control names must have a stood-up stub
    owning-home surface — so the map and the collaborator set can never
    drift apart silently."""
    controls_map = load_consent_controls_map(good_map(tmp_path))
    report = ComplianceReport(
        findings=tuple(
            compliance_findings(controls_map, surfaces={"template": build_home_stubs()["template"]})
        ),
    )
    assert report.green is False
    assert any("core" in f and "no stub" in f for f in report.findings)


# ------------------------------------------- the stub owning-home set


def test_every_home_the_map_may_name_has_a_stub_surface():
    """The home vocabulary and the stub set are one-to-one: a home added to
    `HOMES` without a surface would make every control homed there a
    finding, so the two are asserted together."""
    assert set(HOME_STUBS) == set(HOMES)
    stubs = build_home_stubs()
    assert set(stubs) == set(HOMES)
    assert all(isinstance(surface, StubCollaborator) for surface in stubs.values())


def test_each_stub_surface_serves_the_base_contract_over_the_http_seam():
    """The stub owning-home surfaces are asserted at their CONTRACT surfaces
    — the one HTTP seam — never against internals: each answers over its
    `/v1/...` path with its home/seam body, and the base contract holds on
    every response."""
    from tests.contract.runner import failures

    stubs = build_home_stubs()
    svc = InProcessService(
        api_keys=["sk-correct"], extra_routes=[s.route for s in stubs.values()]
    )
    try:
        with svc.authorized() as client:
            for home, stub in stubs.items():
                response = client.get(stub.path)
                assert response.status_code == 200, home
                assert response.json() == {
                    "home": home,
                    "seam": HOME_STUBS[home]["seam"],
                    "surface": "stub-ok",
                }
                assert failures(response) == []
                assert stub.requests[-1]["path"] == stub.path
    finally:
        svc.close()


def test_the_stub_surfaces_are_deterministic_and_offline():
    """Determinism: two builds answer identically, in order — no network, no
    clock, no randomness (spec #67's testing rule, as #66's for security)."""
    first, second = build_home_stubs(), build_home_stubs()
    assert [s.path for s in first.values()] == [s.path for s in second.values()]
    assert [s.body for s in first.values()] == [s.body for s in second.values()]


@pytest.mark.parametrize("home", sorted(HOME_STUBS))
def test_each_stub_records_the_registry_name_where_the_adrs_name_one(home):
    """Where an ADR names the registry entry a home's surface carries, the
    stub records it (ADR-0008 §8) as DATA — never probed, never invented for
    a home the ADRs keep out of the registry (the template's own contract
    surface, and the assistant container the core allocates)."""
    spec = HOME_STUBS[home]
    named = {"core": "core.datasets"}  # ADR-0003 names the datasets capability
    if home in named:
        assert spec.get("stable_name") == named[home]
    else:
        assert "stable_name" not in spec


# --------------------------------------- the sweeper entry point (AC 4)


def test_the_checker_is_consumable_by_the_sweeper():
    """#285 AC 4: an explicit, documented entry point the sweeper (#68/#85)
    can call — it loads the service's OWN vendored map (no arguments),
    stands the stub surfaces up, and returns a report it can render
    pass/fail. #85 does not exist yet, so the proof is this ticket's test
    against the template/canary. The check consumes the foundation
    template's contract-checker seam (#46/#68): the same
    loader-next-to-contract + checker-in-tests/support shape #275 shipped."""
    report = check_consent_controls()  # the shipped map, discovered by location
    assert isinstance(report, ComplianceReport)
    assert report.path.name == "consent_controls_map.toml"
    assert report.green is True, report.findings
    lines = report.render().splitlines()
    assert lines == ["consent placement green: 4 sections, 12 controls, 3 homes"]
    assert not any(line.startswith("  - ") for line in lines)


def test_the_shipped_map_passes_the_checker_end_to_end():
    """The template's own map — the model a copied service inherits — is
    green with no fixture meddling (the acceptance shared with the canary).

    Discovered through the loader's own location constant, never a literal
    `src/_service_/` path: the copy-to-start ritual renames that directory,
    and a hard-coded placeholder would make a copied service's suite red.
    """
    report = check_consent_controls(DEFAULT_MAP_PATH)
    assert report.green is True, report.findings
    assert report.path == DEFAULT_MAP_PATH


def test_the_required_pair_is_stated_as_data_not_inferred():
    """The consent-bearing-home requirement is explicit data keyed on the
    map's control ids (the map is the key vocabulary) — never a heuristic
    that guesses which homes carry consent surfaces."""
    assert CONSENT_BEARING_REQUIREMENTS == {
        "template": ("consent-flag", "private-secret-exclusion"),
    }
    shipped_ids = {c.id for c in load_consent_controls_map().controls}
    for required in CONSENT_BEARING_REQUIREMENTS.values():
        assert set(required) <= shipped_ids


def test_a_malformed_map_still_raises_rather_than_reporting(tmp_path):
    """A load failure is not a finding: a malformed map is not a model, so
    the sweep raises instead of reporting a green-looking report."""
    with pytest.raises(ConsentControlsMapError):
        check_consent_controls(write_map(tmp_path, "[[sections]]\nid = 'One One'\n"))
