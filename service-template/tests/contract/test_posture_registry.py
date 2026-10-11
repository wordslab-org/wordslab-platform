"""The posture-registry tests (ticket #276 AC 3).

The posture registry is where each control's **runtime stance** is recorded
and read back — the security-controls map's "has a home" made concrete ("and
its current stance is recorded here"). Its contract surface is the public
loader/record/read-back API (the #74/#75 data-surface precedent: a
data-surface ticket has no HTTP seam — the seam is the loader, validated
from inline TOML written via `tmp_path`).

The shape is CLOSED like the map's: unknown keys, a stance outside the
closed vocabulary, or a stance for an unmapped control id fail loudly at
load with a precise message naming the offending entry — every rejection
rule fed its offending entry here. Stances key on the map's control ids:
the map is the key vocabulary the seven lanes (#277–#283) write against and
the coherence bar (#284) reads back.
"""

from __future__ import annotations

import textwrap

import pytest

from tests.support.posture_registry import (
    STANCES,
    PostureRegistryError,
    load_posture_registry,
    record_stance,
)
# The map loader lives in the service package (contract.*), like the checker's.
from contract.security_controls import load_security_controls_map

from tests.support.security_controls_fixtures import good_map

# ------------------------------------------------------------- the vocabulary

REGISTRY_HEADER = """\
# posture registry
[registry]
"""


def record(control_id: str, stance: str, *, lane: str = "#277") -> str:
    return f"""
[[stances]]
control = "{control_id}"
stance = "{stance}"
lane = "{lane}"
"""


def write_registry(tmp_path, content: str):
    path = tmp_path / "posture_registry.toml"
    path.write_text(textwrap.dedent(content))
    return path


# ------------------------------------------- AC 3: record + read back, asserted


def test_a_stance_round_trips_through_the_registry_surface(tmp_path):
    """#276 AC 3: the registry records and reads back a control's runtime
    stance through a contract surface — inputs in, stance out — asserted,
    never as prose."""
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path, REGISTRY_HEADER + record("control-one", "verified-holding")
    )
    registry = load_posture_registry(registry_path, map_path=map_path)
    stance = registry.stance("control-one")
    assert stance.stance == "verified-holding"
    assert stance.control == "control-one"
    assert stance.lane == "#277"
    assert registry.render().startswith("posture registry: 1 stance")


def test_record_stance_returns_the_stance_the_registry_read_back(tmp_path):
    """The record surface is inputs in, stance out: `record_stance` writes
    the entry and the loaded registry answers with the same stance — the
    round-trip is the contract, not an in-memory echo."""
    map_path = good_map(tmp_path)
    registry_path = tmp_path / "posture_registry.toml"
    stance = record_stance(
        registry_path,
        control="control-two",
        stance="verified-holding",
        lane="#280",
        map_path=map_path,
    )
    assert stance.stance == "verified-holding"
    reloaded = load_posture_registry(registry_path, map_path=map_path)
    assert reloaded.stance("control-two") == stance


def test_a_control_may_be_re_recorded_and_the_latest_stance_reads_back(tmp_path):
    """A lane re-verifying its control re-records: the registry answers with
    the latest stance for that control (the coherence bar reads the current
    posture, not the history)."""
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path,
        REGISTRY_HEADER
        + record("control-one", "not-yet-verified")
        + record("control-one", "verified-holding"),
    )
    registry = load_posture_registry(registry_path, map_path=map_path)
    assert registry.stance("control-one").stance == "verified-holding"


def test_the_stance_vocabulary_is_closed():
    """The stance vocabulary is the closed set the lanes and the coherence
    bar share — exported so a lane names a stance, never invents one."""
    assert STANCES == ("not-yet-verified", "verified-holding", "verified-broken")


# ------------------------------------------------- the loud rejections (AC 3)


def test_a_stance_for_an_unmapped_control_id_is_a_loud_rejection(tmp_path):
    """The map is the key vocabulary: a stance for a control the map does not
    declare fails at load naming the offending entry — a lane cannot key a
    stance on a control that does not exist."""
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path, REGISTRY_HEADER + record("control-nonexistent", "verified-holding")
    )
    with pytest.raises(PostureRegistryError, match="control-nonexistent"):
        load_posture_registry(registry_path, map_path=map_path)


def test_a_stance_outside_the_closed_vocabulary_is_a_loud_rejection(tmp_path):
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path, REGISTRY_HEADER + record("control-one", "probably-fine")
    )
    with pytest.raises(PostureRegistryError, match="probably-fine"):
        load_posture_registry(registry_path, map_path=map_path)


def test_an_unknown_key_is_a_loud_rejection(tmp_path):
    """Closed shape: the closed-shape scan runs before presence checks — a
    typo'd key fails naming the entry, never silently."""
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path,
        REGISTRY_HEADER
        + """
[[stances]]
control = "control-one"
stance = "verified-holding"
lane = "#277"
who_knows = "extra"
""",
    )
    with pytest.raises(PostureRegistryError, match="who_knows"):
        load_posture_registry(registry_path, map_path=map_path)


def test_a_missing_field_is_a_loud_rejection(tmp_path):
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path,
        REGISTRY_HEADER
        + """
[[stances]]
control = "control-one"
lane = "#277"
""",
    )
    with pytest.raises(PostureRegistryError, match="stance"):
        load_posture_registry(registry_path, map_path=map_path)


def test_an_empty_registry_is_valid_data_not_an_error(tmp_path):
    """Before any lane has run, the registry is legitimately empty — the
    substrate ships the scaffolding, it verifies no control. An empty
    registry loads; the coherence bar (#284) is what later demands every
    control's stance present."""
    map_path = good_map(tmp_path)
    registry_path = write_registry(tmp_path, REGISTRY_HEADER)
    registry = load_posture_registry(registry_path, map_path=map_path)
    assert registry.stances == ()
    with pytest.raises(PostureRegistryError, match="control-one"):
        registry.stance("control-one")


def test_a_missing_registry_file_is_a_loud_rejection(tmp_path):
    """The load surface names the missing path — a lane pointing at a
    registry that was never written fails loudly, never loads empty."""
    with pytest.raises(PostureRegistryError, match="posture registry not found"):
        load_posture_registry(tmp_path / "absent.toml", map_path=good_map(tmp_path))


def test_a_registry_header_carrying_keys_is_a_loud_rejection(tmp_path):
    """The registry's shape is fixed by its loader, not configured per file —
    a `[registry]` table with a key is an unknown key."""
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path,
        """\
[registry]
version = 2
"""
        + record("control-one", "verified-holding"),
    )
    with pytest.raises(PostureRegistryError, match="header with no keys"):
        load_posture_registry(registry_path, map_path=map_path)


def test_stances_as_a_non_array_is_a_loud_rejection(tmp_path):
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path,
        REGISTRY_HEADER
        + """
[stances]
control = "control-one"
""",
    )
    with pytest.raises(PostureRegistryError, match="array of tables"):
        load_posture_registry(registry_path, map_path=map_path)


def test_record_stance_rejects_a_stance_outside_the_vocabulary_before_writing(
    tmp_path,
):
    """The record surface fails closed on the vocabulary too — nothing lands
    for an invented stance."""
    map_path = good_map(tmp_path)
    registry_path = tmp_path / "posture_registry.toml"
    with pytest.raises(PostureRegistryError, match="definitely-fine"):
        record_stance(
            registry_path,
            control="control-one",
            stance="definitely-fine",
            lane="#277",
            map_path=map_path,
        )
    assert not registry_path.exists()


def test_a_lane_label_needing_quotes_still_round_trips(tmp_path):
    """The record surface's promise is that the file it WRITES LOADS: a
    value carrying a quote is TOML-escaped on write, so the round-trip
    survives instead of poisoning the registry for every later lane."""
    map_path = good_map(tmp_path)
    registry_path = tmp_path / "posture_registry.toml"
    tricky = '#279 "quoted" \\ lane'
    recorded = record_stance(
        registry_path,
        control="control-one",
        stance="verified-holding",
        lane=tricky,
        map_path=map_path,
    )
    reloaded = load_posture_registry(registry_path, map_path=map_path)
    assert reloaded.stance("control-one") == recorded
    assert reloaded.stance("control-one").lane == tricky


def test_the_registry_is_consumable_by_the_coherence_bar(tmp_path):
    """#284's read-back shape: one sweep over the registry against the map —
    which controls have a recorded stance and which are missing, as data the
    bar asserts green over, not an exception on the first gap."""
    map_path = good_map(tmp_path)
    registry_path = write_registry(
        tmp_path, REGISTRY_HEADER + record("control-one", "verified-holding")
    )
    registry = load_posture_registry(registry_path, map_path=map_path)
    controls_map = load_security_controls_map(map_path)
    assert registry.missing_for(controls_map) == ("control-two",)
    assert registry.covered_for(controls_map) == ("control-one",)


def test_record_stance_rejects_an_unmapped_control_before_writing(tmp_path):
    """The record surface fails closed like the loader: an unmapped control
    never lands in the file."""
    map_path = good_map(tmp_path)
    registry_path = tmp_path / "posture_registry.toml"
    with pytest.raises(PostureRegistryError, match="control-nonexistent"):
        record_stance(
            registry_path,
            control="control-nonexistent",
            stance="verified-holding",
            lane="#277",
            map_path=map_path,
        )
    assert not registry_path.exists()
