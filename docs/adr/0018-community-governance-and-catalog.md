# ADR-0018 — Community governance of the service catalog (the governance half of the combined Publishing & Governance service)

**Status:** accepted (resolution of wayfinder ticket "Design community governance of the service catalog", #15); **amends none**; **sharpens ADR-0002** (implementation declarations as a named `implementation.toml`, symmetric with `service.toml`; the community-catalog listing surface); **sharpened by ADR-0019** (`catalog.toml` renamed `platform.toml` everywhere, including the community-catalog listing file); **feeds** "Define how agents publish generated web apps & services" (#21 — the combined service's publishing half resolves alongside; the `33-publishing-governance.md` chapter fills when #21 closes); **references but does NOT resolve** "Define the platform's component license policy" (#23) and "Define what evaluation means in the platform" (#16).

## Context

The soul lists **easy community contributions as a stated goal** — but every settled decision so far is **solo-first**: the code surface (ADR-0002) optimizes for one contributor and defers community machinery until demand. This ADR resolves the *governance/process* layer on top of that code surface — **where the community catalog lives, the review process, the quality bar, and how a community contribution graduates to a bundled platform service.** It does NOT re-decide the template (ADR-0002), the registry's name authority (ADR-0008), or the versioning scheme (ADR-0016) — it designs the governance layer on them.

ADR-0013 §2 determined that governance is the *catalog-of-solutions + compliance* half of a **combined Publishing & Governance service** (candidate 13th, chapter `33-publishing-governance.md`); #21 owns the publishing half. This ADR is #15's contribution to that combined scope.

The tension #15 must resolve: how to be **genuinely open** to community contributions without building **heavyweight enterprise governance** (boards, CLAs, formal review pipelines) before there is demand. The answer below keeps governance light, transparent and mostly mechanical — **status is computed, never asserted**, so there is no black box.

## Decision

### 1. Three distinct catalog surfaces, with a defined relationship

"Catalog" is not one thing. Three surfaces coexist, each doing one job:

- **Community catalog** — a **git repo** of thin catalog listing records (see §6). This is where community services are *submitted and browsed*. The **official one lives on the `wordslab-org/wordslab-platform` GitHub repo** (a page/directory of the most popular community packages); **anyone can host their own catalog repo** (their own GitHub or elsewhere). A machine points at a catalog *source* — default the official repo, changeable to any other. A git repo is both *hosted* (discoverable anywhere) and *transparent* (forkable, clonable, diffable) — exactly the soul.
- **Core `catalog` capability** (ADR-0003) — the per-machine inventory of **what's installed and available to install** on this machine (placement/version/status, leader-only). A service chosen from a community catalog flows into it through the **normal `install`/update machinery (ADR-0016)** — never a parallel path.
- **Runtime registry** (ADR-0008) — the **name authority** that resolves stable names at runtime once a service is installed and running (`document.parse` → endpoint). Unchanged.

Flow: **community catalog (git repo, source) → user chooses → core `catalog`/`install` (ADR-0016) → runtime registry (ADR-0008).** The community catalog is the discovery/submission surface; the core catalog is the machine surface; the registry is the runtime-resolution surface.

This confirms ADR-0003's "Deliberately NOT centralized": the service catalog's *content & governance* is not the core's — the community catalog is a distinct, hosted surface the core's `catalog` capability merely consumes.

### 2. Two contribution tiers — the review bar scales with blast radius

Community contributions come in two fundamentally different shapes (ADR-0002/0008 vocabulary):

- **Implementation contribution** — delivers a concrete way to satisfy an **already-defined capability API** (a new STT engine for `audio.stt`, a new model). The contributor defines **no new API** and builds **no UI** (the UI comes from the owning service/capability). Lands in an **existing service's implementation set** (`implementation.toml`, §5) — extends an existing catalog entry, creates no new namespace.
- **Full service contribution** — creates a new `services/<name>/` from the template (ADR-0002). The contributor **defines new APIs themselves** (capabilities/families) and **must implement a UI integrated into the platform** (shared UI kit + dashboard nav). Rarer, much heavier: new API surface the whole platform's name authority and catalog must accommodate.

### 3. The review/validation process — automated gate + light maintainer look

The review bar scales with the contribution's blast radius; **nothing is fully automated-merge, nothing needs a review board.**

- **Implementation contribution** → low bar, mostly automated: conformance to the *existing* capability API + resource/privacy declaration + license check + supply-chain scan (1-week gate, ADR-0017) → **light maintainer look**. No new-API or UI review.
- **Full service contribution** → higher bar: the ADR-0002 conformance gate (vendored contract, `service.toml`) + **maintainer review of the contributor's own API design** (new capabilities/families, name grammar) + **UI integration** against the UI kit + license + supply-chain scan.

The maintainer look is a spam/malicious/duplicate filter, not a quality-of-model judgment. Solo-first keeps it cheap and open.

### 4. The quality bar — conformance + safety, mechanical, not quality-of-model

A service/implementation is acceptable to list when it:

1. **Passes the contract conformance gate** (ADR-0002 — vendored contract, `service.toml`/`implementation.toml` validation);
2. **Declares a clear OSS license** (→ #23; we *reference* the check, we do not decide the license policy here);
3. **Passes the supply-chain scan + 1-week wait** on its dependencies (ADR-0017);
4. **Declares resource requirements + privacy labels correctly** (so placement and privacy surfacing work — ADR-0005/0008).

**Explicitly NOT part of the bar:** "is the model good?" (that's evaluation, #16 — a service is listable even if nothing is benchmarked), popularity/stars, contribution size, subjective taste. The bar is **mechanical and checkable, not subjective** — transparency over gatekeeping.

### 5. Three review-status levels — computed, never declared

A catalog entry's status is a **pure function of where the code lives + official-catalog membership**, so there is no status field that can drift or lie:

- **`bundled`** — implemented **in the `wordslab-platform` repo itself**: ships with the platform, appears in the v1 catalog on install, and the platform **takes on updating/maintaining it with the bundle** (ADR-0016 Tier 2/3 bundled lane). The strongest bar.
- **`listed`** — implemented **in another repo** but **referenced in wordslab-platform's `platform.toml`** (the catalog listing file, renamed from `catalog.toml` by ADR-0019): accepted via the PR + light maintainer look into the official community catalog.
- **`third-party`** — implemented elsewhere and **not referenced** by wordslab-platform's catalog: living in someone else's catalog repo, **not reviewed by the platform at all**. Installable, but visibly unvetted.

Status is **derived**, not declared — no hidden judgment field, no black box. Because `third-party` exists, entries carry **source/attribution** (which catalog repo they came from) so the "unreviewed" label is traceable.

### 6. Graduation to `bundled` — conservative, maintainer-decided

Graduation to `bundled` is a **deliberate, human-decided step** — and **conservative**, because bundling carries a real ongoing cost (the platform updates/maintains the service with its bundle). Specifically:

- **Bundling = an ongoing update/maintenance commitment** (the defining cost — the thing that keeps graduation rare).
- **Trigger:** the maintainer (Laurent, solo-first) decides a service is ready at a **higher bar** — proven real usage/demand, stable well-formed API, well-maintained, passes the same conformance/safety bar — and is willing to commit to maintaining it. **Not automatic by popularity** — usage is a *signal* that helps decide, never a rule that forces graduation.
- The default posture: **few bundled services, graduate rarely**; the vast majority of community services stay `listed` (or `third-party`) forever.

### 7. Governance roles — minimal, solo maintainer, no community machinery in v1

- **Maintainer** (Laurent, solo-first) — the only human with authority. Decides `bundled` (graduation) and is the human half of the light look for `listed`. No formal structure.
- **Contributor** — anyone who opens a PR to a catalog repo (or hosts their own). **No CLA, no governance board, no formal RFC pipeline in v1** (ADR-0002's explicit stance). 
- **Automation** — the CI conformance gate, supply-chain scan, catalog-format validation, license check. Does the mechanical work, **never decides**.

**No community-reviewer role in v1.** If contribution volume ever grows past what the maintainer can eyeball, *then* introduce trusted community reviewers — that is exactly the "defer community machinery until demand" move. Do not build the reviewer role before there is traffic to justify it.

### 8. The catalog format — description vs. listing (two distinct metadata kinds)

Two metadata kinds must not be conflated:

**Description metadata** (lives in the **source repo**, authoritative at install):
- `service.toml` for a full service (ADR-0002 §5);
- **`implementation.toml`** for an implementation — a named file symmetric with `service.toml`, formalizing what ADR-0002 §5 described as per-capability implementation declarations (identity, source, resource profile, privacy tier, license, links). *(Sharpen of ADR-0002, recorded here.)*

**Catalog listing metadata** — what a catalog repo actually *is*: a **thin index of listing records**, each **pointing to** the description above, never duplicating it. One **`platform.toml`** per repo lists the `service.toml`/`implementation.toml` files available from this repo **or other repos**. *(Renamed from `catalog.toml` by ADR-0019 — a project root now carries `platform.toml` (platform services/implementations) + `publish.toml` (generic publishables); the name `catalog.toml` is retired.)* Each listing record carries:

- **name** + **type** (`service` vs `implementation`);
- **source/attribution** — which catalog repo + which source repo it points to (traceability, §5);
- **version + checksum** of the referenced package (§9 — a pinned, verifiable pointer, dovetailing ADR-0016 versioning and ADR-0017 authenticity);
- **license** (records what the source declares; → #23);
- a **copy of the description** for browsing efficiency — but the **source `service.toml`/`implementation.toml` is the reference when installing**; the catalog copy is a cache, never the authority.

TOML throughout — one language, consistent with the soul's "whole stack readable."

### 9. Reference integrity — version + checksum

When a `platform.toml` references another repo, it references a **version and a checksum** of the package. A reference is a **pinned, verifiable pointer** — consistent with ADR-0016 versioning (per-tier versions, float-or-pin) and ADR-0017's update-authenticity stance (checksummed third-party artifacts). No unverifiable "latest whatever" reference.

### 10. The compliance catalog — the "governance" half of the combined service

Per ADR-0013 §2, governance = **"a catalog of all the solutions built and run on the platform, with the documentation and monitoring necessary to check their compliance."** This is **distinct from the community catalog** (the discovery/submission surface, §1). The compliance catalog is the **platform-side, per-machine audit view** — surfaced in the dashboard's **Administrator view** (ADR-0015) as "what's on my platform and is it compliant." It inventories every **installed/running** service, capability, implementation, and published app/workflow, each carrying its **compliance facts**:

- version + update status (ADR-0016);
- license (the declared one; → #23);
- privacy tier (`local` / `cloud_no_data` / `cloud`, ADR-0008);
- supply-chain scan status (ADR-0017 — passed / flagged);
- resource usage (ADR-0005);
- **computed** review status (`bundled` / `listed` / `third-party`, §5).

This is the monitoring/audit side of governance; the community catalog is the discovery side. They are deliberately separate surfaces.

## Considered options

- **Three surfaces (chosen) vs collapsing the community catalog into the core's `catalog` or the registry** — the core `catalog` is per-machine (installed/available) and leader-only; the registry is the runtime name authority. Neither is a hosted, browsable, submittable index of *new* community services. The community catalog is the one **shared** surface — a local-first platform still needs a hosted git index so anyone can discover a service published by someone else. Chose three distinct surfaces with a defined relationship.
- **Community catalog as git repo (chosen) vs a bespoke hosted index/database** — a git repo is simultaneously hosted (discoverable) and transparent (forkable, diffable, reviewable via PRs); it also lets anyone host their own, which no central database allows. Chose the git repo.
- **Two contribution tiers (chosen) vs one uniform review process** — implementations (no new API/UI, conform to an existing capability) and full services (new API + UI) have very different blast radius; one bar would either over-gate implementations or under-gate services. Chose per-tier bars.
- **Automated + light maintainer look (chosen) vs fully-automated merge vs formal review board** — fully-automated merges leave no spam/malicious filter; a review board is exactly the heavyweight enterprise governance the soul rejects and solo-first defers. Chose a light maintainer look on top of the automated gate, no board.
- **Mechanical quality bar (chosen) vs quality-of-model bar** — a subjective "is it good" bar is a black box and belongs to evaluation (#16); a conformance/safety bar is checkable and transparent. Chose mechanical.
- **Computed review status (chosen) vs declared status field** — a declared status can drift or lie; deriving it from code location + official-catalog membership is transparent and self-consistent. Chose computed.
- **Conservative maintainer-decided graduation (chosen) vs automatic/popularity-driven** — bundling carries an ongoing update/maintenance cost, so it must be a deliberate, rare decision, not a popularity reflex. Chose maintainer-decided.
- **Solo maintainer, no community reviewers (chosen) vs a reviewer role now** — there is no contribution volume yet; adding reviewers is premature. Defer until demand. Chose solo maintainer.

## Consequences

- **Creates ADR-0018** — the governance half of the combined Publishing & Governance service. `33-publishing-governance.md` **deferred** until #21 resolves the whole combined service (ADR-0013 §6; the chapter is combined by design, so writing half now would mean a placeholder + near-total rewrite; the ADR is the source of truth until then).
- **Sharpens ADR-0002** — implementation declarations formalized as a named **`implementation.toml`** symmetric with `service.toml`; the community-catalog listing surface (a catalog repo is a thin index of pointing records, not a re-statement of service definitions).
- **Glossary (CONTEXT.md):** add "community catalog", "platform.toml" (renamed from `catalog.toml`), "implementation.toml", "bundled service", "listed service", "third-party service", "compliance catalog", "graduation".
- **References, does not resolve:** license policy → #23 (this ticket's quality bar references a license *check*, never decides the policy); evaluation → #16 (quality-of-model is out of this bar).
- **Feeds #21** (publishing) — the combined service's scope resolves together; #21's body updated with an "Updated by #15" provenance note. The `33-publishing-governance.md` chapter fills when #21 closes.
- **Unblocks:** the dashboard's Install & Updates / Administrator surfaces (ADR-0015) can render the compliance catalog; the v1 catalog (#18) can mark bundled services by the computed rule.
