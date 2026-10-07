"""The control-placement map — the machine-readable index of ADR-0017's
security model (ticket #275, parent spec #66).

ADR-0017 is the **single source**: it names the threat frames and the
controls, each with exactly one home. This module does **not** restate any
control's internals — it *places* them. The map is the index that says
*where* each control lives, and the invariant harness
(`tests/support/placement.py`) proves the index is complete (no control
homeless, no control re-implemented in two places).

## The map's shape (a data file + a loader with a CLOSED shape)

The map is **data**, discovered/loaded explicitly — never a declaration
key. A `[security]` / `[placement]` table inside `service.toml` or
`implementation.toml` would be an **unknown key** and is rejected by those
loaders (the closed-shape rule they already enforce; the same ruling that
struck down a declared `[learning]` table for #75 — the FILES are the
declaration). The map lives in its own file next to this module:

    contract/placement_map.toml      the map (data)
    contract/placement.py            this loader (the seam)

    [frames]    every threat frame of ADR-0017 §1 — its id, the ADR
                citation, and `boundary = true` when §1 names it an
                *explicit boundary* (not fully defended).
    [controls]  every control ADR-0017 decides — its id, the ADR section
                that defines it, the ONE owning home it lives in, the seam
                within that home, and the threat frame(s) it answers.

The frame→control direction is **derived** from each control's `backs`
(`PlacementMap.controls_for`) — one source, so the two directions cannot
drift apart.

## What the loader validates (loudly) and what it deliberately does not

The loader validates **shape and references**:

- the closed key sets (a typo fails at load, never silently);
- every id is a lowercase slug; frame ids are unique (a frame's own
  definition may not be declared twice — its `boundary` flag and its role
  would be contradictory);
- every `backs` entry names a declared frame (a dangling reference would
  silently drop a control out of the model);
- every `home` is one of the closed `HOMES` (a typo'd home would silently
  place a control nowhere);
- every citation names ADR-0017 (the single source — an evolution note may
  accompany it, e.g. ADR-0030's per-tool tiering, but ADR-0017 is always
  cited).

It does **not** reject placement drift: a homeless control, or two controls
sharing one home, are exactly the **placement** facts the harness exists to
report (#275's own acceptance criterion — "a map with a homeless or
double-homed control is caught by the harness"). Shape errors are load
errors; placement drift is a harness finding. A *typo'd* home (a value
outside `HOMES`) is neither: it is a shape error, because the map would
otherwise place the control nowhere without saying so.

## What this map deliberately does not carry

- **Control internals.** The map cites ADR-0017; §-numbers, never prose
  paraphrases of a mechanism.
- **The honest non-goals as a narrative.** §1's *host-OS-malware* frame is
  one of the five frames, so it is representable here as a declared
  `boundary` — the minimum the frame invariant needs. The remaining
  non-goals (the disk thief, no unified harness accept/refuse trail, the
  heavy guardrail tier off by default) are #276/#282's model state and
  #284's narrative, not this ticket's.
- **What ADR-0017's Context takes as given.** Machine identity keys (ADR-0003),
  the overlay (ADR-0003/0004), the `keys`/`secrets` split (ADR-0003/0006),
  per-agent registry scoping (ADR-0008 §5) and the cloud action-context
  boundary (ADR-0004 §10) are settled ground the ADR explicitly takes as
  given, and §1's frame parentheticals name per-agent scoping and the
  privacy labels as §1's own summary. They are **cross-referenced, not
  placed**: a control in this map is one ADR-0017 itself decides. The
  per-control verification lanes (#277–#283) verify exactly this map's
  controls — the set is deliberately the same set.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

#: The governing ADR — the map's single source (`docs/adr/0017-security-model.md`).
#: Every citation names it; an evolution note may accompany it, but never
#: replace it.
ADR_0017 = "ADR-0017"

#: The map's shipped data file, module-adjacent. Discovered by *location*
#: (the same convention the bar uses): the copy-to-start ritual renames
#: `src/<service>/` but never `contract/placement_map.toml`, so the default
#: path survives the rename — and a copied service carries its own copy.
DEFAULT_MAP_PATH = Path(__file__).resolve().with_name("placement_map.toml")

#: The closed home vocabulary: **the single owning home of a control**. Each
#: home names the platform service or layer ADR-0017's placement settles, with
#: the ADR/chapter that defines it. A control names ONE home — where ADR-0017
#: §8 settles a placement across two sites (the guardrail layer's hooks sit in
#: the agent loop *and* at the outbound door), that is two controls, each with
#: its own home, never one control with two entries.
HOMES: dict[str, str] = {
    "installer": (
        "the installer / bootstrap layer (ADR-0014) — the local-CA HTTPS "
        "surfaces and the default-deny WSL mount stance (#63)"
    ),
    "core": "the platform core service (ADR-0003) — its `keys` / `secrets` capabilities",
    "chat-and-agents": (
        "the Chat + Agents service (ADR-0007 §8) — the agent loop and the "
        "per-workspace-session containers"
    ),
    "connectors": "the Connectors service (ADR-0030 §1) — the single audited door",
    "inference": "the Inference service (ADR-0029) — its classic-AI model capability",
    "media-transformations": (
        "the Media transformations service (`docs/architecture/30-services/43`) "
        "— the builtin transforms"
    ),
    "lifecycle": (
        "the update / lifecycle flow at its metadata/check step (ADR-0016 §5) "
        "— the flow the core's `install`/`catalog` capabilities carry (#65)"
    ),
}

FRAME_KEYS = {"id", "adr", "boundary"}
CONTROL_KEYS = {"id", "adr", "home", "seam", "backs"}

_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SECTION_RE = re.compile(r"ADR-0017\s+§(\d+)")


def adr_0017_sections(citation: str) -> tuple[str, ...]:
    """The ADR-0017 `§N` sections a citation names, in written order.

    Citations are prose (`ADR-0017 §2; ADR-0014 (the mount mechanics…)`), so
    membership is READ from the citation — one parser, shared by the loader's
    sweep (`cited_sections`) and the harness's section grouping. Only sections
    written against ADR-0017 count: a co-cited ADR's own `§N` (e.g. ADR-0004
    §12) is that ADR's, not this one's.
    """
    return tuple(_SECTION_RE.findall(citation))


class PlacementMapError(ValueError):
    """A placement map that violates its declared shape.

    Raised at load time: a malformed map is not a model, so it must not load
    half-read (the settled #74/#75 contract — the loader validates the closed
    shape and raises a precise error naming the offending entry).
    """


@dataclass(frozen=True)
class Frame:
    """One threat frame of ADR-0017 §1 — its id, its citation, and whether §1
    names it an **explicit boundary** (a surface the model declares *not*
    fully defended; the honest non-overclaim)."""

    id: str
    adr: str
    boundary: bool = False

    @property
    def sections(self) -> tuple[str, ...]:
        """The ADR-0017 sections this citation names (its own `§N` tokens)."""
        return adr_0017_sections(self.adr)


@dataclass(frozen=True)
class Control:
    """One control ADR-0017 decides, PLACED: the section that defines it, the
    ONE owning `home`, the `seam` within that home (which surface it lives
    on — citing the settled capability name where an ADR names one), and the
    threat frame(s) it `backs` (empty when the control settles a concern of
    its own section rather than one of §1's five frames)."""

    id: str
    adr: str
    home: str
    seam: str
    backs: tuple[str, ...] = ()

    @property
    def sections(self) -> tuple[str, ...]:
        """The ADR-0017 sections this citation names (its own `§N` tokens) —
        the fact the harness reads to tell which section a control lives
        under, never a substring probe of the citation prose."""
        return adr_0017_sections(self.adr)


@dataclass(frozen=True)
class PlacementMap:
    """The parsed, validated map — ADR-0017's frames and its placed controls.

    The frame→control direction is derived (`controls_for`), never stored
    twice, so the two directions cannot disagree.
    """

    frames: tuple[Frame, ...] = ()
    controls: tuple[Control, ...] = ()
    path: Path | None = field(default=None, compare=False, repr=False)

    def frame(self, frame_id: str) -> Frame:
        """The declared frame with this id, or a loud rejection."""
        for frame in self.frames:
            if frame.id == frame_id:
                return frame
        raise PlacementMapError(f"`{frame_id}` is not a declared threat frame")

    def control(self, control_id: str) -> Control:
        """The (first) control with this id, or a loud rejection."""
        for control in self.controls:
            if control.id == control_id:
                return control
        raise PlacementMapError(f"`{control_id}` is not a declared control")

    def controls_for(self, frame_id: str) -> tuple[Control, ...]:
        """The controls backing a frame — derived from `Control.backs`, so a
        frame's resolution is never a second declaration that can drift."""
        self.frame(frame_id)  # a foreign id is a loud rejection, not an empty answer
        return tuple(c for c in self.controls if frame_id in c.backs)

    @property
    def homes_used(self) -> tuple[str, ...]:
        """The homes the placed controls name — sorted, so a report is stable."""
        return tuple(sorted({c.home for c in self.controls if c.home}))

    @property
    def cited_sections(self) -> tuple[str, ...]:
        """The ADR-0017 sections cited across the map (frames and controls
        alike), by their top-level `§N` — the sweep that proves no control
        section of the ADR is silently unplaced. §6 states the platform does
        NOT intercept the harness, and §1 carries the frames themselves, so a
        control's `adr` must not name either: the map cites the section a
        control LIVES under (the harness reads the same `sections` fact)."""
        sections: set[str] = set()
        for entry in (self.frames, self.controls):
            for item in entry:
                sections.update(item.sections)
        return tuple(sorted(sections, key=int))


# --------------------------------------------------------------- the loader


def load_placement_map(path: str | Path | None = None) -> PlacementMap:
    """Load and validate the control-placement map.

    `path` defaults to the module-adjacent `placement_map.toml` (the shipped
    map, which travels with the copy-to-start ritual — pass an explicit path
    to load a fixture). A malformed map raises `PlacementMapError` naming the
    offending entry — never a silent partial read.
    """
    path = Path(path) if path is not None else DEFAULT_MAP_PATH
    if not path.is_file():
        raise PlacementMapError(f"placement map not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PlacementMapError(f"placement map is not valid TOML: {exc}") from None

    unknown = set(raw) - {"frames", "controls"}
    if unknown:
        raise PlacementMapError(
            f"unknown top-level key(s) {sorted(unknown)} — the placement map"
            " declares only `frames` and `controls` (closed shape, typos fail"
            " loudly). It is NOT a declaration key: a `[security]`/`[placement]`"
            " table in service.toml/implementation.toml is an unknown key there"
            " (ticket #75's ruling stands — the FILES are the declaration)."
        )

    frame_raw = raw.get("frames")
    if (
        not isinstance(frame_raw, list)
        or not frame_raw
        or not all(isinstance(entry, dict) for entry in frame_raw)
    ):
        raise PlacementMapError(
            "`frames` must be a non-empty array of tables (`[[frames]]`) — the"
            " map resolves ADR-0017 §1's threat frames, so a map without them"
            " is not a model"
        )
    control_raw = raw.get("controls")
    if (
        not isinstance(control_raw, list)
        or not control_raw
        or not all(isinstance(entry, dict) for entry in control_raw)
    ):
        raise PlacementMapError(
            "`controls` must be a non-empty array of tables (`[[controls]]`) —"
            " a map that places no control is not a model"
        )

    frames = _parse_frames(frame_raw)
    controls = _parse_controls(control_raw, {f.id for f in frames})
    return PlacementMap(frames=frames, controls=controls, path=path)


def _parse_frames(entries: list) -> tuple[Frame, ...]:
    frames: list[Frame] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"frames[{index}]"
        unknown = set(entry) - FRAME_KEYS
        if unknown:
            raise PlacementMapError(
                f"`{where}` has unknown key(s) {sorted(unknown)} — a frame"
                f" declares only: {', '.join(sorted(FRAME_KEYS))}"
            )
        frame_id = _require_slug(entry, "id", where)
        where = f"{where} (`{frame_id}`)"
        if frame_id in seen:
            raise PlacementMapError(
                f"`{where}` declares threat frame {frame_id!r} twice — a frame's"
                " own definition may not be duplicated (its `boundary` flag and"
                " its role would contradict each other). A CONTROL landed twice"
                " is the different, *placement* fact the harness reports."
            )
        seen.add(frame_id)
        adr = _require_str(entry, "adr", where)
        _check_cites_adr_0017(adr, where)
        boundary = entry.get("boundary", False)
        if not isinstance(boundary, bool):
            raise PlacementMapError(
                f"`{where}.boundary` must be true or false — it marks a §1"
                " frame the model declares an explicit, incomplete boundary"
                " (never silently claimed as defended)"
            )
        frames.append(Frame(id=frame_id, adr=adr, boundary=boundary))
    return tuple(frames)


def _parse_controls(entries: list, frame_ids: set[str]) -> tuple[Control, ...]:
    controls: list[Control] = []
    for index, entry in enumerate(entries):
        where = f"controls[{index}]"
        unknown = set(entry) - CONTROL_KEYS
        if unknown:
            raise PlacementMapError(
                f"`{where}` has unknown key(s) {sorted(unknown)} — a control"
                f" declares only: {', '.join(sorted(CONTROL_KEYS))}"
            )
        control_id = _require_slug(entry, "id", where)
        where = f"{where} (`{control_id}`)"
        adr = _require_str(entry, "adr", where)
        _check_cites_adr_0017(adr, where)

        # `home` is where the control lives. It is DELIBERATELY optional here:
        # a control with no home is the placement fact the harness reports
        # (#275 AC: "a map with a homeless ... control is caught by the
        # harness"). A *declared* home that is not in the closed vocabulary is
        # a different thing — a typo — and fails loudly at load.
        home = entry.get("home", "")
        if not isinstance(home, str):
            raise PlacementMapError(f"`{where}.home` must be a string")
        if home and home not in HOMES:
            raise PlacementMapError(
                f"`{where}.home` is {home!r} — not one of the map's homes"
                f" {sorted(HOMES)}. A control's home is the single owning"
                " capability/service ADR-0017's placement settles (a typo'd"
                " home would silently place the control nowhere)."
            )

        seam = entry.get("seam", "")
        if not isinstance(seam, str) or not seam.strip():
            raise PlacementMapError(
                f"`{where}.seam` must be a non-empty string — where inside its"
                " home the control lives (the surface/capability the ADR's"
                " placement names); the map cites ADR-0017 rather than"
                " restating the control."
            )

        backs_raw = entry.get("backs", [])
        if not isinstance(backs_raw, list) or not all(isinstance(b, str) for b in backs_raw):
            raise PlacementMapError(
                f"`{where}.backs` must be an array of threat-frame ids — the"
                " §1 frame(s) the control answers (empty when the control"
                " settles a concern of its own section rather than one of the"
                " five frames)."
            )
        dangling = [b for b in backs_raw if b not in frame_ids]
        if dangling:
            raise PlacementMapError(
                f"`{where}.backs` names undeclared threat frame(s) {dangling} —"
                " a dangling reference would silently drop the control out of"
                f" the model; declared frames: {sorted(frame_ids)}"
            )
        controls.append(
            Control(id=control_id, adr=adr, home=home, seam=seam, backs=tuple(backs_raw))
        )
    return tuple(controls)


# ------------------------------------------------------------ check helpers


def _require_str(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlacementMapError(f"`{where}.{key}` must be a non-empty string")
    return value


def _require_slug(table: dict, key: str, where: str) -> str:
    value = _require_str(table, key, where)
    if not _SLUG_RE.fullmatch(value):
        raise PlacementMapError(
            f"`{where}.{key}` is {value!r} — ids are lowercase slugs"
            " (a-z, digits, hyphens; the map's keys are what the harness and"
            " the later verification lanes name)"
        )
    return value


def _check_cites_adr_0017(adr: str, where: str) -> None:
    if ADR_0017 not in adr:
        raise PlacementMapError(
            f"`{where}.adr` is {adr!r} — every entry cites {ADR_0017} (the"
            " single source; an evolution note such as ADR-0030's per-tool"
            " tiering may accompany the citation, never replace it)"
        )


__all__ = [
    "ADR_0017",
    "CONTROL_KEYS",
    "DEFAULT_MAP_PATH",
    "FRAME_KEYS",
    "HOMES",
    "Control",
    "Frame",
    "PlacementMap",
    "PlacementMapError",
    "load_placement_map",
]
