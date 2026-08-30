# 22 — Document

> **Status:** created at the resolution of wayfinder ticket "Sharpen the Document & Knowledge services" (#28 / ADR-0023), building on the Document/Knowledge split (#26 / ADR-0009), the DocETL engine (#24 / ADR-0010), the grounding capability (#25 / ADR-0011), and the memory/capture loop (#27 / ADR-0012). **Source of truth:** ADR-0009 (Document/Knowledge split), ADR-0010 (DocETL engine / faithful representations), ADR-0011 (grounding; the `Document → Knowledge` ontology-fetch edge), ADR-0012 (memory substrate), ADR-0023 (9-part indexing, hybrid index, bidirectional index). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Document service** is expert in the **raw material** — document bundles and the faithful representations built from them, across every modality (text, image, audio). It answers *"what's in my documents, where, and how do I find it"* — the counterpart to the Knowledge service's *"what did we learn across them"* (ADR-0009 §1). Document **stores and indexes the raw content and its representations**; it **executes storage and retrieval only, never interpretation**. Knowledge is the semantic authority on meaning; Document is the physical executor where the data lives.

## Part 1 — Use cases (user guide)

### What the user sees and does

- **Ingesting** (User view): add an email + attachments, a meeting's transcript + slides + audio, a set of scanned papers, a photo album. Each arrives as a **document bundle** — the unit of organization — while every individual document stays its own index entry.
- **Browsing by granularity**: navigate a collection at **chunk / document / bundle** level, and at each level read the **raw** element, a **summary** of it, or the **facts/claims** extracted from it — the 9 parts.
- **Searching the corpus**: a hybrid search (lexical BM25 + semantic dense/multi-vector) across the 9 parts, with structured-property and facet filters.
- **Navigating both levels**: from a chunk, see which concepts/entities it instantiates; from a concept in the Knowledge graph, retrieve the chunks that ground it — the **bidirectional index** (ADR-0023 §2).
- **The document search agent**: a configurable agent that searches/navigates the corpus on the user's behalf (partnership with the agent service).

### Representative use cases

1. **"Find everything about Acme in my documents"** (User) — the user filters the corpus by the **Acme facet** (a concept grounded in Knowledge). The faceted search composes: `knowledge.entities.resolve` → canonical Acme ID → filter Document's `chunks` data source by that ID, joined with BM25 + semantic retrieval in a single hybrid query. Supporting: Knowledge service (grounded facet values, ADR-0011/0023), Document hybrid index (ADR-0023 §3).
2. **"Summarize this bundle for me"** (User) — read the bundle's **summary part** (generic, deterministic) without re-processing raw text. The summary/triple parts are a **context-length optimization** for agents (ADR-0023 §1). Supporting: Document representation capabilities (ADR-0010).
3. **"Navigate from a concept to its sources"** (User) — from a fact/entity in the Knowledge graph, follow the **concepts → documents** index back to the exact chunks and spans that ground it. Supporting: Knowledge (provenance `document.<bundle>`+span), Document bidirectional index (ADR-0023 §2).
4. **"Jump from a document to the concepts it instantiates"** (User) — from a chunk, read the entity/concept IDs indexed onto it (**documents → concepts**) and open them in the Knowledge browser. Supporting: Document bidirectional index, Knowledge (ADR-0023 §2).

## Part 2 — Build spec (organized reference + citations)

### The 9-part indexing model (ADR-0023 §1)

Every document is stored and indexed at **3 granularities (chunk / document / document bundle) × 3 abstractions (raw / summary / unsupervised fact-claim triples) = 9 parts**, each vectorized + indexed. All 9 are **faithful representations** — generic, mechanical, task-independent, human-verifiable; anything reflective/task-chosen stays in Knowledge (ADR-0010 dispatch, ADR-0023 §1). Motivation: the summaries/triples are a context-length optimization; the triples are the efficient direct source for knowledge extraction.

### The hybrid index (ADR-0023 §2/§3)

- **Document's index store = PostgreSQL** (a scoped, deliberate exception to SQLite-everywhere): pgvector (dense + **multi-vector / late-interaction**, ADR-0009's settled requirement) + pg_search/ParadeDB (sparse BM25) + JSONB (structured facets) + recursive CTEs (lightweight graph traversal). One database supports every filter kind in a single hybrid query.
- **Storage delegation:** Knowledge computes the semantics and delegates the **computed index values + hybrid query execution** to Document. Document never interprets.
- **Bidirectional index:** chunks are indexed **by** their grounded concept/facet IDs (**documents → concepts**); Knowledge's concepts are indexed **by** their source documents (**concepts → documents**). Raw content lives only in Document — never copied.

### Capability surface (ADR-0009 §1, sharpened by ADR-0023)

- **ingest / parse** — structured markdown · schema-driven JSON · docling · image rendering; assembly of multi-modal bundles (representations produced by Image/Audio services).
- **organize** — bundle-level classification/sorting/splitting/merging; the bundle is the unit of organization.
- **index** — the 9-part model, multilingual, late-interaction, multimodal, aligned embeddings in one vector space (ADR-0010).
- **search / retrieval** — collection + single long document; reranker; hybrid lexical/semantic; structured-property + **facet filters** (facets grounded in Knowledge, ADR-0023 §5).
- **bundle-level structural operators** — merge/check/format/order, expressed in the same DocETL syntax (faithful-representation dispatch → Document, ADR-0010).
- **representation capabilities** — the generic 9-part production surface; batch-capable for GPU saturation (ADR-0010 §7).
- **document search agent** — configurable, partnership with the agent service.
- **tools & skills at both levels + bridge tools** (ADR-0023 §2) — Document-side navigation of the 9 parts; bridge tools that jump to the Knowledge level through the bidirectional index.

### Key flows

- **Ingest → 9-part index:** a bundle is parsed, organized, and each part vectorized + indexed in the hybrid store; grounded facet values arrive from Knowledge and are indexed onto chunks (ADR-0023 §2).
- **Faceted hybrid search:** caller resolves a facet via `knowledge.entities.resolve`, then filters Document's `chunks` by that canonical ID, joined with BM25 + multi-vector in one query (ADR-0023 §5).

### ADR cross-references

ADR-0009 (split, residency, data_source `chunks` kind) · ADR-0010 (representation capabilities, dispatch, embeddings) · ADR-0011 (Document → Knowledge ontology-fetch edge) · ADR-0012 (raw episodic memory as bundles) · ADR-0023 (9-part model, hybrid index, bidirectional index, facets). Contract/template/provider/privacy per ADR-0001/0002/0006; data residency per ADR-0003/0004.
