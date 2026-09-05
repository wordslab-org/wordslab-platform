# ADR-0028 — The architecture document (replaces ADR-0013's numbered spec tree)

**Status:** accepted (resolution of wayfinder ticket "Restructure the spec to ADR-0013's tree and decide chapter depth for the nine chapterless services", #34); **supersedes ADR-0013's tree mechanics**; **amends the map's Destination** (issue #1: the deliverable is now a detailed **architecture** document, not a per-service buildable spec); **creates** the `docs/architecture/` tree; **defers** ADR-0013's content-level conventions that survive into the new doc.

> **Supersedes ADR-0013 §1–§2, §5 (tree mechanics only).** ADR-0013's *content* conventions that carry over unchanged into the architecture document — organize-and-cite-never-restate (ADR = source of truth), user-guide-accessible writing, `docs/spec/README.md`-style master index with a conventions note — remain in force. What this ADR overturns is the **shape of the deliverable**: a numbered tree of per-service *build spec* chapters at "organized reference + citations" depth, generated in two passes. That shape served a *specification* phase. Wordslab is in the **wayfinder/architecture** phase, so the deliverable is a **detailed architecture document**: the emphasis is on platform concepts, the general architecture, and cross-cutting concerns; individual service internals are treated lightly.

## Context

ADR-0013 (resolved by #12) mandated a `docs/spec/` tree — a `README.md` master index, `00-overview.md`, `10-foundations.md`, `20-services/21-…-33` (one build-spec chapter per service at level-C "organized reference + citations"), `90-lifecycle.md`, `91-dashboard.md` — generated in two passes (Part 1 = use cases, Part 2 = build spec). That tree was never realized: `docs/spec/` held eight flat files (four service chapters at `22/24/25/33` plus the overview/foundations/lifecycle/dashboard), no `README.md`, no `20-services/`, and nine of the catalog's thirteen services had neither a chapter nor a dedicated design ADR. Ticket #34 opened as "execute the ADR-0013 move, then decide chapter depth for the nine chapterless services."

In the grilling, Laurent redefined the deliverable rather than executing ADR-0013. The map is in the **wayfinder phase, not the specification phase**. A per-service *buildable* spec is not what the map owes: the deep decisions already live in the twenty-seven ADRs, and a chapter the builder can't execute from is not the map's destination. What the platform's own audience (non-technical users who want to understand, and the developers/agents who implement) needs is a document that teaches the **architecture**: the platform concepts, the general architecture, and the cross-cutting concerns, at a detailed level, with service internals kept light. The existing `docs/architecture-overview.md` already sketches this shape and becomes the seed the new document grows from.

The soul governs as always: **no magic, no black box, learn-and-understand**. A document that explains *how the platform is put together and why* — visible, structured, teachable — serves that soul better than a flat inventory of build specs. And a key discipline carries over: nothing already decided and written down may be lost — the architecture document is a **detailed** document at the concept/cross-cutting level, and must relocate every existing fact rather than drop it.

## Decision

### 1. The deliverable is a detailed architecture document, not a per-service build spec

The map's destination (issue #1) is amended: from "a complete, buildable spec … such that building becomes mechanical execution" to **a detailed architecture document** of the platform. Per-service *buildable* depth is consciously out of scope of this map. The architecture document is authoritative as the organized current view of how the platform is structured and why; the twenty-seven ADRs remain the source of truth for each decision, and the document cites, never restates them.

The document is written **detailed at the concept, general-architecture, and cross-cutting-concern level**; **light on the internals of most services**. "Detailed" means no settled fact scattered in the ADRs, CONTEXT.md, or the prior overview may be dropped — it must be relocated into the right concept/concern file. "Light" means a service chapter states identity + its few capabilities + pointers to its design ADRs — not a mechanical build inventory.

### 2. The tree: `docs/architecture/`, emphasis on concepts and concerns

The spec tree is renamed and re-structured to give the concepts and cross-cutting concerns the space they deserve (more files, numbered first), and services a lighter region (numbered after):

```
docs/architecture/
  README.md                 master index + conventions (see §4)
  00-soul.md                the soul, audience, the ZX-Spectrum framing, "no magic no black box"
  10-concepts/              platform concepts & general architecture (THE emphasis)
    11-what-is-a-service.md   service · capability · implementation · contract · template
    12-the-machine.md         core · bootstrap · topology · resources · front door
    13-models.md              where models come from: Inference · engines · providers · privacy
    14-composing.md           agents vs workflows · the registry
    15-knowledge.md           the data side: Document · Knowledge · memory · consent
    16-building-and-publishing.md  develop → publish lifecycle
  20-concerns/              cross-cutting concerns (each gets its own file)
    21-security.md
    22-license.md
    23-learning-and-operability.md
    24-data-consent.md
    25-lifecycle-and-updates.md   (was 90-lifecycle)
    26-dashboard.md               (was 91-dashboard)
  30-services/              the service catalog, renumbered sequentially in catalog order
    31-inference.md … 43-media-transformations.md   (one file per service)
```

The four former heavy chapters (Document, Knowledge, Training & Evaluation, Publishing & Governance) are **relocated into `30-services/` with their full detail intact** — no written detail is lost. Their service chapters keep their depth; the remaining services get either a **detailed** chapter (see §3) or a **light** one.

### 3. Chapter depth per service

Service chapters divide into **detailed (foundational)** and **light (catalog-entry)**:

- **Detailed / foundational** — the services that carry the platform's architecture and/or are already written deep: **Document** · **Knowledge** · **Training & Evaluation** · **Publishing & Governance** (the four relocated chapters, kept at their existing depth) plus **Inference** (the model-serving spine; its chapter is written by ticket #35), **Chat + Agents** and **Workflow** (the agentic/composition spine), **Development** (paired with the Publishing & Governance build→publish thread), and **Connectors** (the single audited security door — foundational; may need its own consolidation ticket first). Nine detailed.
- **Light (catalog-entry treatment)** — identity + a few capabilities + pointer to design ADRs: **Audio** · **Image** · **Generation** · **Media transformations**. Four light.

Existing chapters are relocated *as-is* this ticket; their **recasting** to architecture form (removing the "two-pass / Part 1 / Part 2" spec framing from prose) is a consistency matter handled by the follow-up consistency pass (#36), not done here.

### 4. README.md is the master index

`docs/architecture/README.md` is the master index: what this document is (a detailed architecture document; the ADRs are the source of truth, cited never restated), how to read it, the chapter map, and the conventions. It lists the full service catalog; a service chapter that is not yet physically written is shown as **pending with its owning ticket** — no placeholder files (ADR-0013 §9's no-placeholders discipline carries over).

### 5. `docs/architecture-overview.md` is folded in as the seed

`docs/architecture-overview.md` becomes the **seed** of the new document: its conceptual content (§1–§11) is relocated into the concept/concern/service region files, and its §12 open-questions inventory survives (it is the source of the ticket list). The file itself is retired once its content is folded (this ticket folds its conceptual sections; what remains after the region files are populated is deleted). Cross-references that pointed at `docs/architecture-overview.md` are repointed into the new tree.

### 6. Numbering / renumbering

Service chapters are renumbered **sequentially in catalog order** under `30-services/` (the old `22/24/25/33` numbers encoded ticket-resolution order, not a catalog sequence, and every reference was being rewritten anyway):

| # | Service | Depth |
|---|---|---|
| 31 | Inference | detailed (#35 writes it) |
| 32 | Chat + Agents | detailed |
| 33 | Workflow | detailed |
| 34 | Document | detailed (relocated) |
| 35 | Knowledge | detailed (relocated) |
| 36 | Training and Evaluation | detailed (relocated) |
| 37 | Development | detailed |
| 38 | Connectors | detailed |
| 39 | Publishing & Governance | detailed (relocated) |
| 40 | Generation | light |
| 41 | Image | light |
| 42 | Audio | light |
| 43 | Media transformations | light |

The relocation of the four existing chapters (22→34, 25→35, 24→36, 33→39) and the repointing of every cross-reference (the ADRs that name the old `docs/spec/*.md` paths and chapter numbers, `00-overview.md`/the architecture view, CONTEXT.md) happen in this ticket's commit so nothing dangles.

## Considered options

- **Execute ADR-0013's tree as written vs redefine the deliverable.** Executing a numbered spec tree of buildable per-service chapters was the ticket's literal ask, but the grilling surfaced that the map is in the wayfinder/architecture phase, not the specification phase — a per-service mechanical spec is not what the map owes, and the deep decisions already live in the ADRs. Chose to redefine.
- **Depth: uniform per-service build specs vs concepts/cross-cutting emphasis + light services.** Uniform build specs duplicate the ADRs (which are the source of truth) and read as a dry inventory (against the soul). Chose to put the emphasis on concepts and cross-cutting concerns — more files, numbered first — and treat service internals lightly.
- **Which services are foundational.** Chose the nine that carry the architecture / are already written deep (including Development, paired with build→publish, and Connectors, the security door) and the four content/consumer services light.
- **Keep the two-pass / Part 1 / Part 2 structure per chapter vs drop it.** The two-pass reading order was ADR-0013's device for building from use cases outward; the architecture document is not a build tool, so the per-chapter two-part split is dropped (its useful residue — organized, cite-never-restate, user-guide-accessible — survives as conventions).
- **Keep `architecture-overview.md` as a sibling vs fold it in.** Two overlapping architecture-ish documents would drift. Chose to fold it in as the seed and retire the file.

## Consequences

- **Supersedes ADR-0013 §1–§2, §5** (tree mechanics); ADR-0013's surviving content conventions (cite-never-restate, master-index with conventions note, no placeholders) are re-stated in this ADR §4 and carry into the README.
- **Creates `docs/architecture/`** with the tree in §2; relocates the four service chapters (22→`30-services/34-document`, 25→`30-services/35-knowledge`, 24→`30-services/36-training-and-evaluation`, 33→`30-services/39-publishing-and-governance`) and `90-lifecycle.md`→`20-concerns/25`, `91-dashboard.md`→`20-concerns/26`, all detail preserved.
- **Folds `docs/architecture-overview.md`** into the region files as the seed; the file is retired.
- **Amends the map's Destination** (issue #1) to the detailed architecture document; per-service buildable depth is out of scope of this map.
- **CONTEXT.md updated** (glossary "Spec (the destination)" → architecture document; chapter-path references).
- **Feeds the spawned ticket plan** (see the #34 resolution): #35 writes the Inference chapter; new grilling tickets write the Chat + Agents, Workflow, Development, and Connectors detailed chapters (Connectors may first consolidate its scattered design); a batch task writes the four light entries (Audio, Image, Generation, Media transformations); the consistency pass (#36) recasts the relocated chapters to architecture form.
- **Renumbering blast radius** handled in the same commit: every ADR and doc that named `docs/spec/<file>` or the `22/24/25/33` chapter numbers is repointed to its new home.
