# The per-user export/restore contract + its compliance checker

The template ships ADR-0021 §3's storage constraint as **shipped contract
machinery** plus the **test-side compliance checker** that verifies a
service honors it. Unlike the sibling placement checkers (#275
security-controls, #285 consent-controls — plain-data maps), this contract
is a SURFACE: the closest prior art is the shipped consent contract
(`contract/base/consent.py`, #72) — a base-contract module plus stub-backed
contract tests. Vocabulary: the test-side artifact is a **compliance
checker / test harness** — never bare "harness", which in this platform
means the AI agent harness.

## What it is

- `contract/base/export_restore.py` — **the contract surface**: the route
  pair every service exposes, the shape the core's `backup` capability
  (ADR-0021 §8, registry name `core.backup` — recorded as data, not built)
  will call at the end.
  - `GET /v1/export?owner=&role=[&since=]` — export one user+role's data as
    **one self-contained unit** (ADR-0021 §3). `owner` + `role` are
    REQUIRED: the whole-DB export — the shape ADR-0021 §3 forbids ("would
    capture every user at once and defeat the per-user encryption and
    per-user restore") — is not expressible. `since` selects a
    **true-incremental delta** (records with `seq > since`, ADR-0021 §5).
    The unit is deliberately NOT item-5 paginated: a paginated export is
    not a self-contained unit (ADR-0001 item 5's amendment).
  - `POST /v1/restore` — apply one export unit: a full replaces the
    user+role's records; a delta must chain onto the current high-water seq
    (else 409 `conflict`); the unit's service identity is verified against
    the target (ADR-0021 §7's "provides the same services").
  - The closed unit shape (`service`, `version`, `owner`, `role`, `kind`,
    `since`, `through`, `items`) — unknown/missing keys, values outside the
    closed vocabularies (the three data-sphere roles, the two export kinds)
    are 400 `invalid_request` naming the offending entry.
  - The **store protocol** a service implements (`records` / `high_water` /
    `apply_full` / `apply_delta`) — the contract owns the payload rules;
    the per-service storage design stays each service's own spec.
- `tests/support/export_restore_check.py` — **the compliance checker**:
  stands up a **controlled stub service** (a base-contract–conforming
  service exposing the surface, standing in for Inference/Document/…) and
  probes it over the one HTTP seam: the whole-DB export is not expressible,
  per-user isolation holds, the unit is self-contained, the delta chains,
  the restore gates shapes and chains, full + delta replay reproduces the
  state, and the surface is deterministic. `check_export_restore()` is the
  sweeper-consumable entry point (#68/#85 re-runs it per service as each
  lands from #47 on) and the seam the backup orchestration tickets
  (#270–#272) call when the `backup` machinery is deepened. Contract drift
  is **reported as findings, never raised** — the sweeper prints what is
  wrong rather than crashing on it; a service whose export is whole-DB is
  caught (`WholeDbExportService` is the asserted negative, #269 AC 3).
- The **canary** (#46) carries the user+role attribution on every record
  and wires the surface — the template's demonstration that a service
  passes the contract (`tests/contract/test_export_restore.py`,
  `test_export_restore_check.py`).

## How to use it

1. **Realize it in your service** — wire `export_restore_routes(store,
   service_name=..., version=...)` like any capability surface and
   implement the store protocol over your storage; the contract module owns
   the payload rules and the loud rejections.
2. **Run the checker** (`check_export_restore(client, ...)`) and read
   `report.green` / `report.render()`.
3. **No declaration** — there is no `[backup]`/`[export]` table anywhere
   (#75's ruling: the FILES are the declaration); the surface rides the
   OpenAPI document, and the MCP tools inherit it zero-drift.

## Scope fence

This ships the CONTRACT + the CHECK, not the machinery: the scheduler +
compelled policy + cumulative-uptime cadence is #270's, per-sphere
encryption & packaging #271's, the restore/DR story #272's, the backup bar
#274's. The core `backup` capability itself (ADR-0021 §8) is #62's lane.
The per-service storage design is each service's own spec. The checker
asserts the contract SHAPE over the seam, never a service's storage
internals.

## See also

- ADR-0021 (the backup & recovery story — the single source; §1 spheres,
  §3 per-user extraction, §5 cadence semantics, §7 restore granularity,
  §8 the core `backup` orchestration) · spec #65 (the parent) · #46 (the
  canary) · #270–#272 + #274 (the orchestration tickets that call this
  seam) · #68/#85 (the sweeper) · #269 (this ticket).
- `docs/security-controls.md` / `docs/consent-controls.md` — the sibling
  map-shaped checkers; `contract/base/consent.py` — the shipped-contract
  shape this one copies.
- `docs/architecture/20-concerns/25-lifecycle-and-updates.md` (the
  build-view chapter).
