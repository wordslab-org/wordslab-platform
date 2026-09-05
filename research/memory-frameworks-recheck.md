# Memory frameworks re-check — does ADR-0012's "no embedded memory framework" rationale still hold? (Sept 2026)

**Purpose:** re-verify the ecosystem assessment behind ADR-0012's decision to build agent memory
on the platform's own Document + Knowledge primitives instead of embedding a memory framework
(Letta/MemGPT, Mem0, Zep/Graphiti, LangMem, Memary). Decision-time claims were made in Aug 2026;
this is a Sept 2026 re-check against live sources (GitHub API verified 2026-09-05; vendor docs,
Zep engineering blog, 2026 comparison surveys).

---

## 1. Ecosystem state per framework (2026)

### Letta (f.k.a. MemGPT)
- **What it is:** a full *agent runtime* with self-editing tiered memory blocks + archival
  retrieval (MemGPT's OS-style virtual memory). Apache-2.0, self-hostable; hosted Letta Cloud
  exists (free BYOK tier, Pro $20/mo).
- **Status verified 2026-09-05:** the decision-time claim is confirmed with a nuance.
  `letta-ai/letta` (24.6k★, Apache-2.0) is no longer marked "archived" on GitHub but the repo
  itself states: *"The retired Letta V1 server source is preserved on the `archive` branch"*
  — the legacy Python agent server **is retired**. The project pivoted to `letta-ai/letta-code`
  (TypeScript, 3.2k★, very active, npm-first: `@letta-ai/letta-code`). The famous Python
  MemGPT/Letta server is historical source; adopting it means adopting a retired runtime or
  rewriting across the TS pivot.
- **Relevance:** memory-*tier* ideas (pinned core block + agent-invoked archival retrieval)
  remain durable and are what ADR-0012 borrows. The code is not a safe dependency.

### Mem0
- **What it is:** the mainstream extract-then-retrieve memory layer (LLM distills conversation
  into compact fact records; ADD/UPDATE/DELETE/NOOP reconciliation; vector store + optional
  graph, "Mem0g"). Apache-2.0 core, self-hostable (Docker), hosted platform at app.mem0.ai.
  ~64.7k★, very actively maintained (pushed 2026-09-04). AWS made it the memory provider for
  their Agent SDK. Benchmarks: LoCoMo ~67% LLM-judge, p95 search ~0.2s, ~1.8k tokens/conv.
- **Caution:** open-core vendor drift is real — graph memory and features like "Dream"
  consolidation are **gated behind the hosted top tier**; teams report indexing-reliability
  issues at scale and the hosted-product gravity in roadmap/UX. Still, the OSS core is genuine.
- **Relevance:** its *pattern* (extract-then-retrieve, provenance-bearing fact records,
  multi-signal retrieval, MCP `add`/`search` tool shape) is exactly what ADR-0012 borrows.

### Zep / Graphiti
- **What it is:** Zep = commercial "context" platform on top of **Graphiti** (Apache-2.0,
  30.6k★, active, pushed 2026-09-04) — a bi-temporal knowledge-graph engine (entities,
  relations, facts with validity windows; episodic subgraph). Neo4j / FalkorDB / Kuzu backend.
- **Status:** **Zep Community Edition deprecated** (April 2025, further feature retirements
  Feb 2026 — confirmed via Zep's own blog and docs). Self-hosting = raw Graphiti + your own
  graph DB + embedding/LLM infra. Full Zep stack is SaaS-only.
- **Relevance:** confirms the decision-time claim. Graphiti's temporal/non-lossy episode model
  is cited by ADR-0012 as the model for Document's raw bundles; borrowing the *idea* (not the
  dependency) was the right call — self-hosting Graphiti is an infra burden (3+ systems).

### LangMem (LangChain)
- MIT, ~1.6k★, maintained but modest; deep LangGraph integration (its value collapses outside
  LangGraph). Benchmarks middling on LoCoMo (~58%) with severe retrieval latency (~60s p95 in
  tests). A framework building block, not a platform. No reason to embed.

### Memary
- **Dead — confirmed.** The original repo (kingjulio8238/Memary, ~2.6k★) has no commits since
  **Oct 2024**. Decision-time claim ("Memary dead") holds.

### Notable newer entrants (post-decision landscape)
- **Hindsight (Vectorize.io)** — MIT, ~22.7k★, very active. Memory-as-structured-belief:
  separates evidence from inference/opinion, four parallel retrieval strategies + cross-encoder
  rerank, `retain`/`recall`/`reflect`, entity resolution, LongMemEval ~91.4%. Self-host = one
  Docker command with full feature parity (embedded Postgres). Closest OSS analog to what
  ADR-0012 built (facts-vs-interpretation split, provenance, review).
- **Cognee** — Apache-2.0, ~30.5k★, very active. Graph-pipeline memory platform
  (`remember`/`recall`/`improve`/`forget`); requires operating graph+vector+relational infra.
- **Supermemory, mem9, Kumiho, Memora, Membase** — early/managed-first or niche; some
  proxy-layer designs route every LLM request through vendor servers (Supermemory) — contrary
  to the platform's privacy-tier model.
- **Category read:** a 2026 survey consensus — the space is in a "vector-DB-in-2022" phase:
  active benchmark wars (Mem0 vs Zep), consolidation pending, no canonical winner. Embedding
  any one framework now buys churn risk, not stability.

## 2. Comparison against what ADR-0012 built on Document/Knowledge

| Concern | Embedded framework (best case) | ADR-0012 substrate |
|---|---|---|
| Raw, non-lossy memory | Framework-specific stores (Mem0 records, Graphiti episodes) | Document bundles (transcripts, dossier, task history) — verbatim, human-verifiable |
| Reasoned/derived layer | Framework-internal, partially opaque; graph features often hosted-tier-only | Knowledge derives lazily; profile as a #25 KB with provenance back to bundle IDs |
| Retrieval | Vendor pipeline (scores, precedence mostly hidden) | Explicit precedence (profile > chunks > graph), deterministic, logged, no black box |
| Human review / HITL | None first-class anywhere in the field | Shared review queue (ADR-0011), delta-logging capture, reviewer-confirmed routing |
| Model routing / privacy | Framework-configured LLM calls | Inference-service implementation choices with explicit privacy tiers |
| Durability | Verified churn: Letta V1 retired; Zep CE deprecated; Memary dead; open-core gating | Own code on own primitives; borrow patterns only |

Notably, the *newest* framework thinking (Hindsight's evidence-vs-inference split, fact
validity windows) is converging on what ADR-0012 already specified — raw-with-provenance as
source of truth, beliefs derived and correctable. The 2026 ecosystem validates the substrate's
design rather than offering a drop-in replacement for it.

## 3. Verdict

**The rationale still holds — YES, confirmed.** Every specific decision-time claim survives
re-verification: Letta's V1 Python server is retired (preserved only on an archive branch; the
project pivoted to TypeScript `letta-code`); Zep Community Edition is deprecated with
self-hosting reduced to raw Graphiti + your own graph DB; Memary has been dead since Oct 2024;
Mem0 remains a genuine Apache-2.0 OSS core but is open-core with graph memory gated behind the
hosted tier. Nothing in the 2026 ecosystem offers an embeddable memory framework that is at
once fully self-hostable, feature-complete (graph memory, review, provenance), long-term
durable, and compatible with the platform's no-black-box / explicit-privacy-tier principles.
The market is also pre-consolidation (benchmark wars, new entrants monthly), so pinning to any
one of them now maximizes churn risk. ADR-0012's approach — own the raw layer in Document,
derive reasoned memory in Knowledge, borrow only proven patterns (extract-then-retrieve,
memory tiers, multi-signal retrieval, MCP tool shape) — remains correct and is in fact the
direction the field itself is converging toward (evidence/inference separation, provenance,
inspectable memory). **No change to the decision.**

*Sources: GitHub API repo states (2026-09-05): letta-ai/letta, letta-ai/letta-code,
mem0ai/mem0, getzep/graphiti, getzep/zep, topoteretes/cognee, vectorize-io/hindsight,
langchain-ai/langmem, kingjulio8238/Memary; Zep blog "Announcing a New Direction for Zep's
Open Source Strategy"; docs.letta.com; letta README; 2026 surveys (vectorize.io/hindsight
open-source memory systems, developersdigest.tech memory providers 2026, graphlit.com memory
frameworks survey, digitalapplied.com Mem0/Letta/Zep compared).*
