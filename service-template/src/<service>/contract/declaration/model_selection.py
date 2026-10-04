"""`supported`/ordering — computed, never stored (ticket #74; ADR-0002 §5,
ADR-0005, **ADR-0031 §5 — declaration model v2**).

Two read-time computations, both pure functions:

- **`compute_supported`** — which implementations this machine can run:
  hardware facts (ADR-0005 §4's hard gates). Never stored.
- **`order_supported`** — the model-selection goal orders the supported
  set: `performance` (intelligence index / Elo) · `speed` · `cost` · `size`
  (declared disk) · `performance-per-dollar` (performance ÷ cost — replaces
  `balanced`). The quality/speed/cost numbers are **dynamic metrics**
  supplied by the caller (the core's implementation-selection code, which
  fetches artificialanalysis.ai at selection time — cache ≤ 1 day; offline
  or unfound → unknown). **Unknown values order last** in every ranking.

This module computes; it never writes, never fetches. The AA fetch is the
core's job (ticket #294) — the template only orders what it is handed.
"""

from __future__ import annotations

from .implementation_toml import Implementation
# The model-selection goals (CONTEXT.md *Model selection goal*, amended by
# ADR-0031 §5: `balanced` retired, `performance-per-dollar` replaces it,
# `accuracy` → `performance`).
GOALS = ("performance", "speed", "cost", "size", "performance-per-dollar")


def validate_goal(goal: str | None) -> str | None:
    """Validate a goal string (or None for 'no ordering')."""
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
    §2: `{"disk_free_gb": float, "ram_free_gb": float, "vram_free_gb":
    float, "technologies": {feature: bool}}`).

    A local implementation is supported when its required CPU/GPU
    technologies are all present and its install-and-run quantities fit the
    machine: disk, RAM, and VRAM (ADR-0005 §4's memory fit when running
    alone at minimum parameters; VRAM gates only implementations that
    declare a non-zero `vram-gb`). ALL are hard gates — a missing/unknown
    hardware quantity never silently passes (quantity fit is the hard gate,
    ADR-0005 §4). A cloud implementation (`is_cloud` — every content part
    is a cloud part) does not consume this machine
    — always supported (the cloud-subscription check is the caller's, with
    its subscription list). Declaration order preserved.
    """
    disk_free = hardware.get("disk_free_gb")
    ram_free = hardware.get("ram_free_gb")
    vram_free = hardware.get("vram_free_gb")
    technologies = hardware.get("technologies") or {}

    def _fits(needed: float, free: object) -> bool:
        return (
            isinstance(free, (int, float))
            and not isinstance(free, bool)
            and needed <= free
        )

    supported: list[Implementation] = []
    for impl in implementations:
        if impl.is_cloud:
            supported.append(impl)
            continue
        req = impl.requirements
        tech_ok = all(
            technologies.get(t, False)
            for t in req.cpu_technologies + req.gpu_technologies
        )
        # Hard gates: an unknown quantity (None, or a non-number) fails the
        # fit — never a silent pass.
        disk_ok = _fits(req.disk_gb, disk_free)
        ram_ok = _fits(req.ram_gb, ram_free)
        vram_ok = req.vram_gb == 0.0 or _fits(req.vram_gb, vram_free)
        if tech_ok and disk_ok and ram_ok and vram_ok:
            supported.append(impl)
    return supported


def order_supported(
    supported: list[Implementation],
    goal: str | None,
    metrics: dict[str, dict],
) -> list[Implementation]:
    """Order the supported implementations by the goal (ADR-0031 §5) —
    best first. `metrics` maps each implementation's **artificial-analysis
    slug** to its current dynamic values: `{"performance": …?, "speed": …?,
    "cost": …?}` — None/missing (or no slug) means **unknown → orders last**.

    - `performance` — highest intelligence index / Elo score first.
    - `speed` — highest speed first.
    - `cost` — lowest cost first.
    - `size` — smallest declared install-and-run disk first (a declared
      fact, not a dynamic metric).
    - `performance-per-dollar` — highest performance ÷ cost first
      (replaces `balanced`); unknown performance or cost (or cost ≤ 0)
      → last.

    No goal → the supported order unchanged (no hidden ranking). Name is
    the final deterministic tie-breaker.
    """
    validate_goal(goal)
    if not goal:
        return list(supported)

    def _metric(impl: Implementation, key: str) -> float | None:
        # Ordering keys off the FIRST content part carrying an AA slug —
        # a bundled implementation is one model + satellites in practice;
        # the alternative (rejecting multi-slug parts) waits for a real need.
        slug = next(
            (p.artificial_analysis for p in impl.contents if p.artificial_analysis),
            None,
        )
        if slug is None:
            return None
        value = (metrics.get(slug) or {}).get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    if goal == "size":
        def size_key(impl: Implementation) -> tuple[float, str]:
            return (impl.requirements.disk_gb, impl.name)
        return sorted(supported, key=size_key)

    if goal in ("performance", "speed"):
        def metric_key(impl: Implementation) -> tuple[int, float, str]:
            value = _metric(impl, goal)
            return (0, -value, impl.name) if value is not None else (1, 0.0, impl.name)
        return sorted(supported, key=metric_key)

    if goal == "cost":
        def cost_key(impl: Implementation) -> tuple[int, float, str]:
            value = _metric(impl, "cost")
            return (0, value, impl.name) if value is not None else (1, 0.0, impl.name)
        return sorted(supported, key=cost_key)

    # performance-per-dollar: performance ÷ cost — unknown on either side → last
    def ppd_key(impl: Implementation) -> tuple[int, float, str]:
        performance = _metric(impl, "performance")
        cost = _metric(impl, "cost")
        if performance is None or cost is None or cost <= 0:
            return (1, 0.0, impl.name)
        return (0, -(performance / cost), impl.name)
    return sorted(supported, key=ppd_key)