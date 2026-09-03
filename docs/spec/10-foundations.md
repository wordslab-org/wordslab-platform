# 10 — Foundations: the platform-wide substrate and the learning experience

> **Status:** created at the resolution of wayfinder ticket "Design the learning experience" (#29, ADR-0024), resolving the deferral recorded by #28. **Source of truth:** the substrate ADRs (0001–0008) plus ADR-0024 (learning experience). This chapter is the **organized build-view** — it cites, never restates. It holds the platform-wide substrate (what every service shares) **and** the cross-cutting **learning experience** thread, plus the platform-lifecycle use cases that don't start in any one numbered service.

## Identity

`10-foundations.md` is the platform-wide substrate — the parts of the system every service shares and builds on — together with the **learning experience**, the cross-cutting thread that makes the platform's educational goal real across every service. Per ADR-0013 §2, Foundations covers the service contract + families, the service template & contribution surface, the platform core + bootstrap, topology, resource management, inference providers + privacy, composition, and the capability registry (ADR-0001…0008), *plus* the platform-lifecycle use cases (first-run/onboarding, joining a machine, backup) that don't start in any one numbered service, *plus* the learning experience (ADR-0024).

## Part 1 — Use cases (user guide)

### Platform-lifecycle journeys (don't start in a numbered service)

1. **"First-run: get to a working, understood platform"** (onboarding, ADR-0024 §4) — the initial journey through getting started: recap of what's installed and running, the front-door address, a short guided tour, **datasets opt-in (off by default)**, and — specifically — entering the **backup passphrase**, told explicitly that it must be remembered because it encrypts the backups so only the user can decrypt them. Supporting: dashboard first-run surface (ADR-0015/0024), backup (ADR-0021), install (ADR-0014).
2. **"Join a machine to the platform"** (ADR-0004/0014) — leader-dashboard-initiated join, guided end to end. Supporting: topology (0004), installer (0014).
3. **"Back up and restore my data"** (ADR-0021) — per data sphere, encrypted per-user zips; restore to a new platform by re-entering the passphrase. Supporting: backup (0021), lifecycle (`90-lifecycle.md`).

### The learning experience (the platform's educational goal)

1. **"Learn how to use and understand any installed capability"** (everyone) — every service/implementation carries a graded learning bar (how to use · how it works · study in depth · going further); the dashboard's "every surface teaches" guidance layers on top; the learning assistant can explain any capability. Supporting: learning bar (ADR-0024 §1), dashboard guidance (ADR-0015), registry (ADR-0008).
2. **"Ask my personal assistant"** (everyone) — a continual learning assistant (Hermes Agent) is accessible everywhere; launched from a view it runs as that acting identity (user/builder/admin), with docs mounted for all and tools/skills scoped by role. Supporting: ADR-0024 §2, Chat + Agents (0007/0008), #31 (consent).
3. **"Build an AI application, guided"** (everyone, esp. Builder) — a versioned skill set (Matt Pocock engineering skills, platform-adapted) + a human-readable process guide teach the build process, with ML/evaluation best practices designed in and steering to the eval capability. Supporting: ADR-0024 §3, Development (agentic-dev-workflow), eval (ADR-0020), #30.

## Part 2 — The substrate (organized reference + citations)

Each substrate element lists its governing ADR and the essentials; the ADR is the source of truth (cite-never-restate).

### 2.1 The uniform service contract (ADR-0001)
Base contract (transport/OpenAPI, Bearer keys, `/v1`, 11-code errors, cursor pagination, health+resources+per-model, idempotency, usage) + nine contract families (Responses API, copy-the-best inference, stateless MCP + capability registry, Realtime/WebRTC, async jobs & model lifecycle, batch, resumable uploads, HMAC webhooks, authoring & management).

### 2.2 The service template & contribution surface (ADR-0002)
A service is a folder `services/<name>/` copied from `template/`: self-contained vendored contract, in-process `capabilities/` (each with its own business logic, implementation declarations, routes, UI, sharing one SQLite DB), three callable surfaces (human UI / agent MCP / deterministic OpenAPI), FastHTML + Alpine (vendored, no CDN), declaration in `service.toml` + per-implementation `implementation.toml`, heavy-dependency coordination, and — added by ADR-0024 — the **learning/operability bar** (see §4.1). Solo-first contribution: copy-to-start, CONTRIBUTING checklist, conformance gate.

### 2.3 The platform core + bootstrap (ADR-0003)
One platform core per machine (fleet/install/catalog/resources/backup/users/keys/secrets/monitoring/logs/stats/datasets; UI = dashboard) + a native bootstrap layer. Leader/worker role split; the core centralizes control, never the request path; deliberately NOT centralized are business logic/DBs/UI/APIs, model lifecycle, raw logs/usage storage, backup data, catalog content, evaluation, security mechanics, inbound exposure, data residency.

### 2.4 Multi-machine topology (ADR-0004)
Leader (cloud nodes can be leaders; single leader, no HA in v1) + workers; join = leader-dashboard-initiated, guided (LAN via mDNS + manual fallback; cloud joins overlay first). Two-layer install; dependency graph + activities; placement simulation, user-confirmed, no scheduler; routing = placement outcome, visible per call; multi-disk = data locations named after disks, roles as folders, no shared storage; front door = static reverse proxy on the leader.

### 2.5 Resource management (ADR-0005)
Uniform requirements (install disk + running formula) on services/capabilities/implementations; measured capacity + speed rank; **reservation ledger** (load/unload bookings); install-fit separated from runtime; working set = desired, resident = loaded; idle sweep + ask-on-ambiguity with remembered rules, no LRU; disk quotas; cloud spend (monthly cap + opaque remaining-% gauges).

### 2.6 Inference providers + privacy (ADR-0006)
Cloud access = implementations of the Inference service's capabilities (same surface as local); provider registry on leader-core config; bundles (one provider row, capability-tagged legs); shared `secrets` vault; two exclusive billing modes; **three privacy tiers `local` / `cloud_no_data` / `cloud`**, documented + user-chosen. **Privacy is a property of the chosen implementation** (ADR-0007 §10); no inference policy anywhere.

### 2.7 Composition (ADR-0007)
**Agent** (interactive loop) vs **workflow** (deterministic Python DAG), interoperable, agent→workflow graduation path; workflow = a Python program with a tiny primitive set (`call`/`model`/`agent`/`subworkflow`/`delay`/`event`/`user_input`); invocation follows the caller (workflow→OpenAPI-first/MCP-fallback, agent→MCP, `model`→Responses); **MAF** = the platform-native loop; **harness images (Hermes Agent, OpenCode, Pi) = bring-your-own-loop**, second-class for composition, driven as workspace-session runners; explicit implementation choice, no inference policy, no automatic cloud fallback.

### 2.8 The capability registry (ADR-0008)
Thin index + name authority on the leader core; entries `tool | api | agent | workflow | skill | data_source | webapp`; each holds `id` · type · one-line description (with privacy label) · reference to the owning service (full definition fetched on demand); search/load = hardcoded core primitive; **per-agent scoping enforced server-side** (accessible set lives in the agent definition, preloaded subset in the system prompt); name authority validates/reserves/rejects at registration; stable names `<service>.<capability>`; implementations are the selectable unit; dependency declaration loose (capability) or specific (implementation).

### 2.9 The learning experience (ADR-0024) — the cross-cutting thread

#### 4.1 The learning/operability bar (ADR-0024 §1)
Every **service and implementation** carries a **required, auditable bar** of learning/operability artifacts, graded by depth (**how to use · how it works · study in depth · going further**), in three categories:
- **Documentation** — the four depth levels, written to be **readable and indexed for agents**: structured Markdown, canonical section schema + front-matter (title, capability/implementation, level, keywords, MCP tool refs). **One source, dual-consumed** (human surface + agent indexer read the same file; no separate agent-authored set).
- **Skills + MCPs** — MCP tools auto-generated from OpenAPI (with `@tool` overrides) plus a **how-an-agent-drives-me `skill`** (a registry `skill` entry); a genuinely-not-agent-drivable capability records an explicit **"not agent-operable"** note (no theater).
- **Diagnostics tools** — to fix and optimize.
Declared in the service template (ADR-0002); **mandatory to publish for `bundled`/`listed`, recommended-with-tracked-gaps for `third-party`** (ADR-0018's tiers). Applies to published things (ADR-0019).

#### 4.2 The continual learning assistant (ADR-0024 §2)
A personal assistant to learn and build, **literally Hermes Agent** (the vendored harness — the teaching vehicle for the most popular personal assistant; MAF unchanged as the composition primitive). **One workspace = one Hermes state per physical user.** On **new-user creation**, the platform automatically mounts every installed service/implementation's bar artifacts (docs + skills + MCP tools + diagnostics) into the user's Hermes workspace via the registry. **Docs everywhere; tools by role** — documentation is mounted for all users (incl. admin docs for non-admins, for education); admin/builder tools+skills are not mounted for users who lack that role. **One identity per session, chosen at launch** (User view → `user`; Builder view → `builder`; Administrator view → `admin`), governing tool mounting + action-context for the whole session; no mid-session role switching. Role-scoped **tool access is consent content, designed in #31**.

#### 4.3 The guided build process (ADR-0024 §3)
A **versioned, first-class skill set** — the Matt Pocock engineering skills (wayfinder/grilling/tdd/code-review/…) **adapted/whitelabelled by the platform** to call the platform's own capabilities (Inference, Eval/ADR-0020, the agentic-dev-workflow) — **extended with ML + evaluation best practices** from Shreya Shankar & Hamel Husain (evaluation designed into the build flow, steering to the eval capability). A **human-readable process documentation** teaches the process before the learner uses the skills. Surfaced through the **Development service's `agentic-development-workflow` capability**.

#### 4.4 Onboarding (ADR-0024 §4)
The first-run/initial journey (recap, front-door address, guided tour, datasets opt-in off) including the **backup-passphrase** step (user told explicitly to remember it; hashed key encrypts per-service backup zips; re-entered on restore). Lands in the dashboard first-run surface and here.

### 2.10 Data consent & handling (ADR-0026) — the cross-cutting consent model

The platform-wide, GDPR-aware model for how data may leave one user's private sphere and enter a builder's/admin's sphere, mediated through the core. The ADR is the source of truth; this section cites, never restates.

- **Consent capture** — per-interaction consent **defaults to "may use for improvement"**, with a **very visible "private/secret — do not use" toggle** on every user input (prompt or data/document upload) in the platform UI and in published artifacts. A **user-written remembered default per surface/input-type** is allowed (always visible + overridable, never a heuristic). A user can **withdraw consent / delete** any past interaction, barring it from future extraction.
- **The single mediated boundary** — each service runs its own **dataset-extraction UI/API** sending the core `datasets` capability a **standardized dataset file** (HF-datasets-like) already **filtered** of private/secret interactions (mandatory) plus service-specific filters. The **core anonymizes before storing**, records **dataset provenance** (service, date, builder), **centralizes the platform's non-user-related logs**, and serves/syncs anonymized datasets (to HuggingFace after anonymization). **Filter = consent gate; anonymize = data replacement** (personal data AND secrets — names, emails, phones, addresses, passwords, tokens, API keys, ID-card numbers), **text-only in v1**.
- **Quality bar** — detect by type → per-type replacement pools → **dataset-wide replacement dictionary** (same source always maps to same replacement, preserving signal) → **best-effort = indistinguishability** (you can't tell whether a value was replaced). Anonymization is **mandatory before any trace enters a dataset**; quality is surfaced as an explained transform report, never hidden.
- **Builder sphere is anonymize-free** — simulated/builder-injected interactions run as the builder identity, need **no filter/anonymize** (synthetic); nothing real-usage enters the builder sphere except through the core's filter+anonymize; a manual paste of raw user data is **flagged as a user action, not blocked**.
- **Assistant acting identity** — the assistant (Hermes Agent) runs in a **workspace-only container**, so its only path to service data is **tool calls**; **services enforce data-access/export rules at the callable surface** per the acting identity carried in action-context (user → own data; builder → anonymized + non-sensitive builder data; admin → admin data not linked to a user). Any trace the harness produces is attributed to that identity.

Supporting: core `datasets` log-extraction (ADR-0003), per-service dataset-extraction surface (ADR-0002), eval (ADR-0020 §5), backup spheres (ADR-0021), assistant role-scoping (ADR-0024 §2), Training (ADR-0025 §5).

## ADR cross-references

ADR-0001 (contract) · 0002 (template + learning bar) · 0003 (core + bootstrap) · 0004 (topology) · 0005 (resources) · 0006 (providers + privacy) · 0007 (composition) · 0008 (registry) · 0013 (spec anatomy) · 0015 (dashboard guidance) · 0021 (backup / onboarding) · **0024 (this chapter's learning-experience governing ADR — bar, assistant, guided build, onboarding)** · **0026 (this chapter's data-consent cross-cutting section — consent, log-extraction, anonymization, assistant sphere gates)** · 0020 (eval destination) · 0022 (license of model-backed steps).
