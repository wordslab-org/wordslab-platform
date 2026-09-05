# ADR-0013 — The spec anatomy (structure & conventions of the destination)

**Status:** accepted (resolution of wayfinder ticket "Define the spec anatomy", #12); **feeds the map's destination** — the complete, buildable spec. This ADR is the **master structural decision** that organizes ADR-0001…0012 into the deliverable; it does **not** re-decide any of their content. It also records two **catalog refinements** that #12 surfaces but that land as content in their own open tickets (#15, #16, #21, and a note on #18).

> **Evolution (2026-09, terminology sweep #33):** this ADR's scope statements predate later tickets. The catalog has since settled on **13 services** (the Document/Knowledge split at #26 and the combined Publishing & Governance service included), the ADRs now run **past 0013** (current: 0027, resolved by #32), and the Training & Evaluation chapter is **`24-training-evaluation.md`** — created by #30/ADR-0025; `22` is the Document chapter, not Training.

## Context

The map's destination is "a complete, buildable spec … written down in this repo's docs such that building becomes mechanical execution." Every ADR from 0007 onward explicitly records "Feeds the spec anatomy (#12)". This ADR decides the **structure and conventions** of the spec document itself — the `docs/` layout, how each service gets a chapter, how the platform core is specified, the level of detail, where ADRs fit, how the spec is maintained as decisions land, and how it tracks the map's decisions. The *content* of the spec is fixed by the closed tickets (ADR-0001…0012); this ADR organizes that content, it does not change it.

The soul shapes the conventions as much as the content: **no black box, nothing implicit, learn-and-understand**. The spec is written to be read by the platform's own audience — non-technical users who want to understand, and the developers/agents who will implement it.

## Decision

### 1. The spec is a numbered `docs/spec/` tree, not a single file

One file would be too large for a 13-service platform with a deep Knowledge thread, and would be hard to review and maintain as decisions land. A numbered tree mirrors how the map dispatches per-topic: each chapter is a diffable, justifiable file, and the numbering gives stable ordering (foundations → services → lifecycle → dashboard) independent of filesystem sort. `docs/spec/README.md` is the master index: the destination, how to read it (the two-pass reading order), the chapter map, and the conventions.

### 2. Layered parts

- **`00-overview.md`** — the soul, the service architecture, and the cross-cutting principles. **Security and license are cross-cutting principles that live here — not separate chapters.**
- **`10-foundations.md`** — the platform-wide substrate (ADR-0001…0008): service contract + 9 families, service template & contribution, platform core + bootstrap, topology, resource management, inference providers + privacy, composition, capability registry. **Also holds the platform-lifecycle use cases** (first-run/onboarding, joining a machine, backup) — platform-level journeys that don't start in any one numbered service.
- **`20-services/`** — one chapter per service (see §5; up to 13).
- **`90-lifecycle.md`** — **installer + updates + backup in one chapter** (they all describe how to install/update/backup the platform on user machines).
- **`91-dashboard.md`** — its own chapter (the container for the services'/use cases' UIs).

### 3. User-guide-first

The spec is written as close to a **user guide** as it can be while still being complete enough to build from. Every feature is described **from the user experience** — starting from a realistic use case (what a non-technical user is trying to do), then showing how the platform enables it. Never a dry API inventory. The intro-level user and the implementer read the same document; the educational material (Laurent's videos) can lift from the use-case sections almost directly.

### 4. Two-pass generation — the defining structure

Each service chapter is **split into two distinct parts**, and the whole platform is generated in **two passes**:

- **Pass 1 — use cases (Part 1 of every chapter; the user guide and the design input).** A list of **representative use cases**, each **attached to one home service** (where the user's journey starts), even though its implementation reaches into supporting services. Each use case is **decomposed**: the capabilities it needs in the home service, plus the capabilities it needs in **supporting services**, each with its **impact on that service's callable surface**. This is where features are *designed*, from the experience outward. Reading all chapters' Part 1 = pass 1.
- **Pass 2 — build specs (Part 2 of every chapter; mechanical execution).** For each service, **gather every requirement the use cases surfaced for it** (across all use cases that touch it), then describe **how to build it**: callable surfaces (UI/MCP/OpenAPI), contract families, `implementation.toml` shape (the declaration of the service's capabilities and their implementations), key flows, and ADR cross-refs. Reading all chapters' Part 2 = pass 2.

The two passes are a **reading order across the chapters**, not a separate part of the tree. Each service chapter holds both its use cases (Part 1) and its build spec (Part 2), so a reader can read all Part 1s to understand the use cases attached to one service, then all Part 2s to understand how each service is implemented. Every build requirement **traces back to the use case(s) that generated it** (nothing implicit).

### 5. Service chapters (level of detail = "organized reference + citations")

Each service chapter: identity + capabilities, then Part 1 (use cases, decomposed with supporting-service impacts) and Part 2 (build spec). The service part holds **up to 13 chapters**: the 12 settled services (with **Training → Training and Evaluation**, see §6) plus the combined **Publishing & Governance** service, whose slot is reserved and fills when #15/#16/#21 resolve.

**Part 2's level of detail is (C) "organized reference + citations":** the chapter gives enough concrete precision to be buildable at a glance — it *lists* the exact capability names, contract families, and the *shape* of each callable surface and `implementation.toml` — but the parameter-level detail lives in the ADR / service-contract reference the chapter links. Not a dry endpoint dump (the soul argues against the API-summary-style doc the project inverts), but precise about *what exists* and *how it fits together*, deferring depth to the cited ADR.

### 6. Two catalog refinements (content, landed in their own tickets — NOT settled here)

The anatomy surfaced two scope changes. #12 records the *direction* but the *content* lands where it belongs:

- **Evaluation (#16) is a capability of the Training and Evaluation service** — the Training service is renamed and gains the evaluation capability. Chapter `24-training-evaluation.md` becomes the Training and Evaluation chapter. Content → #16 / #30.
- **Publishing (#21) + Governance (#15) form a single combined service** — publishing moved off the Development service's surface, and governance (the catalog of all solutions built/run on the platform, with the documentation and monitoring to check compliance) joins it. The combined **Publishing & Governance** service is the candidate 13th, chapter `33-publishing-governance.md` (created by #15 + #21; ADR-0018 governance + ADR-0019 publishing). Content → #15, #21 (both resolved); catalog note → #18.

### 7. ADRs: "spec cites, never restates" + bidirectional cross-reference

- A chapter's Part 2 **cites each shaping ADR by id** (e.g. the Audio chapter cites ADR-0001 contract, ADR-0002 template, ADR-0006 providers/privacy).
- Each ADR carries a **reverse "Feeds spec chapter X" pointer** naming the chapter it shapes (upgrading the existing "Feeds the spec anatomy (#12)" lines into concrete chapter pointers).
- **The ADR is the source of truth** for a decision; the spec chapter is the **organized build-view**. A chapter never states anything as authoritative that isn't in its cited ADR — it re-presents at the right level of detail. This keeps the spec from becoming a second, drifting ledger.

### 8. The maintenance loop

On each map-ticket resolution: its **ADR is written/updated** → **and, in the same commit, the consuming spec chapter is updated** (or a placeholder *filled*). The map's **"Decisions so far" stays the upstream index** (the chronological record of what was decided); the **spec is the organized current buildable state** (the mechanical-execution view). Neither duplicates the other. **Each resolving session is responsible for landing its decision in the spec** as part of its resolution — the spec is never a separate cleanup task.

### 9. Placeholder chapters are NOT used for the open tickets

The open cross-cutting tickets do not get placeholder chapters. Instead they map onto real chapters or principles (per §2/§6): installer+updates+backup → `90-lifecycle.md`; dashboard → `91-dashboard.md`; security + license → Foundations principles; evaluation → the Training and Evaluation chapter; publishing+governance → the combined service chapter. When each resolves, its content fills the already-reserved place.

### 10. Vocabulary & conventions

Spec chapters use **CONTEXT.md terms exclusively** — service, capability, document bundle, abstract request, explicit implementation choice, callable surfaces, review queue, use case, decomposition, mechanical execution, etc. A **"Conventions"** note at the top of `docs/spec/README.md` states the naming/format rules (two-part chapter anatomy, cite-never-restate, two-pass reading order). CONTEXT.md is sharpened: the "Spec (the destination)" term is updated to reflect this anatomy, and the terms **"use case"** and **"decomposition"** are added.

## Considered options

- **Single file vs tree** — a single `spec.md` is too large for a 13-service platform and hard to diff/maintain; a numbered tree mirrors the map's per-topic dispatch and keeps chapters diffable. Chose the tree.
- **Organize by ADR/foundation vs by service vs layered** — by-ADR scatters each service across many chapters (bad for building one service); by-service leaves the platform-wide substrate homeless (repeated 12× or awkwardly stuffed). Chose **layered**: Foundations (platform-wide ADRs) + Services (one chapter each) + lifecycle/dashboard. The deep Knowledge thread (ADR-0009…0012) **folds into its service chapter** rather than getting its own part, because with the two-pass structure its cross-cutting reach is captured through decomposition impacts in each use case.
- **User-guide vs dry spec** — a dry API inventory inverts the soul; a pure user guide can't be built from. Chose **user-guide-first with a precise build section**: Part 1 is the user guide (and design input), Part 2 is mechanical execution at the "organized reference" level.
- **Per-service split vs a separate Use-cases part** — use cases are mainly attached to one home service even when their implementation spans others, so they stay in their service's chapter (Part 1), not in a separate part. The two passes become a reading order across chapters.
- **Part 2 detail level (A) enumerate-everything vs (B) terse-reference vs (C) organized-reference+citations** — (A) is a dry dump; (B) too thin to build from at a glance; chose (C): precise about what exists and how it fits, deferring parameter-level depth to the ADR.
- **ADR as source of truth vs spec as second ledger** — restating ADRs inline would create a second ledger that drifts; chose cite-never-restate + bidirectional cross-refs.
- **Placeholder chapters for open tickets vs map-onto-real-chapters** — placeholders for cross-cutting concerns would duplicate the fact that these concerns already have homes (lifecycle, dashboard, principles, Training, Publishing & Governance); chose to map each open ticket onto its real chapter and fill it on resolution.

## Consequences

- **Creates ADR-0013** (spec anatomy) — the master structural decision.
- **Layout:** `docs/spec/{README.md, 00-overview.md, 10-foundations.md, 20-services/21-…-33, 90-lifecycle.md, 91-dashboard.md}`; `docs/adr/` holds 0001…0013 as the source of rules.
- **Catalog refinements recorded but landed elsewhere:** Training → Training and Evaluation (→ #16); combined Publishing & Governance service (→ #15, #21; #18 note). Not settled here.
- **Glossary (CONTEXT.md):** sharpened "Spec (the destination)"; added "use case", "decomposition".
- **Every resolving session** is responsible for updating its spec chapter in the same commit as its ADR (the maintenance loop).
- **Feeds the map's destination** — this is the shape of the deliverable; the spec is generated by the two passes and organized into this tree.
