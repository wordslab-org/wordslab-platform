# ADR-0009 — The Document/Knowledge split (raw document bundles vs derived knowledge)

**Status:** accepted (resolution of wayfinder ticket "Split the Document service into Document + Knowledge", #26); **re-homes** the DocETL engine (#24) and entity resolution / concept repository / knowledge-graph building (#25) into the Knowledge service; **amends ADR-0007 §6/§11** (DocETL abstract request + boundary — the home service); **amends ADR-0008** (data_source entries produced by both; adds a `kind` tag); **reshapes the v1 catalog (#18)** into 12 services.

## Context

The v1 catalog (#18) scoped a single **Document service** for document understanding: parse, organize, index, search/retrieval, a document search agent, and transform (DocETL-style). Grilling the composition model (#13) and capability registry (#20) surfaced two open design tickets — the DocETL engine (#24) and entity resolution / concept repository / knowledge-graph building (#25) — both scoped to "the Document service." Laurent's decision (made during the #20 grilling, this ticket): **split Document into two services** — **Document** and **Knowledge** — on a fundamental distinction between *storing and understanding raw document sets* and *reasoning over them to produce knowledge*.

The soul shapes it: the boundary must be **understandable** to a non-technical user — "my documents" vs "the knowledge we built from them." Data locality is the point of the DocETL engine (the optimizer runs where the data lives). No magic, no black box: the two services have crisp, non-overlapping identities and every piece of derived knowledge traces back to a source bundle.

## Decision

### 1. Two services, boundary = raw data vs derived knowledge

**Document service** — expert in the raw material. Owns:
- ingest/parse (structured markdown · schema-driven JSON · docling format · image rendering for complex pages)
- organize (page/document classification · sorting · splitting · merging)
- index (multilingual · late-interaction · multimodal)
- search/retrieval (collection + single long document · reranker · hybrid lexical/semantic · structured-property filters)
- **bundle-level structural operators** — merge / check / format / order the documents within a bundle, expressed with the **same DocETL syntax** as the engine's, but as a limited, specialized subset operating on raw data in place
- raw extraction queries on a single document bundle · filtering · source-of-data
- configurable **document search agent** (partnership with the agent service)

*(Refined by the DocETL engine ticket, #24 / **ADR-0010**: Document's role is more precisely stated as producing **faithful representations** of content — formats, the different ways to split, **contextualized splits**, raw structured-data extractions, and **embeddings for all of them** — across **every modality** (the Image service contributes captions + photo embeddings, the Audio service transcription + speaker diarization + audio embeddings, all stored together in bundles with **embeddings aligned in one vector space**). These are easier ways to consume the exact content, with **no reflection or interpretation**: a human can read/see/listen and verify the representation matches the source. Everything *beyond* faithful representation — choosing a representation for a task, summarizing, thinking, cross-checking even within a bundle — is the Knowledge service's. The engine dispatches by this **representation-vs-interpretation** rule.)*

**Knowledge service** — expert in reasoning over bundles to produce derived knowledge. Owns:
- ontologies / concepts
- entity resolution + grounding (to canonical concept/entity IDs)
- knowledge-graph building
- cross-document-set aggregation
- facts extraction
- transversal semantic view (references into documents, tied to no single document)
- **bridge to the structured information system** (systems of record)

The test that keeps the boundary clean: **Document answers "what's in my documents, where, and how do I find it"; Knowledge answers "what did we learn across them, and how is it linked to the rest of our records."**

### 2. The document bundle — the unit of organization

A **document bundle** is a coherent collection of related raw inputs that arrive together and make sense as one unit: an email + its attachments + history; a meeting's transcript + invitation + attendees + agenda + presentations; a set of scanned paper documents found in a physical envelope. A bundle may be **multi-modal** — audio transcription of a meeting, the text agenda, images of slides, a word-processor study — where the textual representation may have been **produced by another service** (audio transcription, image description) and assembled by the Document service; Document does not re-derive text from raw media it did not capture.

The bundle is the unit of **organization** (format/order/normalize) and, in some flows, of **search** — while each **individual document inside it is still tracked as its own index entry**. The index is two-level: each document individually indexed, and grouped/ordered/normalized under its bundle.

### 3. Data residency — no shared storage, references not copies

Per ADR-0004 ("data lives where its service lives") and ADR-0003 (no shared/networked storage in v1):
- **Document** owns the raw bundles and their indexes (the document data, textual representations, chunk index) in its own data location.
- **Knowledge** owns only the derived knowledge (ontologies, concept graph, entity repository, knowledge base), which **references** bundles by stable ID (`document.<bundle>`) — never copies content.

Raw docs = Document's data location; derived graph = Knowledge's. Knowledge reaches Document's raw data over the wire via Document's normal callable surfaces — the `call` primitive (OpenAPI), the registry's `data_source` entries, and the DocETL dispatch — as sibling services over the LAN. No shared storage, no content copies, no new transport machinery.

### 4. The DocETL engine lives in Knowledge, dispatching to Document (#24)

The **#24 abstract-request engine lives in the Knowledge service** (ADR-0010): it receives the serialized DocETL pipeline (the abstract request) from a workflow, optimizes it, and orchestrates execution. **Data locality via dispatch:** because raw bundles and representations live in Document, the engine dispatches **faithful-representation** steps (formats, splits, contextualized splits, raw structured extraction, embeddings — across all modalities) back to **Document**, which produces them where the data lives via its **representation capabilities**. The engine keeps in **Knowledge** everything else — choosing a representation for a task, summarizing, reasoning, cross-checking across documents *and within a bundle*. Both speak the same DocETL expression syntax; a workflow builds one pipeline and the engine routes each step by the **representation-vs-interpretation** rule (ADR-0010). The two coordinate as sibling services over the LAN (ADR-0004) — no new machinery.

**Why Knowledge and not Document:** the point of the engine (per the split) is to reason over multiple document sets and extract derived knowledge — Knowledge's expertise. Document is the data holder, not the reasoning engine. The **request surface** (the abstract-request API workflows send pipelines to) is therefore exposed by **Knowledge**.

### 5. Entity resolution / concept repository / knowledge graph live in Knowledge (#25)

Entity resolution, the concept repository, and knowledge-graph building are the reasoning/ontology side — they **re-home to Knowledge** (ADR-0007's "re-scoped by the Document/Knowledge split" note is made concrete). Knowledge grounds resolved entities to canonical concept/entity IDs, stores the controlled vocabulary (concept repository), and builds the knowledge graph — giving indexed documents a structured grounding layer that DocETL extraction and retrieval both sit on.

### 6. The capability registry: one `data_source` type with a `kind` tag (#20)

Both services register `data_source` entries (ADR-0008). They are distinguished by **expected result**, via a `kind` tag on the entry — the registry stays thin (id · type · kind · one-line description · owning-service ref):
- **`chunks`** — document retrieval returns chunks of documents (Document service; `document.<bundle>`).
- **`graph`** — retrieval returns structured/knowledge-graph results (Knowledge service; `knowledge.<kb>`).
- **Natural-language answers** (agentic search and reasoning over both) is a **`tool` entry**, not a data_source: producing a synthesized answer requires agentic reasoning over an LLM (non-deterministic), which is the agent/tool side of the house (ADR-0007), not the passive deterministic data side. Modeled as an agentic search/QA tool composing over the `chunks` and `graph` sources.

### 7. The bridge to the structured information system

- **Inbound (read/query):** Knowledge exposes its derived knowledge via the **base contract** — the normal callable surfaces (OpenAPI, MCP, UI). Any structured IS app or workflow queries the knowledge graph/entities/facts through the standard API. "Just a service," no special machinery.
- **Outbound (export into external IS apps):** goes through the **Connectors service** — the single audited door, with the security/audit/approval layer over every outbound call. Knowledge does not build its own outbound connectors.
- **No new inbound-exposure machinery in v1.** If a Knowledge knowledge base is to be *published* (exposed inbound to external apps), that is a #21 publishing decision.

### 8. Versioning & the catalog

The v1 catalog becomes **12 services** (Knowledge added). Knowledge is a **v1 service** (not deferred — #24 and #25 live in it and are already v1 scope). Build order (amends #18): Inference → Chat+Agents → Document(parse) → Connectors(web) → Development → Document(rest) → **Workflow → Knowledge** → Connectors(rest) → Audio → Image → Media → Generation → Training(v1.1). Knowledge builds after Workflow because knowledge-extraction pipelines are often implemented as workflows — the Workflow service should exist first to orchestrate them.

### 9. Agent memory & enterprise knowledge capture (new ticket)

The agent system's memory substrate (user identity/profile, job & role, knowledge/skill level, preferences, current-task context, procedural knowledge) is backed by **Document** (raw memory artifacts stored as document bundles) + **Knowledge** (reasoned profile/knowledge graph, semantic retrieval feeding agent context); the agent loop itself stays in Chat + Agents (the partnership pattern). Enterprise knowledge demonstrated by employees in HITL sessions is **progressively captured**: corrections/confirmations in sessions are logged as **proposed knowledge items** (full provenance via action-context) into a **review surface**; a human approves each before it enters the Knowledge base. Nothing is committed implicitly. Captured knowledge routes to one of **three destinations by nature**: facts/entities → Knowledge graph; exact repeated procedures → Workflow (graduation path); reusable approaches → **Skills**. Owned by a dedicated **memory-system ticket** (spawned by this resolution).

## Considered options

- **Single Document service vs the split** — a single service conflates *storing/understanding raw documents* with *reasoning over them to produce knowledge*; two distinct problems with different users and dev skills. The split keeps each identity crisp and explainable.
- **Engine in Document vs Knowledge** — the engine reasons over multiple bundles and produces derived knowledge; that is Knowledge's function. Placing it in Document would leave Knowledge an empty shell.
- **One `data_source` type vs a sixth type / sub-type machinery** — the registry stays thin (ADR-0008); the kind tag captures the expected-result distinction without new registry machinery.
- **Natural-language answers as a data_source vs a tool** — synthesized answers are agentic (LLM reasoning), which is the agent/tool side, not the passive deterministic data side; modeling it as a tool composes correctly over the two data sources.
- **Explicit per-delta capture vs proposed-log with review** — the soul forbids silent mining; but forcing an explicit "save?" on every correction burdens the employee. The transparent proposed-log (Option B) captures demonstrated knowledge with low friction while keeping everything visible and reviewed.

## Consequences

- **Re-homes** #24 (DocETL engine) and #25 (entity resolution / concept repo / graph) into the **Knowledge service**; both bodies updated accordingly.
- **Reshapes** the closed #18 catalog into 12 services; CONTEXT.md notes the 12-service catalog and the Knowledge-service entry.
- **Amends ADR-0007** §6/§11 (DocETL home is Knowledge; boundary updated).
- **Amends ADR-0008** (data_source entries from both services; `kind` tag `chunks`/`graph`; natural-language answers as a tool).
- **Creates** a memory-system design ticket (agent memory + enterprise knowledge capture).
- **Glossary (CONTEXT.md):** document bundle, Knowledge service, Document service entry updated, memory/knowledge-capture terms.
