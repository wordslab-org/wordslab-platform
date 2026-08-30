# 25 — Knowledge

> **Status:** created at the resolution of wayfinder ticket "Sharpen the Document & Knowledge services" (#28 / ADR-0023), building on the Document/Knowledge split (#26 / ADR-0009), the DocETL engine (#24 / ADR-0010), the grounding capability (#25 / ADR-0011), and the memory/capture loop (#27 / ADR-0012). **Source of truth:** ADR-0009 (Document/Knowledge split), ADR-0010 (DocETL engine), ADR-0011 (ontologies, entity resolution, knowledge graph), ADR-0012 (memory substrate + capture), ADR-0023 (LLM-generated ontology, ontology relations, facets, generated/verified loop). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Knowledge service** is expert in *reasoning over* document bundles to produce **derived knowledge** — ontologies, entity resolution/grounding, the knowledge graph, cross-bundle aggregation, facts extraction, and the transversal semantic view. It answers *"what did we learn across them, and how is it linked to the rest of our records."* Knowledge is the **semantic authority**: it computes the ontology, grounds mentions to canonical entities, and delegates the computed index values + query execution to the Document service's hybrid index. Its authoritative store is small and **independently navigable** (SQLite); it references bundles by stable ID (`document.<bundle>`), never copies content (ADR-0009 §3).

## Part 1 — Use cases (user guide)

### What the user sees and does

- **Generating an ontology** (User/Builder): an LLM proposes an ontology from a collection of documents (a **draft**); the user **browses, reviews, fixes, edits** it before it is **versioned** — never a silent schema. The ontology stays **simple** (a ~50-concept guideline). Several ontologies can apply to one document set and be **related to one another**.
- **Grounding & reviewing** (User): extracted mentions resolve to canonical entities (`knowledge.entities.resolve`); new/ambiguous items and facts flow into the **review queue** where the user approves / rejects / skips / creates-new, each with evidence. High-confidence items may auto-commit only under an explicit per-KB threshold.
- **Navigating knowledge independently** (User): traverse ontology → entities → graph without touching documents — pure concept-space reasoning.
- **Filtering documents by knowledge** (User): use extracted entities/properties as **structured facets** to filter the corpus; the filter is applied over Document's `chunks` data source at retrieval time.
- **Validating generated knowledge** (User): an agent's derived "generated knowledge" is a **proposed item** in the same review queue; on approval it is reintegrated as a **verified fact** (grounded in the graph, and/or folded back as indexed enrichment in Document).

### Representative use cases

1. **"Build me an ontology of my document collection"** (User) — an LLM proposes an ontology (draft) → the user reviews/fixes/edits → versioned → it now shapes grounding and raw extraction. Supporting: `knowledge.ontology`, ADR-0011 §1 + ADR-0023 §4.
2. **"Link these documents to a shared concept"** (User) — extracted mentions resolve to a canonical entity via `knowledge.entities.resolve` (scoped to one KB); NIL entities and facts go to the review queue; approved items commit to `knowledge.entities`/`knowledge.graph` with provenance (ADR-0011 §8). Supporting: Document hybrid index (facets), Knowledge authoritative store.
3. **"Find all documents about this entity"** (User) — from an entity in the graph, follow the **concepts → documents** index back to the chunks that mention it (ADR-0023 §2). Supporting: Knowledge (provenance), Document bidirectional index.
4. **"Validate what the agent figured out"** (User) — an agent combined Document + Knowledge tools and derived generated knowledge with a thin provenance trace; the user reviews it in the shared queue and it is promoted to a **verified** fact (ADR-0012 routing, ADR-0023 §6/§7). Supporting: shared review queue, `knowledge.graph`, Document (indexed enrichment).

## Part 2 — Build spec (organized reference + citations)

### The layered model (ADR-0011 §1)

**Ontology** (classes/entity-types + relation-types + validation rules; importable JSON and/or auto-extracted from a dataset) → **knowledge base** (canonical entities, several per ontology) → **knowledge graph** (facts/edges with provenance). **LLM-generated ontology = auto-extract-from-dataset realized** (draft → human review → versioned), with a **~50-concept simplicity guideline** and **ontology-to-ontology relations** (subsumption/overlap links, human-authored, reused by `resolve`) — ADR-0023 §4.

### Capability surface (ADR-0011 §2, sharpened by ADR-0023)

- **`knowledge.ontology`** — create/import (JSON) / auto-extract (LLM-generated, draft) / edit / version; **validate** (proposed violations → review queue); **ontology-to-ontology relations** (ADR-0023 §4).
- **`knowledge.entities`** — the entity repository (multiple KBs per ontology); **`resolve`** (mentions → canonical ID, scoped to one chosen KB; deterministic candidate gen + explicit LLM/classic-AI judgment via Inference with privacy tier). Stable IDs `entities.<ontology>.<kb>.<opaque>`.
- **`knowledge.graph`** — facts/edges with provenance; the `graph` data_source kind; parallel resolve/query with the unified candidate shape.
- **Storage delegation:** Knowledge computes the semantics (ontology, grounding, facets, entity links) and delegates the **computed index values + hybrid query execution to Document** (ADR-0023 §2/§3). Facets are grounded here, applied as filters over Document's `chunks` at retrieval time.
- **Bidirectional index:** Knowledge's concepts are indexed by their source documents (**concepts → documents**), and Document's chunks are indexed by the grounded concept IDs (**documents → concepts**) — ADR-0023 §2.
- **tools & skills:** ontology/entity/graph browsing and reasoning tools (Knowledge side) + **bridge tools** that jump to the Document level through the bidirectional index (ADR-0023 §2).

### Storage (ADR-0011 §7, unchanged)

One Knowledge-service **SQLite** DB, tables grouped by capability (ontology+versions, kb, entity, fact, fact_evidence, review_queue). **No graph engine in v1** (Kuzu deferred); the authoritative graph is vertex/edge tables in SQLite. Lightweight graph traversal at query time over Document's hybrid index uses recursive queries (ADR-0023 §3).

### The generated/verified validation-state qualifier (ADR-0023 §7)

Every **derived artifact** — facts, entities, and automatically inferred **skills, memories, workflows** — carries a `generated` vs `verified` qualifier, **orthogonal to the #31 attribution spheres** (user/builder/admin). **Generated** = candidate/model-produced (unverified); **verified** = human-approved. The **review queue is the gate** promoting generated → verified; nothing enters the verified state without user approval. Attribution (who owns it) and validation (is it human-approved) are separate axes.

### The generated-knowledge loop (ADR-0023 §6)

Agent-derived generated knowledge is a **proposed knowledge item** (provenance + provisional kind) in the **same shared review queue** (ADR-0011 decision, ADR-0012 queue). Validation = approve/reject/skip/create-new/edit-then-promote with evidence. Reintegration = reviewer chooses destination by the one-axis determinism test: verified fact → `knowledge.entities`/`knowledge.graph` (grounded); procedure → Workflow; approach → skill; **or** fold back as **indexed enrichment in Document** (a facet/summary value). Provenance = the **thin PROV-aligned envelope** (source `document.<bundle>`+spans, short reasoning chain, explicit implementation + privacy tier, reviewer + decision) — ADR-0012, ADR-0023 §6.

### Model routing & license (ADR-0007 §10, ADR-0023 consequences)

Any LLM/classic-AI step (ontology generation, extraction, judgment, generated knowledge) routes through the **Inference service** as an **explicit implementation choice** carrying its **privacy tier**; no inference policy, no auto-fallback. Every such model must respect its **model compliance profile** (ADR-0022 §3, #23).

### ADR cross-references

ADR-0011 (ontology/entities/graph, resolution, review, validation, storage) · ADR-0010 (DocETL engine, resolve-then-ground seam) · ADR-0012 (memory substrate, capture, shared review queue) · ADR-0009 (split, residency, data_source `graph` kind, bridge to IS) · ADR-0023 (LLM-generated ontology, ontology relations, facets, bidirectional index, generated/verified loop). Contract/template per ADR-0001/0002; registry `graph` kind per ADR-0008; bridge outbound via Connectors per ADR-0009 §7.
