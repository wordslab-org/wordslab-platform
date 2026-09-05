# Wordslab Platform — Architecture Overview

> **Audience:** someone who knows nothing about this project. This document discloses the platform progressively — soul first, then the big picture, then each layer and cross-cutting concern in an order where every concept is defined before it is used. It cites ADRs (the source of truth) rather than restating them. It is an *organized reading companion* to `CONTEXT.md` (the glossary) and `docs/spec/` (the build spec), not a replacement.
>
> **Diagrams** (open in a browser): `docs/diagrams/01-system-overview.html`, `02-services-capabilities.html`, `03-data-knowledge-memory.html`.
>
> **Status flags:** ⚑ marks things that still need clarification or that are inconsistent across the docs today — collected in the final section.

---

## 1. The soul — why this platform exists

Wordslab is a **home-scale AI platform**, 100% built from open-source components and models, aimed at AI enthusiasts at home and in small businesses who want to **own their intelligence**: learn how AI works, own their data, stay in control. It is deployed in a trusted environment at a very small scale — never a "serve millions" system.

The ambition is to be the **ZX Spectrum / C64 of the AI era**: the machine a generation learns on. Everything traces back to three commitments:

1. **Openness** — 100% open source, and honestly visible.
2. **Simplicity** — the main feature; small scale, self-hosted, understandable.
3. **Control** — the user owns their data, chooses their implementations, and sees what the AI does.

The phrase that recurs in every design decision is **"no magic, no black box"**: nothing is silently routed, auto-decided, or hidden. Where most platforms would put a heuristic or a scheduler, Wordslab puts a visible choice and an explanation. This one sentence explains most of the architecture below — when you wonder "why isn't this automatic?", the answer is almost always the soul.

---

## 2. The 10,000-foot view

A Wordslab installation is a **fleet of machines** (your PCs, possibly a rented cloud box) running:

- **Services** — independent, composable components (chat, document, image, inference, …). Each service has **its own database, business logic, UI, and API**, and can run fully standalone — on this machine, another machine, or in the cloud. Services are the unit of independence; there is no shared monolith.
- **A platform core on every machine** — a small control service (fleet, install, catalog, resources, backup, users, keys, secrets, monitoring, logs, datasets). The core **centralizes control only, never the request path, business logic, or data** (ADR-0003).
- **A bootstrap layer** below everything — the native installer/updater with no API and no daemon (ADR-0014).
- **A front door** — a tiny static reverse proxy on the leader machine (`wordslab.local`): the one stable address for the dashboard and every service UI (ADR-0004).

One machine is the **leader** (single, no high-availability in v1); the others are **workers** that join via a short type-in code. The leader's dashboard is the platform's single human front door (ADR-0015).

**Layered installation** (ADR-0004): *Layer 1* = services/capabilities software (the leader gets everything; workers get only what their activities need). *Layer 2* = **implementations** — the concrete, downloadable artifacts: models, engines, harness images — installed per need, gated by a hardware fit check.

## 3. Reading map for the concepts

The rest of this document walks the concepts in dependency order:

| Step | What you learn | Authority |
|---|---|---|
| §4 | What a *service*, *capability*, and *implementation* are | ADR-0001, 0002, 0027 |
| §5 | What surrounds services: bootstrap, core, topology, resources | ADR-0003, 0004, 0005, 0014 |
| §6 | Where models come from: the Inference service, engines, providers, privacy | ADR-0006, 0027 |
| §7 | How things compose: agents, workflows, registry | ADR-0007, 0008 |
| §8 | The full service catalog | CONTEXT.md, map ticket #18 |
| §9 | The data side: Document, Knowledge, memory, consent, backup | ADR-0009–0012, 0023, 0026, 0021 |
| §10 | Security and license — the two policy pillars | ADR-0017, 0022 |
| §11 | Learning and building on the platform | ADR-0024, 0020, 0025, 0018, 0019 |
| §12 | What's open, inconsistent, or flagged | this document |

---

## 4. The anatomy of a service

### 4.1 The uniform service contract (ADR-0001)

Every service speaks the same **base contract**: HTTP/1.1 + JSON + SSE, OpenAPI at `/openapi.json`, per-service Bearer keys, `/v1` versioning, one fixed 11-code error taxonomy, cursor pagination, `/health`, optional idempotency, and `usage` on responses. On top of the base, nine **opt-in family contracts** copy proven industry shapes by reference: the OpenAI **Responses API** (LLM inference), **stateless MCP** (agent tools), **Realtime/WebRTC** (voice), async jobs + model lifecycle, batch, resumable uploads, HMAC webhooks, and authoring/training sessions.

The consequence: everything in the platform is callable three ways — **human UI, agent MCP, deterministic OpenAPI** — and any tool that speaks these industry protocols speaks to Wordslab services without adaptation.

### 4.2 The service template (ADR-0002)

A new service is a **folder copied from `template/`** — no generator, no SDK. Inside, a service is a set of in-process **capabilities**: modules that own their business logic, models, routes, and UI pages while sharing the service's one contract surface, one auth, one `/health`, one OpenAPI, and **one SQLite database**. MCP tools are auto-generated from the OpenAPI spec (zero drift). The UI stack is vendored FastHTML + Alpine.js — no CDN, because a home LAN may be offline.

### 4.3 Capability vs implementation (ADR-0002, 0004, sharpened by 0027 ⚑)

This pair is the platform's central abstraction:

- A **capability** is *what the platform can do* (e.g. `image.generate`, `llm.chat`, `stt`). It has an API that is the union of its implementations' variants.
- An **implementation** is *one concrete way to do it*, with tradeoffs (size/speed/performance). Implementations declare **resource requirements** and get downloaded, loaded, and unloaded. **Models are implementations.**

ADR-0027 sharpened this into **engine/model capability pairs**: `llm.engine` + `llm.model`, `diffusion.engine` + `diffusion.model`, `ml.engine` + `ml.model`. An engine (Ollama, vLLM, ComfyUI, the cloud gateway) is itself an implementation — one the user sees but never installs directly; it's pulled automatically as a model's dependency. Every implementation — service, capability, model, engine — is declared the same way, in **`implementation.toml`**.

⚑ *ADR-0004 still textually lists engines as layer-1 substrate; ADR-0027 reversed this (engines are layer 2) with only a parenthetical amendment in 0004. Read 0027 as canonical.*

### 4.4 What the user installs (ADR-0004)

An **activity** is the user-facing install unit: a pre-configured graph of capabilities. Selecting one installs its implementations (gated by fit) and places them via a **placement simulation** the user confirms — deliberately **no auto-scheduler** (a scheduler is exactly the kind of black box the soul forbids).

---

## 5. Around the services: core, topology, resources

### 5.1 Platform core & trust (ADR-0003)

One core service per machine. It centralizes **control** — fleet, install, catalog, resources, backup, users, keys, secrets, monitoring, logs, stats, datasets — and deliberately **nothing else**: not business logic, not DBs, not the model lifecycle, not raw logs, not backup data, not security mechanics, not data residency. Trust is per-machine identity keys issued via a join code — no PKI, no shared cluster secret, no public ports ever (an internet crossing is a WireGuard/Tailscale overlay).

### 5.2 Topology (ADR-0004)

Leader + workers; the leader can be a cloud node. Placement is a simulation, user-confirmed; **routing is the placement's outcome**, visible per call. Data lives in **data locations** — volumes named after physical disks, with roles as folders inside; no shared storage in v1.

### 5.3 Resources (ADR-0005)

Every resource consumer declares requirements in two states: **at install** (disk + required technologies) and **when running** (RAM/VRAM as a **formula** over configurable parameters — context length, batch size — capped by hardware). A **reservation ledger** tracks bookings against measured capacity; loading books, unloading releases. Eviction is a deterministic idle sweep plus **ask-on-ambiguity** with remembered rules — explicitly **no LRU** (black box). Quotas cover disk and cloud spend (a monthly money cap enforced locally; `429 resource_exhausted` with resource `cloud-spend` when hit).

⚑ *ADR-0004's original two-level concurrency vocabulary (`co-resident`/`swappable`) was replaced by ADR-0005's three explicit levels (`always load jointly` / `load jointly if possible` / `load on demand`); 0004's glossary text is not visibly amended. Read 0005 as canonical.*

---

## 6. Where models come from: Inference, providers, privacy

**The Inference service is the unique model-serving service.** Every model-backed service rides it over HTTP; multiple instances mean model placement, not a new contract (ADR-0002).

**Cloud access is the same shape as local** (ADR-0006): the **cloud gateway is an engine implementation** (reclassified by ADR-0027) fronting external providers (OpenRouter, OpenAI, Anthropic, …). The **provider registry** is leader-core configuration — *add a provider = add a row, not code* — with preconfigured, tested provider cards, bring-your-own-key, and provider **bundles** (models + tools in one subscription). Credentials live in the core's `secrets` vault, distributed at install/rotation.

**Privacy is a property of the chosen implementation** (ADR-0007 §10). Every implementation carries one of three tiers: **`local`** (your machines, data never leaves your control), **`cloud_no_data`** (Zero Data Retention), **`cloud`**. The platform **abolished the inference policy** — there is no `local-then-cloud` routing, no automatic fallback, anywhere. Choosing the implementation *is* the privacy decision, and the UI warns rather than routes.

*ADR-0001's decision text keeps its historical name "the unique LLM inference service" — now annotated by an evolution note (recorded in the #33 sweep); ADR-0006's decision body likewise keeps its pre-0027 capability names (`llm`/`diffusion`/`classic AI`) as historical record. Read ADR-0027 / CONTEXT.md as canonical.*

---

## 7. How things compose: agents, workflows, the registry

### 7.1 Agents vs workflows (ADR-0007)

Two interoperable primitives:

- An **agent** is an interactive, flexible, non-deterministic loop. The platform-native loop is **MAF** (in-process, Python); vendored harnesses (**Hermes Agent, OpenCode, Pi**) are bring-your-own-loop, second-class for composition, driven as workspace sessions.
- A **workflow** is a **plain Python program** — no DSL, no Node-RED — using a tiny primitive set: `call` / `model` / `agent` / `subworkflow` / `delay` / `event` / `user_input`. Branching and loops are ordinary Python; a read-only visual view exists (no editable canvas in v1).

The **agent→workflow graduation path** is deliberate: automation starts as an agent while the problem is fuzzy, then gets formalized into a workflow when it's understood. Invocation follows the caller: deterministic callers get OpenAPI, agents get MCP.

### 7.2 The capability registry (ADR-0008)

A **thin discovery index + name authority on the leader core**. Entries are one of **seven types** — `tool | api | agent | workflow | skill | data_source | webapp` (the last two added by ADR-0019) — holding only an id, type, one-line description with privacy label, and a reference to the owning service (which holds the full definition). **Models are deliberately not in the registry**: choosing a model is a planning decision, not a context-loading lookup. Stable names `<service>.<capability>`; per-agent tool **scoping is enforced server-side** (the accessible set lives in the agent definition).

---

## 8. The service catalog

The v1 platform is **11 services plus one combined service** (settled by the wayfinder map, ticket #18). Grouped by what they do for the user:

**The front door to AI**
- **Chat + Agents** — chat sessions, agent authoring and runs, memory, workspaces. Human surface = vendored **Open WebUI**. Also hosts the platform's continual learning assistant (Hermes Agent, see §11).
- **Workflow** — composes, schedules, and triggers everything (§7.1).

**Understanding your material (§9)**
- **Document** — the raw-material expert: ingest/parse, organize, the 9-part index, hybrid search.
- **Knowledge** — the reasoning expert: ontologies, entity resolution, the knowledge graph.

**Creating and transforming**
- **Generation** — documents/reports/websites *creation*, the output-side counterpart to Document.
- **Image** — generate / edit / video (diffusion models via ComfyUI behind a thin MIT bridge).
- **Audio** — STT, TTS, VAD, voice cloning, realtime voice chat (WebRTC).
- **Media transformations** — ready-to-use transforms: translation, summarization, anonymization, redaction, guardrails.

**The machine room**
- **Inference** — the unique model-serving service (§6).
- **Training and Evaluation** — the dev-side counterpart to Inference: `train.dataset/fine-tune/publish` + `eval.dataset/simulate/annotate/judge/report`. Notebook-driven (JupyterLab is the human surface; no wizard UI); Trackio for training metrics, Arize Phoenix for eval traces; the model **license gate lives at `train.fine-tune`** (§10).
- **Connectors** — the single audited door to the outside world: web, X, Outlook, YouTube, GitHub, HuggingFace (+ a post-v1 seed catalog). Read-only connectors are logged; send/mutate connectors require **caller-identity-scoped human approval**.
- **Development** — code-server, JupyterLab, and an agentic development workflow embodying the platform's guided build process (§11).

**Publishing and governing**
- **Publishing & Governance** (combined 13th service, ADR-0019 + 0018) — packaging/deploying/exposing the result of development (two regimes: platform things follow platform versioning; a builder's generic apps get a separate deployable-packages catalog), plus the compliance catalog (per-machine audit view).

Every service is internally a set of **capabilities** — see diagram `02-services-capabilities.html` for the full capability map.

---

## 9. The data side — the most distinctive part of the design

### 9.1 The Document / Knowledge split (ADR-0009)

One service became two, along a deliberately teachable line:

- **Document** answers *"what's in my documents, where, and how do I find it?"* It owns the raw material: **document bundles** (an email + its attachments + history; a meeting's transcript + slides + agenda), parsed into **faithful representations** — generic, mechanical, task-independent, human-verifiable. Document **stores, indexes, and retrieves — it never interprets**.
- **Knowledge** answers *"what did we learn across them?"* It owns only **derived knowledge** — ontologies, canonical entities, the knowledge graph — **referencing** bundles by stable ID (`document.<bundle>`), never copying content.

The dispatch rule between them is one sentence: **faithful representation → Document; interpretation → Knowledge.**

### 9.2 The 9-part index and the hybrid store (ADR-0023)

Every document is stored at **3 granularities** (chunk / document / bundle) × **3 abstractions** (raw / summary / unsupervised fact-claim triples) = **9 parts**, each vectorized and indexed — a context-length optimization so agents can read a summary instead of the raw text. Document's index store is **PostgreSQL** — a scoped, deliberate exception to SQLite-everywhere, forced by the late-interaction/multi-vector requirement (pgvector + BM25 + JSONB facets + recursive CTEs).

Knowledge computes the semantics and **delegates the computed index values + query execution to Document** (storage delegation). The index is **bidirectional**: chunks are indexed by their grounded concept IDs (*documents → concepts*); concepts are indexed by their source documents (*concepts → documents*).

⚑ *The "summary" boundary is subtle: ADR-0010 lists "summarizing" as interpretation, while ADR-0023 makes generic, uniformly-produced summaries a faithful Document representation. The line is "generic and mechanical vs task-chosen" — the overview must teach it explicitly or readers will see a contradiction.*

### 9.3 Grounding: ontologies, entities, the graph (ADR-0011)

Three layers: **ontology** (classes + relation types + validation rules — LLM-generatable as a *draft* the user reviews and versions; ~50-concept simplicity guideline) → **knowledge bases** (canonical entities) → **knowledge graph** (facts with provenance). `knowledge.entities.resolve` grounds mentions to canonical IDs, scoped to one explicitly-chosen KB — never silent cross-KB search. Storage is SQLite vertex/edge tables — **no graph engine in v1** (Kuzu deferred).

Everything derived carries a **`generated` vs `verified` validation-state qualifier**: model-produced candidates become human-approved facts only through the **review queue** — nothing enters the verified state without a human. This is orthogonal to *who owns* the artifact (the attribution spheres, §9.5).

### 9.4 The DocETL engine (ADR-0010) and knowledge capture (ADR-0012)

Knowledge hosts the **DocETL abstract-request engine** ("SQL for unstructured data"): pipelines authored in Python, executed with an optimizer that shows its plan as a reviewable diff. The **memory substrate** and **knowledge capture** ride the same machinery:

- **Memory**: raw **episodic** memory (conversation transcripts, profile dossier, task history) is Document bundles — non-lossy source of truth; Knowledge lazily **derives** semantic memory (the reasoned profile — itself a KB, resolved with the same grounding machinery). Working memory is the agent loop's context; retrieval is a cited, deterministic, observable capability.
- **Capture**: in a human-in-the-loop session, the minimal change a user corrected or confirmed is **delta-logged** as a *proposed knowledge item* with full provenance. *Capture, not extraction* — the system records that a human changed something; truth is validated at review. The review queue routes items by a one-axis determinism test: **facts/entities → the Knowledge graph; exact repeated procedures → the Workflow service (the graduation path); reusable approaches → a skill.**

### 9.5 Data spheres, consent, and backup (ADR-0021, 0026)

A physical user has **three identities**: `user`, `builder`, `admin` — three **data spheres**, the units of attribution and backup.

- **Consent** (ADR-0026, GDPR-aware): per-interaction consent defaults to "may use for improvement" with a very visible "private/secret" toggle on every input. The single mediated boundary is the core's `datasets` capability: **filter** (the consent gate, never bypassable) then **anonymize** (data replacement of personal data *and secrets*, by the core before storing, text-only in v1; quality bar = indistinguishability). Anonymization is mandatory before any trace enters a dataset. The builder sphere is anonymize-free (synthetic); real usage reaches it only through the core's filter+anonymize.
- **Backup** (ADR-0021): per sphere, compelled-at-install policy, then automatic by cumulative uptime — full every ~20h, incremental every ~1h, keep 5 fulls. User data = per-service encrypted zips keyed by a user-chosen **backup passphrase**; builder data pushes to GitHub + HuggingFace; admin data is encrypted with an admin passphrase. The backup story **is** the disaster-recovery story: restoring the admin sphere returns a dead leader as the *same* platform in minutes. *Note:* the automatic backup cadence is the platform's one deliberate exception to "no automatic anything" — reconciled as *chosen automation at install time*.

---

## 10. The two policy pillars

### 10.1 Security — the trusted home environment (ADR-0017)

An **honest, light** stance sized to a trusted home, governed by the soul (transparent, visible, no black box):

- **Threat model**: defend a *compromised agent/harness* and *accidental data leakage*; explicitly not fully defended: OS-level host malware, a skilled malicious admin, a disk thief (only lightly).
- **Host-filesystem isolation**: WSL VM with default-deny host access; file sharing is an explicit mounted directory.
- **Browser-aware TLS**: HTTPS on every browser surface via a local CA; plain HTTP + Bearer on the trusted LAN; no mTLS.
- **Secrets at rest deliberately light** — obfuscation, not theater-strength crypto; the real defense is **short-lived rotated credentials**.
- **The harness is the execution authority**; the platform provides backstops: container network policy (default-allow-but-scoped-to-need), the single audited connectors door, per-agent scoping.
- **Guardrails** = cheap, on-by-default, *visible* data-safety at the two boundaries (outbound leakage, inbound prompt injection); the heavy moderation tier is optional and off by default.
- **Update authenticity**, two supply chains: the platform's own code is signed + checksummed; external OSS packages get an audited supply-chain scan + a 1-week freshness wait.

### 10.2 License — one policy, four kinds (ADR-0022)

- **Platform components**: strict open bar — `bundled` code must keep the repo Apache-2.0-shippable (copyleft only as a separate process); `listed` = every dependency open and consistent; reject no-clear-license and revenue-capped *software* libraries.
- **Models**: a five-question compliance profile (pay-to-use · research-only · revenue cap · attribution · train-on-output · fine-tune). Default catalog offers only commercial-safe weights; forbidden uses are **hard-blocked at the action boundary** (e.g. no fine-tuning a no-fine-tune model — the gate at `train.fine-tune`).
- **Vendored OSS UIs**: copyleft acceptable as a separate process; never fork/embed; AGPL avoided when a GPL/MIT equivalent exists.
- **Published things**: platform regime inherits the strict bar; a builder's generic apps get a builder-chosen license, SPDX-declared and surfaced as a compliance fact.

---

## 11. Learning, building, and the lifecycle

### 11.1 The learning experience (ADR-0024)

The educational goal made concrete, three ways:

1. **The learning/operability bar** — every service and implementation must carry graded documentation (how to use · how it works · study in depth · going further), auto-generated MCP tools, an agent-driving skill (or an honest "not agent-operable" note — no theater), and diagnostics. One source, dual-consumed: humans and the agent indexer read the same docs.
2. **The continual learning assistant** — literally **Hermes Agent**, vendored, accessible everywhere, one state per physical user, with all installed services' docs/skills/tools mounted (docs for everyone; tools scoped by role). Launched from a dashboard view, it runs as that **acting identity** (user/builder/admin) for the whole session.
3. **The guided build process** — the Matt Pocock engineering skills (wayfinder, TDD, code-review, …), whitelabelled to call the platform's own capabilities, extended with the Shankar/Husain evaluation methodology; surfaced through the Development service.

### 11.2 Evaluation and training (ADR-0020, 0025)

Both halves of the Training & Evaluation service are **builder-run, notebook-driven, deliberately not centralized**. Evaluation follows **Analyze–Measure–Improve**: dataset → simulate → open coding → axial coding (binary failure modes) → **LLM-as-judge validated against human labels** (the judge scores *known* failure modes; discovery stays human) → report, with history kept in the project repo. Real usage reaches eval datasets **only** through the core's filtered+anonymized extraction (§9.5).

### 11.3 Install, update, publish (ADR-0014, 0016, 0018, 0019)

- **Install** is a guided, phased wizard (native C# console → Python TUI → web UI), never silent; it ends with a recap and leaves a **resident launcher** on every machine. Invariant: **updates never touch data volumes.**
- **Updates**: three tiers versioned by what they are — the date-based **platform bundle** (the one user-facing version), service semver, implementation artifact versions — on a per-capability-API-version substrate. **No automatic updates in any tier**; a persistent, leader-centralized updates list; one-click per item at the user's pace. Rollback = the previous consistency unit.
- **Publishing**: a published thing is light by default (static site or long-running container; no serverless in v1); full service contract is opt-in. Exposure in v1 is LAN + a private-mesh overlay with auto-managed default-deny ACLs (share an app with a friend = one invite link, one visible rule); the public-internet gateway is deferred to v1.1. **Compliance is coupled to publishing only** — an operational-facts + EU-AI-Act/GDPR exit-early checklist, advisory, stored as documentation. Agent-generated code runs one OS container per app, network-scoped, with a visible "runs agent code" trust badge.

---

## 12. Open questions, inconsistencies, and flags ⚑

Everything this review found that still needs a decision, a clarification, or a cleanup — grouped. *(Original review items 2–8 — the dangling reference and the superseded-terminology sweep — were resolved by ticket #33 and are removed here.)*

### Spec-structure gaps (the biggest real gap)

1. **`20-services/` is referenced but absent.** `00-overview.md` points to "`20-services/` for the service chapters", and ADR-0013 mandates that tree plus a `docs/spec/README.md` master index — neither exists; the four service chapters sit flat. **Nine services have no chapter and no dedicated design ADR**: Inference, Chat + Agents, Workflow, Development, Audio, Image, Connectors, Generation, Media transformations. Only 4 of ~13 chapters exist (22, 24, 25, 33). For Inference — the central service — design lives only in CONTEXT.md fragments plus ADR-0006/0027. *This is the main "still open" inventory; it is tracked as ticket #34.*

### Apparent contradictions that need one clarifying sentence each

2. **"Automatic" wording**: ADR-0014 §6 and `90-lifecycle.md` still call Tier-1 updates "automatic"; ADR-0016's rule is *no automatic anything* (automatic = delivered to the list). Same for backup auto-run vs "no automatic anything" (reconciled as chosen-at-install automation).
3. **"Summary" faithful vs interpretation** (ADR-0010 vs ADR-0023, see §9.2) — resolvable via the generic-vs-task-chosen line, but must be taught explicitly.
4. **SQLite-everywhere vs Document = PostgreSQL** — an explicit, justified, scoped exception (ADR-0023); say so everywhere it's mentioned, or it reads as drift.
5. **ADR-0009 vs ADR-0010** on Document's operators: 0010 refined "limited DocETL operator subset" into "representation capabilities" — cite 0010's wording as current.
6. **Registry type count**: ADR-0008's options section says "five entries" while the decision lists seven (post-0019) — always state seven.

### Genuinely open design points (deferred, by decision)

7. **Task-shaped model capabilities** (tts/stt/embeddings) naming — deferred to the Inference service design (ADR-0027 §2), which doesn't exist yet (see gap #1).
8. **v1.1 deferrals**: public-internet gateway (ADR-0019/0017); full Training job-runner (ADR-0025); serverless runtime (rejected v1); multimodal anonymization (ADR-0026, text-only v1); Kuzu graph DB (ADR-0011); editable workflow canvas (ADR-0007); per-user provider keys (ADR-0006); HA/leader re-election (ADR-0004).
9. **Soft spots to re-check at build time**: family-contract verification risks (Ollama vision-through-Responses, stateless MCP transport, WebRTC-on-LAN — ADR-0001); rate limiting reserved but out of v1; DocETL intermediate-trace auditability is a goal with known cost, not a guarantee; the "no embedded memory framework" rationale in ADR-0012 depends on ecosystem status (Letta/Mem0/Zep) worth re-verifying; DocETL pipeline outputs split across Document (raw) and Knowledge (derived) may need a clarified residency rule.
10. **Unclosed handoff**: ADR-0017's "secrets at rest must survive leader rebuild" question was resolved in practice by ADR-0021's admin-sphere backup but never explicitly closed in 0017's text.

---

*Generated from the full document set (CONTEXT.md, 27 ADRs, 8 spec chapters) by a four-way parallel review. ADRs are the source of truth; where this document and an ADR disagree, the ADR wins.*
