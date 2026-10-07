---
title: The control-placement map — how it works
keywords:
  - placement
  - loader
  - invariants
  - closed-shape
  - threat-frame
mcp-tools: []
---
# The control-placement map — how it works

## Summary

The map is a data file with a **closed shape** and a loader that rejects
loudly, plus an invariant harness that reports placement drift. Two files:
`contract/placement_map.toml` (the data: `[[frames]]` and `[[controls]]`) and
`contract/placement.py` (the loader and the closed home vocabulary). It is
**not** a declaration key — a `[security]`/`[placement]` table inside
`service.toml`/`implementation.toml` is an unknown key there, the same ruling
that made the learning bar declared-by-layout and not by a `[learning]` table.

## Details

1. **The loader validates shape and references, loudly.** A typo'd key fails
   at load (`unknown key(s) …`); a home outside the closed `HOMES`
   vocabulary fails (`not one of the map's homes`); `backs` naming a
   frame that is not declared fails (`undeclared threat frame`); a frame id
   declared twice fails; an `adr` that does not cite ADR-0017 fails. The
   closed-shape scan runs before field checks, so a typo reports the
   "unknown key" error rather than a confusing "missing".
2. **The loader deliberately does NOT reject placement drift.** A control
   with no home, or the same control landed in two places, is exactly what
   the **harness** exists to report (#275's own acceptance criterion) — the
   loader validates shape, the harness validates placement. A *typo'd* home
   is a shape error instead, because the map would otherwise place the
   control nowhere without saying so.
3. **The frame→control direction is derived, not stored.** `controls_for()`
   filters controls by their `backs`, so the two directions of the map are
   one declaration. `cited_sections` collects the ADR-0017 `§N` sections
   written against ADR-0017 across frames and controls — the sweep that
   proves no control section of the ADR is silently unplaced (§6, which
   states the platform does *not* intercept the harness, and §1, which
   carries the frames, cannot appear as a control's section).
4. **The harness stands up one stub owning-capability surface per home**
   (`build_home_stubs()`, reusing the repo's single stub-factory,
   `StubCollaborator`) and asserts four invariants: every §1 frame backed;
   every control homed; no control re-implemented (a duplicated id, or
   ADR-0017 §8's guardrail layer landing twice on one of its sites); every
   named home with a surface. Test-side only, deterministic and offline.
5. **Where it lives, and why.** The checker is **vendored in the template**
   (`contract/`) so the sweeper (#85) can re-verify placement anywhere, and
   the map travels with the copy-to-start ritual: the ritual renames
   `src/<service>/` but never `contract/placement_map.toml`, so the default
   path survives and a copied service sweeps its own copy with no arguments.
   The map's content carries platform-level capability names, never the
   placeholder service name — so a rename leaves no stale text.

## See also

- `docs/capabilities/placement/study-in-depth.md` — why the seam is shaped
  this way (the home decision, the placement-versus-mechanism split).
- ADR-0017 §1–§9 (the model the map indexes) · spec #66 §Testing Decisions
  (the one seam and the invariant-vs-mechanism discipline).
