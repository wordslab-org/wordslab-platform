# ADR-0011 — Entity resolution, the concept repository & knowledge-graph building (the grounding capability)

**Status:** accepted (resolution of wayfinder ticket "Design entity resolution, the concept repository & knowledge-graph building", #25); **composes with ADR-0010** (the DocETL engine calls into this capability for resolution/grounding); **refines ADR-0009** (the Knowledge service's grounding surface) and **ADR-0008** (the `graph` data_source kind; `knowledge.<kb>` naming)

## Context

The Knowledge service (the Document/Knowledge split, #26 / ADR-0009) grounds documents with canonical concept/entity IDs via entity resolution, a concept repository, and knowledge-graph building. This ADR designs that **grounding capability** — the surface the DocETL engine (#24 / ADR-0010) composes with when a pipeline's `resolve`/grounding steps run. The home is settled (Knowledge); this ticket designs the capability *within* it and the seam with the engine. It is re-introduced into the v1 catalog as Knowledge-service scope.

The soul shapes every decision: **no magic, no black box** — everything is a *proposal with evidence*; merges are verified, never assumed transitive; under-merging is the safe default; a human (or an explicit, user-written rule) decides what is committed; nothing is mined silently.

## Decision

### 1. The layered model — ontology → knowledge base → knowledge graph

Three layers, in domain-standard terms:

- **Ontology** — the *blueprint* of a domain: **classes/entity types** (Person, Organization, Topic) + **object properties/relation types** (works_for, participates_in) + **validation rules/constraints**. Several ontologies coexist. Each is importable as JSON and/or **auto-extracted from a dataset**. An auto-extracted ontology is a **draft** the human reviews/edits before it is versioned and used for grounding — never a silent schema.
- **Knowledge base** — the *instances*: the entity repository. **Entities**, each with a **stable canonical ID**, canonical name, aliases, and class. Several knowledge bases share one ontology (one "Contacts" ontology → a "personal network" KB + an "Acme vendors" KB).
- **Knowledge graph** — the *edges*: **facts** (subject → object property → object), referencing entities by canonical ID, each with **provenance/evidence** (which `document.<bundle>`, which source span).

### 2. The capability surface — three capabilities, named by standard term, operations on each

| Capability | Owns | Operations |
|---|---|---|
| **`knowledge.ontology`** | the blueprints: entity + relation types **+ validation rules/constraints** | create/import (JSON) / **auto-extract from a dataset** / edit / version; **`validate`** (run the rules against any extracted structure — grounded or raw — producing proposed violations) |
| **`knowledge.entities`** | the entity repository: knowledge bases of canonical entities (multiple KBs per ontology) | CRUD, import JSON, progressive population; **`resolve`** (mentions → canonical entity ID, **scoped to one chosen KB**) |
| **`knowledge.graph`** | the knowledge graph: facts/edges with provenance; the `graph` data_source kind (ADR-0008) | register/query facts; parallel resolve/query returning the unified candidate shape |

- **`knowledge.ontology.validate`** is a **set of operations on `knowledge.ontology`**, not a separate capability — validation rules are part of the blueprint. The ontology is the single blueprint that both **grounds** (types resolution matches against) and **shapes raw extraction** (the schema raw extraction must conform to).
- **Entity resolution is an operation on `knowledge.entities`** (`knowledge.entities.resolve`), not a standalone capability — the standard term is an operator on the entity repository. The graph side exposes a parallel resolve/query operation on `knowledge.graph`. **Entity resolution and graph resolution share the same candidate shape** (`id/name/type/score/match`, the Reconciliation API shape) — a single entity is a graph with no edges yet, so the entry points look similar.
- All three share the Knowledge service's UI/MCP/OpenAPI surfaces + one DB (ADR-0002).

### 3. Stable canonical IDs

- An entity ID is **`entities.<ontology>.<kb>.<opaque>`** — ontology (broader scope) first, then KB, then a **stable, opaque, immutable token**. Both scopes are self-evident in every ID; resolution scoping is unambiguous.
- The **canonical name and aliases are separate, mutable fields** — a rename or added spelling never changes the ID.
- **Merging:** when two entities are confirmed to be the same, the survivor keeps its ID; the merged-away ID becomes an **alias/pointer** to it, so existing references still resolve. No reference ever breaks.
- Workflows and facts reference the canonical ID, never the name.

### 4. Resolution — scoped to one KB; deterministic retrieval, explicit LLM/classic-AI judgment

- **Resolution is scoped to one knowledge base at a time, chosen explicitly by the caller** — never a silent search across KBs. A pipeline declares `call("knowledge.entities.resolve", kb=..., ...)`. Multi-KB pipelines **chain explicit per-KB resolve steps**; there is no cross-KB resolve mode. Cross-KB placement ("which KB does this new entity belong to?") is a separate, explicit user-facing question, never a heuristic. This mirrors the "explicit implementation choice" pattern (ADR-0007 §10).
- **Two-stage pipeline:** candidate *generation* is deterministic (normalize + blocking + optional embedding ranking — cheap, no model routing); only the "same entity?" *comparison/judgment* is a model call.
- **Model routing:** the judgment step routes through the **Inference service** as an **explicit implementation choice** — which may be an **LLM *or* a classic-AI model** (the Inference service has both, ADR-0006/catalog), carrying its **privacy tier** (`local`/`cloud_no_data`/`cloud`); no inference policy, no auto-fallback; refusal/`cloud-spend` 429 surfaces + user re-chooses (ADR-0007 §10, ADR-0005 §9).

### 5. Validation = a review decision (human or agent), not a bare gate

- **Validation rules are part of the ontology** and are evaluated by a **deterministic rule engine by default** (an LLM/classic-AI-assisted option is explicit, never implicit).
- `knowledge.ontology.validate` produces **proposed violations that flow into the same review queue** as resolution proposals. It is **human-or-agent**: a violation prompts a human check, with three outcomes:
  - **fix manually** — correct the extracted data in place;
  - **validate the exception with a comment** — the value is legitimately exceptional; approved with the human's rationale recorded;
  - **reject the data sample** — the whole document/sample is unreadable/unusable.
- **Every manual annotation is learning signal** — to improve the extraction model and/or to develop an agent that eventually replaces the human in the loop (the agent→workflow / HITL→automation graduation path, ADR-0007). A validation queue is not just a gate — it is a **learning loop**.

### 6. Review / HITL — graduated, configurable, evidence-backed, no silent anything

- **Default = proposed, human-approved for anything uncertain.** New entities (NIL) and ambiguous resolutions always go to a review queue; facts (edges) go to a review queue by default too.
- **High-confidence, unambiguous matches can auto-commit** — but only under an **explicit, user-visible threshold** set per KB (e.g. "auto-accept matches with score ≥ 0.95 where the candidate is unique"). This is the "remembered choices = explicit user-written rules, never hidden heuristics" principle (ADR-0005/0007).
- **The review surface is the OpenRefine pattern:** approve / reject / skip / create-new, each showing **evidence** (source span + candidate score + *why*), not just a number. **Under-merging is the safe default** — when uncertain, keep it as a proposed item rather than collapsing.
- Even auto-accepted items are recorded as "auto-accepted under rule X at score 0.96" with full provenance.

### 7. Storage & scale — one SQLite DB, graph as tables, no graph engine

- **One Knowledge-service SQLite DB** (ADR-0002), tables grouped by capability: `ontology` (+versioning), `kb`, `entity` (stable ID, canonical name, aliases, class, kb), `fact` (subject_id, object_property, object_id, confidence, status), `fact_evidence` (provenance: `document.<bundle>` + source span), `review_queue` (proposed entities/facts/violations).
- **The graph is vertex/edge tables in SQLite** — a documented standard property-graph schema; fully inspectable, exportable, no hidden machinery. **No separate graph engine in v1; Kuzu is deferred** (MIT but acquired/archived by Apple Oct 2025 — an unmaintained engine is a durability risk). Neo4j (server + GPL), Apache AGE (needs Postgres), RDF/triple stores (wrong mental model for non-technical users) are all out.
- **Data residency (ADR-0009):** Knowledge owns ontology/entities/graph + evidence; it **references** `document.<bundle>` by stable ID, never copies content. Document fetches the ontology from Knowledge on demand (the `Document → Knowledge` edge, see §9). Knowledge fetches representations from Document.

### 8. The resolve-then-ground pipeline (composition with the #24 engine)

1. **Extract** — the engine runs `extract`/`map`. When schema-constrained, the ontology (`knowledge.ontology`) is the schema constraint; raw extraction runs on Document (which pulls the ontology). Output = typed, schema-conformant entities + relations, each with a source span.
2. **Resolve** — the engine calls **`knowledge.entities.resolve`** (scoped to one chosen KB): each mention → a candidate canonical entity or **NIL** (new).
3. **Ground / propose** — matched entities link to their canonical ID; NIL entities and relations/facts become **proposed items** with evidence → the review queue (or auto-commit under an explicit threshold).
4. **Approve → commit** — human approves → promoted into `knowledge.entities` (new entities) and `knowledge.graph` (facts/edges).
5. **Validate** — `knowledge.ontology.validate` runs the domain's validation rules on the extracted/committed structure (grounded or raw); violations flow to the review queue as proposed items (human-or-agent).

The engine **executes** the steps but **does not own the grounding machinery** — it calls into `knowledge.entities.resolve` at run time. A stored procedure whose plan uses `resolve` depends on the KB at run time (ADR-0010 §8).

### 9. Cross-service edges (the seams)

- **Knowledge → Document:** Knowledge fetches faithful representations from Document where the data lives (settled, ADR-0010/0009).
- **Document → Knowledge:** when Document runs a schema-constrained raw structured extraction on a single bundle, it **fetches the corresponding ontology from `knowledge.ontology`** on demand via the callable surface / registry. The ontology is referenced, never copied into Document's store (ADR-0009 residency).

## Considered options

- **Three capabilities (ontology / entities / graph) vs a finer or coarser split** — entity resolution is an *operation* on the entity repository (standard term), not a capability; `kb` was rejected as an unintuitive name in favor of `entities`; validation is a set of operations on `ontology`, not a separate capability, because rules are part of the blueprint.
- **ID scoping `entities.<ontology>.<kb>.<opaque>` vs flat `entity_<n>`** — both scopes (ontology + KB) self-evident in every ID, resolution scoping unambiguous; matches the registry grammar (`knowledge.<kb>`).
- **Validation as a gate vs a report vs a review decision** — a bare gate silently blocks legitimate exceptions; a bare report doesn't close the loop; a review decision (human-or-agent) with fix/validate/reject gives the human full control and turns annotations into training signal.
- **Default-to-human with explicit auto-commit thresholds vs always-human vs mostly-automatic** — always-human is impractical at volume; mostly-automatic hides the no-black-box soul. The graduated policy routes only the uncertain to the human while keeping every decision visible and rule-governed.
- **SQLite tables vs a graph engine** — SQLite is the documented standard two-table property-graph schema, inspectable and exportable; graph engines (Kuzu, Neo4j, AGE, RDF) are overkill, wrong-mental-model, or unmaintained at home scale.
- **LLM-only vs LLM-or-classic-AI routing** — the Inference service has both; the "explicit implementation choice" spans LLMs, embedding/classic-AI models, and deterministic engines uniformly.

## Consequences

- **Creates ADR-0011** (this capability).
- **Composes with ADR-0010** §8 — the seam the DocETL engine calls into for `resolve`/grounding; the engine does not own grounding machinery.
- **Refines ADR-0009** — the Knowledge service's grounding surface (ontology/entities/graph, resolution, review, validation) and the `Document → Knowledge` ontology-fetch edge.
- **Amends/feeds ADR-0008** — the `graph` data_source kind is backed by this capability; `knowledge.<kb>` naming; ontology/entities/graph register entries from Knowledge.
- **Glossary (CONTEXT.md):** ontology (dual role: ground + shape raw extraction), knowledge base, entity repository, knowledge graph, entity resolution, entity linking, canonical ID (`entities.<ontology>.<kb>.<opaque>`), NIL, validation rules/constraints, review queue, resolution scoping, evidence/provenance, grounding, resolve-then-ground.
- **Feeds** the spec anatomy (#12 — this chapter), the capability registry (#20 — entries + the `graph` kind), the dashboard (#8 — the review/validation UI), #27 (enterprise dedup uses `knowledge.entities.resolve`; the review queue is the shared HITL surface), and #14/#23 (any pinned lib passes the OSS/supply-chain gate).
