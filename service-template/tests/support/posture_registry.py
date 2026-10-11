"""The posture registry — where each control's runtime stance is recorded
and read back (ticket #276).

The security-controls map (#275) says a control **has a home**; the posture
registry makes that concrete: **"and its current stance is recorded here."**
Each verification lane (#277–#283) records its control's stance through this
registry, and the coherence bar (#284) reads the whole model back as one
green sweep — so the security posture is auditable as a single reviewable
whole, not a pile of disconnected assertions.

**Contract surface:** the public loader/record/read-back API — the #74/#75
data-surface precedent (a data-surface artifact has no HTTP seam; the seam is
the loader, validated from inline TOML). Inputs in, stance out:
`load_posture_registry()` returns the parsed registry or raises
`PostureRegistryError` naming the offending entry; `record_stance()` writes
an entry and returns the stance as the registry reads it back;
`registry.stance(control_id)` answers the typed stance.

**Closed shape, loud rejections** (the map's discipline, inherited): unknown
keys, a missing field, a stance outside the closed `STANCES` vocabulary, or a
stance keyed on a control the map does not declare all fail at load with a
precise message. The map is the key vocabulary — `load_security_controls_map`
is the source of the control ids the lanes write against, and a stance for an
unmapped control id is a loud rejection, never a silent orphan.

**Home ruling (#276, maintainer-confirmed):** the registry is a TEST-SIDE
support module next to the placement compliance checker — every consumer
(the seven lanes, the coherence bar) is a verification artifact, and the
loader API is its contract surface. If a real running service ever needs to
record a stance at runtime, a production seam gets added then; stage 0 ships
no unused production module (the #275 ruling's plain-data shape).

Test-side only: production code never imports this module. Deterministic and
offline: no network, no clock, no randomness.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from contract.security_controls import SecurityControlsMap, load_security_controls_map

__all__ = [
    "STANCES",
    "STANCE_KEYS",
    "PostureRegistry",
    "PostureRegistryError",
    "Stance",
    "load_posture_registry",
    "record_stance",
]

#: The closed runtime-stance vocabulary the lanes and the coherence bar
#: share. Exported so a lane NAMES a stance, never invents one:
#: `not-yet-verified` (placed, never exercised), `verified-holding` (the
#: lane's behavioral contract passed), `verified-broken` (it failed — the
#: bar goes red on it, honestly).
STANCES = ("not-yet-verified", "verified-holding", "verified-broken")

STANCE_KEYS = {"control", "stance", "lane"}


class PostureRegistryError(ValueError):
    """A posture registry that violates its declared shape.

    Raised at load time: a malformed registry is not a posture record, so it
    must not load half-read (the settled #74/#75 contract — the loader
    validates the closed shape and raises a precise error naming the
    offending entry).
    """


@dataclass(frozen=True)
class Stance:
    """One control's recorded runtime stance: the map's control id, the
    stance value, and the verification lane that recorded it (#277–#283 —
    the audit trail of who verified what)."""

    control: str
    stance: str
    lane: str


@dataclass(frozen=True)
class PostureRegistry:
    """The parsed, validated registry — every recorded stance, keyed by the
    map's control ids.

    The read-back surface the coherence bar (#284) consumes: `stance()`
    answers one control, `covered_for`/`missing_for` sweep the registry
    against a map as DATA (a gap is a fact the bar asserts over, never an
    exception on the first miss).
    """

    stances: tuple[Stance, ...] = ()
    path: Path | None = None

    def stance(self, control_id: str) -> Stance:
        """The LATEST recorded stance for a control (a lane re-verifying
        re-records; the registry answers with the current posture), or a
        loud rejection when no stance is recorded for it."""
        found = None
        for entry in self.stances:
            if entry.control == control_id:
                found = entry
        if found is None:
            raise PostureRegistryError(
                f"no stance is recorded for control `{control_id}` — the map"
                " places it, but no verification lane has recorded its runtime"
                " stance yet (the lane that owns it writes it through"
                " `record_stance`)"
            )
        return found

    def covered_for(self, controls_map: SecurityControlsMap) -> tuple[str, ...]:
        """The map's control ids that carry a recorded stance — sorted, so a
        sweep is stable."""
        recorded = {entry.control for entry in self.stances}
        return tuple(sorted(c.id for c in controls_map.controls if c.id in recorded))

    def missing_for(self, controls_map: SecurityControlsMap) -> tuple[str, ...]:
        """The map's control ids with NO recorded stance — the gaps #284's
        coherence bar reads as data before declaring the model green."""
        recorded = {entry.control for entry in self.stances}
        return tuple(sorted(c.id for c in controls_map.controls if c.id not in recorded))

    def render(self) -> str:
        """One line per stance for the coherence bar's sweep output."""
        head = f"posture registry: {len(self.stances)} stance(s)"
        lines = [
            f"  - {entry.control}: {entry.stance} (recorded by {entry.lane})"
            for entry in self.stances
        ]
        return "\n".join([head, *lines])


# --------------------------------------------------------------- the loader


def load_posture_registry(
    path: str | Path,
    *,
    map_path: str | Path | None = None,
) -> PostureRegistry:
    """Load and validate a posture registry.

    `path` is the registry file (a lane's test writes one under `tmp_path`;
    a lane's suite points at its own). `map_path` resolves the key
    vocabulary through the map loader — a stance for a control the map does
    not declare is a loud rejection naming the entry. A malformed registry
    raises `PostureRegistryError`; an empty one is valid data (the substrate
    ships the scaffolding; it verifies no control).
    """
    path = Path(path)
    if not path.is_file():
        raise PostureRegistryError(f"posture registry not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PostureRegistryError(f"posture registry is not valid TOML: {exc}") from None

    unknown = set(raw) - {"registry", "stances"}
    if unknown:
        raise PostureRegistryError(
            f"unknown top-level key(s) {sorted(unknown)} — the posture"
            " registry declares only the `[registry]` header and `[[stances]]`"
            " entries (closed shape, typos fail loudly). It is NOT a"
            " declaration key: a `[posture]` table in"
            " service.toml/implementation.toml is an unknown key there (the"
            " #75 ruling stands — the FILES are the declaration)."
        )
    registry_table = raw.get("registry")
    if registry_table is not None and (
        not isinstance(registry_table, dict) or set(registry_table)
    ):
        raise PostureRegistryError(
            "`[registry]` is a header with no keys — the registry's shape is"
            " fixed by its loader, not configured per file"
        )
    stances_raw = raw.get("stances", [])
    if not isinstance(stances_raw, list) or not all(
        isinstance(entry, dict) for entry in stances_raw
    ):
        raise PostureRegistryError(
            "`stances` must be an array of tables (`[[stances]]`) — an empty"
            " registry before any lane has run is valid; a non-array is not"
        )

    controls_map = load_security_controls_map(map_path)
    mapped_ids = {control.id for control in controls_map.controls}
    stances = tuple(_parse_stance(entry, index, mapped_ids) for index, entry in enumerate(stances_raw))
    return PostureRegistry(stances=stances, path=path)


def _parse_stance(entry: dict, index: int, mapped_ids: set[str]) -> Stance:
    where = f"stances[{index}]"
    unknown = set(entry) - STANCE_KEYS
    if unknown:
        raise PostureRegistryError(
            f"`{where}` has unknown key(s) {sorted(unknown)} — a stance"
            f" declares only: {', '.join(sorted(STANCE_KEYS))}"
        )
    control = _require_str(entry, "control", where)
    where = f"{where} (`{control}`)"
    if control not in mapped_ids:
        raise PostureRegistryError(
            f"`{where}.control` is not a control the security-controls map"
            " declares — the map is the key vocabulary the verification"
            " lanes write against; a stance for an unmapped control is an"
            " orphan, never a silent extra"
        )
    stance_value = _require_str(entry, "stance", where)
    _validated_stance(stance_value, where)
    lane = _require_str(entry, "lane", where)
    return Stance(control=control, stance=stance_value, lane=lane)


def _validated_stance(stance: str, where: str) -> str:
    """The closed-vocabulary rule, stated ONCE — the loader's parse and the
    record surface reject the same way, so the two can never drift."""
    if stance not in STANCES:
        raise PostureRegistryError(
            f"`{where}.stance` is {stance!r} — not one of the closed"
            f" runtime-stance vocabulary {STANCES} (a lane NAMES a stance it"
            " verified, never invents one)"
        )
    return stance


def _require_str(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PostureRegistryError(f"`{where}.{key}` must be a non-empty string")
    return value


# ---------------------------------------------------------- the record surface


def record_stance(
    path: str | Path,
    *,
    control: str,
    stance: str,
    lane: str,
    map_path: str | Path | None = None,
) -> Stance:
    """Record one control's runtime stance — inputs in, stance out.

    The record surface fails closed like the loader: an unmapped control or a
    stance outside the vocabulary raises BEFORE anything is written. The
    returned `Stance` is what a subsequent `load_posture_registry` reads back
    — the round-trip is the contract (AC 3), not an in-memory echo.
    """
    _validated_stance(stance, "record_stance")
    controls_map = load_security_controls_map(map_path)
    if control not in {c.id for c in controls_map.controls}:
        raise PostureRegistryError(
            f"control `{control}` is not a control the security-controls map"
            " declares — the map is the key vocabulary; nothing is written"
            " for an unmapped control"
        )
    path = Path(path)
    entry = (
        f'\n[[stances]]\ncontrol = "{control}"\nstance = "{stance}"\n'
        f'lane = "{lane}"\n'
    )
    if path.is_file():
        text = path.read_text(encoding="utf-8") + entry
    else:
        text = "# posture registry (ticket #276) — runtime stances, keyed by\n" \
               "# the security-controls map's control ids.\n[registry]\n" + entry
    path.write_text(text, encoding="utf-8")
    return Stance(control=control, stance=stance, lane=lane)
