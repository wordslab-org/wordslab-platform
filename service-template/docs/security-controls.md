# The security-controls map + the placement compliance checker

The template ships the platform's security model as a **machine-readable
index** plus the **test-side compliance checker** that keeps the index
complete. It is **plain data + test functions — not a capability** (no
`[<service>.<capability>]` section, no catalog entry, no UI): a test
function declared as a capability is misleading (maintainer ruling on
#275). Vocabulary: this is a **compliance checker / test harness** — never
bare "harness", which in this platform means the AI agent harness
(ADR-0017 §6's, a different thing).

## What it is

- `contract/security_controls_map.toml` — **the map (data)**: ADR-0017's
  five §1 threat frames, and every control ADR-0017 decides with its ONE
  owning home, its seam inside that home, and the frames it backs. The map
  **cites** ADR-0017 by section; it never restates a control's internals.
- `contract/security_controls.py` — **the loader**: `load_security_controls_map()`
  returns the parsed map or raises `SecurityControlsMapError` naming the offending
  entry (closed shape — typos and unknown keys fail loudly at load).
- `tests/support/security_controls_check.py` — **the compliance checker**:
  stands up a stub owning-capability surface per home (the repo's single
  stub-factory) and reports placement findings — every frame backed, every
  control homed, no control re-implemented in two places, every home with a
  surface. `check_security_controls()` is the sweeper-consumable entry
  point (#68/#85 re-runs it per service); drift is **reported, never
  raised** — only a malformed map raises.

## How to use it

1. **Read it** to know *where* a security control belongs:
   `map.controls_for("accidental-data-leakage")`, `map.control(id).home`.
2. **Run the checker** (`check_security_controls()`, no arguments — it
   finds the shipped map next to the loader) and read
   `report.green` / `report.render()`.
3. **Change it only when the model changes**: a new control or frame means
   a new map entry citing ADR-0017 — the ADR stays the source
   (ADR → template → services), never a paraphrase in code.

## Scope fence

The checker asserts *that* each control is placed, never *how* it behaves —
each mechanism is tested once, in its owning service (#66's
no-double-testing rule). The runtime stance of each control is the
verification substrate's (#276) and the seven lanes' (#277–#283).

## The verification substrate (#276)

The shared scaffolding the seven per-control verification lanes consume, so
the verification environment is built once, not per control:

- `tests/support/verification_substrate.py` — **the stub-collaborator set**:
  a **stub agent-harness** (its native accept/refuse surface, ADR-0017 §6 —
  a test flips the verdict, so a control can be asserted to hold *even when
  the harness approves the call*), a **stub shared mount** and a **stub LAN**
  (the host-OS / LAN surfaces the isolation and network-policy lanes
  wander), plus #275's stub owning-capability surfaces — reused via
  `build_stub_collaborators()`, never re-created. Every stub is the repo's
  single stub-factory at its contract seam, served over the one HTTP seam.
- `tests/support/posture_registry.py` — **the posture registry**: where each
  lane records its control's **runtime stance** and the coherence bar
  (#284) reads the whole model back as one sweep. Its contract surface is
  the loader/record/read-back API (`load_posture_registry`,
  `record_stance`, `registry.stance`); stances key on the map's control ids
  — the map is the key vocabulary — and the shape is closed (unknown keys,
  stances outside the vocabulary, and stances for unmapped controls fail
  loudly at load).

The substrate verifies **no control**: it ships the scaffolding plus its own
behavioral contract (a stub harness approving a call, a stub LAN being
wandered, a stance round-tripping through the registry). The per-control
stance assertions are the seven lanes'; the coherence sweep is #284's.
Vocabulary: never bare "harness" — the artifact is the **stub agent-harness**
(what it models is the AI agent harness, ADR-0017 §6's).

## See also

- ADR-0017 (the security model — the single source) · spec #66 (its Testing
  Decisions) · #275 (this ticket) · #276 (the verification substrate) ·
  #277–#283 (the per-control verification lanes) · #284 (the coherence bar).
- `docs/architecture/20-concerns/21-security.md` (the build-view chapter).
