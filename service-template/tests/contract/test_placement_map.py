"""Control-placement map tests (ticket #275; parent spec #66, ADR-0017).

The map is DATA with a CLOSED shape and a loader that rejects loudly (the
settled #74/#75 contract); the placement invariants over it are the harness's
(`tests/support/placement.py`, tested in `test_placement_harness.py`).

Two things are asserted here:

- the **loader** — the closed shape, the references, and every loud-rejection
  rule fed its offending entry and matched on the specific message (a grep of
  the shipped file proves nothing);
- the **shipped map** — ADR-0017's five §1 frames resolve, every control has
  exactly one home, and every control section of the ADR is cited.

The map is loaded at the data seam: `load_placement_map(path)` returns the
parsed shape or raises a precise `PlacementMapError`, validated from inline
TOML written via tmp_path. No HTTP seam — this is a data surface.
"""

from __future__ import annotations

import textwrap

import pytest

from contract.placement import (
    ADR_0017,
    CONTROL_KEYS,
    DEFAULT_MAP_PATH,
    FRAME_KEYS,
    HOMES,
    PlacementMap,
    PlacementMapError,
    load_placement_map,
)

from tests.support.placement_fixtures import (
    FRAME_ALPHA,
    FRAME_BETA,
    CONTROL_ONE,
    CONTROL_TWO,
    map_document,
    write_map,
)

# --------------------------------------------------------------- the loader


def test_a_well_formed_map_loads_into_frames_and_controls(tmp_path):
    placement_map = load_placement_map(write_map(tmp_path))
    assert isinstance(placement_map, PlacementMap)
    assert [f.id for f in placement_map.frames] == ["alpha", "beta"]
    assert [c.id for c in placement_map.controls] == ["control-one", "control-two"]
    # the map's own path rides the parsed shape (the sweep reports it)
    assert placement_map.path.name == "placement_map.toml"
    # every citation names ADR-0017 — the single source
    assert all(ADR_0017 in c.adr for c in placement_map.controls)


def test_the_frame_to_control_direction_is_derived_not_declared(tmp_path):
    """A frame's resolution comes from its controls' `backs` — one source, so
    the two directions of the map cannot drift apart."""
    placement_map = load_placement_map(write_map(tmp_path))
    assert [c.id for c in placement_map.controls_for("alpha")] == ["control-one"]
    assert [c.id for c in placement_map.controls_for("beta")] == ["control-two"]
    assert placement_map.control("control-one").backs == ("alpha",)
    assert placement_map.frame("beta").adr == "ADR-0017 §1.2 (accidental data leakage)"


def test_a_control_may_back_several_frames_and_settle_its_own_section(tmp_path):
    """§8's guardrails answer BOTH §1.2 and §1.1; §3's stance answers §1.4
    while settling a concern of its own section. `backs` may carry several
    frames — or none at all."""
    shared = CONTROL_ONE.replace('backs = ["alpha"]', 'backs = ["alpha", "beta"]')
    placement_map = load_placement_map(
        write_map(tmp_path, FRAME_ALPHA + FRAME_BETA + shared + CONTROL_TWO)
    )
    assert [c.id for c in placement_map.controls_for("alpha")] == ["control-one"]
    assert [c.id for c in placement_map.controls_for("beta")] == [
        "control-one",
        "control-two",
    ]

    self_settling = CONTROL_ONE.replace('backs = ["alpha"]', "backs = []")
    placement_map = load_placement_map(
        write_map(tmp_path, FRAME_ALPHA + self_settling)
    )
    assert placement_map.controls[0].backs == ()
    assert placement_map.controls_for("alpha") == ()


def test_a_boundary_frame_is_marked_as_such(tmp_path):
    """§1 names the host-OS-malware frame an EXPLICIT BOUNDARY — the model
    declares it does not fully defend it. The flag is data the later lanes
    read; it defaults to false."""
    frames = FRAME_ALPHA + FRAME_BETA.replace(
        'id = "beta"', 'id = "beta"\nboundary = true'
    )
    placement_map = load_placement_map(write_map(tmp_path, frames + CONTROL_ONE))
    assert placement_map.frame("alpha").boundary is False
    assert placement_map.frame("beta").boundary is True


def test_an_empty_backs_list_is_legal_but_a_dangling_one_is_not(tmp_path):
    """`backs = []` is the honest record for a control that settles a concern
    of its own ADR section; a name that is not a declared frame is a dangling
    reference that would silently drop the control out of the model."""
    path = write_map(
        tmp_path, FRAME_ALPHA + CONTROL_ONE.replace('backs = ["alpha"]', "backs = []")
    )
    assert load_placement_map(path).controls[0].backs == ()

    with pytest.raises(PlacementMapError, match="undeclared threat frame"):
        load_placement_map(
            write_map(
                tmp_path, FRAME_ALPHA + CONTROL_ONE.replace('["alpha"]', '["gamma"]')
            )
        )


def test_asking_for_an_undeclared_frame_or_control_is_loud(tmp_path):
    """A foreign id is a rejection, never an empty answer (`controls_for`
    validates the frame first)."""
    placement_map = load_placement_map(write_map(tmp_path))
    with pytest.raises(PlacementMapError, match="not a declared threat frame"):
        placement_map.controls_for("gamma")
    with pytest.raises(PlacementMapError, match="not a declared control"):
        placement_map.control("control-ghost")


# ------------------------------------------------------- loud-rejection rules
#
# Every rule gets a test feeding the offending entry and asserting the
# specific message (the settled #74 lesson: a text grep proves nothing).


@pytest.mark.parametrize(
    "content,match",
    [
        # closed shape, top level: the map is its own file, never a key
        (
            map_document() + '\n[security]\nplacement = "here"\n',
            "unknown top-level key",
        ),
        # closed shape, per frame
        (
            map_document(frames=FRAME_ALPHA + 'boundaryish = "x"\n'),
            "declares only",
        ),
        # closed shape, per control
        (
            map_document(controls=CONTROL_ONE + 'consequence = "tier"\n'),
            "declares only",
        ),
        # a frame's OWN definition may not be duplicated
        (map_document(frames=FRAME_ALPHA + FRAME_ALPHA), "twice"),
        # a control's home must come from the closed home vocabulary
        (
            map_document(controls=CONTROL_ONE.replace('home = "core"', 'home = "the-core"')),
            "not one of the map's homes",
        ),
        # a home that is not a string at all
        (map_document(controls=CONTROL_ONE.replace('home = "core"', "home = 3")),
         "must be a string"),
        # seam is required — where inside the home the control lives
        (map_document(controls=CONTROL_ONE.replace('seam = "the keys/secrets capabilities"', "")),
         "must be a non-empty string"),
        # ids are slugs (the harness and the later lanes name them)
        (map_document(frames=FRAME_ALPHA.replace('id = "alpha"', 'id = "Alpha One"')),
         "lowercase slugs"),
        # every citation names ADR-0017 — the single source
        (map_document(controls=CONTROL_ONE.replace("ADR-0017 §2", "ADR-0016")),
         "every entry cites"),
        # a frame's `boundary` flag is a boolean, never a truthy string
        (
            map_document(frames=FRAME_ALPHA + '\nboundary = "yes"\n'),
            "boundary.* must be true or false",
        ),
        # `backs` is an array of threat-frame ids
        (map_document(controls=CONTROL_ONE.replace('backs = ["alpha"]', "backs = 3")),
         r"backs.* must be an array"),
        (map_document(controls=CONTROL_ONE.replace('backs = ["alpha"]', 'backs = [1]')),
         r"backs.* must be an array"),
        # frames are required — a map without them is not a model
        (map_document(frames=""), "`frames` must be a non-empty array"),
        (map_document(controls=""), "`controls` must be a non-empty array"),
        # a frame is an array of tables, not a scalar
        ('frames = ["alpha"]\n' + CONTROL_ONE, "non-empty array"),
        # not valid TOML at all
        (map_document() + "\nthis is not = toml\n", "not valid TOML"),
    ],
)
def test_map_rejections(tmp_path, content, match):
    with pytest.raises(PlacementMapError, match=match):
        load_placement_map(write_map(tmp_path, content))


def test_a_missing_map_file_is_rejected_loudly(tmp_path):
    with pytest.raises(PlacementMapError, match="placement map not found"):
        load_placement_map(tmp_path / "nowhere.toml")


def test_a_homeless_control_is_NOT_a_load_error(tmp_path):
    """The deliberate split: a control with no home is a *placement* fact the
    HARNESS reports (#275 AC 3), never a load error — the loader validates
    shape and references, the harness validates placement. A *typo'd* home is
    the load error instead (above), so the two can never be confused."""
    path = write_map(
        tmp_path,
        FRAME_ALPHA + FRAME_BETA + CONTROL_ONE.replace('home = "core"\n', "") + CONTROL_TWO,
    )
    placement_map = load_placement_map(path)  # loads fine
    assert placement_map.controls[0].home == ""


def test_a_control_landed_twice_is_NOT_a_load_error_either(tmp_path):
    """Same split for duplication: the same control placed in two places —
    both in its own home and split across two — is the placement drift the
    harness catches, so the loader leaves it to the harness (a loader-level
    duplicate check would have to guess which drift shape to reject)."""
    twin = CONTROL_ONE.replace('home = "core"', 'home = "connectors"')
    placement_map = load_placement_map(
        write_map(tmp_path, FRAME_ALPHA + CONTROL_ONE + twin)
    )
    assert [c.id for c in placement_map.controls] == ["control-one", "control-one"]


# ------------------------------------------------- the shipped map (the model)


def test_the_shipped_map_is_discovered_next_to_the_loader():
    """The map travels with the copy-to-start ritual: it sits next to the
    loader inside `contract/`, a path the rename never touches."""
    assert DEFAULT_MAP_PATH.is_file()
    assert DEFAULT_MAP_PATH.name == "placement_map.toml"
    assert DEFAULT_MAP_PATH.parent.name == "contract"


def test_the_shipped_map_resolves_adr_0017_section_1_five_threat_frames():
    """ADR-0017 §1's five surfaces, in the ADR's own order — and every one
    backed by at least one control."""
    placement_map = load_placement_map()
    assert [f.id for f in placement_map.frames] == [
        "compromised-agent-or-harness",
        "accidental-data-leakage",
        "host-os-malware",
        "trusted-lan-untrusted-internet",
        "host-os-files-unreachable",
    ]
    for frame in placement_map.frames:
        controls = placement_map.controls_for(frame.id)
        assert controls, f"§1 frame `{frame.id}` resolves to no control"
        assert all(ADR_0017 in c.adr for c in controls)


def test_the_shipped_map_marks_only_the_host_os_malware_frame_a_boundary():
    """§1.3 is the frame the ADR names an explicit, incomplete boundary (the
    honest non-overclaim). The other four are defended surfaces."""
    placement_map = load_placement_map()
    boundaries = [f.id for f in placement_map.frames if f.boundary]
    assert boundaries == ["host-os-malware"]


def test_every_control_in_the_shipped_map_has_exactly_one_home():
    """#275 AC 1 — every control resolves to exactly one owning
    capability/home."""
    placement_map = load_placement_map()
    assert placement_map.controls, "the map places no control"
    homeless = [c.id for c in placement_map.controls if not c.home]
    assert homeless == [], f"homeless control(s): {homeless}"
    assert set(placement_map.homes_used) <= set(HOMES)
    # every control's own id is unique — no control landed twice
    ids = [c.id for c in placement_map.controls]
    assert len(ids) == len(set(ids))


def test_the_shipped_map_places_the_guardrail_layer_once_per_section_8_site():
    """§8 settles the guardrail placement across sites; each site hosts
    exactly one of §8's controls, so the layer is not re-implemented (the
    duplication invariant, read off the shipped map)."""
    from tests.support.placement import GUARDRAIL_SITES, _guardrails_by_site

    by_site = _guardrails_by_site(load_placement_map())
    assert set(by_site) == set(GUARDRAIL_SITES)
    assert all(len(ids) == 1 for ids in by_site.values()), by_site


def test_the_shipped_map_cites_every_control_section_of_adr_0017():
    """§1 carries the frames, §6 states the platform does NOT intercept the
    harness (the controls it enumerates are placed under their own sections,
    §2/§5/§7), and the ADR's Context takes the trust basics as given. Every
    other section decides controls, so every other section must be cited —
    the sweep that proves no control section of the ADR is silently unplaced."""
    cited = load_placement_map().cited_sections
    assert cited == ("1", "2", "3", "4", "5", "7", "8", "9")
    assert "6" not in cited  # the harness-authority section places no control


def test_the_shipped_map_covers_the_homes_the_verification_lanes_expect():
    """The map's home set is the set the per-control lanes verify
    (#277 installer/Chat+Agents, #278 Chat+Agents, #279 core, #280 Connectors,
    #281 the three guardrail homes, #282 installer, #283 the lifecycle) — the
    two tickets' scopes are deliberately the same set."""
    assert load_placement_map().homes_used == (
        "chat-and-agents",
        "connectors",
        "core",
        "inference",
        "installer",
        "lifecycle",
        "media-transformations",
    )


def test_the_map_is_not_a_declaration_key(tmp_path):
    """The trap #275 names: a `[security]`/`[placement]` table inside a
    declaration is an UNKNOWN KEY — the same ruling that struck down a
    declared `[learning]` table for #75 (the FILES are the declaration). The
    map is its own file precisely so the closed declaration shapes stay closed."""
    from contract.declaration import ServiceDeclarationError, load_service_toml

    service_root = tmp_path / "svc"
    service_root.mkdir()
    toml = textwrap.dedent(
        """\
        name = "svc"
        description = "d"
        version = "1.0.0"

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1

        [svc.canary]
        description = "d"
        version = "0.1.0"
        api = "/v1/echo"
        api-functions = "d"
        versions-history = "d"
        required = false

        [svc.canary.ui]
        description = "d"
        versions-history = "d"

        [security]
        placement-map = "contract/placement_map.toml"
        """
    )
    path = service_root / "service.toml"
    path.write_text(toml)
    with pytest.raises(ServiceDeclarationError, match="unknown"):
        load_service_toml(path)


def test_the_shipped_map_and_loader_carry_no_service_name():
    """Rename-safety: the map's keys are capability/service names from the
    platform's own model, stable across the copy ritual — never the
    placeholder service name (`template-service` / `<service>`)."""
    text = DEFAULT_MAP_PATH.read_text()
    for forbidden in ("<service>", "template-service"):
        assert forbidden not in text
    assert set(CONTROL_KEYS) == {"id", "adr", "home", "seam", "backs"}
    assert set(FRAME_KEYS) == {"id", "adr", "boundary"}
