# ADR-0015 — The integrated dashboard (role-based views, layout, educational layer)

**Status:** accepted (resolution of wayfinder ticket "Design the integrated UI (dashboard)", #8); **amends none**; **shapes the `91-dashboard.md` spec chapter** (ADR-0013 §2); **feeds** "Define the security model for the trusted home environment" (#14 — per-agent scoping presented in the Builder view), "Design the backup & recovery story" (#22 — backup surface presented in the Administrator view), publishing (#21 / ADR-0019 — the Builder view's publishing + compliance-authoring surface, the Administrator view's read-only compliance audit).

## Context

The map's soul demands a **single, simple, familiar, guided, transparent** interface — "a very simple interface to install services and an integrated UI." ADRs 0003/0004/0005/0006/0008/0014 settled the *semantics* of every surface the user sees (status, gauges, working set, topology, storage, simulation, providers, spend, privacy, registry, per-agent scoping, install, first-run). This ADR decides the **user-facing presentation** of those surfaces: how they group into a dashboard, who sees what, the overall layout, and the educational guidance woven through every screen. It deliberately does **not** re-decide any of those settled semantics — it renders them.

The decision also reflects a clarification from Laurent: the dashboard is **not only the core's surface** — it is the host and navigation shell for **the UI of every service capability** (each service has its own human surface per ADR-0002).

## Decision

### 1. The dashboard's job

The dashboard is the platform's **single human front door** — a role-aware shell that:

1. **Groups the platform's four feature sets** under three views (below).
2. **Hosts the UI of every service capability** — not just the core's. Every service has its own human surface (ADR-0002 callable surfaces); the dashboard is the navigation shell that groups, links, and embeds them. The front door routes; the dashboard navigates and presents.
3. **Keeps an always-on metrics right rail** present on every screen and view (set 4).
4. **Hosts the initial install phase** as a web UI before everything is ready (the wizard's Phase 3, ADR-0014 §3) and the **first-run welcome** (ADR-0014 §8).

### 2. Four feature sets

1. **Ops** — install / config / update / backup, machines, activity & stats screens.
2. **Capability explorer** — a simple UI for the capabilities of *all* services.
3. **Builder** — Development service, agent builder, workflow builder, app publishing.
4. **Always-on metrics** — working set + CPU/GPU/VRAM/RAM/storage per machine (plus **cloud spend**), present everywhere as clickable small metrics & graphs.

### 3. Three views, gated by the settled admin/member level — not new permission levels

The three are **views (personas / nav organizations), not new permission levels.** Access is gated by the existing `admin`/`member` model (ADR-0003):

- **Admin** accounts can open **all three views: Administrator + User + Builder**.
- **Member** accounts can open **User + Builder only** (the Administrator view is the one gated to admins).
- **Every user is also a builder** — User and Builder are both available to non-admins; their split is purely nav organization (capability explorer vs builder tools), not a tier.

| View | Who can open | Presents |
|---|---|---|
| **Administrator** | admin only | **Set 1** — install/config/update/backup, machines (topology, working set, storage, simulation), cloud providers, users, registry management, activity & logs. |
| **User** | everyone | **Set 2** — a simple UI for the capabilities of all services. |
| **Builder** | everyone | **Set 3** — Development service, agent builder, workflow builder, app publishing, authored registry entries. |

A **view selector** (Administrator · User · Builder) sits at the top of every screen. **Advanced sections** keep all three views simple where relevant (deep diagnostics tucked under an "Advanced" affordance).

### 4. Educational design principle — the interface teaches, everywhere

The platform's **main goal is educational**: users are here to *learn and understand* AI. Every surface carries a guidance layer — the soul's "no magic, no black box" as in-context help, not a separate docs site:

- **Explain what you're looking at** — one plain-language line per screen ("what this is and why it matters") plus a deeper "learn more" affordance locating the topic in the docs/chapters.
- **Explain what the user is deciding** — every decision point (a load, a provider choice, a placement) shows *what the options mean and their trade-offs* in plain words before the user acts. Choosing an implementation *is* the privacy decision — the interface teaches that.
- **Show the cause behind every state** — green/orange/red, refusals, advisor suggestions each carry a plain-language *why* (shortfall, overstepper, reason line in the simulation). Never a bare warning.

The layer is **pervasive but thin by default, deep on request**: default = one line per screen and one line per active decision, plus the cause behind any color; on demand = an explicit "Learn more" / "Why?" affordance opening the deeper explanation and locating the docs topic. The first-run tour establishes this pattern.

### 5. Overall layout — editor-style

- **Left bar + top bar** carry **navigation** (view selector, per-view nav).
- **Bottom status bar** (like most editors).
- **Always-on metrics: a narrow vertical right rail**, present on every screen and view:
  - **GPU/VRAM and CPU/RAM** are the primary always-visible metrics (these matter most).
  - **Cloud subscription % spent** is surfaced whenever the working set uses cloud providers (models or web-search tools).
  - **Disk space is de-emphasized** — prominent only when downloading something or creating a workspace.
  - **The working set drives prominence** — which metrics the rail emphasizes adapts to the currently loaded working set (e.g. a resident/loading model → GPU/VRAM lead; an active connector → cloud gauge leads).
  - **Hover** a metric → a **floating card** with all stats of that machine/cloud service (full RAM/VRAM/disk, speed rank, green/orange/red, working-set count).
  - **Click** a metric → the **full-metrics screen** in the main area: all metrics of all machines at a glance; clicking a machine jumps to its deep page in Administrator → Machines.

### 6. The screens (rendering the settled semantics — grouped by view)

**Global shells (every view):** view selector · always-on metrics right rail · leader-failure banner (authority surfaces down until the leader is rebuilt; services keep working).

**S0 — Initial install web UI + first-run welcome (before everything is ready):** the dashboard hosts the install's Phase 3 web UI (the rest of the install via the core's `install` capability), then the first-run welcome (recap, front-door address, short tour deferring to chapters; datasets opt-in, off).

**Contextual surfaces (not top-level):** the **load dialogue** (the soul, no magic — lower-this-parameters / lower-a-resident / unload-something; ask the user to choose when several unload ways exist, with a visible editable "remember my decision" rule; refusals surface as `429 resource_exhausted` with the shortfall, then re-choose) and the **dependency-declaration choice** (loose → dynamically-populated implementation list with privacy label + fit status; specific → pin + refusal with an explicit re-choice).

**Administrator (set 1):** Overview/Status · Machines (Topology / Working set cards / Storage / Simulation) · Install & Updates (two update lanes; Update vs Repair) · Backup · Cloud (Provider cards w/ inline key management / Spend & remaining-% gauges / Privacy & cloud-enablement) · Users & auth · Connectors & service keys (co-located at the connection's config, never a detached secrets page) · Registry (browse/search, drill-in, name-authority/registration, per-agent scoping, install) · Activity & logs.

**User (set 2):** Home · Capabilities (the service catalog grouped — chat, image, audio, document, knowledge, workflow, media, connectors, generation; selecting one opens/embeds that service's own UI) · My Activity.

**Builder (set 3):** Development (code-server, JupyterLab, agentic dev workflow) · Agent builder (author agents; set accessible tool set + preloaded subset — the allowlist; review what it can see/call — feeds #14) · Workflow builder (Python + primitive set, read-only visual view, publish) · App publishing (→ #21) · My registry (publish/register authored entries on publish; versions float/pin).

### 7. Keys & credentials co-located, not centralized

Keys live **at the place the connection is configured**, never on a single detached secrets page: provider keys inline on the provider card, connector keys inline in each connector's config, per-service Bearer keys inline in each service's settings. The core's `secrets` vault (ADR-0006 §5) remains the storage; rotation re-distributes to consuming services. The dashboard surfaces the key *at its point of use*.

### 8. Scope boundary with the resident launcher (ADR-0014)

- **Resident launcher** = machine-lifecycle + connect: start / stop / update / monitor / backup, wake, data-location add, machine registry. UI on Windows; headless/remote on Linux.
- **Dashboard** = deep management (all views) + first-run + install web UI + **the host of all service capability UIs**. Reached through the front door; the launcher opens it on Start.
- **No duplicated surfaces.**

## Considered options

- **Three new permission levels vs three nav views gated by admin/member** — adding a "Builder" security tier would amend the settled `admin`/`member` model (ADR-0003) and drag RBAC into a presentation ticket. Chose **views gated by the existing level**: admin sees all three, members see User + Builder. "Every user is also a builder" keeps the builder tools open to all.
- **Flat wall of ~19 pages vs a few grouped sections** — the soul wants "a very simple interface"; a flat page wall is the opposite. Chose **grouped sections under three views** with deep-dive pages reached from a section.
- **Metrics as a top bar / sidebar vs a narrow right rail** — the top and left bars are needed for navigation and the bottom for a status bar; a right rail keeps metrics glanceable without crowding the nav. Chose the **narrow right rail** with hover-card detail + a click-through full-metrics screen.
- **One centralized secrets page vs keys co-located with their connection** — a central secrets page disconnects each key from the other config parameters of its distant service; co-locating keeps the key next to what it authenticates. Chose **co-located**, keeping the `secrets` vault as storage.
- **Guidance always-on vs thin-by-default/deep-on-request** — always-on guidance fights simplicity; hidden help abandons the non-technical user. Chose the **layered** model: one line by default, "Learn more" on demand.
- **Dashboard as core-only UI vs host of all service capability UIs** — the dashboard is the platform's front door and every service has a human surface; restricting it to the core would bury the other 12 services. Chose the dashboard as **navigation shell hosting/embedding all service UIs**.

## Consequences

- **Shapes the `91-dashboard.md` spec chapter** (created this resolution; ADR-0013 maintenance loop).
- **Reference prototype:** `docs/prototypes/dashboard-flow.md` (markdown screen-by-screen outline; the artifact this resolution reacts to).
- **Glossary (CONTEXT.md):** no new core term required — "dashboard" is the platform core's human surface (existing), and "view" is a presentation term defined here. A short "dashboard view" gloss may be added when the spec chapter is written.
- **Feeds** #14 (per-agent scoping presented in Builder), #22 (backup surface in Administrator), #21 (publishing surface in Builder). None resolved here — the dashboard *presents* their surfaces.
- **Update & versioning (#10)** — the two update lanes are *presented* in Administrator → Install & Updates; mechanics stay in #10.
