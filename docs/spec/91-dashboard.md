# 91 — Dashboard

> **Status:** drafted at the resolution of wayfinder ticket "Design the integrated UI (dashboard)" (#8) — the first spec chapter to be created (per Laurent, other chapters kept deferred). **Source of truth:** ADR-0015 (dashboard UX) plus the ADRs whose surfaces it renders (0003 core, 0004 topology, 0005 resources, 0006 providers, 0008 registry, 0014 install). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **dashboard** is the platform core's human surface and the **platform's single human front door** — a role-aware shell that groups the platform's four feature sets under three views, hosts the UI of every service capability, keeps an always-on metrics rail, and hosts the initial install phase + first-run welcome. Not a separate service: it is the core's UI (ADR-0003), reached through the front door.

## Part 1 — Use cases (user guide)

### What the user sees and does

- **On first use**, the dashboard hosts the **initial install web UI** (the wizard's Phase 3 — the rest of the install via the core's `install` capability), then the **first-run welcome**: recap of everything installed and running, the front-door address (`wordslab.local`), and a short guided tour that defers to its chapter (updates, security, backup; datasets opt-in, off).
- **On every screen**, a **view selector** (Administrator · User · Builder) and a **bottom status bar**; the **left + top bars** carry navigation; a **narrow right rail** shows always-on metrics.
- **Administrators** see the Administrator view (ops). **Everyone** sees User (capability explorer) and Builder (dev/agent/workflow/publishing) views. (ADR-0015 §3.)
- **Every surface teaches**: one plain-language line per screen, one line explaining each decision, and the *cause* behind every status color; "Learn more"/"Why?" deepens on demand. (ADR-0015 §4.)

### Representative use cases

1. **"Install and configure my platform"** (Administrator) — S0 install web UI → machines (topology, working set, storage, simulation) → install/update services → cloud providers → users → backup. Supporting: core `install`/`resources`/`users`/`secrets` (ADR-0003), topology (0004), resources (0005), providers (0006), backup (#22).
2. **"Use an AI capability"** (User) — browse the capability catalog, launch a capability's own UI, choose an implementation (dependency-declaration choice), handle a load that doesn't fit (load dialogue). Supporting: all 12 services' human surfaces (ADR-0002), registry (0008), resources (0005).
3. **"Build an agent / workflow / app"** (Builder) — Development, agent builder (set accessible tool set + preloaded subset), workflow builder (Python + primitives), app publishing, publish to My registry. Supporting: agent/workflow (0007), registry name-authority (0008), Development, publishing (0019 — Builder = own devs + compliance authoring; Administrator = read-only audit).
4. **"Keep an eye on the platform"** (everyone) — the always-on right rail (GPU/VRAM + CPU/RAM primary, cloud % spent when in use), hover for a machine's full stats, click for the full-metrics screen. Supporting: resources gauges (0005), providers spend (0006).
5. **"Respond when the leader fails"** (Administrator) — the leader-failure banner shows authority surfaces down while services keep working. Supporting: ADR-0004 §1, recovery (#22).

## Part 2 — Build spec (organized reference + citations)

### The dashboard's structure (ADR-0015 §1–§5)

- **Four feature sets:** Ops (1) · capability explorer (2) · builder (3) · always-on metrics incl. cloud spend (4).
- **Three views, gated by the settled `admin`/`member` level** (not new permission levels): admin → Administrator + User + Builder; member → User + Builder. View selector in the top bar. Advanced sections keep views simple.
- **Layout:** left + top bars = navigation; bottom = status bar; always-on metrics = narrow right rail (GPU/VRAM + CPU/RAM primary; cloud % spent when in use; disk de-emphasized; working-set-driven prominence; hover → floating card; click → full-metrics screen).
- **Educational layer:** thin-by-default (one line/screen, one line/decision, cause behind every color) + deep-on-request ("Learn more"/"Why?" locating the docs topic).

### The screens (rendering settled semantics; each cites its ADR)

- **Global shells:** view selector · metrics right rail · leader-failure banner (ADR-0004 §1).
- **S0 Install web UI + first-run welcome** (ADR-0014 §3/§8; core `install`).
- **Contextual:** load dialogue (ADR-0005 §6) · dependency-declaration choice (ADR-0008 §11).
- **Administrator:** Overview · Machines: Topology (0004 §2) / Working set cards (0004 §5, 0005 §6) / Storage (0004 §8, 0005 §8) / Simulation (0004 §5) · Install & Updates (0014, #10 lanes) · Backup (#22) · Cloud: Provider cards + inline keys (0006 §2/§5), Spend & remaining-% (0006 §6), Privacy & cloud-enablement (0006 §7, 0008 privacy labels) · Users (0003) · Connectors & service keys co-located (0006 §5, 0003 keys) · Registry manage (0008) · Activity & logs (0003).
- **User:** Home · Capabilities (all services' UIs, ADR-0002) · My Activity (0003).
- **Builder:** Development · Agent builder (0007, 0008 scoping) · Workflow builder (0007) · App publishing (0019 — projects, deployable-packages catalog, start/stop/update/version; compliance authoring for own developments) · My registry (0008).

### Key flows

- **Co-located keys** (ADR-0015 §7): each provider/connector/service config carries its own add/rotate/revoke; the core `secrets` vault (0006 §5) stores and re-distributes on rotation.
- **Load dialogue** (0005 §6): lower-this / lower-a-resident / unload-something; ask-to-choose when several ways; visible editable "remember my decision"; `429 resource_exhausted` + shortfall then re-choose.
- **Launcher boundary** (0014 §4, 0015 §8): launcher = machine-lifecycle + connect; dashboard = deep management + first-run + install + host of all service UIs; no duplicates.

### ADR cross-references

ADR-0002 (callable surfaces, service UIs) · 0003 (core, users/keys/secrets, logs) · 0004 (topology, working set, storage, simulation) · 0005 (gauges, load dialogue, quotas) · 0006 (providers, spend, privacy, secrets) · 0007 (composition, agents/workflows) · 0008 (registry, name authority, per-agent scoping, dependency choice) · 0013 (spec anatomy) · 0014 (install, first-run, launcher) · **0015 (this chapter's governing ADR — dashboard UX, views, layout, educational layer)**.
