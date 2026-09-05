# 39 — Publishing & Governance

> **Status:** drafted at the resolution of wayfinder tickets "Design community governance of the service catalog" (#15) and "Define how agents publish generated web apps & services" (#21). **Source of truth:** ADR-0018 (governance half) + ADR-0019 (publishing half). This chapter is the **organized build-view** — it cites, never restates. The governance half (community catalog, review levels, compliance catalog) is ADR-0018's; the publishing half (published things, runtimes, two regimes, project, inbound exposure, agent-code security) is ADR-0019's.

## Identity

The combined **Publishing & Governance** service (candidate 13th, ADR-0013 §2/§6) has **two halves**:

- **Publishing** — used by the Development service to **package, deploy, and expose the result of a development activity** (an API / tool / agent / UI / web app / static site — code written or generated, or agent/workflow configuration). Its three goals: expose a **stable service you build on yourself**, expose a **LAN app for family**, and expose a **demo on the internet** for friends / a learning group. It is the **small-scale** deploy/expose layer — not a "serve millions" platform.
- **Governance** — the catalog of all solutions built and run on the platform, with the documentation and monitoring to check their compliance.

The two are one service because publishing is the *act* that triggers governance: **compliance is coupled to publishing** — it is only mandatory at the act of publishing, not during development (ADR-0019 §8).

## Part 1 — Use cases (user guide)

### What the user sees and does

- **Building a project** (Builder view): a user develops an API/tool/agent/UI in the Development service, backed by a **project** (a GitHub/local repo). At publish time the project's root declares what it publishes — `platform.toml` (platform services/implementations) and `publish.toml` (generic APIs/apps/agents/tools).
- **Publishing** (Builder view): the user chooses the artifacts and the **runtime** (static site or long-running container), the **exposure** (LAN / overlay / later, public link), and completes the **compliance checklist**. Publishing is explicit and visible.
- **Managing published things** (Builder view): deploy/undeploy, start/stop, update, version, on each published thing; the **deployable-packages catalog** (generic publishables) or the centralized updates list (platform services/implementations).
- **Auditing** (Administrator view, read-only): everything installed/running, with its compliance facts.
- **Consuming shared apps** (User view): launchable URLs behind the front door, with a "runs agent/generated code" trust badge where relevant.

### Representative use cases

1. **"Publish a web app I generated with an agent"** (Builder) — develop/generate a web app in Development → pick runtime (long-running container) + exposure (LAN) → complete the AI-Act/GDPR checklist (exit-early: low-risk, no personal data) → publish → it runs containerized, appears in the dashboard, and is reachable at the front door on the LAN. Supporting: Development service, registry (ADR-0008 `webapp`/`api` entries), agent-code containment (ADR-0019 §10).
2. **"Share a demo app with friends who are learning AI with me"** (Builder) — pick an app → "share this app" → single-use invite link → the friend's device joins the private-mesh overlay, granted **only that one app's port** (Publishing auto-manages the default-deny ACL; the builder never touches ACL syntax). Supporting: overlay/ACL capability of the Publishing service (ADR-0019 §9). *(A public "anyone with a link" demo is v1.1 via the Connectors gateway.)*
3. **"Turn a developed service into a real platform service"** (Builder + Administrator) — publish a `platform.toml` service/implementation → it follows ADR-0016 platform versioning + centralized updates list → appears in the compliance catalog (Administrator) with a computed review status (`bundled`/`listed`/`third-party`, ADR-0018). Supporting: community catalog (ADR-0018), ADR-0016.
4. **"Check my published app is compliant"** (Builder) — the Builder view shows the app's operational facts (version, license, privacy tier, supply-chain) + the completed compliance checklist; the builder can fix and improve. Supporting: ADR-0018 compliance catalog, ADR-0019 compliance checklist.
5. **"Audit what's running on my platform"** (Administrator, read-only) — every service/capability/implementation/published app with its compliance facts. Supporting: ADR-0018.
6. **"Expose a stable API I build on in my own projects"** (Builder) — publish an API (OpenAPI) as a `api` registry entry, invocable by workflows (`call("…")`) and agents. Supporting: registry (ADR-0008), published-thing surfaces (ADR-0019).

## Part 2 — Build spec (organized reference + citations)

### The combined service's surface (ADR-0019 §1–§6)

- **Published thing** = code + a runtime declaration (static site OR long-running container; no serverless in v1). Light by default — NOT automatically a full base-contract platform service (ADR-0019 §1/§3). Full service contract (template, `service.toml`, ADR-0002) is **opt-in** at publish time.
- **Two regimes** (ADR-0019 §5): **regime 1** = platform services/implementations → follow **ADR-0016** (centralized updates list, two-part package, one-click); **regime 2** = generic APIs/apps/agents/tools → **separate deployable-packages catalog** (GitHub + local repos), deploy/undeploy, start/stop, author-versioned, no ADR-0016 adherence.
- **Project** = GitHub/local repo, shared with Development; root carries **`platform.toml`** (services/impls) + **`publish.toml`** (generic publishables). `catalog.toml` is renamed `platform.toml` everywhere (ADR-0019 §7, sharpens ADR-0018).
- **Deployable-packages catalog** = a real Publishing-service surface (the "what can I deploy / what's deployed" list), distinct from the compliance catalog's audit purpose (ADR-0019 §6).

### Registry interplay (ADR-0019 §4, sharpens ADR-0008)

- Registry types are extended to **seven**: `tool | api | agent | workflow | skill | data_source | webapp`.
- **`api`** = a published OpenAPI surface (code/workflow/agent-callable, not LLM-shaped); **`webapp`** = a published UI (static site = simpler webapp); **`tool`** = the LLM-optimized MCP subset. **One entry per surface exposed.** The **Publishing service** registers published things on publish (discoverable = launchable). UIs register because agents can drive them via **webMCP**.

### Compliance (ADR-0019 §8, ADR-0018 §10)

- **Coupled to publishing**: mandatory at the act of publishing.
- Two dimensions: **operational facts** (version, license, privacy tier, supply-chain, review status) + **regulatory posture** (EU AI Act + GDPR) as an **exit-early checklist** the author answers; answers stored as documentation; **advisory** (advice on redaction/guardrails, author documents risk-managed). Privacy tier is the GDPR proxy.
- **Builder view** = authoring-mode compliance for the builder's own developments (editable). **Administrator view** = read-only audit of everything (the compliance catalog, ADR-0018).

### Inbound exposure (ADR-0019 §9, ADR-0017)

- **v1**: LAN (front door, local CA) + **private-mesh overlay** (Tailscale/WireGuard node inside WSL2; single-use invite links; **Publishing auto-manages default-deny, one-app-to-device ACLs**; the builder never edits ACL syntax — only a "share this app" gesture + a human-readable summary). No public ports.
- **v1.1**: public-internet gateway (Connectors service), implementing ADR-0017's browser-aware TLS + edge-auth. Goals 1 & 2 in v1; goal 3 via overlay in v1, public link in v1.1.

### Security of agent-generated code (ADR-0019 §10, ADR-0017)

- **One OS container per published app**; network **default-allow-but-scoped-to-need** (no unrestricted host/LAN); **dedicated runtime user + filesystem boundary**; **secrets via the core `secrets` capability** (never embedded); **"runs agent/generated code" trust badge**. Stronger sandboxing deferred.

### ADR cross-references

ADR-0008 (registry — sharpened: `api`/`webapp` types) · ADR-0018 (**this chapter's governance half** — community catalog, review levels, compliance catalog) · **ADR-0019 (this chapter's publishing half)** · ADR-0002 (service template — opt-in for full services) · ADR-0016 (versioning/update — regime 1) · ADR-0017 (security — agent-code containment, inbound-exposure stance) · ADR-0013 (spec anatomy).
