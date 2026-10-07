"""The control-placement invariant harness (ticket #275) — the cross-cutting
assertions that keep ADR-0017's placement claim checkable *from the first
service* (the build order's testability rule; spec #66's Testing Decisions).

The harness stands up a **stub owning-capability surface** per home the map
names (each a `StubCollaborator` — the repo's single stub-factory, wired via
the service factory's `extra_routes`, never a mock of internals), then asserts
the placement invariants against the map:

1. **every threat frame of ADR-0017 §1 is backed** by at least one control;
2. **every control has a home** — a control the model names but never places
   is homeless;
3. **no control is re-implemented in two places** — a control id landed in
   two places, or ADR-0017 §8's guardrail layer landing twice on one of its
   sites. (A home legitimately hosts several DISTINCT controls — Connectors
   carries the door's audit, its tier, its approval and its guardrail hook —
   so the invariant is about a control's identity and §8's layer, never a
   count of controls per home.)
4. every home a control names has a stub owning-capability surface.

Test-side only: production code never imports this module (spec #68). The
stubs here stand in for the OWNING SERVICES at their contract surfaces — the
real seams are #48 (session containers, network policy, the agent loop), #50/
#55 (the door, its tiers, its guardrail hook), #58 (Media transforms), #62
(the core's keys/secrets), #63 (the installer's stances), #65 (the update
flow). **#276** (the verification substrate) replaces this collaborator set
with the stub harness / host-OS / LAN surfaces and adds the posture registry
where each control's *runtime stance* is recorded; this module has no stance
and verifies no control's behaviour — it asserts only *placement*.

The sweep entry point (`sweep_placement`) is what the test-harness sweeper
(#68) calls to re-verify placement per service: it loads the map (the
service's own copy — the map travels with the copy-to-start ritual), stands
the stub surfaces up, and returns a report the runner can print pass/fail.
`#85` (the sweeper) does not exist yet, so this is an explicit, documented
entry point proven by this ticket's own tests against the template/canary —
not an integration with a sweeper that isn't there.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contract.placement import PlacementMap, load_placement_map

from tests.support.stubs import StubCollaborator

__all__ = [
    "GUARDRAIL_SECTION",
    "GUARDRAIL_SITES",
    "HOME_STUBS",
    "PlacementReport",
    "build_home_stubs",
    "placement_findings",
    "sweep_placement",
]


# ---------------------------------------------------------------------------
# The stub owning-capability surfaces — one per home the map may name.
#
# Each entry is the CONTRACT SURFACE a home exposes, stood up as a
# `StubCollaborator` so placement can be asserted from the template with no
# real service present. The path names the home and the seam the map cites;
# the real paths belong to the owning service's spec (see the module
# docstring). `stable_name` records the capability-registry name where the
# ADRs name one (ADR-0008 §8) — recorded as data, never probed.
# ---------------------------------------------------------------------------

HOME_STUBS: dict[str, dict[str, str]] = {
    "installer": {
        # the installer is a LAYER, not a base-contract service (ADR-0003): it
        # registers no capability and therefore no registry entry. Its surface
        # is the runbook checkpoint (#63) the mount/TLS stances are checked at.
        "path": "/v1/installer/stance-checkpoint",
        "seam": "runbook checkpoint",
    },
    "core": {
        "path": "/v1/core/secrets",
        "seam": "keys/secrets",
        "stable_name": "core.secrets",
    },
    "chat-and-agents": {
        # the session container / agent loop is execution state the core's
        # `resources` allocates, not a discoverable capability (ADR-0008 §2:
        # workspaces/environments stay out of the registry) — so no stable name.
        "path": "/v1/chat/sessions",
        "seam": "session containers",
    },
    "connectors": {
        "path": "/v1/connectors/audit",
        "seam": "audited door",
        "stable_name": "connectors.audit",
    },
    "inference": {
        "path": "/v1/models",
        "seam": "classic-AI model capability",
    },
    "media-transformations": {
        "path": "/v1/media/transforms",
        "seam": "builtin transforms",
    },
    "lifecycle": {
        "path": "/v1/lifecycle/check",
        "seam": "metadata/check step",
    },
}


def build_home_stubs() -> dict[str, StubCollaborator]:
    """One stub owning-capability surface per home, keyed by home.

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


#: The sites ADR-0017 §8 settles for the guardrail layer — the Inference
#: moderation model + the Media builtin transforms + the two boundary policy
#: hooks (the agent loop's inbound hook and the outbound door hook), exactly
#: the four `guardrail-*` controls the map homes. The duplication invariant
#: checks the layer's sites, NOT the homes: the agent-loop hook and the
#: container network policy share Chat + Agents, the door's audit/tier/
#: approval and the door's guardrail hook share Connectors — every service has
#: more than one control.
GUARDRAIL_SITES: dict[str, str] = {
    "inference": "the moderation model in Inference's classic-AI capability",
    "media-transformations": "the builtin transforms in Media transformations",
    "connectors": "the outbound policy hook at the door",
    "chat-and-agents": "the policy hook in the agent loop",
}

#: The ADR-0017 section that places the guardrail layer — the map's §8
#: controls are the ones whose citation names it.
GUARDRAIL_SECTION = "8"


@dataclass(frozen=True)
class PlacementReport:
    """The harness's answer for one map: what it checked and what it found.

    `findings` is empty exactly when the placement invariants hold — the
    sweeper prints the report's `render()` line per service, so "placement is
    green" is a fact read off the map, not a promise.
    """

    findings: tuple[str, ...] = ()
    frames: tuple[str, ...] = ()
    controls: tuple[str, ...] = ()
    homes: tuple[str, ...] = ()
    path: Path | None = None

    @property
    def green(self) -> bool:
        """Placement holds: no homeless control, no unbacked frame, no
        double-homed control, no home without a surface."""
        return not self.findings

    def render(self) -> str:
        """One pass/fail line for the sweeper's per-service output."""
        state = "green" if self.green else f"RED ({len(self.findings)} findings)"
        line = (
            f"placement {state}: {len(self.frames)} frames, "
            f"{len(self.controls)} controls, {len(self.homes)} homes"
        )
        if self.green:
            return line
        return "\n".join([line, *(f"  - {finding}" for finding in self.findings)])


def placement_findings(
    placement_map: PlacementMap,
    *,
    surfaces: dict | None = None,
) -> list[str]:
    """The placement findings for `placement_map` — empty when the invariants
    hold.

    `surfaces` is the set of stood-up owning-capability surfaces, keyed by
    home (defaults to the harness's own `HOME_STUBS`); a control whose home
    has no surface is a finding, so the map and the stub set can never drift
    apart silently.
    """
    surfaces = HOME_STUBS if surfaces is None else surfaces
    findings: list[str] = []

    # (1) every threat frame of ADR-0017 §1 is backed by ≥1 control.
    for frame in placement_map.frames:
        if not placement_map.controls_for(frame.id):
            findings.append(
                f"threat frame `{frame.id}` ({frame.adr}) resolves to no"
                " control — a frame with no control is an unbacked surface"
            )

    census: dict[str, list[str]] = {}
    for control in placement_map.controls:
        census.setdefault(control.id, []).append(control.home or "<no home>")
        # (2) every control has a home.
        if not control.home:
            findings.append(
                f"control `{control.id}` ({control.adr}) has no home — a"
                " homeless control is a control the model names but never places"
            )
            continue
        # (4) the home has a stood-up surface.
        if control.home not in surfaces:
            findings.append(
                f"control `{control.id}`'s home `{control.home}` has no stub"
                " owning-capability surface — the map names a home the harness"
                " cannot stand up, so its placement cannot be asserted"
            )

    # (3) no control is re-implemented in two places. Two drifts share that
    # shape, and ADR-0017 §8's own placement gives the second one its terms
    # ("no control is re-implemented in two places (guardrails once —
    # Inference model + Media transforms + agent-loop/door hooks; the door
    # once — Connectors; the vault once — the core)", spec #66).
    #
    # (3a) the SAME control landed in two places — a duplicated id, whatever
    #      the homes: the model names one control and places it twice.
    for control_id, homes in sorted(census.items()):
        if len(homes) > 1:
            findings.append(
                f"control `{control_id}` is landed in {len(homes)} places"
                f" (homes {homes}) — a control re-implemented in two places is"
                " duplicated placement: the model names one control, so it has"
                " exactly one home"
            )
    #
    # (3b) §8's guardrail layer re-implemented — each site §8 settles hosts
    #      exactly one of §8's controls.
    for site, ids in sorted(_guardrails_by_site(placement_map).items()):
        if len(ids) > 1:
            findings.append(
                f"ADR-0017 §8's guardrail site `{site}` carries {len(ids)}"
                f" guardrail controls {ids} — the layer is re-implemented in"
                " two places there: §8 settles one control per site"
                f" ({sorted(GUARDRAIL_SITES)})"
            )

    return findings


def _guardrails_by_site(placement_map: PlacementMap) -> dict[str, list[str]]:
    """ADR-0017 §8's guardrail controls grouped by the site each is homed in
    (a control is a §8 control when its citation NAMES that section — read
    from the parsed citation, never a substring probe of the prose)."""
    by_site: dict[str, list[str]] = {}
    for control in placement_map.controls:
        if GUARDRAIL_SECTION in control.sections and control.home in GUARDRAIL_SITES:
            by_site.setdefault(control.home, []).append(control.id)
    return by_site


def sweep_placement(map_path: str | Path | None = None) -> PlacementReport:
    """Stand the stub surfaces up, load the map and assert placement (the
    sweeper-consumable entry point).

    `map_path` defaults to the shipped map next to the loader, so a copied
    service sweeps its own vendored copy with no arguments. A malformed map
    raises `PlacementMapError` (a load failure — the map is not a model);
    placement drift is reported as findings, never raised, so the sweeper can
    print what is wrong rather than crash.
    """
    placement_map = load_placement_map(map_path)
    stubs = build_home_stubs()
    return PlacementReport(
        findings=tuple(placement_findings(placement_map, surfaces=stubs)),
        frames=tuple(f.id for f in placement_map.frames),
        controls=tuple(c.id for c in placement_map.controls),
        homes=tuple(sorted({c.home for c in placement_map.controls if c.home})),
        path=placement_map.path,
    )
