# V1 scope — what's in the first release, and what's not

**Source of truth: the ADRs cited per row below** (this ledger centralizes already-decided scope boundaries — it cites, never restates, and it does **not** decide anything new). Home of the single "is this in v1 or later?" answer a builder checks.

A Wordslab builder planning a build asks one question before anything else: *is this capability in the first release, or out of it?* Today the answer is scattered across the ADRs — each v1-limiting statement lives where its decision was made, which is exactly right for a decision record and exactly wrong for a builder who wants one place to check. This chapter is that one place: a **ledger of everything deliberately out of v1 scope**, with a back-pointer to the ADR that decided it (the source of truth) and, where one exists, the chapter that restates it. Nothing here re-decides a settled boundary.

The verdicts are not uniform, and the difference matters:

- **Deferred to a future version** — out of v1; the item is genuinely wanted, just not in the first release. It may or may not have a target; the ADR decides.
- **Rejected for v1** — out of v1 scope, and deliberately so, with the reason recorded (often "simplicity is the main feature" / home scale doesn't need it).
- **Open option (v1 default stands)** — a capability that is *not* a settled deferral: the option is genuinely open for a later decision, but a v1 default is in force until then.

---

## The v1 deferral ledger

| Feature / capability | Verdict | Decided by (back-pointer) |
|---|---|---|
| Public-internet gateway (Connectors) | **Deferred** — v1 exposes published things on the LAN + a private-mesh overlay; a public "anyone with the link" demo is future version. | ADR-0019 §9 (restated in `30-services/39-publishing-governance` and `10-concepts/16`) |
| Full Training job-runner (scheduled / managed jobs) | **Deferred** — v1 is notebook-driven + dataset APIs + model upload. | ADR-0025 (restated in `30-services/36-training-evaluation`) |
| Serverless runtime for published things | **Rejected for v1** — small scale + the soul favor always-running containers or static files. | ADR-0019 |
| Multimodal anonymization | **Deferred** — anonymization is text-only in v1; images/audio are a future version. | ADR-0026 (restated in `20-concerns/24-data-consent`) |
| Kuzu standalone graph engine (Knowledge) | **Deferred** — the authoritative Knowledge graph is SQLite vertex/edge tables; Kuzu was archived by its owner (durability risk). | ADR-0011 (restated in `30-services/35-knowledge`) |
| Cypher-capable graph index over Document's Postgres (Apache AGE / SQL-PGQ) | **Open option (v1 default stands)** — *not* a settled deferral: Document's index store already runs PostgreSQL, so a graph-query extension there is a live option a later ticket may weigh. Recursive CTEs serve graph traversal in v1. | ADR-0023 §3 (restated in `30-services/34-document`) |
| Editable workflow canvas | **Rejected for v1** — workflows are Python; a read-only visual view shows the flow, no editable canvas. | ADR-0007 (restated in `10-concepts/14-composing`) |
| Per-user provider keys | **Deferred** — v1 is admin-wide keys; the provider row carries an optional `owner` field (empty = shared) leaving room. | ADR-0006 |
| HA / leader re-election | **Rejected for v1** — single leader; services keep working with the leader down; recovery is a guided rebuild (ADR-0021 makes it minutes). | ADR-0004 (restated in `10-concepts/16`) |
| ROCm & MLX GPU stacks | **Deferred** — v1 is one GPU stack (CUDA); ROCm/MLX kept possible by the per-OS bootstrap, engine variants, and hardware-spanning model implementations. | ADR-0003 |
| Active notifications / alerting | **Deferred** — alerting is dashboard-only in v1; the data contract is the same either way. | ADR-0003 |
| Stronger app sandboxing | **Deferred** — per-app VM isolation and the heavy Shieldstral guardrail tier are not v1; one container per app + scoped network + isolated user/fs is the v1 bar. | ADR-0019 |
| Rate limiting | **Out of v1 scope** — no rate limiting; `429 resource_exhausted` means resource exhaustion (RAM/VRAM/disk/GPU/cloud-spend), nothing else. | ADR-0001 |
| DocETL stored-procedure offline optimization (MOAR) | **Deferred** — simple execution ships first; the offline optimize path lands later (its calibration dataset belongs to Training, last in the v1 build order). | ADR-0010 |
| No shared / networked storage | **Deferred (v1 constraint)** — each machine's disks are local to it in v1; data lives where its service lives; cross-machine movement is backup/restore or reinstall. | ADR-0004 |
| Community machinery (generator CLI, community reviewers, CLA / governance board) | **Deferred until real demand** — solo-maintainer v1, contribution story optimized for one contributor; add machinery only when traffic justifies it. | ADR-0002, ADR-0018 |

This list is the **consolidated** "out of v1 scope" boundary as decided across the ADRs. It is not exhaustive of every deliberate small-scale limit (those are design choices, not deferrals — e.g. no orgs/RBAC/SSO, no key expiry, no scheduler); it holds the items a builder is likely to ask "is this in v1?" about and find deferred or rejected. If a later ticket defers something new for v1, it belongs in this table in the same commit.

---

## Build-time soft spots (re-check when implementing)

A few items are not "is it in v1?" questions but **known-soft areas to re-check at build time** — places where the architecture records a posture that implementation should verify it can honor. Each is a pointer, not a re-decision:

| Soft spot | Posture to re-check (back-pointer) |
|---|---|
| Family-contract verification risks | The risk of a service drifting from its family contracts is real and should be verified at build — a dedicated posture ticket is **open** (`#40`, "family-contract verification-risk posture"); this ledger does not fold its answer in. |
| Rate limiting | Resolved for v1 as **out of scope** (ADR-0001 — see the deferral table above); re-check the posture if rate limiting is ever revisited. |
| DocETL intermediate-trace auditability | Recorded as a **goal with a known cost, not a hard guarantee** — implementation may challenge it (configurable trace retention, sampled/summarized intermediates, final + plan-diff by default with full traces opt-in), preserving the soul's readable-runs intent without locking an unaffordable mechanism. | ADR-0010 |
