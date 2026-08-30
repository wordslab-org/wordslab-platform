# ADR-0020 — Evaluation capability of the Training and Evaluation service

**Status:** accepted (resolution of wayfinder ticket "Define what evaluation means in the platform", #16); **amends none**; **sharpens none**; **consumes** the platform's data-consent-and-handling model (its own graduated ticket, #31 — see below); **references** ADR-0013 (Training → Training and Evaluation; chapter `22-training.md` fills on resolution) and ADR-0019 (publishing); **feeds** the `22-training.md` (Training and Evaluation) spec chapter — **deferred until the Training service grilling resolves** (see §"Deferred chapter").

## Context

Evaluation is listed among the centralized platform services, but its concrete meaning at home scale was unresolved. The spec-anatomy session (ADR-0013 §6) renamed the Training service to **Training and Evaluation** and made evaluation a capability of it, with the spec chapter `22-training.md` filling on this ticket's resolution. This ADR resolves what evaluation *concretely is* at home scale: of what, by what, how minimal, and where it appears in the UI.

The soul shapes every decision: **no magic, no black box** — evaluation must be a **user-understood, user-triggered, visible** activity with explained results, never a hidden background scorer, never an automatic rating that silently steers the platform. Home scale is the deliberate inverse of enterprise evaluation infrastructure.

The design draws on the application-centric AI-evaluation methodology of **Shreya Shankar & Hamel Husain** (the *Analyze–Measure–Improve* lifecycle and grounded-theory error analysis). Reference documents are listed in §"Reference documents" — they are the source material for the capabilities and process described here.

## Decision

### 1. What evaluation is

**Evaluation** is the **systematic measurement of the quality/behavior of a versioned, published artifact** — at home scale, an on-demand activity the builder runs on *their own* published thing, producing an explainable quality assessment they can act on.

- **Of what:** a **versioned published artifact** — which is exactly what ties evaluation to the Publishing service (ADR-0019). A published thing is a stable, versioned form, so it is comparable across versions. The subject can be a **model-backed implementation** (an embedded capability / platform extension), or any published thing: **agent / skill / workflow / api / tool / webapp**.
- **By what:** a **pipeline** from an eval dataset, through simulated user inputs, human annotation (open coding → axial coding), an **LLM-as-judge**, to a version comparison report. See §2.
- **How minimal:** entirely home-scale — a single builder, on demand, in an evening. No enterprise eval harness, no labeling workforce, no continuous monitoring in v1.
- **Where it appears:** the **Builder view** of the dashboard (evaluation is a builder activity on the authored/published project), with results also surfacing on the **implementation card** via the `implementation.toml` `links (… evaluations)` field (ADR-0002). **Not** in the always-on metrics right rail (that's live gauges, not eval results).

Evaluation is **deliberately NOT centralized** (ADR-0003) — it lives in the Training and Evaluation service, not the core.

### 2. The evaluation pipeline (Analyze → Measure → Improve)

Evaluation is a **user-triggered workflow** (never automatic, never background) with five stages, matching the Shankar/Husain lifecycle:

1. **Assemble an eval dataset** (`eval.dataset`) — a set of inputs simulating user behavior toward the artifact.
2. **Simulate** (`eval.simulate`) — run the dataset as user inputs against the **versioned published artifact** to gather a **result dataset** (the traces). This is the harness that drives the published thing; it works in tandem with the Publishing service (see §4).
3. **Open coding → axial coding** (`eval.annotate`) — the human review phase. The builder reviews the result dataset **one by one**, writing **free-form annotations** on what works and what doesn't (open coding), in a **generated, task-specific annotation UI**. Then the builder clusters these into a small set of **binary failure modes** (axial coding), forming a **structured rubric**, and annotates more records against it.
4. **LLM-as-judge** (`eval.judge`) — the builder prompts an LLM to score the dataset against the *now-known* failure modes, **automating the scoring of known failure modes** — never the discovery of what's failing. The judge is **validated against the human labels** from stage 3 before it is trusted.
5. **Iterate & compare** (`eval.report`) — the builder improves the artifact, re-runs a new evaluation round, **compares successive versions' results** to choose which is good, and keeps the **history in the project repo** as durable proof.

**Human-gated automation.** The mechanics (data generation, trace collection, judge scoring once validated) are automated; the judgment stays human. The source material's evidence is decisive here: fully-automated error analysis recovers only ~72–87% of human-identified failures and *systematically misses* the class where "the trace looks correct but falls short of a great user experience." So the judge automates scoring of known failure modes, never discovery.

### 3. The capability decomposition

Evaluation is one *workflow* made of several **distinct tools**, so it is **five sibling capabilities** of the Training and Evaluation service (ADR-0002 in-process capability pattern), each with its own business logic, routes, and UI pages, sharing the service's contract surfaces and database:

- **`eval.dataset`** — eval datasets: **import** (downloaded, e.g. from Hugging Face) or **synthetic generation** (personas + target use-cases + source documents → an LLM generates candidate interactions → the LLM and a human **filter** them on quality criteria → a **versioned eval dataset**). Real-usage input comes only from the core's filtered+anonymized log-extraction (see §5) — there is **no raw-traces path**.
- **`eval.simulate`** — run an eval dataset as simulated user inputs against a **versioned published artifact** → a **result dataset** (the traces). The harness that drives the published thing; works in tandem with the Publishing service.
- **`eval.annotate`** — the human review surface: the **generated, task-specific annotation UI** for **open coding** (free-form annotations on the result dataset) and **axial coding** (clustering into **binary failure modes** and annotating more against the resulting rubric). The one non-notebook human surface in the pipeline.
- **`eval.judge`** — the **LLM-as-judge**: an explicit judge implementation, **validated against the human labels** from `eval.annotate` (train/dev/test splits, precision/recall), then scores the result dataset against the rubric.
- **`eval.report`** — **version comparison + history**: compare successive versions' results, produce the eval report, export to the **project repo** as durable proof.

Open coding and axial coding live together in `eval.annotate` — they are one annotation surface that evolves from free notes to rubric-driven labels, not two separate tools.

### 4. Interfaces with other services (precise)

- **Projects** — evaluation is anchored to a **project** (ADR-0019 §6, the shared unit of Development and Publishing). The project stores its **eval datasets, result datasets, and evaluations** (its eval artifacts). History is exported to the **project repo** as durable, portable proof.
- **Publishing** — evaluation works **in tandem** with Publishing: `eval.simulate` needs the **versioned published artifact** (the thing to evaluate) and automates **user-input simulation** against it; and the generated **task-specific annotation UI** is deployed as a **temporary published thing** by the Publishing service for the annotation phase.
- **Development** — evaluation is **notebook-driven**: the builder drives the eval capabilities from a **notebook** (JupyterLab, the Development service), which is the natural continuation of Training's "v1 notebook-driven" shape and the source material's notebook-centric preference. The generated annotation UI is the **one non-notebook human surface**. The capabilities expose **MCP/OpenAPI** so a notebook (or an agent) calls them.
- **Agents** — agents are callers of the eval capabilities: they **generate synthetic data**, **generate the custom annotation UI**, **automate user-input simulation**, **assist during annotation**, and **act as the judge** (`eval.judge`). All via the explicit implementation choice (ADR-0007).

### 5. Data inputs & the platform's data-consent-and-handling model

Evaluation **consumes** the platform's **data consent & handling model** (a platform-wide concern, its own graduated ticket — see §"Graduated tickets"); it does **not** re-implement it. Real-usage input to evaluation comes **only** through the core's log-extraction, which **always** returns data that is (1) **filtered** of secret/private content and (2) **anonymized** of personal data — the single, mandatory boundary for data leaving one user's private sphere and entering a builder's/admin's sphere, mediated through the core. **There is no raw-traces path**: a builder or admin never receives un-filtered, un-anonymized real usage.

The consent model's parts (as settled) — (1) a user's own prompt/input history is private to them alone (access/review/delete on demand); (2) builders/admins access real usage only filtered+anonymized ("better to fail to improve/fix than expose a life-altering secret"); (3) per-interaction consent, default "may use for improvement", with a **very visible "this data is private/secret — do not use" toggle** on every user input; (4) **anonymization is mandatory before any trace enters a dataset** (GDPR — personal data in a project-repo dataset is illegal in Europe), best-effort via data replacement, and must **not** degrade evaluation/training quality. Cases where anonymization is genuinely impossible (e.g. fraud detection on national-ID card images) are **out of v1 scope** — the user's responsibility to build a proper, legal processing pipeline.

So `eval.dataset`'s real-input sources are: **anonymized datasets** from the core's log-extraction (the only real-usage path) · **downloaded** datasets (Hugging Face etc.) · **synthetic** (grounded on the anonymized real data's dimensions). The synthetic pipeline grounds its personas/dimensions in the anonymized real data.

### 6. The judge implementation & the eval store

- **Judge implementation** — the LLM-as-judge is itself a model-backed thing running through the platform. Under **ADR-0007**, it is an **explicit implementation choice** with its privacy tier surfaced before the run (there is **no hidden/automatic judge**). **Local by default** (the data being scored — the result dataset — is the user's own business data / possibly from anonymized logs; keeping it local is the privacy-preserving default), with a **cloud** implementation as an explicit choice.
- **Eval store — Arize Phoenix, vendored + local.** Evaluation uses **Arize Phoenix** as its evaluation store, **vendored and run locally** as a component of the Training and Evaluation service (the vendored-proven-OSS-UI principle and the soul). Phoenix is the panel-verified "favorite open source eval tool": open-source, local-first, notebook-centric, hackable, runs fully locally. The **generated task-specific annotation UI** is the human surface on top of it; results/history are additionally **exported into the project repo** as the durable, portable proof.

### 7. Boundary with `implementation.toml` ranks (no in-platform link)

The `accuracy` / `size` / `speed` ranks in `implementation.toml` (ADR-0002 §5) and the `supported`/`recommended` computation (ADR-0005) are **manually authored by the builder** — nothing is automatic (the soul, ADR-0016). The builder *may* run the evaluation process to gather the data they need to write those ranks, but there is **no direct, in-platform link** between evaluation and `implementation.toml`. Evaluation is the builder's own on-demand quality check; it produces **eval reports** in the project repo; the ranks are a separate, manually-authored declaration. They do not conflate.

### 8. Audience

Evaluation is run by the **builder** on **their own** published artifact. At home scale the builder is the **principal domain expert** ("benevolent dictator" — they know what they're building for); annotations are the builder's own judgment. Admins do not run evaluations for others; single-builder, self-evaluation.

## Deferred chapter

Per ADR-0013 §6/§7 (the maintenance loop), this resolution would normally also create/update the consuming spec chapter **`docs/spec/22-training.md`** (the **Training and Evaluation** chapter) in the same commit. That is **deferred**: the chapter covers the whole Training *and* Evaluation service, and the Training side (training & fine-tuning capabilities) is not yet settled — writing the chapter now would force inventing the training half. The Training service grilling is graduated as its own ticket (see below), which **blocks** the fill of the `22-training.md` chapter. ADR-0020 is the source of truth for the evaluation half until then.

**Feeds spec chapter `docs/spec/22-training.md` (Training and Evaluation) — deferred until the Training service grilling resolves.**

## Graduated tickets

This resolution graduates two cross-cutting decisions into their own open tickets (per the wayfinder grilling practice — a side-quest that re-visions a different settled scope gets its own ticket, not folded in):

- **#31 — "Design the data consent & handling / GDPR-aware usage-data model (platform core + all services)"** — the platform-wide data consent & handling model described in §5. It is a cross-cutting concern spanning the platform core and all services, not evaluation-specific. Evaluation *consumes* it (its real input is always the core's filtered+anonymized data; the raw-traces path is dropped). It should also surface as a cross-cutting principle in the Foundations chapter / a dedicated ADR when that ticket resolves.
- **#30 — "Sharpen the Training service design (training & fine-tuning capabilities)"** — the training half of the Training and Evaluation service, which is not settled here. This ticket **blocks** the fill of the `22-training.md` chapter.

## Reference documents

The evaluation capabilities and process are designed from the application-centric AI-evaluation methodology of **Shreya Shankar & Hamel Husain**. Source material:

- **Course reader (PDF):** `llm_eval_course_notes_july.pdf` — "Application-Centric AI Evals for Engineers and Technical PMs" (Shankar & Husain, Summer 2025, draft). The *Analyze–Measure–Improve* lifecycle; grounded-theory error analysis (open → axial coding); LLM-as-judge validated against human labels; evaluation at different levels (multi-turn, RAG, agents); custom review interfaces; improvement. *(Also archived at `/opt/data/attachments/llm_eval_course_notes_july.pdf`; the eval-reference distillation is at `/opt/data/handoffs/eval-reference-16.md`.)*
- **Hamel Husain, blog & notes:** hamel.dev/notes/llm/evals/ (topic hub), hamel.dev/notes/llm/ai-product-engineering/, hamel.dev/blog/posts/{field-guide, eval-smell, revenge, evals-skills, eval-tools, evals-faq}.
- **Parlance Labs (Hamel Husain):** parlance-labs.com/blog/posts/auto-evals/ — the human-vs-automated error-analysis study (auto systems recover ~72–87% of human-identified failures, miss the "looks correct but falls short" class).
- **Shreya Shankar:** sh-reya.com/blog/{ai-qual-analysis, in-defense-ai-evals}/.
- **evals skills (OSS):** github.com/ai-evals-course/evals-skills — `start`, `error-discovery`, `generate-synthetic-data`, `write-judge-prompt`, `validate-evaluator`, `build-review-interface`, etc.
- **Eval tool survey:** the eval-tools panel (LangSmith, Braintrust, Arize Phoenix) informing the Arize Phoenix choice.

## Considered options

- **One evaluation capability vs several distinct capabilities** — evaluation is one *workflow* but several *distinct tools* (dataset, simulation, annotation, judge, reporting); folding them into one capability would blur their distinct business logic, surfaces, and UIs. Chose **five sibling capabilities**.
- **Evaluation produces vs verifies the `accuracy` ranks** — if evaluation wrote back into `implementation.toml`, ranks would mix declared facts with human quality evidence; the source material and the soul favor keeping them separate. Chose **separate**: ranks are manually authored, eval is the builder's own on-demand check, no in-platform link.
- **Notebook-driven vs UI-driven evaluation** — UI-driven fights the settled Training "v1 notebook-driven" shape and the source material's notebook-centric preference; a pure notebook flow would bury the human review. Chose **notebook-driven**, with the generated annotation UI as the one non-notebook human surface.
- **Arize Phoenix (vendored, local) vs other eval stores vs bespoke** — Phoenix is the open-source, local-first, notebook-centric tool that fits the soul and the vendored-OSS-UI principle; it is the panel-verified OSS favorite. Chose **vendored + run locally** as the service's eval store, with project-repo export for durable history.
- **Automated vs human-gated judgment** — full automation is a top pitfall (it misses the "looks correct but falls short" class). Chose **human-gated**: mechanics automated, judgment human, judge validated against human labels.
- **Raw vs anonymized real traces** — a raw-traces path would expose un-filtered personal data (GDPR-illegal in a repo, and against the soul). Chose **no raw-traces path**: real input is always the core's filtered+anonymized data.

## Consequences

- **Creates ADR-0020** — the evaluation capability of the Training and Evaluation service (five capabilities + the pipeline).
- **Glossary (CONTEXT.md):** add **evaluation**, **evaluation run**, **eval dataset**, **LLM-as-judge**, **open coding / axial coding**; update the **Training service** gloss to **Training and Evaluation**; add the data-consent-and-handling terms.
- **Graduates #30** (Training service design) and **#31** (data consent & handling model) — see §"Graduated tickets".
- **Defers** the `docs/spec/22-training.md` (Training and Evaluation) chapter until #30 resolves.
- **Feeds** the dashboard (Builder view evaluation surface; implementation-card eval links), Publishing (simulation + temporary annotation-UI deployment), Development (notebook-driven), and the future `22-training.md` chapter.
- **References, does not resolve:** the data consent & handling model (→ #31, open); the Training service (→ #30, open); license (#23), backup (#22), Document/Knowledge (#28), learning experience (#29). One ticket per session — none of these are resolved here.
