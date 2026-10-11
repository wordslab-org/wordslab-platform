"""The consent-controls compliance checker (ticket #285) — the test-side,
cross-cutting assertions that keep ADR-0026's placement claim checkable
*from the first service* (the build order's testability rule; spec #67).

Vocabulary note: this is a **test harness / compliance checker**. In an
agentic platform "harness" alone reads as the *AI agent harness* — so the
module, its functions, and its docs always say **compliance checker** or
**test harness** (the agent harness ADR-0026 §6 bounds is a different thing
entirely).

The checker stands up a **stub owning-home surface** per home the map names
(each a `StubCollaborator` — the repo's single stub-factory, wired via the
service factory's `extra_routes`, never a mock of internals), then asserts
the placement invariants against the map:

1. **every declared ADR-0026 section places at least one control** — a
   control-carrying section with no control is an unplaced part of the model;
2. **every control has a home** — a control the model names but never places
   is homeless;
3. **no control is re-implemented in two places** — a control id landed in
   two places. (A home legitimately hosts several DISTINCT controls — the
   template carries the flag, the exclusion, the extraction surface and the
   data-shape declaration — so the invariant is about a control's identity,
   never a count of controls per home.)
4. every home a control names has a stub owning-home surface;
5. **every consent-bearing home carries the required pair** — the consent
   flag and the never-bypassable private/secret exclusion (#285 AC 3: the
   checker flags a service/template that ships a consent-bearing surface
   without the flag or without the exclusion).

Test-side only: production code never imports this module (spec #68). The
stubs here stand in for the OWNING HOMES at their contract surfaces — the
real seams are #72 (the shipped flag + gate in `contract/base/consent.py`,
whose BEHAVIOR is tested there — this checker asserts only *placement*, the
#66-style no-double-testing rule), #62/#111 (the core `datasets` capability,
not yet built — hence the stub), and #48 (the assistant container and the
sphere gate at the callable surface).

The sweep entry point (`check_consent_controls`) is what the test-harness
sweeper (#68/#85) calls to re-verify placement per service: it loads the map
(the service's own copy — the map travels with the copy-to-start ritual),
stands the stub surfaces up, and returns a report the runner can print
pass/fail. #85 does not exist yet, so this is an explicit, documented entry
point proven by this ticket's own tests against the template/canary — not an
integration with a sweeper that isn't there.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contract.consent_controls import ConsentControlsMap, load_consent_controls_map

from tests.support.stubs import StubCollaborator

__all__ = [
    "CONSENT_BEARING_REQUIREMENTS",
    "HOME_STUBS",
    "ComplianceReport",
    "build_home_stubs",
    "check_consent_controls",
    "compliance_findings",
]


# ---------------------------------------------------------------------------
# The stub owning-home surfaces — one per home the map may name.
#
# Each entry is the CONTRACT SURFACE a home exposes, stood up as a
# `StubCollaborator` so placement can be asserted from the template with no
# real service present. The path names the home and the seam the map cites;
# the real paths belong to the owning service's spec (see the module
# docstring). `stable_name` records the capability-registry name where the
# ADRs name one (ADR-0008 §8) — recorded as data, never probed.
# ---------------------------------------------------------------------------

HOME_STUBS: dict[str, dict[str, str]] = {
    "template": {
        # the template home is the copied service's own input/extraction
        # contract (`contract/base/consent.py`, #72) — its surface is the
        # consent-bearing input surface every service ships.
        "path": "/v1/consent/input-surface",
        "seam": "consent flag + gate",
    },
    "core": {
        # the core's `datasets` capability is not built yet (#62/#111) — the
        # ADR names its registry entry, so the stable name is recorded as
        # DATA, never probed (the #275 pattern for unbuilt homes).
        "path": "/v1/core/datasets",
        "seam": "datasets boundary",
        "stable_name": "core.datasets",
    },
    "chat-and-agents": {
        # the assistant's session container is execution state the core's
        # `resources` allocates, not a discoverable capability (ADR-0008 §2:
        # workspaces/environments stay out of the registry) — so no stable
        # name; the sphere gate itself rides every service's callable surface.
        "path": "/v1/chat/sessions",
        "seam": "assistant container",
    },
}


def build_home_stubs() -> dict[str, StubCollaborator]:
    """One stub owning-home surface per home, keyed by home.

    Each is a real contract surface (a `StubCollaborator`, deterministic and
    offline) that a test wires into a service with
    `InProcessService(extra_routes=[...])` — so a home's surface is exercised
    over the one HTTP seam, never against internals.
    """
    return {
        home: StubCollaborator(
            path=spec["path"],
            body={"home": home, "seam": spec["seam"], "surface": "stub-ok"},
        )
        for home, spec in HOME_STUBS.items()
    }


#: The homes that ship consent-bearing surfaces, and the pair each MUST
#: place: the consent flag and the never-bypassable private/secret
#: exclusion (ADR-0026 §1/§2 — the build order's testability rule: present
#: in every service's surfaces from the first service). The template home is
#: where a copied service's user-input and extraction surfaces live; the
#: core's boundary controls ARE the §2 passes (the gate filter is the
#: exclusion at the boundary, homed explicitly by id), and Chat + Agents'
#: controls are the identity/container pair of §6 — so the required pair is
#: stated as explicit data per home, never inferred by a heuristic.
#: The ids are the map's control ids — the map is the key vocabulary.
CONSENT_BEARING_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "template": ("consent-flag", "private-secret-exclusion"),
}


@dataclass(frozen=True)
class ComplianceReport:
    """The checker's answer for one map: what it checked and what it found.

    `findings` is empty exactly when the placement invariants hold — the
    sweeper prints the report's `render()` line per service, so "placement is
    green" is a fact read off the map, not a promise.
    """

    findings: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    homes: tuple[str, ...] = ()
    path: Path | None = None

    @property
    def green(self) -> bool:
        """Placement holds: no homeless control, no section without a
        control, no double-homed control, no home without a surface, no
        consent-bearing home missing the required pair."""
        return not self.findings

    def render(self) -> str:
        """One pass/fail line for the sweeper's per-service output."""
        state = "green" if self.green else f"RED ({len(self.findings)} findings)"
        line = (
            f"consent placement {state}: {len(self.sections)} sections, "
            f"{len(self.controls)} controls, {len(self.homes)} homes"
        )
        if self.green:
            return line
        return "\n".join([line, *(f"  - {finding}" for finding in self.findings)])


def compliance_findings(
    controls_map: ConsentControlsMap,
    *,
    surfaces: dict | None = None,
) -> list[str]:
    """The placement findings for `controls_map` — empty when the invariants
    hold.

    `surfaces` is the set of stood-up owning-home surfaces, keyed by home
    (defaults to the checker's own `HOME_STUBS`); a control whose home has
    no surface is a finding, so the map and the stub set can never drift
    apart silently.
    """
    surfaces = HOME_STUBS if surfaces is None else surfaces
    findings: list[str] = []

    # (1) every declared ADR-0026 section places >=1 control.
    for section in controls_map.sections:
        if not controls_map.controls_for(section.id):
            findings.append(
                f"section `{section.id}` ({section.adr}) places no control —"
                " a control-carrying section of the ADR with no placed"
                " control is an unplaced part of the model"
            )

    census: dict[str, list[str]] = {}
    for control in controls_map.controls:
        census.setdefault(control.id, []).append(control.home or "<no home>")
        # (2) every control has a home.
        if not control.home:
            findings.append(
                f"control `{control.id}` ({control.adr}) has no home — a"
                " homeless control is a control the model names but never"
                " places"
            )
            continue
        # (4) the home has a stood-up surface.
        if control.home not in surfaces:
            findings.append(
                f"control `{control.id}`'s home `{control.home}` has no stub"
                " owning-home surface — the map names a home the checker"
                " cannot stand up, so its placement cannot be asserted"
            )

    # (3) no control is re-implemented in two places — the SAME control
    # landed twice (a duplicated id, whatever the homes): the model names one
    # control and places it twice. Two DISTINCT controls sharing one home is
    # legal (the template carries the flag, the exclusion, the extraction
    # surface and the data-shape declaration).
    for control_id, homes in sorted(census.items()):
        if len(homes) > 1:
            findings.append(
                f"control `{control_id}` is landed in {len(homes)} places"
                f" (homes {homes}) — a control re-implemented in two places is"
                " duplicated placement: the model names one control, so it has"
                " exactly one home"
            )

    # (5) every consent-bearing home carries the required pair (#285 AC 3):
    # a service/template that ships a consent-bearing surface WITHOUT the
    # consent flag or WITHOUT the never-bypassable exclusion is flagged.
    homed_by_home: dict[str, set[str]] = {}
    for control in controls_map.controls:
        if control.home:
            homed_by_home.setdefault(control.home, set()).add(control.id)
    for home, required in sorted(CONSENT_BEARING_REQUIREMENTS.items()):
        placed = homed_by_home.get(home, set())
        for control_id in required:
            if control_id not in placed:
                findings.append(
                    f"consent-bearing home `{home}` does not place control"
                    f" `{control_id}` — a consent-bearing surface without the"
                    f" {control_id} is an ADR-0026 §1/§2 breach (the flag and"
                    " the never-bypassable exclusion are template contracts"
                    " from the first service)"
                )

    return findings


def check_consent_controls(map_path: str | Path | None = None) -> ComplianceReport:
    """Stand the stub surfaces up, load the map and assert placement (the
    sweeper-consumable entry point).

    `map_path` defaults to the shipped map next to the loader, so a copied
    service sweeps its own vendored copy with no arguments. A malformed map
    raises `ConsentControlsMapError` (a load failure — the map is not a
    model); placement drift is reported as findings, never raised, so the
    sweeper can print what is wrong rather than crash.
    """
    controls_map = load_consent_controls_map(map_path)
    stubs = build_home_stubs()
    return ComplianceReport(
        findings=tuple(compliance_findings(controls_map, surfaces=stubs)),
        sections=tuple(s.id for s in controls_map.sections),
        controls=tuple(c.id for c in controls_map.controls),
        homes=tuple(sorted({c.home for c in controls_map.controls if c.home})),
        path=controls_map.path,
    )
