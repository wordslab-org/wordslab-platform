# ADR-0012 — The agent memory substrate & progressive enterprise knowledge capture

**Status:** accepted (resolution of wayfinder ticket "Design the agent memory system & progressive enterprise knowledge capture from HITL sessions", #27); **composes with ADR-0011** (the profile is a knowledge base; `knowledge.entities.resolve` is the enterprise dedup; the review queue is the shared HITL surface), **ADR-0010** (the capture pipeline is a DocETL pipeline on the Knowledge engine), and **refines ADR-0009** (§9 — this ticket is the child it spawned); **rests on ADR-0007** (agent→workflow→skill graduation path, explicit implementation choice) and **ADR-0008** (registry `data_source` kinds, `skill`/`agent`/`workflow` entry types)

## Context

True to the Document/Knowledge split (#26, ADR-0009 §9), the agent system's memory components — user identity & profile, job & role, knowledge & skill level, preferences, current-task context, procedural knowledge for the job — should be backed by the **Document service** (raw memory artifacts stored as document bundles) plus the **Knowledge service** (reasoned profile / knowledge graph, semantic retrieval feeding agent context), rather than bespoke storage. The agent loop itself stays in the **Chat + Agents** service (the partnership pattern, ADR-0007). The ticket couples two things: the **memory substrate** (how agent memory is stored & reasoned over) and **progressive enterprise knowledge capture** (how knowledge demonstrated by employees in HITL sessions accumulates at enterprise scale).

The home and composer seams are settled by prior ADRs: the DocETL engine (#24, ADR-0010) lives in Knowledge; the grounding capability — entity resolution / concept repo / knowledge-graph building (#25, ADR-0011) — also lives in Knowledge. This ADR designs the **memory substrate** within that home and the **capture pipeline** that composes the engine and the grounding capability. Nothing here re-derives #24/#25/#26.

The soul shapes every decision: **no magic, no black box, nothing implicit**. Memory is written and captured transparently; nothing enters the knowledge base without a proposal and a human review; every derived item traces to its source; every model-backed step names its implementation and privacy tier.

## Decision

### Part 1 — The agent memory substrate

**Document stores the raw episodic memory as document bundles (non-lossy, source of truth).** Concretely:
- a **conversation-transcript bundle** per agent session (the raw exchange, append-only),
- a **user-profile dossier bundle** — the *verbatim stated facts* the user told the system ("I work at X", "I prefer Y") — deliberately **not** pre-summarized,
- a **task-history bundle** — past tasks, goals, outcomes as raw records.

These are faithful representations (ADR-0010): human-verifiable, no interpretation. They follow the "memory as a document bundle" model — honest, local, traceable, and consistent with Zep/Graphiti's non-lossy episode subgraph.

**Knowledge derives the reasoned memory over those bundles, lazily/asynchronously** (sleep-time compute, not in the hot path):
- a **compact user-profile summary** (the curated "core memory block"),
- the **user profile / knowledge graph** (see below),
- **grounded skills & procedural knowledge** mapped to concepts.

Every derived item **points back to the bundle IDs that support it** (provenance/traceability); a summary is a *separate derived artifact*, never a replacement for the raw bundle. The derived layer stays **small and lazy** — a profile and a lightweight index, not an exhaustive graph (against over-building; stale profiles; memory bloat).

**The user profile is a knowledge base.** The reasoned profile/graph conforms to a **person/profile ontology** in `knowledge.ontology` and is stored as one of #25's **knowledge bases** — entities + facts, resolvable via `knowledge.entities.resolve`, stable canonical IDs (`entities.<ontology>.<kb>.<opaque>`). Grounding a session's content resolves mentions to profile concepts through the *same* machinery as every other KB. The profile is **per-user** (a personal profile KB; not a separate KB per agent — what each agent *knows* flows through the profile, scoped by the agent's accessible set). The capture pipeline (Part 2) feeds this profile KB directly.

**Current-task context is working memory**, held by the agent loop in Chat + Agents — not stored in the profile KB.

**Memory retrieval feeds agent context as a callable capability (the partnership pattern), plus a small always-on surface:**
- A **small preloaded context surface** (always in the window): the compact profile summary + current-task notes — cheap continuity that does not depend on the model remembering to call a tool.
- An agent-callable **memory-retrieval capability**, owned by Document + Knowledge, that **composes the `chunks`** (Document, top-k vector semantic recall) **and `graph`** (Knowledge, graph-neighborhood / multi-hop relational recall) data sources, **fuses them with an explicit precedence order** (profile facts > relevant chunks > graph-connected context), and returns **cited, provenance-linked context** (each item tagged with its document/chunk/entity/fact id). The step is **deterministic and observable** — input query, sources hit, scores, assembled context all logged. No black box.
- **Natural-language answers over memory are an agentic search tool** (ADR-0007/0008): the agent decides *when* to search and composes the answer with citations.

Retrieval routing is **explicit** (no hidden heuristics) with the smallest honest default: **preloaded profile facts + agent-invoked retrieval**; auto-retrieval per turn is a deliberate opt-in. Guards (research-verified pitfalls): cap retrieval attempts; keep injected context short with important items early (lost-in-the-middle); tag everything with provenance + freshness; on empty/low-confidence retrieval, say "I could not find a source" rather than fabricate.

Vocabulary adopted from the landscape (CoALA): **working** (loop), **episodic** (Document raw bundles), **semantic + procedural** (Knowledge derived). "Memory is context engineering" — memory becomes useful only when retrieved into the window; the raw layer must stay non-lossy so derived beliefs can be traced and corrected.

### Part 2 — Progressive enterprise knowledge capture (Option B)

**Capture = delta logging, run as a DocETL pipeline on the #24 engine.** The **proposed-log + review (Option B)** is already Laurent's decision from #26; this ADR designs the mechanism:
- Each HITL session's **validated deltas** — the minimal change an employee **corrected** (`from → to`) or **confirmed** — are logged as **proposed knowledge items**, each carrying full **provenance via the action-context** (which session, which employee, when) plus a **provisional kind** (FACT / ENTITY / PROCEDURE / APPROACH). Status = `PROPOSED`. Nothing enters the knowledge base yet.
- **Delta-recognition catches both explicit corrections and implicit confirmations** (accepting an agent output as right). Honesty guard: a correction is the strongest signal; an implicit acceptance is weaker, so it becomes a proposal only when it confirms a *substantive* claim not already in the KB — guarding against over-capture.
- The mechanism is a **DocETL pipeline** on the Knowledge engine (ADR-0010): it **extracts** the deltas from the session's **transcript bundle** in Document (dispatch), **resolves** entity mentions via **`knowledge.entities.resolve`** (scoped to one chosen KB), and **proposes** the item to the review queue. Model-backed steps route through the **Inference service** as explicit implementation choices. There is **no new bespoke capture machinery**.
- Framing: this is **capture, not extraction** — the system records *that a human changed something* (the only thing we actually know); the truth claim is validated only at review.

**Review surface = #25's shared review queue** (the single biggest reuse from the grounding capability). Capture proposals flow into the same evidence-backed queue that already holds resolution/validation proposals. Each item shows **evidence** (provenance + source span); actions **approve / reject / skip / create-new / edit-then-promote**. Graduated policy (no silent anything): uncertain/new default to a human; high-confidence unambiguous items auto-commit only under an explicit user-set threshold. **Dedup-as-proposal** — a flagged "these may be the same entity" is itself a proposed item a human confirms, never an implicit merge.

**Routing to three destinations by nature — the one-axis determinism test, reviewer-confirmed:** a captured item carries a provisional kind; at approval the **reviewer confirms or overrides** it (the agent may *suggest*, a human disposes — no silent auto-routing):
- **facts / entities** (a true statement about the world) → **Knowledge graph** (`knowledge.entities` / `knowledge.graph`; grounded),
- **exact repeated procedures** (always the same way) → **Workflow service** (the agent→workflow graduation path, ADR-0007),
- **reusable approaches** (human improvises each time) → **a skill** (the `skill` registry entry type, ADR-0008).

**Re-routing is a normal lifecycle event** (a "fact" that keeps needing step-by-step explanation is really a procedure; a "skill" with exactly one correct execution is really a workflow); reclassification is itself a review signal, not an error.

**Enterprise-scale dedup = composition with #25.** As proposed items accumulate across many employees' sessions, dedup is a call to **`knowledge.entities.resolve`**, scoped to one explicitly-chosen KB per call — the same person/provider/entity is the same entity. No new dedup machinery (ADR-0011 §2/§4/§8).

**Traceability.** Every captured fact links to its **evidence bundle by stable ID** (`document.<bundle>`) in Document (ADR-0009 residency: references, never copies). The **review decision** — who approved, when, evidence/source span — is recorded. Each annotation **is learning signal**: primarily *retrieval* (promoted knowledge changes next-session behavior); every annotation (including rejections) is persisted as a preference pair (`from`=rejected, `to`=preferred) so an **explicit, opt-in, offline** DPO/RLHF fine-tune is possible later — never implicit.

**Model routing.** Any LLM- or classic-AI-powered reasoning in the capture path routes through the **Inference service** as **explicit implementation choices** carrying their **privacy tier** (`local` / `cloud_no_data` / `cloud`); no inference policy, no auto-fallback; a refused implementation or `cloud-spend` 429 surfaces and the user re-chooses. Reuses ADR-0007 §10 / ADR-0006 exactly.

**Enterprise scale = the accumulation layer:** proposed items from many employees' sessions flow into one reviewable pipeline (provenance via action-context), deduplicated by `knowledge.entities.resolve`, reviewed (human-or-agent), routed to the three destinations. This is the **capture → review → route** pipeline.

## Considered options

- **Raw dossier vs pre-summarized dossier in Document** — pre-summarizing the dossier in Document breaks traceability (the raw layer must be non-lossy so derived beliefs can be corrected); the dossier is a raw record of *stated facts*, and Knowledge derives the compact profile summary. (LlamaIndex static vs fact-extraction blocks; the research.)
- **Profile as a #25 KB vs a bespoke memory store** — a KB reuses the grounding capability (resolve, IDs, review) and unifies memory with everything else; bespoke storage would duplicate it and fragment the model.
- **Per-user vs per-agent profile KB** — per-user keeps one honest profile the user owns and can audit; per-agent separation would fragment identity without clear benefit at home scale (agents scope what they access via the registry allowlist instead).
- **Preloaded + agent-invoked retrieval vs auto-every-turn vs preloaded-only** — the hybrid avoids both over-stuffing (context bloat, lost-in-the-middle) and the agent failing to recall when it should; auto-retrieval stays an explicit opt-in. This matches the industry's settled hybrid (pinned core memory + agentic on-demand retrieval).
- **Delta logging vs whole-turn capture** — whole turns flood the queue and drown real signals; logging only validated deltas keeps capture honest and low-friction (Option B's point).
- **Capture as DocETL pipeline vs bespoke capture code** — reusing the #24 engine and #25's `resolve` gives data locality, explicit model routing, and auditable runs, with no new machinery.
- **Shared #25 review queue vs a separate capture-review surface** — one evidence-backed HITL surface with a consistent approve/reject/evidence model; a separate surface duplicates near-identical mechanics for no benefit (though capture accuracy and dedup read differently, #25 already unifies them under one review model).
- **Reviewer-confirmed routing vs fully manual vs hidden auto-classifier** — a hidden classifier violates the soul; fully manual ignores the agent's useful suggestion; the agent-suggests / reviewer-disposes middle keeps it explainable and low-friction.
- **Thin PROV-aligned provenance envelope vs full W3C PROV** — full PROV tooling is overkill at home scale; a thin envelope (session, user, when, from→to, reviewer) maps onto PROV's Entity/Activity/Agent + `wasRevisionOf` if standards-grade traceability is ever needed.
- **Borrow patterns vs embed a memory framework** — Mem0, Letta/MemGPT, LangMem, Memary, Zep all carry vendor/open-core/roadmap risk (Letta's legacy Python server archived Aug 2026; Memary dead; Zep CE deprecated). We build our own thin, transparent layer on Document + Knowledge and borrow only the proven patterns (extract-then-retrieve write path, multi-signal retrieval, MCP `add`/`search` tool shape, memory-tier vocabulary).

## Consequences

- **Creates ADR-0012** (memory substrate + progressive capture).
- **Composes with ADR-0011** — the profile KB and `knowledge.entities.resolve` (dedup); the shared review queue (review surface); grounded destinations (`knowledge.entities`/`knowledge.graph`).
- **Composes with ADR-0010** — the capture pipeline is a DocETL pipeline on the Knowledge engine (extract → resolve → propose).
- **Refines ADR-0009** §9 — the memory substrate + Option B capture, made concrete.
- **Rests on ADR-0007** (agent→workflow→skill graduation path; explicit implementation choice) and **ADR-0008** (registry `data_source` kinds; `skill`/`agent`/`workflow` entry types; `document.<bundle>` / `knowledge.<kb>` names).
- **Glossary (CONTEXT.md):** sharpened "knowledge capture"; added "agent memory", "memory substrate", "episodic / semantic / procedural / working memory", "memory retrieval", "delta logging", "proposed knowledge item", "capture routing".
- **Feeds** the spec anatomy (#12 — agent memory + knowledge capture chapter), the capability registry (#20 — memory-retrieval entry, destinations), the dashboard (#8 — the review queue surface, memory visibility), #14/#23 (any pinned lib passes the OSS/supply-chain gate — none are pinned as dependencies here).
- **Research assets** (from this session) in `/opt/data`: `memory-landscape-frameworks.md`, `memory-substrate-anatomy.md`, `memory-retrieval-context.md`, `knowledge-capture-accumulation.md`.