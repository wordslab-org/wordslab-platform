"""`recommended` — computed, never stored (ticket #74; ADR-0002 §5, ADR-0005).

Which of the supported implementations a service marks **recommended** is a
pure function of the **model-selection goal** (the per-service install-level
setting, `accuracy`/`size`/`speed`/`balanced`, CONTEXT.md — changeable from
the dashboard) applied to the candidate implementations' declared metadata
(their `[ranks]` and `[sizes]`). No goal → no recommendation: every flag that
could go stale is absent.

This module computes; it never writes. The `implementation.toml` files carry
only the factual inputs (ranks, sizes) — check ticket #74's resolution
comment before adding a `recommended` key anywhere.
"""

from __future__ import annotations

from typing import Any

# The model-selection goals, verbatim from CONTEXT.md (*Model selection goal*).
GOALS = ("accuracy", "size", "speed", "balanced")

ModelSelectionGoal = str  # one of GOALS; validated by validate_goal


def validate_goal(goal: str | None) -> str | None:
    """Validate a goal string (or None for 'no recommendation')."""
    if goal is None:
        return None
    if goal not in GOALS:
        raise ValueError(f"unknown model-selection goal {goal!r} (CONTEXT.md's enum: {GOALS})")
    return goal


def compute_supported(
    implementations: list[dict[str, Any]],
    hardware: dict[str, Any],
) -> list[str]:
    """Which implementations this machine can run (ADR-0002 §5).

    The fit test's quantity gates (ADR-0005 §4): a `local-weights`
    implementation is supported when its required technologies are all
    present on the machine's hardware (`hardware.technologies`, the
    yes/no per-feature capacities — ADR-0005 §2) and its install disk
    fits the hardware's free disk (`hardware.disk_free_gb`). A `cloud:*`
    implementation does not consume this machine — always supported.
    """
    disk_free = hardware.get("disk_free_gb")
    technologies = hardware.get("technologies", {}) or {}
    supported: list[str] = []
    for impl in implementations:
        if not isinstance(impl, dict):
            continue
        source = impl.get("source", "")
        if not isinstance(source, str):
            continue
        if source.startswith("cloud:"):
            supported.append(impl["name"])
            continue
        if not isinstance(impl.get("name"), str):
            continue
        required = impl.get("resource_profile", {}).get("technologies", {}) or {}
        tech_ok = all(technologies.get(t, False) for t, needed in required.items() if needed)
        profile_disk = impl.get("resource_profile", {}).get("disk_gb")
        sizes_disk = impl.get("sizes", {}).get("disk_gb")
        disk_needed = profile_disk if profile_disk is not None else sizes_disk
        disk_ok = disk_free is None or (
            isinstance(disk_needed, (int, float))
            and not isinstance(disk_needed, bool)
            and disk_needed <= disk_free
        )
        if tech_ok and disk_ok:
            supported.append(impl["name"])
    return supported


def compute_recommended(
    supported: list[dict[str, Any]],
    goal: str | None,
) -> str | None:
    """Which **supported** implementation to mark `recommended` — or None
    when there is no goal (`no goal → no recommendation`): every flag that
    could go stale is absent (ADR-0002 §5's computed-never-stored rule).

    Selection per goal, from the candidates' *declared* facts only:
    - `accuracy` — the best `[ranks].accuracy` (lowest rank number).
    - `size` — the smallest `sizes.disk_gb`.
    - `speed` — the best `[ranks].speed` rank.
    - `balanced` — the mean of the two ranks, then smaller disk as the
      deterministic tie-breaker. *This weighting is template-owned, the
      one choice ADR-0002 left open; recorded here and on the ticket.*

    `supported` is the same implementation dicts `compute_supported` filtered
    and re-read from — ranks/disk come from the declaration, never from
    stored flags.
    """
    validate_goal(goal)
    if not goal:
        return None
    candidates = [impl for impl in supported if isinstance(impl, dict) and isinstance(impl.get("name"), str)]
    if not candidates:
        return None

    def _num(impl: dict, *keys: str) -> float | None:
        node: Any = impl
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return float(node) if isinstance(node, (int, float)) and not isinstance(node, bool) else None

    def _rank(impl: dict, which: str) -> float:
        # No declared rank on any candidate → rank equally (order-preserving).
        value = _num(impl, "ranks", which)
        return value if value is not None else float(len(candidates) + 1)

    if goal == "size":
        def size_key(impl: dict) -> tuple[float, str]:
            disk = _num(impl, "sizes", "disk_gb")
            return (float("inf") if disk is None else disk, impl["name"])
        sort_key = size_key
    elif goal == "balanced":
        def balanced_key(impl: dict) -> tuple[float, float, str]:
            disk = _num(impl, "sizes", "disk_gb")
            return (
                (_rank(impl, "accuracy") + _rank(impl, "speed")) / 2,
                float("inf") if disk is None else disk,
                impl["name"],
            )
        sort_key = balanced_key
    else:
        which = "accuracy" if goal == "accuracy" else "speed"

        def rank_key(impl: dict) -> tuple[float, str]:
            return (_rank(impl, which), impl["name"])
        sort_key = rank_key

    return min(candidates, key=sort_key)["name"]