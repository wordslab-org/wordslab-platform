"""The consent-controls map — the machine-readable index of ADR-0026's
data consent & handling model (ticket #285, parent spec #67).

ADR-0026 is the **single source**: it names the consent controls and,
section by section, the home each one lives in. This module does **not**
restate any control's internals — it *indexes* them. The map says *where*
each control lives, and the compliance checker
(`tests/support/consent_controls_check.py` — a TEST-side checker; "harness"
here always means the test harness, never the AI agent harness) proves the
index is complete (no control homeless, no control re-implemented in two
places, every consent-bearing home carrying the flag + the exclusion).

## What the checker is NOT

It ships as **plain data + test functions inside the template** — not as a
capability (the #275 ruling, binding on this sibling: a test function
declared as a capability is misleading; there is no `[<service>.<capability>]`
section for it, no catalog entry, no learning-bar subject). It is also not a
declaration key: a `[consent]` table inside `service.toml` or
`implementation.toml` would be an **unknown key** and is rejected by those
loaders (ticket #75's ruling stands — the FILES are the declaration). The
map lives in its own file next to this module:

    contract/consent_controls_map.toml      the map (data)
    contract/consent_controls.py            this loader (the seam)
    tests/support/consent_controls_check.py the compliance checker

    [sections]  the ADR-0026 sections that place controls — their id (the
                section number) and the ADR citation.
    [controls]  every consent control ADR-0026 decides — its id, the ADR
                section(s) that define it, the ONE owning home it lives in,
                and the seam within that home.

The section→control direction is **derived** from each control's parsed
citation (`ConsentControlsMap.controls_for`) — one source, so the two
directions cannot drift apart.

## What the loader validates (loudly) and what it deliberately does not

The loader validates **shape and references**:

- the closed key sets (a typo fails at load, never silently);
- every id is a lowercase slug; section ids are unique (a section's own
  index entry may not be declared twice);
- every control cites at least one ADR-0026 section, and every section it
  cites is DECLARED (a dangling reference would silently drop a control out
  of the sweep);
- `home` is a string when present (a non-string home is a shape error);
- every `home` is one of the closed `HOMES` (a typo'd home would silently
  place a control nowhere);
- every citation names ADR-0026 (the single source — an evolution note such
  as ADR-0003's `datasets` capability may accompany it, never replace it);
- a section's id agrees with the section its own citation names (an id of
  `3` citing §5 would silently mis-index the sweep).

It does **not** reject placement drift: a homeless control, or the same
control landed in two places, are exactly the facts the compliance checker
exists to report (#285's own acceptance criteria — the compliance checker
flags the drift). Shape errors are load errors; placement drift is a reported
finding. A *typo'd* home (a value outside `HOMES`) is neither: it is a
shape error, because the map would otherwise place the control nowhere
without saying so. (Two *distinct* controls sharing one home is not drift
at all — the template legitimately carries the flag, the exclusion, the
extraction surface and the data-shape declaration; the checker checks a
control's *identity*, and the home's required pair.)

## What this map deliberately does not carry

- **Control internals.** The map cites ADR-0026 by §-number, never prose
  paraphrases of a mechanism. The consent flag's behavior is #72's (already
  shipped in `contract/base/consent.py` and tested there); the core
  `datasets` machinery is #62/#111's; the sphere gate and the assistant's
  container are #48's. This map says WHERE each lives; asserting HOW it
  behaves here would be double-testing.
- **ADR-0026 §4 and §5.** §4 sends genuinely un-anonymizable cases out of
  v1 scope and §5 states what the platform does NOT intercept (the builder
  sphere is anonymize-free; a manual paste is flagged, not blocked). They
  place no control of their own — the map cites the sections a control
  LIVES under (the checker reads the same `sections` fact), exactly as the
  security-controls map skips ADR-0017's §6 non-interception statement.
- **What ADR-0026's Context takes as given.** The three-identities
  attribution model (ADR-0021), the assistant's role-scoping (ADR-0024 §2),
  the eval/training consumers (ADR-0020 §5, ADR-0025 §5) are settled ground
  the ADR cross-references, not controls it decides.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

#: The governing ADR — the map's single source (`docs/adr/0026-data-consent-handling.md`).
#: Every citation names it; an evolution note may accompany it, but never
#: replace it.
ADR_0026 = "ADR-0026"

#: The map's shipped data file, module-adjacent. Discovered by *location*
#: (the same convention the security-controls map uses): the copy-to-start
#: ritual renames `src/<service>/` but never `contract/consent_controls_map.toml`,
#: so the default path survives the rename — and a copied service carries its
#: own copy.
DEFAULT_MAP_PATH = Path(__file__).resolve().with_name("consent_controls_map.toml")

#: The closed home vocabulary: **the single owning home of a control**. Each
#: home names the platform layer or service ADR-0026's placement settles,
#: with the ADR/chapter that defines it. A control names ONE home — where
#: ADR-0026 §2 splits ownership across sites (service extraction surface vs
#: the core's anonymize pass), that is distinct controls, each with its own
#: home, never one control with several entries.
HOMES: dict[str, str] = {
    "template": (
        "the service template's contract (`contract/base/consent.py`, #72) — "
        "the per-input consent flag, the never-bypassable private/secret "
        "exclusion, and the extraction/declaration surfaces every copied "
        "service carries (ADR-0026 §1/§2, sharpening ADR-0002)"
    ),
    "core": (
        "the platform core's `datasets` capability (ADR-0003, sharpened by "
        "ADR-0026 §2) — the single mediated boundary: the gate's filter, the "
        "anonymize pass, provenance, centralized non-user logs (#62/#111 — "
        "not yet built; the checker stands up a stub surface)"
    ),
    "chat-and-agents": (
        "the Chat + Agents service (ADR-0007 §8, ADR-0024 §2) — the "
        "assistant's session container and the sphere gate at the callable "
        "surface (ADR-0026 §6; #48)"
    ),
}

SECTION_KEYS = {"id", "adr"}
CONTROL_KEYS = {"id", "adr", "home", "seam"}

_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SECTION_RE = re.compile(r"ADR-0026\s+§(\d+)")


def adr_0026_sections(citation: str) -> tuple[str, ...]:
    """The ADR-0026 `§N` sections a citation names, in written order.

    Citations are prose (`ADR-0026 §2; ADR-0003 (the datasets capability)`),
    so membership is READ from the citation — one parser, shared by the
    loader's section checks and the checker's section grouping. Only
    sections written against ADR-0026 count: a co-cited ADR's own `§N`
    (e.g. ADR-0024 §2) is that ADR's, not this one's.
    """
    return tuple(_SECTION_RE.findall(citation))


class ConsentControlsMapError(ValueError):
    """A consent-controls map that violates its declared shape.

    Raised at load time: a malformed map is not a model, so it must not load
    half-read (the settled #74/#75/#275 contract — the loader validates the
    closed shape and raises a precise error naming the offending entry).
    """


@dataclass(frozen=True)
class Section:
    """One ADR-0026 section that places controls — its id (the section
    number) and its citation."""

    id: str
    adr: str

    @property
    def sections(self) -> tuple[str, ...]:
        """The ADR-0026 sections this citation names (its own `§N` tokens)."""
        return adr_0026_sections(self.adr)


@dataclass(frozen=True)
class Control:
    """One consent control ADR-0026 decides, PLACED: the section(s) that
    define it, the ONE owning `home`, and the `seam` within that home
    (which surface it lives on — citing the settled capability name where an
    ADR names one, never the mechanism it implements)."""

    id: str
    adr: str
    home: str
    seam: str

    @property
    def sections(self) -> tuple[str, ...]:
        """The ADR-0026 sections this citation names (its own `§N` tokens) —
        the fact the checker reads to tell which section a control lives
        under, never a substring probe of the citation prose."""
        return adr_0026_sections(self.adr)


@dataclass(frozen=True)
class ConsentControlsMap:
    """The parsed, validated map — ADR-0026's control-carrying sections and
    its placed controls.

    The section→control direction is derived (`controls_for`), never stored
    twice, so the two directions cannot disagree.
    """

    sections: tuple[Section, ...] = ()
    controls: tuple[Control, ...] = ()
    path: Path | None = field(default=None, compare=False, repr=False)

    def section(self, section_id: str) -> Section:
        """The declared section with this id, or a loud rejection."""
        for section in self.sections:
            if section.id == section_id:
                return section
        raise ConsentControlsMapError(f"`{section_id}` is not a declared section")

    def control(self, control_id: str) -> Control:
        """The (first) control with this id, or a loud rejection."""
        for control in self.controls:
            if control.id == control_id:
                return control
        raise ConsentControlsMapError(f"`{control_id}` is not a declared control")

    def controls_for(self, section_id: str) -> tuple[Control, ...]:
        """The controls a section places — derived from each control's
        parsed citation, so a section's resolution is never a second
        declaration that can drift."""
        self.section(section_id)  # a foreign id is a loud rejection, not an empty answer
        return tuple(c for c in self.controls if section_id in c.sections)

    @property
    def homes_used(self) -> tuple[str, ...]:
        """The homes the placed controls name — sorted, so a report is stable."""
        return tuple(sorted({c.home for c in self.controls if c.home}))

    @property
    def cited_sections(self) -> tuple[str, ...]:
        """The ADR-0026 sections cited across the map (sections and controls
        alike), by their top-level `§N` — the sweep that proves no
        control-carrying section of the ADR is silently unplaced. §4 sends
        un-anonymizable cases out of v1 scope and §5 states what the
        platform does NOT intercept, so a control's `adr` must not name
        either: the map cites the section a control LIVES under (the
        checker reads the same `sections` fact)."""
        sections: set[str] = set()
        for entry in (self.sections, self.controls):
            for item in entry:
                sections.update(item.sections)
        return tuple(sorted(sections, key=int))


# --------------------------------------------------------------- the loader


def load_consent_controls_map(path: str | Path | None = None) -> ConsentControlsMap:
    """Load and validate the consent-controls map.

    `path` defaults to the module-adjacent `consent_controls_map.toml` (the
    shipped map, which travels with the copy-to-start ritual — pass an
    explicit path to load a fixture). A malformed map raises
    `ConsentControlsMapError` naming the offending entry — never a silent
    partial read.
    """
    path = Path(path) if path is not None else DEFAULT_MAP_PATH
    if not path.is_file():
        raise ConsentControlsMapError(f"consent-controls map not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConsentControlsMapError(f"consent-controls map is not valid TOML: {exc}") from None

    unknown = set(raw) - {"sections", "controls"}
    if unknown:
        raise ConsentControlsMapError(
            f"unknown top-level key(s) {sorted(unknown)} — the consent-controls"
            " map declares only `sections` and `controls` (closed shape, typos"
            " fail loudly). It is NOT a declaration key: a `[consent]` table in"
            " service.toml/implementation.toml is an unknown key there"
            " (ticket #75's ruling stands — the FILES are the declaration)."
        )

    section_raw = raw.get("sections")
    if (
        not isinstance(section_raw, list)
        or not section_raw
        or not all(isinstance(entry, dict) for entry in section_raw)
    ):
        raise ConsentControlsMapError(
            "`sections` must be a non-empty array of tables (`[[sections]]`) —"
            " the map indexes ADR-0026's control-carrying sections, so a map"
            " without them is not a model"
        )
    control_raw = raw.get("controls")
    if (
        not isinstance(control_raw, list)
        or not control_raw
        or not all(isinstance(entry, dict) for entry in control_raw)
    ):
        raise ConsentControlsMapError(
            "`controls` must be a non-empty array of tables (`[[controls]]`) —"
            " a map that places no control is not a model"
        )

    sections = _parse_sections(section_raw)
    controls = _parse_controls(control_raw, {s.id for s in sections})
    return ConsentControlsMap(sections=sections, controls=controls, path=path)


def _parse_sections(entries: list) -> tuple[Section, ...]:
    sections: list[Section] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"sections[{index}]"
        unknown = set(entry) - SECTION_KEYS
        if unknown:
            raise ConsentControlsMapError(
                f"`{where}` has unknown key(s) {sorted(unknown)} — a section"
                f" declares only: {', '.join(sorted(SECTION_KEYS))}"
            )
        section_id = _require_slug(entry, "id", where)
        where = f"{where} (`{section_id}`)"
        if section_id in seen:
            raise ConsentControlsMapError(
                f"`{where}` declares section {section_id!r} twice — a"
                " section's own index entry may not be duplicated (the"
                " section→control sweep would count it twice)."
            )
        seen.add(section_id)
        adr = _require_str(entry, "adr", where)
        _check_cites_adr_0026(adr, where)
        cited = adr_0026_sections(adr)
        if section_id not in cited:
            raise ConsentControlsMapError(
                f"`{where}.adr` cites {cited or 'no ADR-0026 section'} — a"
                f" section's id must agree with the section its own citation"
                f" names (id {section_id!r} would silently mis-index the"
                " sweep)."
            )
        sections.append(Section(id=section_id, adr=adr))
    return tuple(sections)


def _parse_controls(entries: list, section_ids: set[str]) -> tuple[Control, ...]:
    controls: list[Control] = []
    for index, entry in enumerate(entries):
        where = f"controls[{index}]"
        unknown = set(entry) - CONTROL_KEYS
        if unknown:
            raise ConsentControlsMapError(
                f"`{where}` has unknown key(s) {sorted(unknown)} — a control"
                f" declares only: {', '.join(sorted(CONTROL_KEYS))}"
            )
        control_id = _require_slug(entry, "id", where)
        where = f"{where} (`{control_id}`)"
        adr = _require_str(entry, "adr", where)
        _check_cites_adr_0026(adr, where)

        # A control's citation must name a DECLARED section — a dangling
        # reference would silently drop the control out of the section sweep
        # (the same shape as the security map's dangling `backs`).
        cited = adr_0026_sections(adr)
        dangling = [s for s in cited if s not in section_ids]
        if dangling:
            raise ConsentControlsMapError(
                f"`{where}.adr` cites undeclared section(s) {dangling} — a"
                " dangling reference would silently drop the control out of"
                f" the model; declared sections: {sorted(section_ids)}"
            )
        if not cited:
            raise ConsentControlsMapError(
                f"`{where}.adr` cites no ADR-0026 section — every control"
                " lives under a declared section of the ADR."
            )

        # `home` is where the control lives. It is DELIBERATELY optional
        # here: a control with no home is the placement fact the checker
        # reports (#285 AC: the compliance checker flags it). A *declared* home that is
        # not in the closed vocabulary is a different thing — a typo — and
        # fails loudly at load.
        home = entry.get("home", "")
        if not isinstance(home, str):
            raise ConsentControlsMapError(f"`{where}.home` must be a string")
        if home and home not in HOMES:
            raise ConsentControlsMapError(
                f"`{where}.home` is {home!r} — not one of the map's homes"
                f" {sorted(HOMES)}. A control's home is the single owning"
                " layer/service ADR-0026's placement settles (a typo'd home"
                " would silently place the control nowhere)."
            )

        seam = entry.get("seam", "")
        if not isinstance(seam, str) or not seam.strip():
            raise ConsentControlsMapError(
                f"`{where}.seam` must be a non-empty string — where inside its"
                " home the control lives (the surface/capability the ADR's"
                " placement names); the map cites ADR-0026 rather than"
                " restating the control."
            )

        controls.append(Control(id=control_id, adr=adr, home=home, seam=seam))
    return tuple(controls)


# ------------------------------------------------------------ check helpers


def _require_str(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConsentControlsMapError(f"`{where}.{key}` must be a non-empty string")
    return value


def _require_slug(table: dict, key: str, where: str) -> str:
    value = _require_str(table, key, where)
    if not _SLUG_RE.fullmatch(value):
        raise ConsentControlsMapError(
            f"`{where}.{key}` is {value!r} — ids are lowercase slugs"
            " (a-z, digits, hyphens; the map's keys are what the checker and"
            " the later consent lanes name)"
        )
    return value


def _check_cites_adr_0026(adr: str, where: str) -> None:
    if ADR_0026 not in adr:
        raise ConsentControlsMapError(
            f"`{where}.adr` is {adr!r} — every entry cites {ADR_0026} (the"
            " single source; an evolution note such as ADR-0003's `datasets`"
            " capability may accompany the citation, never replace it)"
        )


__all__ = [
    "ADR_0026",
    "CONTROL_KEYS",
    "DEFAULT_MAP_PATH",
    "SECTION_KEYS",
    "HOMES",
    "ConsentControlsMap",
    "ConsentControlsMapError",
    "Control",
    "Section",
    "adr_0026_sections",
    "load_consent_controls_map",
]
