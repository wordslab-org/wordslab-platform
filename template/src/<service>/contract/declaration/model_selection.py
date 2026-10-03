"""`supported`/`recommended` — computed, never stored (ticket #74; ADR-0002
§5, ADR-0005).

Which implementations this machine can run (`supported`) and which of those
a service marks `recommended` are pure functions applied at **read time** —
to the parsed `Implementation` declarations (`implementation_toml.py`) and
the machine's **hardware facts** (ADR-0005 §2) + the **model-selection goal**
(the per-service install-level setting, `accuracy`/`size`/`speed`/`balanced`,
CONTEXT.md — changeable from the dashboard). No goal → no recommendation;
every flag that could go stale is absent.

Scope fence: this module is the *declaration-side* gate (required
technologies + install-disk fit). The full ADR-0005 §4 fit test — evaluating
the running formula for memory fit at minimum parameters against the
reservation ledger — is the installer/topology machinery's (ADR-0004/0005),
not the template's: formulas are declared strings here, evaluated where the
ledger lives.

This module computes; it never writes. Declarations carry only factual
inputs (ranks, sizes) — check ticket #74's resolution comment before adding
a `recommended` key anywhere.
"""

from __future__ import annotations

from .implementation_toml import Implementation

# The model-selection goals, verbatim from CONTEXT.md (*Model selection goal*).
GOALS = ("accuracy", "size", "speed", "balanced")


def validate_goal(goal: str | None) -> str | None:
    """Validate a goal string (or None for 'no recommendation')."""
    if goal is None:
        return None
    if goal not in GOALS:
        raise ValueError(f"unknown model-selection goal {goal!r} (CONTEXT.md's enum: {GOALS})")
    return goal


def compute_supported(
    implementations: list[Implementation],
    hardware: dict,
) -> list[Implementation]:
    """Which declarations this machine can run, hardware facts in (ADR-0005
    §2: `{"disk_free_gb": float, "technologies": {feature: bool}}`).

    A `local-weights` implementation is supported when its required
    technologies are all present and its install disk fits the free disk.
    BOTH are hard gates — a missing/unknown hardware quantity never
    silently passes (quantity fit is the hard gate, ADR-0005 §4). A
    `cloud:*` implementation does not consume this machine — always
    supported. Declaration order preserved.
    """
    disk_free = hardware.get("disk_free_gb")
    technologies = hardware.get("technologies") or {}
    supported: list[Implementation] = []
    for impl in implementations:
        if impl.source.startswith("cloud:"):
            supported.append(impl)
            continue
        required = impl.resource_profile.technologies
        tech_ok = all(technologies.get(t, False) for t, needed in required.items() if needed)
        # Hard gate: an unknown disk_free (None, or a non-number) fails the
        # quantity fit — never a silent pass.
        disk_ok = (
            isinstance(disk_free, (int, float))
            and not isinstance(disk_free, bool)
            and impl.resource_profile.disk_gb <= disk_free
        )
        if tech_ok and disk_ok:
            supported.append(impl)
    return supported


def compute_recommended(
    supported: list[Implementation],
    goal: str | None,
) -> Implementation | None:
    """Which **supported** implementation to mark `recommended` — None when
    there is no goal (no goal → no recommendation). Selection per goal, from
    the candidates' *declared* facts only:

    - `accuracy` — the best `[ranks].accuracy` (lowest rank number).
    - `speed` — the best `[ranks].speed` rank.
    - `size` — the smallest install disk (`[resource-profile].disk_gb`).
    - `balanced` — the mean of the two ranks, then smaller disk as the
      deterministic tie-breaker. *This weighting is template-owned, the one
      choice ADR-0002 left open; recorded here and on ticket #74.*

    A candidate with no declared rank ranks equally last (order-preserving);
    name is the final deterministic tie-breaker.
    """
    validate_goal(goal)
    if not goal or not supported:
        return None
    unranked = float(len(supported) + 1)  # worse than any real rank

    def _rank(impl: Implementation, which: str) -> float:
        value = impl.ranks.get(which)
        return float(value) if value is not None else unranked

    if goal == "size":
        def size_key(impl: Implementation) -> tuple[float, str]:
            return (impl.resource_profile.disk_gb, impl.name)
        key = size_key
    elif goal == "balanced":
        def balanced_key(impl: Implementation) -> tuple[float, float, str]:
            return (
                (_rank(impl, "accuracy") + _rank(impl, "speed")) / 2,
                impl.resource_profile.disk_gb,
                impl.name,
            )
        key = balanced_key
    else:
        which = "accuracy" if goal == "accuracy" else "speed"

        def rank_key(impl: Implementation) -> tuple[float, str]:
            return (_rank(impl, which), impl.name)
        key = rank_key

    return min(supported, key=key)
