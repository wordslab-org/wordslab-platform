# ADR-0010 — The DocETL abstract-request engine (document transformation engine)

**Status:** accepted (resolution of wayfinder ticket "Design the document transformation engine (DocETL pipelines as an abstract request)", #24); **refines ADR-0009** (operator dispatch = faithful representation vs interpretation; Document's surface = representation capabilities, not a DocETL operator subset); **amends ADR-0007** §6/§11 (the dispatch model behind the abstract request); **§2 output residency amended by #39** (traces/logs are user-sphere, per-service records — never Documents or `data_source`s; output materialization is opt-in, Levels 0–2; the residency boundary test is per-artifact); **consumes ADR-0026** (user sphere = consent boundary; core filter + anonymize) and **ADR-0003** (per-service logs)

## Context

The composition model (ADR-0007 §6) makes **DocETL to unstructured data what SQL is to structured data**: a workflow builds a **DocETL pipeline expression natively in Python** (the Frame-API chain), serializes it as an **abstract request**, and sends it to the **Knowledge service** — the home of the DocETL engine (the Document/Knowledge split, #26 / ADR-0009) — which **optimizes and executes it**, dispatching to the **Document service** where the raw data lives (data locality). This ADR designs the **engine** — the receiving side of the abstract request: the request surface, the optimizer integration, operator dispatch, model routing, execution semantics, and the seam with entity resolution (#25).

The **home is settled** by #26 / ADR-0009 (the engine lives in Knowledge; the request surface is Knowledge's; Document holds the raw data). It is **not re-derived here**; this ticket designs the engine within that home and refines the *mechanism* of dispatch.

The soul shapes every decision: **no magic, no black box** — the optimizer's rewrite is something the user reads and approves; intermediate results are auditable; every model-backed step names its implementation and privacy tier.

## Decision

### 1. Two execution modes — the SQL analogy continued

The engine offers two modes, mirroring ad-hoc query vs prepared/stored procedure:

- **Simple execution** — flexible, **no optimizer**, uses a **default model**. The ad-hoc path: `POST /v1/docetl/requests`. Like typing a query and running it.
- **Stored procedure** — the query is **defined once and associated with a calibration dataset** (and an eval metric). The optimizer (MOAR) runs **offline — potentially hours — on that calibration set** to maximize performance and minimize cost. The resulting **optimized execution plan is stored**; executions **reuse it** until **recomputed** (new models, updated calibration set). Like SQL's prepare/optimize-once-run-many.

The hours-long optimization is a **deliberate, visible act**; the payoff (a reusable plan) is something the user owns and re-runs.

### 2. The abstract-request surface

- `POST /v1/docetl/requests` with body `{pipeline: <serialized YAML>, sources: [<data_source refs>]}` → a **family-5 job** `{id, status: queued|running|completed|failed, progress, result, error?}`; `GET /v1/jobs/{id}` (progress), `POST /v1/jobs/{id}/cancel`, optional family-8 webhook on completion. The pipeline is **inline YAML** (self-contained, readable in run history — no black box).
- **Result = the output + the run trace.** A run yields its **output** — the final transformed dataset *or* derived knowledge, returned to the caller — together with its **run trace**: job status, the optimized plan + **plan-diff**, and per-step log lines. The trace is what makes a run readable and auditable.
- **Traces live in the user sphere, per-service — never as Documents.** Every run's trace/log is retained in the **executing service's own user-sphere store** (an *ad hoc* store fit to its capability; raw per-user logs stay per-service — ADR-0003), correlated by the **family-5 job id** riding the action-context. A trace is **not** a Document and **not** a `data_source`; it reaches builder space **only** through the core's filter + anonymize boundary (ADR-0026).
- **Output materialization is opt-in, at two levels** (declared at pipeline level, with per-run override):
  - **Level 0 — default:** the output is returned to the caller and **not persisted** — no Document, no `data_source`;
  - **Level 1 — output materialization:** only the **final output** persists, **by nature** (the boundary test below);
  - **Level 2 — full intermediate materialization:** every **intermediate dataset** persists as a Document too — the heavy tier, and the one whose stored intermediates are reused as the **free caching byproduct** (§7).
- **The boundary test — per artifact, not per run** (ADR-0009 residency, ADR-0023 delegation): *"a thing I keep and process further"* → **Document** (a materialized dataset/structure, written as a new bundle + `chunks`-kind `data_source` in the user sphere — ADR-0008); *"a thing I now know"* → **Knowledge** (a claim/entity/edge entering the semantic store, ontology-constrained and promoted via the review path, referencing source bundles by stable ID). A run emitting both lands each artifact by its own nature; residency is **per-artifact**, never per-run. Document stays the physical executor of materialized values; Knowledge stays the semantic authority (ADR-0023).
- **Composability (load-bearing):** from **Level 1 up**, a materialized result is itself addressable as a `data_source`, so it can be the `source` of a follow-up request — *the result of a request is a relation you can query again* (the SQL relation analogue).
- **This rule is general, not DocETL-only:** the same opt-in — *"any capability or pipeline output may optionally materialize as a Document (user sphere); the default is not persisted"* — holds for a direct capability call as for a DocETL run.
- **The readable run record is guaranteed; full intermediates are the cost knob.** Auditability is a **settled default**, not an open goal: the trace/log is always retained in the user sphere, while Levels 1–2 (and their retention) carry the known disk/complexity cost.

> **Evolution note (#39 — output residency):** the earlier §2 wording — *"the result = final transformed dataset **and** execution trace"*, *"all output files are persisted as new documents in Document"*, and *"intermediate-result auditability is recorded as a goal with a known cost, not a hard guarantee"* — is **superseded**. Traces/logs are **user-sphere, per-service** records (not Documents, not `data_source`s; builder access only through the core's filter + anonymize — ADR-0026), and output persistence is **opt-in** (Levels 0–2), not automatic. The readable run record is now a **settled default**; only full intermediate materialization remains a build-time cost knob. *(Resolved by #39; back-pointed from the #37 v1-scope ledger, `20-concerns/27`.)*

### 3. Operator dispatch — faithful representation vs interpretation

The engine routes each step by **one question**, not by a per-operator home table (the table proved too complex for a user to hold while authoring a request):

- **Document service** produces **faithful representations** of a document/bundle's content — office/PDF/HTML form, image form, markdown form, the **different ways to split** the content, **contextualized splits**, **raw structured-data extractions**, and **embeddings for all of these**. These are *easier ways to consume the exact content* — **no reflection or interpretation**; a human who can read can glance and verify the representation matches the source.
- **Knowledge service** does **everything else** — chooses the *most convenient representation* for the task, **summarizes, thinks, cross-checks data between documents — even inside a single bundle**.

**Document's surface is a set of representation capabilities** (parse-to-markdown, split+contextualize, extract-raw-fields, embed, retrieve) — its native APIs, **not a subset of DocETL operators**. The engine (in Knowledge) runs the **reasoning** and **calls Document to fetch representations** on demand, over the LAN via Document's callable surface and `data_source` entries (ADR-0004) — **no new transport machinery**. The engine is the orchestrator; Document is the representation provider executing where the data lives.

**Representation spans every modality.** A phone call, meeting recording, or real-world photo is a source whose faithful representations live in a Document bundle, alongside its raw media. The modality services produce the representations: **Image** → text captions + photo embeddings; **Audio** → transcription + speaker diarization + (optionally) tone/hesitation markers + audio embeddings. **Everything is stored together in a document bundle**, with **all embeddings aligned in the same vector space** (a Document index concern) so retrieval and similarity work across modalities. The partnership pattern holds: modality services *capture* faithful representations (verifiable by looking/listening); **Document aggregates and indexes** them; **Knowledge reasons across them**.

### 4. Model routing (privacy)

- Every LLM-powered step routes through the **Inference service** as an **explicit implementation choice** (ADR-0007 §10, ADR-0006) — never a raw external key, no inference policy, no auto-fallback.
- A pipeline declares a **default implementation** (carrying its **privacy tier**) at the **pipeline level**, with **per-operator overrides** where a specific step needs a different model.
- **Model cascades stay within explicitly-named implementations:** the author names the cascade chain (e.g. "for this `reduce`, escalate over `[local-8b → local-32b]`"); the runtime escalates only within that pre-approved set, never to anything unlisted. Escalation choices are visible in the trace.
- **MOAR's model changes flow through the review** (the "optimizer proposes, human disposes" rule): a swapped model appears in the diff and is approved before the plan is stored — final implementations remain explicit even after optimization.
- A refused implementation or **`cloud-spend` 429** (ADR-0005 §9) **surfaces and the user re-chooses** — no silent fallback.

### 5. The optimizer integration (the soul's test)

- Both optimizers are **engine-internal** (Knowledge service machinery; not new composition primitives, not separate services).
- The engine **exposes the optimized declarative pipeline** (the rewritten YAML) so the user reads it — surfaced **before execution** as a reviewable preview, and in the **execution trace** alongside the run.
- **Model cascades** run per-operator at runtime (cheap model first, escalate on validation failure), mapped onto explicit implementations, choices visible in the trace.
- **MOAR** is an **explicit, user-invoked** offline optimization step (never silent). It tries rewritten variants on the calibration data sample and returns **candidate optimized plans** for the user to review and **pick from** — the best shown as a diff ("I reordered your operators, split→map-per-chunk→reduce, changed the model here"), each rewrite explained.
- **The optimizer proposes; the human disposes.** No invisible rewrite-and-execute.

### 6. The stored-procedure lifecycle

Reusing the Studio vocabulary (family 9: definition → deployment → run) plus family-5 jobs:

- **Define** — `POST /v1/docetl/procedures` `{name, pipeline, calibration_dataset, eval_metric}` → id, status `defined`.
- **Optimize** — `POST /v1/docetl/procedures/{id}/optimize` → a family-5 job (the hours-long MOAR run); on completion the **optimized plan is stored**; status `optimizing → optimized`. The job shows progress + the candidate plans as scored.
- **View plan** — `GET /v1/docetl/procedures/{id}/plan` → the stored optimized YAML **plus the rewrite diff/explanation**.
- **Execute** — `POST /v1/docetl/procedures/{id}/execute` `{sources}` → a family-5 job that runs the **stored plan** → result files + trace (the surface shape).
- **Recompute** — call `optimize` again (new models / updated calibration set) → a new plan.
- **Delete** — `DELETE /v1/docetl/procedures/{id}`.
- **Versioning:** each `optimize` produces a **new plan version**; executions run against the **current (latest)** plan unless the caller **pins a specific version**. Recomputing never silently changes a pinned caller.

### 7. Execution semantics

- Runs are **family-5 jobs** with **per-step retries with backoff**; a side-effecting step retries under the base contract's `Idempotency-Key` so a retry doesn't double-fire (ADR-0001 base §7, ADR-0007 §8).
- **Caching is a free byproduct** of storing intermediate results as full documents in bundles: a re-run over unchanged sources references the already-stored intermediate bundles; the trace marks what was reused. No separate cache machinery.
- **Parallelism = as much as the platform allows:** local → the **max batch size per implementation** (from the resource running-formula / declared batch range); cloud → **server-managed** on the provider's side. **No author concurrency knob.**
- **Batch-capable representation extraction is load-bearing for GPU saturation**, especially VLMs over many document pages (OCR, layout, image understanding). The **representation-extraction capabilities in Document, Image, and Audio must offer batch operations over sets of elements** (many pages/images/segments in one call), not just single-element calls, so GPU capacity stays saturated — mapped onto the platform's **family-6 batch contract** and the resource layer's batch fit lever.
- `cloud-spend` 429 / resource refusal → surface + user re-chooses (no silent fallback).

### 8. Seam with entity resolution / grounding (#25)

The engine **executes** pipeline reasoning steps (including `resolve` / `extract` / grounding) but **does not own the grounding machinery** — it **composes with #25's capability** (entity-resolution / concept-repo / graph surface, an in-Knowledge capability per ADR-0002), which owns the controlled vocabulary, stable IDs, dedup, and graph storage. A stored procedure whose optimized plan uses `resolve` depends on #25's concept repo at run time.

## Considered options

- **Two modes vs a single ad-hoc mode** — the stored procedure gives the optimize-once-run-many pattern and the visible, owned payoff of offline optimization; without it the optimizer has nowhere deliberate to live.
- **Inline YAML vs a file reference for the pipeline** — inline keeps the request self-contained and readable in run history; a file ref adds an indirection with no benefit at this size.
- **Result = single dataset vs final + execution trace** — the trace is the soul's auditability requirement (no black box); several file refs, persisted as documents, make it real.
- **Outputs as composable data sources vs throwaway results** — addressable results are what keeps the SQL relation analogy honest and enables chaining.
- **Representation/interpretation boundary vs a per-operator home table** — the table was too complex for a user to hold while authoring; the representation/interpretation rule is teachable and matches how a user thinks ("do I want a faithful copy, or an interpretation?").
- **Document as representation capabilities vs a DocETL operator subset** — the operator-subset framing conflated raw representation with reasoning; representation capabilities are a coherent, human-verifiable surface.
- **Pipeline default + per-operator override vs per-op tagging everywhere** — the default keeps authoring simple while still allowing targeted override; model cascades and MOAR stay within explicitly-named implementations.
- **Intermediates-as-cache vs a separate cache layer** — intermediates are already stored as documents for auditability; reusing them as the cache is free and visible.
- **Automatic vs opt-in output persistence** — automatically persisting every output *and* the trace as a Document piled traces into Document (wrong: a trace is a user-sphere, per-service log) and made users pay disk for results they never kept. Chose **opt-in materialization (Levels 0–2)**, with traces staying in the user sphere per-service.
- **Resource-driven parallelism vs an author concurrency knob** — the platform already knows max batch per implementation; a knob would add a hidden knob for no benefit, and cloud is server-managed anyway.

## Consequences

- **Creates ADR-0010** (this engine).
- **Amended by #39** — §2 output residency: traces/logs are **user-sphere, per-service** records (never Documents/`data_source`s; builder access only via the core's filter + anonymize — ADR-0026, ADR-0003); output persistence is **opt-in** (Levels 0–2); the **per-artifact boundary test** replaces the automatic "all outputs persisted as documents" rule; auditability is a **settled default** (readable run record guaranteed; full intermediates the cost knob). Back-pointed from the #37 v1-scope ledger (`20-concerns/27`).
- **Amends ADR-0007** §6/§11 — the abstract-request dispatch is now "faithful representation → Document, interpretation → Knowledge"; Document's surface is representation capabilities, not a DocETL operator subset.
- **Refines ADR-0009** §1/§4 — the mechanism wording (Document implements representation capabilities; dispatch is representation/interpretation), while the home (engine in Knowledge, request surface in Knowledge) is unchanged.
- **CONTEXT.md** — add/sharpens "representation" (faithful representation vs interpretation); updates the Knowledge service and Document service / bundle entries for the representation boundary and multi-modal aligned embeddings.
- **Build order** (ADR-0009): Knowledge (the engine) builds **after Workflow**; the **stored-procedure optimize path lands later** — the calibration dataset belongs to the **Training service** (dataset capability), and Training is last in the v1 build order. Simple execution ships first.
- **Feeds** the dashboard (#8 — plan preview + "what changed" diff), the spec anatomy (#12 — this chapter), the capability registry (#20 — pipeline outputs registered as composable `data_source` entries).
- **Glossary (CONTEXT.md):** representation, faithful representation vs interpretation, DocETL pipeline, abstract request (sharpened).
