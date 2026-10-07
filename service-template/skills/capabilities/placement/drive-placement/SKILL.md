---
name: drive-placement
description: How an agent drives the control-placement checker — load ADR-0017's map, read a frame's controls or a control's home, and sweep placement for findings, over the loader API (`contract/placement.py`) and the harness (`tests/support/placement.py`).
---
# drive-placement

The control-placement checker has **no HTTP surface** — it is a data surface
(a loader plus an invariant harness), so an agent drives it in-process, never
over `/v1`. Load the package the way the template's tests do, then read the
map or sweep it.

```python
import sys; sys.path.insert(0, "src/<service>")   # the template's own suite seeds this
from contract.placement import load_placement_map           # the loader (production code)
from tests.support.placement import sweep_placement         # the harness (test-side)
```

## Load and read the map

`load_placement_map()` takes no argument to load the map shipped next to the
loader; pass a `Path` to load a copy. It returns a `PlacementMap` or raises
`PlacementMapError` (the offending entry is named in the message).

- `map.frames` — ADR-0017 §1's threat frames; `frame.id`, `frame.adr`,
  `frame.boundary` (True only for the frame the model declares it does not
  fully defend).
- `map.controls` — the placed controls; `control.id`, `control.adr` (an
  ADR-0017 §N citation), `control.home` (one of `HOMES`), `control.seam`,
  `control.backs` (the frame ids it answers).
- `map.controls_for(frame_id)` — the controls backing a frame (derived from
  `backs`); an undeclared frame id raises.
- `map.control(control_id)` / `map.frame(frame_id)` — one entry, or raise.
- `map.homes_used` / `map.cited_sections` — the homes in play, and the
  ADR-0017 sections the map cites.

## Sweep placement

`sweep_placement(path=None)` loads the map, stands the stub
owning-capability surfaces up, and returns a `PlacementReport`. Check
`report.green` (or `report.findings == []`); print `report.render()` for one
sweeper-style pass/fail line. Placement drift is **reported, never raised** —
a malformed map is what raises.

## Rules

- Never edit the map to add a feature: it cites ADR-0017, and a control that
  belongs in the model is added to the **ADR** first (ADR → template →
  services).
- The map is not a declaration key — a `[security]`/`[placement]` table in
  `service.toml`/`implementation.toml` is an unknown key and fails the load.
- The harness asserts *that* a control is placed, never *how* it behaves; a
  control's runtime stance is recorded in #276's posture registry, not here.
