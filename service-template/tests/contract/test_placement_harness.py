"""Control-placement invariant harness tests (ticket #275 AC 2/3/4).

The harness (`tests/support/placement.py`) stands up a **stub
owning-capability surface** per home and asserts the placement invariants
against the map: every §1 frame backed, every control homed, no control
re-implemented in two places, every named home with a surface.

The third acceptance criterion is the **required negative test**: a map with a
homeless control and a map with a double-homed control must each be CAUGHT,
with the specific finding. The stubs are the repo's single stub-factory
(`StubCollaborator`), exercised over the one HTTP seam — never a mock of
internals, never a real service, never a second mocking framework (#275's
scope fence: the stub harness / host-OS / LAN surfaces are #276's).
"""

from __future__ import annotations

import pytest

from contract.placement import (
    DEFAULT_MAP_PATH,
    HOMES,
    PlacementMapError,
    load_placement_map,
)

from tests.support.placement import (
    GUARDRAIL_SECTION,
    HOME_STUBS,
    PlacementReport,
    build_home_stubs,
    placement_findings,
    sweep_placement,
)
from tests.support.stubs import StubCollaborator
from tests.support.test_server import InProcessService

from tests.support.placement_fixtures import (
    CONTROL_ONE,
    CONTROL_TWO,
    FRAME_ALPHA,
    FRAME_BETA,
    good_map,
    write_map,
)

# --------------------------------------------------- the invariants, green


def test_a_good_map_is_green(tmp_path):
    placement_map = load_placement_map(good_map(tmp_path))
    assert placement_findings(placement_map) == []
    report = sweep_placement(good_map(tmp_path))
    assert report.green is True
    assert report.findings == ()
    assert report.frames == ("alpha", "beta")
    assert report.controls == ("control-one", "control-two")
    assert report.homes == ("connectors", "core")
    assert report.render().startswith("placement green")


def test_a_frame_with_no_control_backing_it_is_caught(tmp_path):
    """Invariant (1): every §1 threat frame resolves to ≥1 named control — an
    unbacked frame is an unbacked surface."""
    # `beta` is declared but no control backs it
    path = write_map(tmp_path, FRAME_ALPHA + FRAME_BETA + CONTROL_ONE)
    report = sweep_placement(path)
    assert report.green is False
    assert any("`beta`" in f and "no control" in f for f in report.findings)
    assert "RED" in report.render()


# -------------------------------- the required negatives (AC 3): homeless /
# -------------------------------- double-homed maps are caught, specifically


def test_a_HOMELESS_control_is_caught(tmp_path):
    """#275 AC 3 (required): a map with a homeless control is caught by the
    harness — a control the model names but never places."""
    homeless = CONTROL_TWO.replace('home = "connectors"\n', "")
    report = sweep_placement(write_map(tmp_path, FRAME_ALPHA + FRAME_BETA + CONTROL_ONE + homeless))
    assert report.green is False
    assert any(
        "control-two" in finding and "homeless" in finding for finding in report.findings
    ), report.findings
    # ... and the frame it backed is unaffected: only the placement finding fires
    assert not any("`beta`" in f for f in report.findings)


def test_a_DOUBLE_HOMED_control_is_caught(tmp_path):
    """#275 AC 3 (required): a map that re-implements a control in two places
    is caught. The drift's shape — the model names ONE control, and the map
    lands it in two places."""
    twin = CONTROL_ONE  # the same control, declared a second time
    report = sweep_placement(write_map(tmp_path, FRAME_ALPHA + CONTROL_ONE + twin))
    assert report.green is False
    (finding,) = [f for f in report.findings if "re-implemented" in f]
    assert "`control-one`" in finding and "landed in 2 places" in finding


def test_section_8s_guardrail_layer_re_implemented_is_caught(tmp_path):
    """The same invariant in ADR-0017 §8's own terms: the guardrail layer is
    re-implemented when one of §8's sites hosts two of its controls."""
    second_media = """\
[[controls]]
id = "guardrail-media-transforms-copy"
adr = "ADR-0017 §8 (builtin transforms, declared twice)"
home = "media-transformations"
seam = "a second builtin transform hook"
"""
    report = sweep_placement(
        write_map(
            tmp_path,
            FRAME_ALPHA
            + CONTROL_ONE  # backs alpha, homes core — unrelated
            + """\
[[controls]]
id = "guardrail-media-transforms"
adr = "ADR-0017 §8 (builtin transforms)"
home = "media-transformations"
seam = "the builtin transforms"
"""
            + second_media,
        )
    )
    assert report.green is False
    (finding,) = [f for f in report.findings if "guardrail" in f]
    assert "`media-transformations`" in finding
    assert "guardrail-media-transforms" in finding
    assert "re-implemented in" in finding


def test_a_control_whose_home_has_no_surface_is_caught(tmp_path):
    """Invariant (4): every home a control names must have a stood-up stub
    owning-capability surface — so the map and the collaborator set can never
    drift apart silently."""
    placement_map = load_placement_map(good_map(tmp_path))
    report = PlacementReport(
        findings=tuple(
            placement_findings(placement_map, surfaces={"core": build_home_stubs()["core"]})
        ),
    )
    assert report.green is False
    assert any("connectors" in f and "no stub" in f for f in report.findings)


def test_the_guardrail_site_grouping_reads_named_sections_not_substrings():
    """§8 membership is READ from the parsed citation (`Control.sections`),
    never a substring probe of the prose: a citation naming a different ADR's
    §8, or ADR-0017 §80, must not be mistaken for the guardrail section. The
    regex is anchored on `ADR-0017 §N`, so a co-cited ADR-0004 §8 is not ours
    and `§80` is its own (unmatched) token."""
    from contract.placement import Control, adr_0017_sections

    assert adr_0017_sections("ADR-0017 §8") == ("8",)
    # only sections WRITTEN against ADR-0017 count: §7.5 shares §7's number
    # only when re-prefixed, so a run like §7.1/§7.5 yields one §7
    assert adr_0017_sections("ADR-0017 §7.1/§7.5; ADR-0030") == ("7",)
    assert adr_0017_sections("ADR-0017 §7; ADR-0017 §7") == ("7", "7")
    # a DIFFERENT ADR's §8 is not ADR-0017's section — the co-citation trap
    assert adr_0017_sections("ADR-0017 §5; ADR-0004 §8") == ("5",)
    assert adr_0017_sections("ADR-0004 §8") == ()
    # a different section NUMBER is not §8: `§80` parses as its own token, so
    # it never matches the guardrail section ("8" != "80")
    assert adr_0017_sections("ADR-0017 §80") == ("80",)
    assert GUARDRAIL_SECTION not in adr_0017_sections("ADR-0017 §80")

    # and it is a property of the parsed entry, on both frames and controls
    control = Control(id="x", adr="ADR-0017 §8", home="inference", seam="s")
    assert control.sections == ("8",)


def test_the_sweep_is_consumable_by_the_sweeper(tmp_path):
    """#275 AC 4: an explicit, documented entry point the sweeper (#68/#85)
    can call — it loads the service's OWN vendored map (no arguments), stands
    the stub surfaces up, and returns a report it can render pass/fail. #85
    does not exist yet, so the proof is this ticket's test against the
    template/canary."""
    report = sweep_placement()  # the shipped map, discovered by location
    assert isinstance(report, PlacementReport)
    assert report.path.name == "placement_map.toml"
    assert report.green is True, report.findings
    lines = report.render().splitlines()
    assert lines == ["placement green: 5 frames, 16 controls, 7 homes"]
    assert not any(line.startswith("  - ") for line in lines)


def test_the_shipped_map_passes_the_harness_end_to_end(tmp_path):
    """The template's own map — the model a copied service inherits — is
    green with no fixture meddling (the acceptance shared with the canary).

    Discovered through the loader's own location constant, never a literal
    `src/<service>/` path: the copy-to-start ritual renames that directory,
    and a hard-coded placeholder would make a copied service's suite red.
    """
    report = sweep_placement(DEFAULT_MAP_PATH)
    assert report.green is True, report.findings
    assert report.path == DEFAULT_MAP_PATH


# ------------------------------------------- the stub owning-capability set


def test_every_home_the_map_may_name_has_a_stub_surface():
    """The home vocabulary and the stub set are one-to-one: a home added to
    `HOMES` without a surface would make every control homed there a finding,
    so the two are asserted together."""
    assert set(HOME_STUBS) == set(HOMES)
    stubs = build_home_stubs()
    assert set(stubs) == set(HOMES)
    assert all(isinstance(surface, StubCollaborator) for surface in stubs.values())


def test_each_stub_surface_serves_the_base_contract_over_the_http_seam():
    """The stub owning-capability surfaces are asserted at their CONTRACT
    surfaces — the one HTTP seam — never against internals: each answers over
    its `/v1/...` path with its home/seam body, and the base contract holds on
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
    clock, no randomness (spec #66's Testing Decisions)."""
    first, second = build_home_stubs(), build_home_stubs()
    assert [s.path for s in first.values()] == [s.path for s in second.values()]
    assert [s.body for s in first.values()] == [s.body for s in second.values()]


@pytest.mark.parametrize("home", sorted(HOME_STUBS))
def test_each_stub_records_the_registry_name_where_the_adrs_name_one(home):
    """Where an ADR names the registry entry a home's surface carries, the
    stub records it (ADR-0008 §8) as DATA — never probed, never invented for a
    home the ADRs keep out of the registry (the installer layer, workspaces,
    and the model capability are deliberately entry-less)."""
    spec = HOME_STUBS[home]
    named = {"core": "core.secrets", "connectors": "connectors.audit"}
    if home in named:
        assert spec.get("stable_name") == named[home]
    else:
        assert "stable_name" not in spec


def test_a_malformed_map_still_raises_rather_than_reporting(tmp_path):
    """A load failure is not a finding: a malformed map is not a model, so the
    sweep raises instead of reporting a green-looking report."""
    with pytest.raises(PlacementMapError):
        sweep_placement(write_map(tmp_path, "[[frames]]\nid = 'Alpha One'\n"))
