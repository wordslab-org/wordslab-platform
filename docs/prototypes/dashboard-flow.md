# Prototype — the integrated dashboard flow (issue #8) — v2 (role-based)

> **PROTOTYPE — throwaway, for reaction only.** A rough screen-by-screen outline of the *integrated dashboard* for `wordslab-platform`. It **renders** the settled semantics from the closed tickets (ADRs 0003/0004/0005/0006/0008/0014); it does **not** re-decide topology, resources, providers, registry, or install mechanics. Nothing here is authoritative until Laurent confirms shared understanding. Screens are described as *what the user sees → what they do → what's shown*.

---

## The dashboard's job

The dashboard is **the platform's single human front door** — a **role-aware shell** that:

1. **Groups the platform's four feature sets** under three user roles (below).
2. **Hosts the UI of every service capability** — not just the core's. Every service has its own human surface (ADR-0002 callable surfaces); the dashboard is the navigation shell that groups, links, and embeds them. The front door routes; the dashboard navigates and presents.
3. **Keeps the always-on metrics right rail present** on every screen, every role (working set · CPU/GPU/VRAM/RAM/storage · cloud spend when in use).
4. **Hosts the initial install phase** as a web UI before everything is ready.

## Design principle — the interface is educational, everywhere

The platform's **main goal is educational**: users are here to *learn and understand* AI, not just operate it. So every surface carries a guidance layer — the soul's "no magic, no black box" expressed as in-context help, not a separate docs site. Three concrete habits woven through every screen:

- **Explain what you're looking at** — each screen has a one-line plain-language "what this is and why it matters," plus a deeper "learn more" affordance that locates the topic in the docs/chapters (first-run's tour establishes the pattern).
- **Explain what the user is deciding** — every decision point (a load, a provider choice, a placement) shows *what the options mean and their trade-offs* in plain words, before the user acts. Choosing an implementation *is* the privacy decision — the interface teaches that.
- **Show the cause behind every state** — green/orange/red, refusals, advisor suggestions each carry a plain-language *why* (shortfall, overstepper, reason line in the simulation). Never a bare warning.

The educational layer is a **voice and placement discipline**, not a separate mode. It is **pervasive but thin by default, deep on request**:

- **Default (always visible):** one plain-language line per screen ("what this is and why it matters") and one line explaining each active decision point, plus the *cause* behind any status color. Never more than one line of help per surface by default — it never hides a decision, but it doesn't lecture a user who already understands.
- **On demand:** an explicit **"Learn more" / "Why?"** affordance on each screen that opens the deeper explanation and locates the topic in the docs/chapters. The first-run tour (S0) establishes this pattern for first-time users.
- Guidance sits next to the action it explains, stays one line where the action is one step, and deepens only on an explicit "learn more."



## Three views — reoriented per persona, gated by the settled admin/member level

> **The three are views, not new permission levels.** Access is gated by the existing `admin`/`member` model (ADR-0003): **admin accounts can open all three views (Administrator + User + Builder); member accounts can open User + Builder only.** Every user is also a builder — User and Builder are both available to non-admins; the User/Builder split is purely *nav organization* (capability explorer vs builder tools), not a tier. The Administrator view is the one gated to admins.

| View | Who can open | What it presents (the feature sets) |
|---|---|---|
| **Administrator** | admin only | **Set 1** — install / config / update / backup, machines (topology, working set, storage, simulation), cloud providers, users, registry management, activity & logs. |
| **User** | everyone | **Set 2** — a simple UI for the capabilities of *all* services (chat, image, audio, document, knowledge, workflow run, media, connectors, generation). |
| **Builder** | everyone | **Set 3** — Development service, agent builder, workflow builder, app publishing, their authored registry entries. |

A **view selector** (Administrator · User · Builder) sits at the top of every screen (admins see all three; members see User + Builder); the **always-on metrics right rail (set 4)** stays visible across all views. **Advanced sections** keep all three views simple where relevant (deep diagnostics tucked under an "Advanced" affordance).

---

## Always-on metrics — the right rail (set 4) + full-metrics screen

**Layout:** the left bar + top bar carry **navigation** (role selector, per-role nav); a **status bar sits at the bottom** (like most editors). The always-on metrics are a **narrow vertical strip on the right** of the screen, present on every screen and every role.

- **Right rail (always present):** a narrow vertical strip of **clickable small metrics & graphs**. It shows **GPU/VRAM and CPU/RAM** as the primary always-visible metrics (these matter most), and surfaces **cloud subscription % spent** whenever the working set is using cloud providers (models or web-search tools). **Disk space is de-emphasized** — it only becomes prominent when the user is downloading something or creating a workspace.
- **The working set drives prominence:** which metrics the rail emphasizes adapts to the **currently loaded working set** at that moment — e.g. when a model is resident/loading, GPU/VRAM lead; when a connector is active, the cloud-subscription gauge leads.
- **Hover** a metric → a **floating card** presents all the stats of that machine or cloud service (full RAM/VRAM/disk, speed rank, green/orange/red, working-set count).
- **Click** a metric → opens the **full-metrics screen** (below) in the main area.
- **Cloud spend** is part of set 4: metered providers' spend vs cap and opaque subscriptions' % remaining appear on the rail when relevant.

### Full-metrics screen (from a rail click)
- **Sees:** a dedicated screen with **all metrics of all machines** in the main area — per machine, the working set, CPU/GPU/VRAM/RAM/storage gauges with speed rank and green/orange/red, plus cloud provider spend/remaining-% for any in use.
- **Does:** scan platform activity at a glance; click a machine to jump to its deep page in Administrator → Machines.
- **Shown:** the "keep an eye on platform activity" overview.

---

## Screen-by-screen outline (grouped by role)

### Global shells (every view)

- **View selector** — Administrator · User · Builder (admins see all three; members see User + Builder).
- **Always-on metrics right rail (set 4)** — the persistent gauges above.
- **Leader-failure banner** — authority surfaces (dashboard login, users/keys/secrets, installs, updates, catalog/aggregation) are down until the leader is rebuilt; shown clearly while services keep working.

### S0. Initial install web UI + first-run welcome (before everything is ready)
- **Sees:** the dashboard hosts the **initial install phase as a web UI** — the wizard's Phase 3, taking over the rest of the install (services, capabilities, activities via the core's `install` capability) before everything is ready. Then the **first-run welcome** ("Welcome to Wordslab Platform"): recap, front-door address (`wordslab.local`), short guided tour deferring to chapters (updates, security #14, backup #22; datasets opt-in, off).
- **Does:** completes install steps in the browser; then takes the tour or enters the dashboard.
- **Shown:** the resident launcher brought the user to this URL; the dashboard is the install + first-run host (ADR-0014).

---

### Contextual surfaces (appear where relevant, not top-level)

- **Load dialogue — the soul, no magic (ADR-0005 §6).** Appears wherever a load doesn't fit (a User launching a capability, an Administrator working-set action). It shows the options plainly — lower *this* implementation's parameters to fit · lower a resident's parameters · unload something — and, when several unload ways exist, **asks the user to choose**, with an optional **"remember my decision"** rule (visible, editable: "to load X, when ambiguous between A and B, choose A"). A refused load surfaces as `429 resource_exhausted` with the shortfall (which resource, by how much), then the user re-chooses an implementation. The educational layer teaches what each option means before the user acts.
- **Dependency-declaration choice** — a **loose** dependency shows a dynamically-populated implementation list (each with privacy label + fit status) to choose from; a **specific** dependency shows its pin (hard fit constraint) and any refusal, with an explicit re-choice path.

---

### ADMINISTRATOR (set 1 — install/config/update/backup, machines, activity)

- **A1. Overview / Status** — leader health, machines up/down (leader/worker, home/cloud), cloud provider status/limits, active advisories (load refusals, advisor suggestions), headline gauges from the metrics right rail.
- **A2. Machines — Topology** — machines (leader/worker; home LAN/cloud), data locations (named after disks), services + implementations per machine, front-door entry; IPs as locators, not identity; "Add a machine" (join flow); add disk/data location.
- **A3. Machines — Working set (cards)** — the current activities' implementations as **movable cards** on machine surfaces: state (**downloading / loading / resident / swappable / cloud-routed**), resident vs non-resident, variable settings (context/batch/media length), live memory estimate. **Drag** to another machine (constraints enforced, refusals explained); **pin** (keeps resident); **delete** (unload + free disk). Idle-timeout auto-clear (~30 min), routing visibility.
- **A4. Machines — Storage** — machines × data locations (capacity/free per disk; role folders `models/`/`workspace/`/per-service), green/orange/red per data location/folder/service/**user** with **who-oversteps** (warn ~80%, red 100%); `models/` quota per data location; reservation ledger.
- **A5. Machines — Simulation** ("where should this run?") — placement projection (activities → implementations → machines + cloud, with costs, **privacy tier as a hard constraint**, one line of reason per proposal); re-runnable; reactive **advisor** (subscribe to cloud / rent a machine when the working set doesn't fit or saturation observed).
- **A6. Install & Updates** — install/update services, capabilities, activities; the **two update lanes** (frequent-automatic implementations vs user-chosen consistent bundles); Update vs Repair (data-preserving).
- **A7. Backup** — backup trigger/review (→ #22 surface).
- **A8. Cloud — Provider cards** — each provider as a card (name, modalities, **privacy tier**, billing mode, status); preconfigured templates activated by entering a key (**one probe call** result shown); custom OpenAI-compatible endpoint de-emphasized; **bundle cards** (one subscription, legs visible). **Each provider card carries its own key management inline** — add / rotate / revoke that provider's key at the point of configuration (rotation re-distributes to consuming services via the core's `secrets` vault).
- **A9. Cloud — Spend & remaining-% gauges** — metered (spend vs monthly cap, green/orange/red) vs opaque subscriptions (% remaining per time scale, orange <30% / red <10%); attributed per service/user/provider; action trail shows each call's cost.
- **A10. Cloud — Privacy & cloud-enablement** — privacy tier on every card/list; enabling a cloud implementation surfaces what a call sends and to whom (informed manual choice).
- **A11. Users & auth** — a few family members (name, `admin`/`member`, per-user quota); admin-created.
- **A12. Connectors & service keys (co-located, not a central page)** — keys live **at the place the connection is configured**, never on a detached secrets page:
  - **Connector keys** (web/x/outlook/youtube/github/huggingface) — add/rotate/revoke inline within each connector's config surface.
  - **Per-service Bearer keys** (human/tool keys) — managed inline within each service's own config/settings.
  - Rotation re-distributes to consuming services via the core's `secrets` vault (ADR-0006 §5); the vault is the storage, the dashboard surfaces the key *at its point of use*.
- **A13. Registry — manage** — browse/search entries (tool|agent|workflow|skill|data_source) with one-line description + privacy label; drill into full definition + versions (float/pin); name-authority/registration; install new services/activities; per-agent scoping review.
- **A14. Activity & logs** — per-user action trails (chronological + hierarchical), log search (`GET /v1/logs`, per-service `q`), stats (per-user + global), cloud-call "served by" + cost; datasets opt-in (off).

---

### USER (set 2 — a simple UI for the capabilities of all services)

- **U1. Home** — what's available; quick launch of capabilities; recent activity; the always-on metrics right rail on top.
- **U2. Capabilities — the service catalog, grouped** (the heart of set 2): each service's capabilities presented simply and launched into the service's own human UI:
  - **Chat & Agents** (Open WebUI) · **Image** (generate/edit/video) · **Audio** (STT/TTS/voice) · **Document** (parse/organize/index/search) · **Knowledge** (ontologies/entities/graph/review queue) · **Workflow** (run/trigger existing) · **Media transformations** · **Connectors** (web search etc.) · **Generation** (create documents/reports) · **Training & Evaluation** (when present).
- **U3. A capability surface** — selecting a capability opens/embeds that service's own UI (the dashboard hosts/navigates all service UIs, not just the core's).
- **U4. My Activity** — my action trails, my usage, my per-user quota.
- *(The **dependency-declaration choice** and the **load dialogue** — see Contextual surfaces above — appear wherever a User launches a capability that needs an implementation.)*

---

### BUILDER (set 3 — dev service, agent builder, workflow builder, app publishing)

- **B1. Development** — code-server (VS Code + Kilo Code), JupyterLab, the agentic development workflow UI; opens the same workspaces the agent service manages.
- **B2. Agent builder** — author agents (model, system prompt, tools, skills); set the **accessible tool set** + **preloaded subset** (the allowlist) and review which registry tools it can see/call (feeds #14 security); save to the agent definition.
- **B3. Workflow builder** — author workflows as Python (with the primitive set), the read-only visual view, triggers/runs; publish.
- **B4. App publishing** — publish generated web apps / services (→ #21 surface).
- **B5. My registry** — my authored entries (agent/workflow/skill): **publish/register on publish** (name-authority visible; discoverable = launchable); versions (float/pin).

---

## Scope boundary (ADR-0014) — launcher vs dashboard

- **Resident launcher** = machine-lifecycle + connect: start / stop / update / monitor / backup, wake, data-location add, machine registry. UI on Windows; headless/remote on Linux.
- **Dashboard** = deep management (all roles) + first-run + install web UI + **the host of all service capability UIs**. Reached through the front door; the launcher opens it on Start.
- **No duplicated surfaces** — the launcher opens the dashboard for deep work.

---

## Open questions (grilling, to be answered with Laurent)

**Settled so far:** the four feature sets (Ops / capability explorer / builder / always-on metrics incl. **cloud spend**) · the three **views** gated by the settled `admin`/`member` level (admins → Administrator + User + Builder; members → User + Builder; every user is also a builder) · the educational guidance layer (pervasive but thin by default, deep on request) · the three-view top-level nav (below, accepted as a starting point to refine) · Cloud = a section under **Administrator** · **keys/credentials co-located** with their connection's config (provider card, connector config, service settings) — never a single detached secrets page · **layout**: left + top bars = navigation, bottom = status bar, always-on metrics = **narrow right rail** (GPU/VRAM + CPU/RAM primary, cloud % spent when in use, disk de-emphasized; working-set-driven prominence; hover → floating card, click → full-metrics screen) · **advanced sections** keep all three views simple where relevant.

- **Q-G. Prototype artifact form** — markdown screen-by-screen outline (this file), kept as `docs/prototypes/dashboard-flow.md`, linked as #8's asset.

## Accepted nav (starting point, to be refined)

- **Administrator:** Overview · Machines (topology / working set / storage / simulation / install-updates / backup) · Cloud (providers / spend / privacy) · Registry (browse + manage) · Users · Activity & logs
- **User:** Home · Capabilities (the service catalog — chat, image, audio, document, knowledge, workflow, media, connectors, generation) · My activity
- **Builder:** Development · Agent builder · Workflow builder · App publishing · My registry


---

## Prototype artifact form

A **markdown screen-by-screen outline** (this file). No working code. Kept as `docs/prototypes/dashboard-flow.md`, linked as #8's asset.
