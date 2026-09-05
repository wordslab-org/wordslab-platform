# ADR-0023 — Sharpening Document & Knowledge: 9-part indexing, LLM-generated ontologies, and the generated/verified validation loop

**Status:** accepted (resolution of wayfinder ticket "Sharpen the Document & Knowledge services", #28 — a re-visioning of the settled Document/Knowledge split, grounding capability, and memory/capture loop); **amends ADR-0009** (§3 data residency — the storage-delegation and bidirectional-index refinement), **ADR-0010** (the 9-part faithful-representation model and its role as a context-length optimization), **ADR-0011** (LLM-generated ontology reconciliation, ontology-to-ontology relations, and the generated/verified validation-state qualifier), and **ADR-0012** (the generated-knowledge loop reuses the one shared review queue; the `generated`/`verified` qualifier generalizes to all derived artifacts); **does NOT reopen** the raw-vs-derived boundary (ADR-0009); **feeds** "Design the learning experience" (#29 — how the 9-part model and the ontology/facets are *taught*), the "Training service" (#30 — dataset-prep may use the generated/verified corpus), and the "data consent & handling" model (#31 — attribution spheres untouched; the generated/verified qualifier is an orthogonal validation axis).

## Context

The v1 Document and Knowledge services were split (#26 / ADR-0009) on a raw-vs-derived boundary, the grounding capability designed (#25 / ADR-0011), and the memory/capture loop settled (#27 / ADR-0012). Laurent then worked on the domain since those tickets closed and surfaced a sharper, more concrete vision of what each service *stores* and *how they compose* — a re-visioning, not a reopening. The ticket adds: (a) a **9-part Document indexing model** (granularity × abstraction), (b) an **LLM-generated, human-reviewed ontology** flow in Knowledge, (c) extracted **entities/properties as structured facets** for filtering documents and chunks, and (d) a **generated-knowledge → validate → reintegrate** loop for agents combining Document and Knowledge tools.

The soul shapes every decision: **no magic, no black box, nothing implicit** — every derived artifact is a proposal with evidence until a human approves it; the user navigates both the concrete documents and the abstract concepts and can always see the links between them.

The settled constraints this builds on (not re-derived): the raw-vs-derived boundary (ADR-0009), faithful-representation-vs-interpretation dispatch (ADR-0010), the grounding capability's ontology → knowledge base → knowledge graph model and its graduated HITL review (ADR-0011), and the thin PROV-aligned provenance envelope + shared review queue (ADR-0012). Data residency stays "no shared storage, references not copies" (ADR-0009 §3); raw content lives in Document only.

## Decision

### 1. The 9-part Document indexing model — all faithful representations

Every document is stored and indexed at **three levels of granularity** (chunk / document / document bundle) × **three levels of abstraction** (raw element / summary of the element / unsupervised extraction of facts & claims as triples) = **9 parts**, each vectorized and indexed. The transformations are **generic, unsupervised, and not linked to any ontology**.

**All 9 parts are Document's faithful representations.** This sharpens the boundary ADR-0010 drew: what makes a representation *faithful* is not that it is raw, but that it is **generic, mechanical, deterministic, task-independent, and human-verifiable against the source**:

- **raw** — the source itself, trivially faithful.
- **summary** — a *generic, deterministic, applied-to-every-element-uniformly* summary (mechanical/extractive), not a model understanding the content for a purpose.
- **unsupervised fact/claim triples** — *generic, unsupervised* subject–predicate–object claim extraction, not ontology-constrained and not interpreted or grounded.

Anything that **reflects or chooses for a task** — a summary sized for a specific question, an ontology-grounded extraction, resolving claims to canonical entities, cross-checking even within a bundle — stays on the **Knowledge / interpretation** side, exactly as ADR-0009/0010 already hold. The 9-part model is the **generic, representation-layer foundation Document always produces**; the ontology, graph, and facets build on top of it in Knowledge.

**Why (the registered motivation):** the 9-part model is a **context-length optimization**. Agents querying the corpus pull in the *summary* and *triple* parts rather than re-reading raw text, and the **triples are the direct, efficient source for knowledge extraction** — far cheaper than re-processing raw documents on every query. This is a deliberate performance rationale, not just "extra ways to consume."

### 2. Two levels, linked — storage, residency, and the bidirectional index

The services now expose **two navigable levels** with a maintained link between them:

- **Level 1 — abstract concepts (Knowledge service; the authoritative store; SQLite).** The ontology, resolved entity IDs, and relations between entities live here, **each linking back to its source** in the documents (`document.<bundle>` + source span — ADR-0009/0011 provenance). This store is **independently navigable**: the user/agent can traverse ontology → entities → graph and back without touching a document. Knowledge is the **semantic authority** — it decides what values mean.
- **Level 2 — concrete documents (Document service; the hybrid index; PostgreSQL).** The raw chunks and their indexes live here, **with the results of the Knowledge analysis physically indexed in the same database**, so a single hybrid query can join a facet value with BM25 + multi-vector over the raw chunks. Document **executes storage and retrieval only**; it never interprets. **Raw content lives only in Document — never copied.**

**The bidirectional index (the navigation seam, indexed both ways):**
- **documents → concepts:** every chunk is indexed by the extracted concept/facet IDs grounded in Knowledge (the filter surface of Q3 below).
- **concepts → documents:** every concept/entity/fact in the Knowledge store is indexed by its **source documents** (`document.<bundle>` + span), so one can jump from any abstract concept straight back to the concrete chunks that ground it.

Both directions are **physically indexed**, not computed on the fly. Tools and skills operate at **both levels** (Document-side tools for searching/navigating concrete chunks across the 9 parts; Knowledge-side tools for browsing/reasoning over ontology/entities/graph) **plus bridge tools** that jump between levels through the link.

**Residency line, sharpened (amends ADR-0009 §3):** the raw content stays only in Document (never copied); the **derived facet/grounding index values** (canonical entity IDs, class tags, ontology links on each chunk) are **physically stored in Document's index** so a single hybrid query can filter by facet + BM25 + multi-vector together. Knowledge remains the semantic authority on what those values mean; Document is the physical executor, not the interpreter. The authoritative graph stays in Knowledge (ADR-0011 §7); lightweight graph traversal at query time is served by recursive queries over the hybrid index (see §3).

### 3. The storage engine — PostgreSQL for Document's hybrid index (a scoped exception)

Document's index must support **every filter kind in one database**: relational columns, JSON structured data, sparse BM25, dense embeddings (incl. multi-vector / late-interaction), and lightweight graph traversal. This is now a *settled requirement* — ADR-0009 already commits Document to **late-interaction** indexing, which is a **multi-vector** technique (ColBERT/ColPali family), and the platform's composition story (ADR-0010) needs a single hybrid query.

- **Document service's index store = PostgreSQL** (pgvector for dense/multi-vector + pg_search/ParadeDB for sparse BM25 + JSONB for structured facets + recursive CTEs for graph traversal). This is a **deliberate, scoped exception** to the platform's SQLite-everywhere bias, justified specifically by the settled late-interaction/multi-vector requirement.
- **Knowledge service's authoritative store stays SQLite** (ontology versions, entities/KB, graph facts, review queue — ADR-0011 §7). Small, independent, inspectable.
- This matches the delegation Laurent confirmed: **Knowledge computes the semantics and delegates the computed index values + hybrid query execution to Document**; Document stays storage + retrieval.

### 4. LLM-generated ontology (reconciles with ADR-0011)

The ticket's "a powerful LLM generates an ontology" is the **concrete realization of ADR-0011's auto-extract-from-dataset**, with the identical gate: it produces a **draft** the user **browses, reviews, fixes, edits** before it is **versioned** — never a silent schema. The **~50-concept cap is a simplicity guideline** (home/small scale, teachable, keeps validation rules manageable), not a hard limit.

**Ontology-to-ontology relations (a light extension of ADR-0011's "several ontologies coexist"):** several ontologies may apply to one document set **and be explicitly related to one another** via lightweight **subsumption/overlap links** (e.g. a general "Contacts" ontology and a specialized "Acme vendors" ontology share Person). These links are **human-authored at review time** and **reused by `knowledge.entities.resolve`** when a mention spans related ontologies.

### 5. Structured facets (where they live)

Extracted **entities and properties become structured facets** used to filter documents and chunks. The facet values are **grounded in Knowledge** (they come from ontology/entity resolution linking a mention to a canonical entity — ADR-0011), while the **act of filtering the raw corpus by those values is Document's native retrieval job** (the structured-property filters ADR-0009 already lists). So a faceted search **composes**: the caller filters Document's `chunks` data source **by a facet value grounded in Knowledge** (`knowledge.entities.resolve` → canonical ID → filter Document's chunks by that ID). No copies; the facet values are stored in Document's hybrid index (§2/§3) but their meaning is Knowledge's authority.

### 6. The generated-knowledge loop — one shared review queue

An agent may combine Document and Knowledge tools to derive **"generated knowledge"** from facts in source documents. This loop **reuses the settled review machinery — it is not a second, parallel review surface**:

- The agent's generated knowledge is a **proposed knowledge item** carrying provenance + a provisional kind, flowing into the **same shared review queue** (ADR-0011 review decision, ADR-0012 queue).
- **Validation** = the existing approve / reject / skip / create-new / edit-then-promote decision with evidence.
- **Reintegration** = the reviewer, using the **same one-axis determinism routing** (ADR-0012), picks the destination: a verified fact → `knowledge.entities`/`knowledge.graph` (grounded); a procedure → Workflow; an approach → skill. The ticket's "reintegrated into the document collection" is one **possible destination**: fold a confirmed fact back as an **indexed enrichment in Document** (a facet/summary value). One queue, one machinery, one reviewer decision.

**Generated-knowledge provenance (same thin envelope):** the "full trace" is the **thin PROV-aligned envelope** already settled in ADR-0012 — the source `document.<bundle>`(+spans), the reasoning chain as a **short, human-readable step list** (not a per-token transcript), the explicit implementation + privacy tier that produced it, and (after validation) the reviewer + decision. No heavyweight per-fact transcript.

### 7. The generated/verified validation-state qualifier (orthogonal to attribution spheres)

The learning loop is explained in **sphere terms**, mirroring the user/builder/admin attribution model (#31) but on an **orthogonal axis**:

- **Generated data sphere** — *candidate* predictions/derivations from a model (unverified; the proposed state).
- **Verified / facts sphere** — source documents plus knowledge a user has *validated* (committed).

The **review queue is the mediation gate** between the two — just as the core mediates user→builder with filter/anonymize (ADR-0021/#31), here the review queue mediates generated→verified with **human approval**. **Nothing enters the verified sphere without user approval** (the soul's no-implicit rule).

The two axes are **orthogonal and both real**: attribution spheres (#31) answer *who owns the data* (user/builder/admin); the **validation state** answers *is it human-approved*. They do not replace each other. So:

- `generated` vs `verified` is a **platform-wide qualifier carried by every derived artifact** — not just facts, but automatically inferred **skills, memories, workflows** too. The "is this trustworthy?" answer is always visible wherever a derived artifact appears.
- The review queue promotes generated → verified. #31's attribution-sphere vocabulary is left intact.

### 8. Where it lands

- **Creates `docs/architecture/30-services/34-document.md` and `docs/architecture/30-services/35-knowledge.md`** (ADR-0013 level C, "organized reference + citations"), grounded in ADR-0009/0010/0011/0012 **plus** this ticket's new content (9-part model, bidirectional index, LLM-generated ontology, facets, generated/verified loop). Created in the same commit (ADR-0013 §8 maintenance loop).
- **`docs/spec/10-foundations.md` *(relocated by ADR-0028 into the `docs/architecture/` tree)* is deferred** — it is the platform-wide substrate for all 12 services and is better filled by a dedicated pass once the remaining cross-cutting tickets (#29, #31) settle. Noted as deferred, not stubbed.

## Considered options

- **All 9 parts in Document vs pushing summary/extraction to Knowledge** — the 9-part model *is* the faithful-representation foundation, provided "faithful" is re-defined as generic/mechanical/task-independent rather than raw-only; pushing summaries/extraction to Knowledge would leave Document unable to serve the generic, ontology-free retrieval that agents need and would force Knowledge to re-process raw text. Chose all 9 in Document.
- **Facets stored in Document's index vs fetched live from Knowledge** — live fetch cannot run a single hybrid query joining facet + BM25 + multi-vector and duplicates grounding state; physically indexing the grounded facet values in Document's store gives one-query retrieval while Knowledge stays the semantic authority. Chose index-in-Document, meaning-in-Knowledge.
- **PostgreSQL vs SQLite for Document's index** — SQLite (FTS5 + sqlite-vec) handles exact search to ~100k rows but not multi-vector late-interaction as a first-class capability, which ADR-0009 already commits Document to; PostgreSQL (pgvector + pg_search + JSONB) does all five filter kinds in one DB. Chose PostgreSQL as a scoped, justified exception; SQLite everywhere else (incl. Knowledge's authoritative store) is unchanged.
- **Ontology generated by an LLM vs a separate mechanism from ADR-0011's auto-extract** — it is the *same* mechanism (auto-extract-from-dataset realized by an LLM) with the same human-review-before-versioning gate; a separate mechanism would duplicate the ontology lifecycle. Chose reconciliation.
- **Ontology-to-ontology relations vs leaving ontologies as isolated coexisting blueprints** — relations (subsumption/overlap) let several ontologies genuinely apply to one document set and give `resolve` a spanning seam; kept light and human-authored. Chose the light extension.
- **A second review surface for generated knowledge vs reusing the shared queue** — a second surface duplicates near-identical approve/reject/evidence mechanics; the same one-axis determinism routing already covers fact/procedure/skill. Chose one shared queue.
- **Full per-fact reasoning transcript vs the thin PROV-aligned envelope** — a transcript per fact is heavy and mostly noise; the thin envelope (sources + short reasoning chain + implementation + reviewer) is readable, auditable, and consistent with ADR-0012. Chose the thin envelope.
- **generated/verified as a second orthogonal qualifier vs absorbing the attribution spheres** — the two axes answer different questions (who owns it vs is it human-approved); absorbing them would blur attribution/privacy (which #31 owns). Chose the orthogonal qualifier layered on top.

## Consequences

- **Amends ADR-0009** §3 — residency sharpened: derived facet/grounding index values are physically stored in Document's index; raw content stays in Document only, never copied. Document = storage + hybrid query execution; Knowledge = semantic authority.
- **Amends ADR-0010** — the 9-part model as Document's faithful-representation foundation; "faithful" re-defined as generic/mechanical/task-independent; motivation recorded as a context-length optimization with triples as the efficient extraction source.
- **Amends ADR-0011** — LLM-generated ontology reconciles with auto-extract-from-dataset; ontology-to-ontology relations as a light extension; the `generated`/`verified` validation-state qualifier; facets grounded in Knowledge but applied as filters over Document's chunks.
- **Amends ADR-0012** — the generated-knowledge loop is the one shared review queue; "reintegrated into the document collection" is one reviewer-chosen destination; the `generated`/`verified` qualifier generalizes to all derived artifacts (skills, memories, workflows).
- **Creates ADR-0023** (this decision). **Creates** `docs/architecture/30-services/34-document.md` + `docs/architecture/30-services/35-knowledge.md`. **Defers** `docs/spec/10-foundations.md` *(relocated by ADR-0028 into the `docs/architecture/` tree)*.
- **Data-residency note:** the platform's "no shared/networked storage in v1" and "no content copies" rules (ADR-0003/0004/0009) are preserved; the bidirectional index stores *derived values* (IDs, links), never raw content, and every derived value carries provenance to `document.<bundle>`.
- **CONTEXT.md glossary** — sharpens: Document service (9-part model, hybrid PostgreSQL index, storage-delegation), Knowledge service (LLM-generated ontology, ontology-to-ontology relations, generated/verified qualifier); adds: "9-part indexing", "bidirectional index", "structured facets", "generated/verified validation state", "ontology-to-ontology relation".
- **Feeds** the spec anatomy (#12 — these chapters), the capability registry (#20 — facets as a `chunks`-side filter surface; bridge tools), the dashboard (#8 — the review queue surface, the two-level navigation UI), #29 (how the 9-part model and ontology/facets are *taught*), #30 (dataset-prep over the generated/verified corpus), #31 (attribution spheres untouched; the generated/verified qualifier is orthogonal).
- **Model-license note (ADR-0022, #23):** the LLM that generates the ontology, and any model in the extraction/generated-knowledge path, routes through the Inference service as an **explicit implementation choice** carrying its privacy tier, and must respect its **model compliance profile** (no train-on-output for fine-tune, etc.).
