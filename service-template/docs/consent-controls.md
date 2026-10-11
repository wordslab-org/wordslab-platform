# The consent-controls map + the consent-controls compliance checker

The template ships the platform's data consent & handling model as a
**machine-readable index** plus the **test-side compliance checker** that
keeps the index complete. It is **plain data + test functions — not a
capability** (no `[<service>.<capability>]` section, no catalog entry, no
UI): the #275 ruling, binding on this sibling — a test function declared as
a capability is misleading. Vocabulary: this is a **compliance checker /
test harness** — never bare "harness", which in this platform means the AI
agent harness (ADR-0026 §6 bounds it; a different thing).

## What it is

- `contract/consent_controls_map.toml` — **the map (data)**: the ADR-0026
  sections that place controls (§1 consent capture, §2 the two passes at
  the mediated boundary, §3 the GDPR quality bar's declared data-shape, §6
  the assistant's acting identity), and every consent control ADR-0026
  decides with its ONE owning home, its seam inside that home, and the
  section(s) citing it. The map **cites** ADR-0026 by section; it never
  restates a control's internals. §4 (un-anonymizable cases out of v1) and
  §5 (the builder sphere is anonymize-free — what the platform does NOT
  intercept) place no control and are deliberately not declared.
- `contract/consent_controls.py` — **the loader**: `load_consent_controls_map()`
  returns the parsed map or raises `ConsentControlsMapError` naming the
  offending entry (closed shape — typos and unknown keys fail loudly at
  load).
- `tests/support/consent_controls_check.py` — **the compliance checker**:
  stands up a stub owning-home surface per home (the repo's single
  stub-factory) and reports placement findings — every declared section
  places a control, every control homed, no control re-implemented in two
  places, every home with a surface, and every consent-bearing home
  carrying the required pair: the consent flag + the never-bypassable
  private/secret exclusion. `check_consent_controls()` is the
  sweeper-consumable entry point (#68/#85 re-runs it per service); drift is
  **reported, never raised** — only a malformed map raises.

## The three homes

- **template** — the copied service's own contract: the per-input consent
  flag and the never-bypassable exclusion (`contract/base/consent.py`,
  shipped by #72), the per-service dataset-extraction surface, and the
  declared trace data-shape (ADR-0026 §1/§2, sharpening ADR-0002).
- **core** — the core's `datasets` capability (ADR-0003; #62/#111, not yet
  built — the checker stands up a stub surface and records the registry
  name `core.datasets` as data): the consent-gate filter at the boundary,
  the anonymize pass before storing, dataset provenance, and the
  centralized non-user logs.
- **chat-and-agents** — the Chat + Agents service (#48): the sphere gate at
  every service's callable surface and the assistant's workspace-only
  container (ADR-0026 §6).

## How to use it

1. **Read it** to know *where* a consent control belongs:
   `map.controls_for("2")`, `map.control(id).home`.
2. **Run the checker** (`check_consent_controls()`, no arguments — it finds
   the shipped map next to the loader) and read `report.green` /
   `report.render()`.
3. **Change it only when the model changes**: a new control means a new map
   entry citing ADR-0026 — the ADR stays the source (ADR → template →
   services), never a paraphrase in code.

## Scope fence

The checker asserts *that* each control is placed, never *how* it behaves —
the consent flag/gate behavior is #72's (tested in `test_consent.py`), the
core `datasets` machinery is #62/#111's, the sphere gate and container are
#48's, and the consent lanes own the remembered-default and
revoke-and-delete surfaces. Each mechanism is tested once, in its owning
lane (the #66-style no-double-testing rule).

## See also

- ADR-0026 (the data consent & handling model — the single source) · spec
  #67 (its parent) · #72 (the shipped consent flag + gate) · #62/#111 (the
  core `datasets` capability) · #48 (Chat + Agents) · #285 (this ticket) ·
  #85 (the sweeper that re-runs both placement checkers per service).
- `docs/security-controls.md` — the sibling checker for ADR-0017's security
  model (the shape this one copies).
- `docs/architecture/20-concerns/24-data-consent.md` (the build-view chapter).
