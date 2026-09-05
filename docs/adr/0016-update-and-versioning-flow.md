# ADR-0016 — The update & versioning flow (versioning scheme, catalog of versions, update & rollback mechanics)

**Status:** accepted (resolution of wayfinder ticket "Design the update & versioning flow", #10); **amends none**; **shapes the `90-lifecycle.md` spec chapter (now `20-concerns/25-lifecycle-and-updates.md` in the architecture doc)** (updates section; ADR-0013 §2); **realizes** the update lanes of ADR-0003/0014 and the two-layer granularity of ADR-0004, and **sharpens** ADR-0008's version float-or-pin in the update context.

## Context

ADR-0003 settled the three update lanes (host layer / services / core), the `install`/`catalog` capabilities, and core self-update with the bootstrap as recovery. ADR-0014 settled the two-layer install and recorded the **frequency-driven taxonomy** (three version tiers: implementations / services / core+bootstrap; two update behaviors: frequent-automatic vs infrequent-user-chosen-bundle) — but explicitly deferred the **mechanics/policy** to this ticket. ADR-0004 added the two-layer granularity (implementations per machine, gated by fit; leader-full / workers-lean) and the supply-chain gate (a week's wait before including the latest version, #14). ADR-0008 settled registry versions float-or-pin. This ADR designs the **versioning scheme, the catalog of versions, and the update & rollback mechanics** on top of those lanes — it does not re-decide the lanes, the layers, or the install shape.

The soul shapes every decision: **no magic, no black box** — nothing changes on the machine without the user acting, and every update is visible and explained before it is applied. Laurent's correction during grilling is foundational: **there is no automatic update in any tier.** The two behaviors differ in *cadence and coordination*, not in autonomy — both are user-triggered and one-click.

## Decision

### 1. Three version tiers, each versioned by what it is

The versioning scheme is **per-tier**, because the tiers advance differently and a single forced version shape would misrepresent them.

- **Tier 3 — platform bundle** — version = the **installer + list of OS programs + uv/Python version + core service APIs**. A **date-based version** on the wordslab-notebooks cadence (`2026-07`). This is **the single user-facing version** that identifies a coherent set of interdependent service+core+bootstrap versions. **Strong backward compatibility is a Tier-3 invariant**: services must be updatable independently of the core.
- **Tier 2 — service** — version = its **list of capabilities + the API & UI of each capability**. **Semver** (`MAJOR.MINOR.PATCH`), each service on its own cadence (e.g. JupyterLab ~1–2/year; the Ollama *engine* rarely though its *models* are weekly).
- **Tier 1 — implementation** — version = the **engine version (e.g. ollama) + the capability-API mappings it targets**. **Not semver** — it is the *artifact's own version* (engine release, model release, harness image tag), because implementations are replaceable artifacts, not software with a semantic contract.

### 2. Capability API versioning (the compatibility substrate)

Each **capability's API has its own version**, built from **required + optional features**:

- A capability API version is defined by a set of **required features** and a set of **optional features** (e.g. an LLM API may have *image input* or *reasoning levels* as optional features).
- **Backward compatibility within a major:** a capability API may only *add* optional features (or make backward-compatible changes) within a major. **A change to the required feature set is a major bump.**
- This is the finest-grained compatibility unit. It is what lets an implementation advance weekly while the service stays put: the service's capability API is unchanged, so the new implementation version is a seamless drop-in.

### 3. Compatibility = declared dependencies (the satisfy relation across the graph)

The core idea that makes the whole scheme coherent: coupling is **not** a lockstep matrix ("impl 3.2 works with service 1.4"). Each artifact **declares dependencies**, and the platform **checks** them. **One rule:** *an update is seamless iff it preserves every compatibility target it touches; an update that changes a target is a coordinated (bundled) change.*

- **Declared dependencies, not a single target.** An implementation (and a service/capability, one level up) **declares dependencies**: for **each** capability API it depends on, it names a **minimum API version + the set of optional features it requires**.
- **The check is a satisfy relation across the dependency graph**: for each declared dependency, the actual implementation of that capability must (a) target an API version **≥ the declared minimum**, and (b) **offer every requested optional feature**.
- **The compatibility verdict** ("is my platform still consistent?") is *all declared dependencies satisfied against their targets* — not one capability matched to one target in isolation.
- An item is flagged **needs-attention** if any declared dependency it depends on is unsatisfied (version too low, or a required optional feature missing). The platform never updates an item into an inconsistent state.
- **How the coupling rules fall out of the one rule:**
  - *Implementation updates frequently while the service stays the same* — the new implementation version targets the **same** capability API version (same required set). Seamless.
  - *A service update ≠ an implementation update* — works when the service bumps a *different* capability's API than the implementation touches, or only adds optional features (which never forces bundling).
  - *Services update independently of the core (Tier-3 backward compat)* — the same mechanism one level up: the base contract stays `/v1`-compatible (ADR-0001), so any service riding `/v1` is untouched by a core update.
  - *Changing only optional features* (e.g. adding image input) is **seamless** — it never touches the required set, so it never forces bundling. **Only a change to the required feature set (a major API bump) is a coordinated change.**

### 4. Update policy — no automatic anything, both behaviors one-click

- **There is no automatic update in any tier.** Tier 1 is *frequent and painless* — a new model appears weekly — but still **user-triggered**: **one click on an Update button suffices**.
- The two behaviors differ in **cadence and coordination**, not autonomy:
  - **Frequent / one-click (Tier 1 — implementations):** additive and swappable (gated by fit, ADR-0004); updated one-click, no coordination.
  - **Bundled / one-click (Tier 2+3 — services + core + bootstrap):** updated **together** as a set of interdependent versions, **one click on the bundle**.
- **v1: one click per item only** — no bulk "update everything" button. Items are pre-ordered by dependency so the user can click down the list in order.

### 5. The two-part update package (metadata first, checks before bytes)

Every update package is split in two:

1. **Metadata file** — the descriptions and *requirements*: resource needs (disk/CPU/RAM), the declared dependencies (per-capability-API minimum version + required optional features), fit info. Small.
2. **The implementation itself** — the heavy artifact (model weights, harness image, service code; GB-scale).

**The download sequence (checks before bytes):**
1. **Download the metadata first** (cheap).
2. **Run the dependency check + fit check** against the dependency graph and machine capacity.
3. **Only if all checks pass → download the implementation.** (Avoids downloading several GB for nothing.)
4. On **verified replace** → prune the previous version (current + one previous retained; see §8).

**When dependencies are not satisfied — no install, no download:**
- The required dependencies are **added to the centralized updates list (§6), in the right dependency order, each with a reason** for install.
- **No automatic install.** The user chooses the installs with individual clicks at his own pace, in order.

### 6. The centralized updates list (the user's regular surface)

- **Persistent, leader-stored state** — the platform keeps **adding available updates** to a leader-centralized list the user can browse regularly. Weekly updates are not automatic; they are *enumerated*.
- An item is **removed when acted on (updated)** or when the **version it refers to is superseded**.
- The leader holds the **metadata** for available versions cheaply (the catalog's "latest-available + requirements") **without downloading the heavy artifacts** — the GB only downloads on an actual apply.
- This is what the dashboard's **Install & Updates** surface renders (§7).

### 7. Update UX / policy (what Install & Updates renders; presentation is #8/ADR-0015)

- **Install & Updates (Administrator view, leader-only)** renders the **centralized list** — persistent, dependency-ordered, browsable. Each item shows: **what it is, its version, what's available, why it's offered (the reason), and the dependency/compat verdict** (safe-to-apply-now, or needs-prerequisites-first).
- **One click per item, no bulk button** (v1). Unsatisfied-dependency items show their reason and stay until their prerequisites are met.
- **The two-lane distinction renders as a filter/label** ("frequent/safe" vs "bundle member"), not a different flow; the action is one click either way.
- **Transparent "what changed":** each item expands to show **the diff in what it touches** — **auto-derived from the metadata diff** (compare required/optional features + API versions between installed and available): which capability API versions/features it changes, whether it is a **major (required-set) change** (which marks it bundled/coordinated) vs **additive**, and the disk/resource cost.
- **Rollback visibility:** the dashboard shows "current bundle: July" with a **rollback to the previous bundle** action (Tier 2+3), and **per-item rollback** (Tier 1).
- **Update vs Repair** (ADR-0014 §7) stays a distinct, clearly-labelled, data-preserving path in the same surface — Update (in place, data volumes untouched) vs Repair/reinstall (separate, guarded, also data-preserving).
- **Leader-only:** updates are a **leader authority surface** (catalog and updates list are leader-centralized; only the leader can click/execute; a worker's dashboard doesn't offer updates, not even read-only; a worker's local `install` executes on the leader's behalf).

### 8. Update & rollback mechanics per lane

- **Frequent / one-click (Tier 1):** click Update on an implementation → download metadata → dependency + fit check → download implementation → **swap in place** (gated by fit) → **prune the old version after the new one is verified**. **Rollback is trivial** (additive + swappable): point back at the **previous version** and prune the new one.
- **Bundled / one-click (Tier 2+3):** click "update to the July bundle" → the platform assembles the **staged set of interdependent versions** → **checks all declared dependencies across the whole graph** first (is this bundle internally consistent and compatible with what's installed?) → applies. **Rollback = the whole bundle rolls back as a unit to the previous bundle**, because the bundle is the atomic consistency unit — never half a service set.
- **Host layer (bootstrap):** updated by **re-running the bootstrap updater** (native, per-machine; the user runs it or the core invokes it locally — ADR-0003). Its recovery path is the re-runnable bootstrap itself.
- **Core self-update (ADR-0003):** the core updates **only as part of the user-clicked bundle** (a Tier-3 item; never a background self-apply). Sequence: two-part download (metadata → checks → implementation) → **keep the previous core version for rollback** → restart into the new version → **verify** (comes up, health check, catalog consistent) → prune the previous core. **On a failed restart, the core automatically reverts to the previous version** on the restart boundary — the one non-click action, and it is a revert-to-known-good, not an update.
- **Core down entirely (crash, failed self-update, machine issue):** the **re-runnable bootstrap** is the recovery path (ADR-0003); data volumes untouched (ADR-0014 invariant).
- **Leader down (ADR-0004 §1):** services keep working, but **updates pause** — you cannot update a leader authority surface while the leader is down. Recovery is the hour-scale guided rebuild.

**Two rollback primitives, one rule:** *rollback restores the previous consistency unit* — the previous implementation version (single) or the **previous whole bundle** (Tier 2+3). Pruning happens only after the replacement is **verified** (checks pass + it actually runs), which is what guarantees "old versions pruned, but never before you can roll back."

### 9. Version retention / pruning (no endless accumulation)

- **Automatic-on-verified-replace:** keep **current + one previous** version of each implementation/service/bundle; prune older versions on successful apply + verification.
- **Implementations are the disk-heavy packages** (model weights, harness images). Bundles are the bundle-rollback disk cost: keep the **full previous bundle** until the new one is verified.
- **Version hygiene** (no endless accumulation) and **backward compatibility** (apps already built keep running) are platform invariants from ADR-0014 §6, realized by the retention rule + the dependency-satisfaction model.

### 10. Interaction with the catalog capability

The core's **`catalog` capability** (ADR-0003) is **leader-only** for versioning. It is a **per-machine inventory of the three tiers** — for each installed item: what it is, its **own version**, **status**, **placement** (which machine(s), ADR-0004), **installed vs latest-available**, and the **dependency-satisfaction verdict** ("is my platform still consistent?" — all declared dependencies satisfied). It is not merely a version list; it is the consistency surface. It also holds the **metadata** for available versions (latest-available + requirements) without the heavy artifacts (§6).

## Considered options

- **A single global version vs per-tier versioning** — a forced uniform version misrepresents how tiers advance (models weekly, Ollama engine rarely, JupyterLab ~1–2/year, core slow). Chose per-tier, each versioned by what it is, with the **platform bundle version** as the single user-facing version.
- **Option A per-capability API versioning (chosen) vs Option B service-semver-as-proxy** — Option A gives each capability API its own version (required+optional features), so an implementation declares its target at the finest grain and can advance independently of unrelated capabilities. Option B (the implementation targets the whole service's semver) is simpler but re-couples an implementation touching only `audio.stt` to an unrelated `audio.tts` API break. Chose **A**: it fully delivers "implementations advance weekly while the service stays put."
- **Strong lockstep coupling vs declared-and-checked target** — a coupling matrix ("impl 3.2 works with service 1.4") is exactly the complexity to avoid; a declared minimum-version+optional-features target checked across the graph is simpler and checkable (no black box).
- **"Automatic" updates vs "no automatic, one-click"** — the handoff inherited "frequent & automatic" from ADR-0014; grilling corrected this to **no automatic anything** (one click suffices). Deliberate deviation, recorded here: nothing changes on the machine without the user acting, even the weekly model swap.
- **One-click-per-item vs a bulk "update everything" button (v1)** — a bulk button is a hidden batch that fights the soul's decisioned stance; items are pre-ordered by dependency so one-click-per-item is still easy. Chose **one click per item in v1**.
- **Two-part package, checks-before-bytes vs direct artifact download** — downloading the metadata first and running dependency+fit checks before the GB download avoids fetching several GB for nothing when deps are unsatisfied. Chose the **two-part package**.
- **Persistent leader-centralized updates list vs recomputed-on-load** — a persistent queue the platform keeps adding to, removed on act/supersede, gives the user a stable "what's pending" surface and keeps the leader's metadata catalog cheap. Chose **persistent leader state**.
- **Auto-derive "what changed" from metadata diff vs author-supplied release notes** — metadata-diff keeps the change summary truthful (no drift) and low-maintenance (no contribution burden). Chose **auto-derived**.
- **Leader-only updates vs workers offer updates** — consistent with the leader-only catalog; updates are a leader authority surface. Chose **leader-only**.
- **Core auto-revert on failed restart vs manual** — the one non-click action is a revert-to-known-good (not an update) on the restart boundary, minimizing user repair for the common failure mode. Chose **auto-revert**.

## Consequences

- **Shapes the `90-lifecycle.md` spec chapter (now `20-concerns/25-lifecycle-and-updates.md`)** (updates section) — deferred this session per Laurent (the chapter is tri-section: installer + updates + backup; #22 backup is open; create once more of its content exists). ADR-0013 maintenance loop: the updates section is filled when the chapter is created.
- **Realizes** the update lanes of ADR-0003 (three lanes, core self-update, bootstrap recovery) and the two-layer granularity of ADR-0004 (implementations per machine, leader-full/workers-lean) in the update context.
- **Sharpens ADR-0008** in the update context: implementation/service versions interact with the registry's float-or-pin (versioned entries, best-effort retention) — an update that changes a target version is what a pinned reference would need to re-pin against.
- **Glossary (CONTEXT.md):** "version", "platform bundle", "capability API version", "update lane", "centralized updates list" (and sharpening existing "update"/"two-layer installation" context).
- **Feeds** "Define the security model for the trusted home environment" (#14 — the supply-chain gate's 1-week wait is a standing requirement this flow *uses* at inclusion, not re-decided here; the metadata/check step is where vulnerability scanning slots in), "Design the backup & recovery story" (#22 — the `20-concerns/25-lifecycle-and-updates.md` chapter (was `90-lifecycle.md`)), "Design the integrated UI (dashboard)" (#8 — the Install & Updates surface renders this flow; already settled).
- **Does NOT resolve** #22 (backup), #14 (security/supply-chain mechanics), #15/#16/#21 (later tickets). One ticket per session.
