"""Consent-controls-map loader tests (ticket #285 AC 1).

The loader (`contract/consent_controls.py`) is the seam: `load_consent_controls_map()`
returns the parsed map or raises `ConsentControlsMapError` naming the
offending entry (the #74/#75/#275 precedent — closed shape, typos fail
loudly at load, validated from inline TOML written via `tmp_path`; a
data-surface ticket has no HTTP seam).

Every loud-rejection rule is fed its offending entry here — the loader
docstring's coverage claim is a contract. Placement drift (a homeless
control, a control landed twice) is NOT rejected here: the compliance
checker reports it (#285's AC wording — the map still LOADS, the sweep
REPORTS).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contract.consent_controls import (
    CONTROL_KEYS,
    DEFAULT_MAP_PATH,
    HOMES,
    SECTION_KEYS,
    ConsentControlsMapError,
    Control,
    Section,
    adr_0026_sections,
    load_consent_controls_map,
)

from tests.support.consent_controls_fixtures import (
    CONTROL_ANONYMIZE,
    CONTROL_FLAG,
    CONTROL_GATE,
    SECTION_ONE,
    SECTION_TWO,
    good_map,
    map_document,
    write_map,
)

# ------------------------------------------------------------- the happy path


def test_a_good_map_loads_with_its_sections_and_placed_controls(tmp_path):
    controls_map = load_consent_controls_map(good_map(tmp_path))
    assert [s.id for s in controls_map.sections] == ["1", "2"]
    assert [c.id for c in controls_map.controls] == [
        "consent-flag",
        "private-secret-exclusion",
        "core-anonymize-pass",
    ]
    assert controls_map.homes_used == ("core", "template")
    assert controls_map.cited_sections == ("1", "2")
    # the section->control direction is DERIVED from the parsed citations
    assert [c.id for c in controls_map.controls_for("1")] == ["consent-flag"]
    assert controls_map.control("private-secret-exclusion").home == "template"
    assert controls_map.section("2").adr.startswith("ADR-0026 §2")


def test_the_shipped_map_is_the_consent_model_as_data():
    """AC 1: the shipped map names each ADR-0026 consent control and pins it
    to its home — discovered through the loader's own location constant
    (rename-safety), never a literal `src/<service>/` path."""
    controls_map = load_consent_controls_map()
    assert controls_map.path == DEFAULT_MAP_PATH
    assert controls_map.homes_used == ("chat-and-agents", "core", "template")
    assert controls_map.cited_sections == ("1", "2", "3", "6")
    assert {c.id for c in controls_map.controls} == {
        # AC 1's named set, each pinned to its home
        "consent-flag",
        "private-secret-exclusion",
        "dataset-extraction-surface",
        "trace-data-shape-declaration",
        "consent-gate-filter",
        "core-anonymize-pass",
        "dataset-provenance",
        "non-user-log-centralization",
        "sphere-gate-at-callable-surface",
        "assistant-container-shape",
    }
    homes = {c.id: c.home for c in controls_map.controls}
    assert homes["consent-flag"] == "template"
    assert homes["private-secret-exclusion"] == "template"
    assert homes["dataset-extraction-surface"] == "template"
    assert homes["trace-data-shape-declaration"] == "template"
    assert homes["consent-gate-filter"] == "core"
    assert homes["core-anonymize-pass"] == "core"
    assert homes["dataset-provenance"] == "core"
    assert homes["non-user-log-centralization"] == "core"
    assert homes["sphere-gate-at-callable-surface"] == "chat-and-agents"
    assert homes["assistant-container-shape"] == "chat-and-agents"


# ------------------------------------------- the citation parse (one parser)


def test_adr_0026_sections_reads_named_sections_not_substrings():
    """Membership is READ from the citation via ONE anchored parser: a
    co-cited different ADR's `§N` is not ours, and `§60` is its own token —
    never a substring hit on `§6`."""
    assert adr_0026_sections("ADR-0026 §1") == ("1",)
    assert adr_0026_sections("ADR-0026 §7.1/§7.5; ADR-0026") == ("7",)
    # a DIFFERENT ADR's section is not ADR-0026's — the co-citation trap
    assert adr_0026_sections("ADR-0026 §2; ADR-0024 §2") == ("2",)
    assert adr_0026_sections("ADR-0024 §2") == ()
    # a different section NUMBER is not §6: `§60` parses as its own token
    assert adr_0026_sections("ADR-0026 §60") == ("60",)
    # an evolution note may accompany the citation, never replace it
    assert adr_0026_sections(
        "ADR-0026 §2; ADR-0003 (the core `datasets` capability)"
    ) == ("2",)


def test_sections_are_a_property_of_the_parsed_entries():
    section = Section(id="2", adr="ADR-0026 §2 (the two passes)")
    assert section.sections == ("2",)
    control = Control(
        id="x", adr="ADR-0026 §2; ADR-0003", home="core", seam="the datasets capability"
    )
    assert control.sections == ("2",)


# ------------------------------------------------- closed-shape rejections


def test_an_unknown_top_level_key_is_rejected(tmp_path):
    doc = "frames = []\n\n" + map_document()
    with pytest.raises(ConsentControlsMapError, match="unknown top-level key"):
        load_consent_controls_map(write_map(tmp_path, doc))


def test_an_unknown_control_key_is_rejected(tmp_path):
    drifted = CONTROL_FLAG.replace(
        'seam = "the per-input consent flag on every user input surface"',
        'seam = "the per-input consent flag"\nbacks = ["1"]',
    )
    with pytest.raises(ConsentControlsMapError, match="unknown key"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_TWO + drifted)
        )


def test_an_unknown_section_key_is_rejected(tmp_path):
    drifted = SECTION_ONE.replace('adr = "ADR-0026 §1', 'backs = []\nadr = "ADR-0026 §1')
    with pytest.raises(ConsentControlsMapError, match="unknown key"):
        load_consent_controls_map(
            write_map(tmp_path, drifted + SECTION_TWO + CONTROL_FLAG + CONTROL_GATE)
        )


def test_a_non_string_home_is_rejected(tmp_path):
    typo = CONTROL_GATE.replace('home = "template"', "home = 3")
    with pytest.raises(ConsentControlsMapError, match="must be a string"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_TWO + CONTROL_FLAG + typo)
        )


def test_a_control_citing_no_ADR_0026_section_is_rejected(tmp_path):
    """A citation that names the ADR but no section would silently drop the
    control out of the section sweep."""
    bare = CONTROL_FLAG.replace('adr = "ADR-0026 §1', 'adr = "ADR-0026')
    with pytest.raises(ConsentControlsMapError, match="cites no ADR-0026 section"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_TWO + bare + CONTROL_GATE)
        )


def test_a_scalar_sections_array_is_rejected(tmp_path):
    with pytest.raises(ConsentControlsMapError, match="non-empty array of tables"):
        load_consent_controls_map(
            write_map(tmp_path, 'sections = ["1"]\n\n' + CONTROL_FLAG + CONTROL_GATE)
        )


def test_a_non_slug_control_id_is_rejected(tmp_path):
    bad = CONTROL_FLAG.replace('id = "consent-flag"', 'id = "Consent Flag"')
    with pytest.raises(ConsentControlsMapError, match="lowercase slugs"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_TWO + bad + CONTROL_GATE)
        )


def test_a_home_outside_the_closed_vocabulary_is_rejected(tmp_path):
    """A typo'd home is a SHAPE error (the map would place the control
    nowhere without saying so) — unlike a MISSING home, which is placement
    drift the checker reports."""
    typo = CONTROL_GATE.replace('home = "template"', 'home = "core-datasets"')
    with pytest.raises(ConsentControlsMapError, match="not one of the map's homes"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_TWO + CONTROL_FLAG + typo)
        )


def test_an_empty_seam_is_rejected(tmp_path):
    empty = CONTROL_FLAG.replace(
        'seam = "the per-input consent flag on every user input surface"',
        'seam = "  "',
    )
    with pytest.raises(ConsentControlsMapError, match="must be a non-empty string"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_TWO + empty + CONTROL_GATE)
        )


def test_a_citation_that_does_not_name_ADR_0026_is_rejected(tmp_path):
    """ADR-0026 is the single source — an evolution note may accompany the
    citation, never replace it."""
    foreign = CONTROL_FLAG.replace('adr = "ADR-0026 §1', 'adr = "ADR-0024 §1')
    with pytest.raises(ConsentControlsMapError, match="every entry cites ADR-0026"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_TWO + foreign + CONTROL_GATE)
        )


def test_a_section_declared_twice_is_rejected(tmp_path):
    with pytest.raises(ConsentControlsMapError, match="declares section '1' twice"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + SECTION_ONE + CONTROL_FLAG)
        )


def test_a_section_id_that_disagrees_with_its_citation_is_rejected(tmp_path):
    drifted = SECTION_ONE.replace('adr = "ADR-0026 §1', 'adr = "ADR-0026 §5')
    with pytest.raises(ConsentControlsMapError, match="cites"):
        load_consent_controls_map(
            write_map(tmp_path, drifted + CONTROL_FLAG + CONTROL_GATE)
        )


def test_a_control_citing_an_undeclared_section_is_rejected(tmp_path):
    """The map's sections are the closed index of the ADR's control-carrying
    sections; a control citing a section the map never declares would
    silently drop out of the sweep."""
    with pytest.raises(ConsentControlsMapError, match="undeclared section"):
        load_consent_controls_map(
            write_map(tmp_path, SECTION_ONE + CONTROL_ANONYMIZE + CONTROL_FLAG)
        )


def test_a_map_without_sections_or_controls_is_rejected(tmp_path):
    with pytest.raises(ConsentControlsMapError, match="sections"):
        load_consent_controls_map(write_map(tmp_path, CONTROL_FLAG))
    with pytest.raises(ConsentControlsMapError, match="controls"):
        load_consent_controls_map(write_map(tmp_path, SECTION_ONE + SECTION_TWO))


def test_a_malformed_map_raises_naming_the_problem(tmp_path):
    with pytest.raises(ConsentControlsMapError, match="not valid TOML"):
        load_consent_controls_map(write_map(tmp_path, "[[controls]\nid = broken"))
    missing = tmp_path / "absent_map.toml"
    with pytest.raises(ConsentControlsMapError, match="not found"):
        load_consent_controls_map(missing)


# ------------------------------------------------------- the shape constants


def test_the_checker_is_not_a_declared_capability():
    """The #275 ruling binds this ticket's shape too: the consent-controls
    checker ships as plain data + test functions, NOT as a capability —
    `service.toml` still declares only the canary."""
    from contract.declaration import load_service_toml

    svc = load_service_toml(Path(__file__).resolve().parents[2] / "service.toml")
    assert [c.name for c in svc.capabilities] == ["canary"]


def test_the_shipped_map_and_loader_carry_no_service_name():
    """Rename-safety: the map's keys are capability/service names from the
    platform's own model, stable across the copy ritual — never the
    placeholder service name."""
    text = DEFAULT_MAP_PATH.read_text()
    for forbidden in ("<service>", "template-service"):
        assert forbidden not in text
    assert set(CONTROL_KEYS) == {"id", "adr", "home", "seam"}
    assert set(SECTION_KEYS) == {"id", "adr"}
    assert set(HOMES) == {"template", "core", "chat-and-agents"}
