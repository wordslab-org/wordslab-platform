# ADR-0024 — The learning experience: per-service learning bar, continual personal assistant, guided AI build process

**Status:** accepted (resolution of wayfinder ticket "Design the learning experience", #29 — the per-service learning/operability bar, the continual learning assistant, and the guided AI build process, plus the folded-in onboarding experience from #22); **amends ADR-0002** (the service template gains a required learning/operability bar declaration); **creates the `10-foundations.md` spec chapter** (hosting the learning-experience cross-cutting thread, resolving the deferral recorded by #28); **amends `91-dashboard.md`** (the learning assistant's surface + the onboarding/first-run experience); **feeds** "data consent & handling" (#31 — role-scoped tool access for the assistant, recorded in #31's body) and the "Training service" (#30 — the guided build process steers learners to the eval capability, recorded in #30's body); **references** the implementation-declaration reconciliation (its per-implementation half is now concrete: #32, resolved by ADR-0027 — the bar is declared per implementation in `implementation.toml`).

## Context

The platform's stated main goal is **educational**: teach non-technical people to learn *and understand* AI, and to **build AI applications** for themselves, their family, and their friends. The map's soul is "no magic, no black box — everything manually chosen, visible and explained step by step." ADR-0015 already added a **thin-by-default / deep-on-request educational guidance layer** in the dashboard ("every surface teaches"). But nothing designed the **learning experience itself**: the per-service documentation/skills/MCP/diagnostics requirements, the continual personal assistant, or the guided build process. This ADR adds that experience as a **cross-cutting thread** across the settled surfaces (template, registry, dashboard, composition, Development) — it does **not** reopen any of them.

The soul shapes everything. The audience learns and understands; the platform is the **ZX Spectrum / C64 of the AI era** — teaching by doing, visibly, step by step. Two standing truths recur: **simplicity is the main feature** (the bar must not burden services into unusability), and **no theater** (a declaration that something is deliberately human-only beats a hollow fake artifact).

Three settled mechanics the design rests on (not re-decided):

- **Composition (ADR-0007):** agent = interactive loop, workflow = deterministic Python, with an agent→workflow graduation path; **harness images** (Hermes Agent, OpenCode, Pi) are bring-your-own-loop, second-class for composition, driven as workspace-session runners. MAF is the platform-native composition primitive.
- **Registry (ADR-0008):** thin index + name authority on the leader core; entries `tool | api | agent | workflow | skill | data_source | webapp`; per-agent scoping enforced server-side (accessible set lives in the agent definition); skills are registry `skill` entries living in the Chat + Agents service.
- **Dashboard (ADR-0015):** the single human front door; role-aware (Administrator · User · Builder, gated by the settled admin/member level — every user is also a builder); hosts the UI of every service capability; hosts first-run welcome.

A clarifying decision: **models vs implementations.** The service template's model-declaration mechanism evolved from a per-capability `models.toml` (ADR-0002 as written) to per-implementation `implementation.toml` (ADR-0004's implementation layer, formalized by ADR-0018, reconciled by ADR-0027). This ADR designs the learning bar against the *implementation* model; #32 (ADR-0027) resolved the file naming — `models.toml` is retired.

## Decision

### 1. A cross-cutting learning/operability bar on every service and implementation

Every **service** and every **implementation** carries a required, graded set of learning/operability artifacts, in four categories, each graded by depth of **how to use · how it works · study in depth · going further**:

- **Documentation** — how to use · how it works · study in depth · going further, authored to be **readable and indexed for agents** (not only for humans). **One source, dual-consumed:** structured Markdown with a canonical section schema + **front-matter** (title, capability/implementation, level, keywords, MCP tool references), so the human surface and an agent indexer read the same file — no separate agent-authored document set, no drift. The front-matter's MCP tool refs point at the capability's registry entries (ADR-0008).
- **Skills + MCPs** — so agents can **configure and use** the capability (the platform's own AI can operate it). MCP tools are **auto-generated from the OpenAPI spec** by default (ADR-0002/0008 — the MCP surface *is* the API), with hand-written `@tool` overrides where the machine API needs an English-friendly interface. Each capability additionally ships a **how-an-agent-drives-me `skill`** (a registry `skill` entry) as a first-class bar artifact. Where a capability genuinely can't be agent-driven, the bar records an explicit **"not agent-operable"** note rather than a fake skill — no theater.
- **Diagnostics tools** — to fix problems and optimize behavior.

**The bar is a declared, auditable requirement, not an aspirational guideline.** It is **declared in the service template** (ADR-0002): per-service/capability in the service declaration, per-implementation in `implementation.toml` (ADR-0027, #32). The bar is **enforced at contribution time**, mirroring the mechanical/compliance quality bar (ADR-0018's computed tiers): **mandatory to publish for `bundled` and `listed`** things (they can't be listed/bundled without it), **recommended-with-tracked-gaps for `third-party`** (the gap is recorded, not blocking). Applies to published things' documentation/skills/diagnostics surface too (ADR-0019).

### 2. A continual learning assistant for every user (built on Hermes Agent)

A **personal assistant to learn on the platform and build AI applications** — the teaching vehicle for the most popular personal assistant, **accessible everywhere**.

- **It is literally Hermes Agent** (the vendored harness image) — **not** a MAF agent. Rationale: the assistant is *not part of a deployed solution built with the platform*; there is no need to parse or compose its sessions. What matters is that the user/builder learns to use the most popular personal assistant by using it, and inherits its **continuous-learning features, learning skills, and efficient tools**. This is consistent with ADR-0007 §2: Hermes is already a vendored harness-image session runner; MAF remains the *composition* primitive, unchanged. The assistant is deliberately outside composition.
- **One workspace = one Hermes agent state per physical user** — not per role. (A physical user has three identities — `laurent` / `laurent-builder` / `laurent-admin`, from #22/#31 — but a *single* Hermes state for the physical person.)
- **Automatic mounting.** On **new-user creation**, the platform automatically mounts every installed service/implementation's **learning-bar artifacts** (docs + skills + MCP tools + diagnostics) into that user's Hermes workspace — via the registry (ADR-0008), no user wiring.
- **Docs everywhere; tools by role.** **Documentation is mounted for all users regardless of role** — including admin-service docs for non-admins — because the goal is educational: a family member can *read* how the admin service works. **Tools/skills are role-scoped**: admin and builder tools/skills are **not mounted** for a non-admin / non-builder user. The platform makes clear to Hermes which tools are out of reach for its current acting identity.
- **One identity per session, chosen at launch.** When a session starts, the acting identity is set by **which view launched the assistant**: User view → `user` identity; Builder view → `builder` identity; Administrator view (admins) → `admin` identity. Tool mounting and action-context (ADR-0003) follow that identity for the whole session. **No mid-session role switching** — the identity is the single ambient fact, visible and explicit (the soul), not re-asked per call.

The assistant's **role-scoped tool access is data-consent content belonging to #31** and is recorded there (not decided here): role=user → a tool can access only that user's own data; role=builder → only anonymized + non-sensitive data in the builder sphere; role=admin → only admin data not linked to a user (platform-service operations). See #31.

### 3. A guided process to build AI solutions

A **guided AI-build process**, designed so a non-technical learner can build real AI applications step by step.

- **A versioned, first-class skill set** (registry `skill` entries, ADR-0008): the **Matt Pocock engineering skills** (wayfinder / grilling / tdd / code-review / …), **adapted/whitelabelled by the platform** so they invoke the platform's own capabilities (call a model through Inference, evaluate through Training-and-Evaluation / ADR-0020, use the Development service's agentic-dev-workflow). Not a bare import of generic skills — they are platform-vendored and platform-aware.
- **Extended with ML + evaluation best practices** from **Shreya Shankar & Hamel Husain**: evaluation is designed **into** the build flow, not bolted on at the end — analyze-first error analysis → build an eval dataset → open coding → axial coding → structured binary failure modes → LLM-as-judge validated against human labels. The platform's own **eval capability (ADR-0020)** is the **destination the guide steers learners to** for checking their builds.
- **Surfaced through the Development service's `agentic-development-workflow` capability** (the UI embodying the guided build).
- **A human-readable process documentation** — a docs deliverable, part of the learning bar — teaches the process *before* the learner uses the skills (the skills are the executable tools; the docs teach the process).

### 4. The onboarding experience (folded in from #22)

The **first-run/initial journey** is part of the learning/guidance experience. A new user is taken through getting started on the platform, and — specifically for backup — **enters their backup passphrase**, told explicitly that they must remember it because it will encrypt their backups so that only they can decrypt them. (Passphrase hashed; the hash stored and used as the key to encrypt the user's per-service backup zips. On restoring to a new platform the user re-enters the same passphrase, points at their chosen backup target, and restores from the other install — ADR-0021.) The onboarding story lands in the dashboard first-run surface (`91-dashboard.md`) and the Foundations chapter.

### 5. Where it lands

- **ADR-0024** (this decision) is the source of truth.
- **Amends ADR-0002** — the service template gains the required learning/operability bar declaration (per-service/capability now; per-implementation in `implementation.toml`, ADR-0027/#32).
- **Creates `docs/spec/10-foundations.md`** — hosting the learning-experience cross-cutting thread as part of the platform-wide substrate, resolving the deferral #28 recorded (this ticket is one of the cross-cutting tickets #28 was waiting on).
- **Amends `docs/spec/91-dashboard.md`** — the learning assistant's surface (the preloaded/embedded assistant, launch-by-view → acting identity) and the onboarding/first-run experience.

## Considered options

- **Declared auditable bar vs aspirational guideline** — an unwritten aspiration vanishes under contribution pressure; the template can enforce the *shape* (which categories must be declared) and the graded depth. Chose a declared, auditable bar with mandatory/listed and tracked-gaps/third-party tiers (mirroring ADR-0018).
- **One-source-dual-consumed docs vs separate agent-authored summaries** — a second, agent-facing document set drifts and duplicates; the canonical schema + front-matter makes one file equally machine-consumable. Chose one source.
- **Full skill for every capability vs "not agent-operable" note** — forcing a fake skill is theater against the soul; an explicit human-only declaration is more honest. Chose the explicit note where the capability genuinely can't be agent-driven.
- **Hermes Agent (harness) as the assistant vs a MAF native agent** — the assistant is not part of a deployed solution, and the goal is to teach the most popular assistant and inherit its learning features/skills; MAF's structured/attributable properties are for *composition*, which the assistant is outside of. Chose literally Hermes Agent, with MAF unchanged as the composition primitive.
- **One state per physical user, one identity per session (chosen) vs per-role states / mid-session switching** — a single Hermes state keeps the person's continuity; one identity per session chosen at launch keeps the acting role visible and auditable (no hidden switching). Chose one state + one identity per session.
- **Docs everywhere + tools-by-role (chosen) vs fully omnipotent or fully role-isolated** — reading admin/builder docs for all is educational (the soul); acting is role-bounded for control. Chose docs everywhere, tools by role.

## Consequences

- **Amends ADR-0002** — the service template gains the learning/operability bar declaration (docs, skills+MCP, diagnostics, graded by depth); mandatory for bundled/listed, tracked-gaps for third-party.
- **Creates `docs/spec/10-foundations.md`** (this resolution) — the platform-wide substrate + the learning-experience cross-cutting thread; resolves the #28 deferral for this content.
- **Amends `docs/spec/91-dashboard.md`** — learning-assistant surface + onboarding/first-run (incl. the backup-passphrase step).
- **Feeds #31 (data consent)** — the assistant's role-scoped tool access (user-own-data / builder-anonymized / admin-platform-ops) is recorded in #31's body as consent content; #31 designs the action-context enforcement.
- **Feeds #30 (Training)** — the guided build process steers learners to the eval capability; recorded in #30's body.
- **Resolves #32** — the bar's per-implementation half is now concrete (ADR-0027: the bar is declared per implementation in `implementation.toml`).
- **Model-license note (ADR-0022):** any model-backed step in the learning experience (e.g. the LLM behind the assistant's skills or the guided-build/eval flow) routes through the Inference service as an explicit implementation choice carrying its privacy tier and respecting its model compliance profile.
- **Glossary (CONTEXT.md):** adds "learning/operability bar", "learning assistant", "acting identity", "guided build process"; sharpens the Development service (agentic-dev-workflow carries the guided build) and the Chat + Agents service (Hermes as the learning assistant; skills home).
