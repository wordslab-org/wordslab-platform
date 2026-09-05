# The data side: understanding and memory

> **Status:** concept chapter assembled from section 9 of the architecture overview — the data side, the most distinctive part of the design. **Source of truth:** ADR-0009 (Document/Knowledge split), ADR-0023 (9-part index, hybrid store), ADR-0011 (grounding: ontologies, entities, the graph), ADR-0010 (DocETL engine), ADR-0012 (memory substrate + knowledge capture), ADR-0021 (backup per sphere), ADR-0026 (consent). This chapter cites, never restates.

The data side is where the platform's most distinctive design lives: two experts that divide the raw material from the reasoning over it, a nine-part index and a hybrid store, grounding through ontologies and a knowledge graph, a capture loop that feeds a memory substrate, and three data spheres governed by consent and backup.

## The Document / Knowledge split (ADR-0009)

One service became two, along a deliberately teachable line:

- **Document** answers *"what's in my documents, where, and how do I find it?"* It owns the raw material: **document bundles** (an email + its attachments + history; a meeting's transcript + slides + agenda), parsed into **faithful representations** — generic, mechanical, task-independent, human-verifiable. Document **stores, indexes, and retrieves — it never interprets**.
- **Knowledge** answers *"what did we learn across them?"* It owns only **derived knowledge** — ontologies, canonical entities, the knowledge graph — **referencing** bundles by stable ID (`document.<bundle>`), never copying content.

The dispatch rule between them is one sentence: **faithful representation → Document; interpretation → Knowledge.**

## The 9-part index and the hybrid store (ADR-0023)

Every document is stored at **3 granularities** (chunk / document / bundle) × **3 abstractions** (raw / summary / unsupervised fact-claim triples) = **9 parts**, each vectorized and indexed — a context-length optimization so agents can read a summary instead of the raw text. Document's index store is **PostgreSQL** — a scoped, deliberate exception to SQLite-everywhere, forced by the late-interaction/multi-vector requirement (pgvector + BM25 + JSONB facets + recursive CTEs).

Knowledge computes the semantics and **delegates the computed index values + query execution to Document** (storage delegation). The index is **bidirectional**: chunks are indexed by their grounded concept IDs (*documents → concepts*); concepts are indexed by their source documents (*concepts → documents*).

⚑ *The "summary" boundary is subtle: ADR-0010 lists "summarizing" as interpretation, while ADR-0023 makes generic, uniformly-produced summaries a faithful Document representation. The line is "generic and mechanical vs task-chosen" — the architecture document must teach it explicitly or readers will see a contradiction.*

## Grounding: ontologies, entities, the graph (ADR-0011)

Three layers: **ontology** (classes + relation types + validation rules — LLM-generatable as a *draft* the user reviews and versions; ~50-concept simplicity guideline) → **knowledge bases** (canonical entities) → **knowledge graph** (facts with provenance). `knowledge.entities.resolve` grounds mentions to canonical IDs, scoped to one explicitly-chosen KB — never silent cross-KB search. Storage is SQLite vertex/edge tables — **no graph engine in v1** (Kuzu deferred).

Everything derived carries a **`generated` vs `verified` validation-state qualifier**: model-produced candidates become human-approved facts only through the **review queue** — nothing enters the verified state without a human. This is orthogonal to *who owns* the artifact (the attribution spheres, "Data spheres" below).

## The DocETL engine (ADR-0010) and knowledge capture (ADR-0012)

Knowledge hosts the **DocETL abstract-request engine** ("SQL for unstructured data"): pipelines authored in Python, executed with an optimizer that shows its plan as a reviewable diff. The **memory substrate** and **knowledge capture** ride the same machinery:

- **Memory**: raw **episodic** memory (conversation transcripts, profile dossier, task history) is Document bundles — non-lossy source of truth; Knowledge lazily **derives** semantic memory (the reasoned profile — itself a KB, resolved with the same grounding machinery). Working memory is the agent loop's context; retrieval is a cited, deterministic, observable capability.
- **Capture**: in a human-in-the-loop session, the minimal change a user corrected or confirmed is **delta-logged** as a *proposed knowledge item* with full provenance. *Capture, not extraction* — the system records that a human changed something; truth is validated at review. The review queue routes items by a one-axis determinism test: **facts/entities → the Knowledge graph; exact repeated procedures → the Workflow service (the graduation path); reusable approaches → a skill.**

## Data spheres, consent, and backup (ADR-0021, 0026)

A physical user has **three identities**: `user`, `builder`, `admin` — three **data spheres**, the units of attribution and backup.

- **Consent** (ADR-0026, GDPR-aware): per-interaction consent defaults to "may use for improvement" with a very visible "private/secret" toggle on every input. The single mediated boundary is the core's `datasets` capability: **filter** (the consent gate, never bypassable) then **anonymize** (data replacement of personal data *and secrets*, by the core before storing, text-only in v1; quality bar = indistinguishability). Anonymization is mandatory before any trace enters a dataset. The builder sphere is anonymize-free (synthetic); real usage reaches it only through the core's filter+anonymize.
- **Backup** (ADR-0021): per sphere, compelled-at-install policy, then automatic by cumulative uptime — full every ~20h, incremental every ~1h, keep 5 fulls. User data = per-service encrypted zips keyed by a user-chosen **backup passphrase**; builder data pushes to GitHub + HuggingFace; admin data is encrypted with an admin passphrase. The backup story **is** the disaster-recovery story: restoring the admin sphere returns a dead leader as the *same* platform in minutes. *Note:* the automatic backup cadence is the platform's one deliberate exception to "no automatic anything" — reconciled as *chosen automation at install time*.

---

Document and Knowledge each have detailed chapters (30-services/34 and 35).
