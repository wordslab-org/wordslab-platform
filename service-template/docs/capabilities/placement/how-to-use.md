---
title: The control-placement map — how to use
keywords:
  - placement
  - security
  - adr-0017
  - load-placement-map
mcp-tools: []
---
# The control-placement map — how to use

## Summary

The control-placement map is the machine-readable index of the platform's
security model (ADR-0017): every threat frame, the controls that answer it,
and the one home each control lives in. You do not edit it to add a feature —
you read it to know *where* a security control belongs, and the invariant
harness tells you the moment the index stops being complete.

## Details

1. **Load the map.** `load_placement_map()` (in
   `contract/placement.py`) reads the map shipped next to it and returns the
   parsed shape; a malformed map raises `PlacementMapError` naming the
   offending entry. Pass a path to load a copy.
2. **Read it as data.** `map.frames` are ADR-0017 §1's threat surfaces
   (`boundary = True` marks one the model declares it does *not* fully
   defend). `map.controls` are the placed controls — each with its `adr`
   citation, its single `home`, its `seam` inside that home, and the `backs`
   frames it answers. `map.controls_for("accidental-data-leakage")` reads the
   frame→control direction, derived from `backs` so the two can never drift.
3. **Run the harness.** `sweep_placement()` (in
   `tests/support/placement.py`, test-side) stands the stub
   owning-capability surfaces up and returns a report whose `findings` are
   empty exactly when every frame is backed, every control is homed, no
   control is landed twice, and every home has a surface. `report.render()`
   gives one pass/fail line for the sweeper.
4. **You change it when the model changes** — a new threat frame or a new
   control in ADR-0017 means a new entry here, never a paraphrase of the
   control in code. The map cites the ADR; the ADR stays the source.

## See also

- `docs/capabilities/placement/how-it-works.md` — what the loader validates.
- ADR-0017 (the security model — the single source) · spec #66 (the security
  model spec and its Testing Decisions).
