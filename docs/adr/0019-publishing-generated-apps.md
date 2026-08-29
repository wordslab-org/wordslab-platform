# ADR-0019 — Publishing generated apps & services (the publishing half of the combined Publishing & Governance service)

**Status:** accepted (resolution of wayfinder ticket "Define how agents publish generated web apps & services", #21); **amends none**; **sharpens ADR-0008** (adds the `api` and `webapp` registry entry types) and **ADR-0018** (`catalog.toml` renamed `platform.toml` everywhere); **creates** the combined `docs/spec/33-publishing-governance.md` chapter (with ADR-0018); **feeds** the dashboard (`91-dashboard.md` Builder/Administrator publishing surfaces, ADR-0015 §3) and the Connectors service (the v1.1 inbound gateway); **references but does NOT resolve** license policy (#23), evaluation (#16), and backup (#22).

## Context

The platform's purpose is to **teach people to build AI applications** — for themselves, their family, and their friends — and to show their progress. It is not to serve millions of users. The three goals when you publish something:

1. **Expose a stable service you build on yourself** in your own projects;
2. **Expose an app on the LAN** to other users in your family;
3. **Expose a demo on the internet** for your friends, or a group you're learning AI with.

The platform offers all the base AI services and runtimes to compose them; the **Development service** lets a user create their own **APIs (OpenAPI)**, **tools (MCP)**, **agents (A2A or chat)**, and **UIs (HTML/HTTP)** by combining platform services. The **publishing service** is used *by the development service* to **package, deploy, and expose** the result of a development activity — whether through code written or generated, or through the configuration of agents and workflows. You should be able to develop and expose any API/tool/agent/web app; the point is often that these apps use the AI capabilities of the platform. One specific type of development is **services or implementations** — the platform should be a great environment to develop and extend itself.

These hosting services must remain **simple**: they are used at a very small scale.

This is the **publishing half** of the combined **Publishing & Governance** service (ADR-0013 §2/§6, candidate 13th, chapter `33-publishing-governance.md`). The **governance half** is settled by ADR-0018 (#15): the community catalog, the computed review-status levels, the compliance catalog. This ADR resolves the publishing half; together they fill the combined chapter. The handoff explicitly deferred that chapter until this ticket closes.

The soul shapes everything: **no magic, no black box** — publishing, updating, exposing, and sharing are explicit, visible, user-triggered actions; nothing is automatic; everything the user runs or exposes is understood and explained.

## Decision

### 1. What a published thing is — code + a runtime declaration, light by default

A **published thing** is the packaged, deployed, exposed **result of a development activity** — code (written or generated) or agent/workflow configuration. It is **NOT automatically a full base-contract platform service** (ADR-0002). Two shapes, chosen by the developer at publish time:

- **Static site / document** — the lightest case: served files (Generation-service HTML/CSS artifacts, a report, a small site). No DB, no contract, no registry entry needed beyond a dashboard link.
- **Web app / service** — a containerized long-running thing, possibly with its own API/DB, and any of the artifact kinds below.

The full service contract (template, `service.toml` conformance, per-capability implementation declarations — ADR-0002) is **opt-in at publish time**, only when the goal is "this is a platform service now" (regime 2, §5). A published web app/API is its **own HTTP surface** (any framework the author used — FastAPI, FastHTML, whatever), contained and exposed via the front door.

### 2. Runtimes — picked explicitly, no auto-detection

Three runtimes, chosen by the developer (never auto-detected — no black box):

- **Static site** — served files behind the front door. Lightest; no container for most cases.
- **Long-running container** — the agent-generated or hand-written web app/API: OS-container-isolated (ADR-0017 §2), port-mapped behind the front door. The workhorse.
- **Serverless / on-demand** — **deferred (no serverless in v1)**. Small scale + the soul favor always-running containers or static files, not a serverless platform.

Composed things (tool / agent / workflow) do **not** get a hosting runtime from publishing — they get **registration + exposure** (§6). Both **static** and **long-running container** ship in v1.

### 3. Relationship to the template/contract — light by default, full contract opt-in

- A published web app/API/site is **not** a full platform service in v1. It does not need the vendored contract, `service.toml` conformance, or per-capability implementation declarations.
- The heavier path is **the same publishing path**, not a separate one: when the developer wants their thing to *become* a real platform service (extend the platform, appear in the catalog, get `bundled`/`listed` per ADR-0018), that is a deliberate, higher-bar step re-entering the template/contract (ADR-0002 + ADR-0018's two contribution tiers).
- **Composability = registration.** A published thing an agent/workflow should invoke exposes **MCP/OpenAPI** and **registers** in the registry (ADR-0008) — registration makes it "discoverable = launchable". **UIs also register**, because agents can now drive a web UI through the **webMCP** protocol. A purely human-facing static site that no agent drives stays a plain URL (no entry).

### 4. Registry — two new entry types: `api` and `webapp` (sharpen of ADR-0008)

The registry's five typed entries (`tool | agent | workflow | skill | data_source`, ADR-0008) are extended with **two**:

- **`api`** — a published programmatic interface (**OpenAPI**). Called by *code/workflows* (`call("…")`) or by an agent, but not necessarily shaped for an LLM agentic loop. The deterministic/workflow surface (ADR-0007 §5).
- **`webapp`** — a published web UI, drivable by a human and (via **webMCP**) manipulable by an agent. **A static site is a simpler implementation of `webapp`** — one UI type, a light implementation variant, not a separate type.
- **`tool`** stays as settled: an API **optimized to be called by an LLM in an agentic loop** (the MCP surface). `tool` is a *specialized kind* of API, not a separate thing.

**One entry per surface exposed.** A published thing registers **one entry per surface it actually exposes**, each typed accordingly (`api` and/or `tool` and/or `webapp`), because "discoverable = launchable" holds per surface. `data_source` is **not renamed** — it stays the broad retrieval parent over raw Document indexes and derived Knowledge bases (and would collide with ADR-0011's "knowledge base").

### 5. Two publishing regimes — platform services vs generic publishables

Publishing splits into two distinct regimes, decided by what is published:

- **Regime 1 — platform services/implementations** (the "extend the platform" path): follow the **platform versioning rules** (ADR-0016) and flow through the **centralized updates list**, like any bundled/listed service. First-class platform citizens.
- **Regime 2 — generic APIs/apps/agents/tools** (the small-scale family/demo/learning things): **no adherence** to platform versioning/update mechanics. They have their own **separate catalog of deployable packages** (based on **GitHub + local repos**) where you **deploy/undeploy** and **start/stop**, author-versioned. This is the deployable-packages catalog.

### 6. The project concept — the unit of development + publishing

A **project** is the shared unit of the Development and Publishing services: a **GitHub (or local) repo** backing a unit that can contain **all types of publishable artifacts** (code or config). At the project root:

- **`platform.toml`** — declares the project's **platform services/implementations** (regime 1). This is the file ADR-0018 called `catalog.toml`; it is **renamed `platform.toml` everywhere** (see §7).
- **`publish.toml`** — declares the project's **publishable APIs/apps/agents/tools** (regime 2), the generic small-scale things.

The generic published things' **deployable-packages catalog** is a **real surface the Publishing service owns** (a "what can I deploy / what's deployed" list), distinct from the compliance catalog's audit purpose.

### 7. `catalog.toml` is renamed `platform.toml` everywhere (sharpen of ADR-0018)

The name `catalog.toml` is replaced by **`platform.toml`** platform-wide — including the community catalog's listing file (ADR-0018 §6/§8). Rationale: a project root now carries *two* manifest files, and keeping `catalog.toml` for one while introducing `publish.toml` for the other would muddy the vocabulary ("catalog" already means several distinct surfaces). `platform.toml` cleanly names "the manifest of platform services/implementations." ADR-0018's community-catalog surface is unchanged in role — its listing file is now called `platform.toml`.

### 8. Compliance — operational facts + a regulatory checklist, coupled to publishing

**Compliance is coupled to the Publishing service**: it is only mandatory if you want to **publish** — it is tied to the **act of publishing**, not to development. Development is free; publishing is the compliance gate.

Compliance has two dimensions, both surfaced in **Builder (authoring, own developments)** and **Administrator (read-only audit, everything)**:

1. **Operational facts** — version + update status, license, privacy tier (`local`/`cloud_no_data`/`cloud`, ADR-0008), supply-chain scan status, resource usage, computed review status (ADR-0018).
2. **Regulatory posture** — the **European AI Act** and **GDPR** as the reference baseline: *compliant to both = OK in most of the world*. Summarized into a **very simple checklist / set of questions the author answers**, structured so the **first questions provide a short exit** if the use case is low risk or there is no personal data. Answers are **stored as documentation** (part of the published thing's record). If the author needs to redact personal data from logs or put guardrails in place, the platform **gives advice on how to implement** it, and the author **documents how they managed the risk**. It is **advisory, not gatekeeping** — the author owns and records the decision.

For most home/small-business published apps (AI-Act minimal-risk tier), the checklist is a light-tier self-assessment (transparency, human oversight), not high-risk machinery. Privacy tier is the GDPR proxy. The *concrete checklist questions* are drafted carefully (factual regulatory content) at spec/build time — this ADR settles the **structure** (exit-early, answers-as-docs, advisory).

### 9. Inbound exposure — LAN + private-mesh overlay in v1; public gateway in v1.1

The security stance is settled (ADR-0017): trusted LAN plain HTTP+Bearer; internet/overlay TLS; browser-aware TLS at the front door (local CA); **no public ports on the host**; overlay for internet crossings; no mTLS. ADR-0003/Connectors schedule the **network gateway** for external clients at v1.1.

- **Goal 1 & 2 — local/LAN:** a published thing is reachable on the trusted LAN via the **front door** (one mDNS address, local CA TLS) — both your own buildable surface and family apps. Family devices get the local-CA cert, so browsers see HTTPS.
- **Goal 3 — internet demo, v1:** **private-mesh overlay sharing** — the Tailscale/WireGuard node runs **inside WSL2** (where the apps live); a friend joins the mesh via a **single-use invite link**, and the friend's device is granted access **only to the one published app's port** (default-deny). Nothing is reachable from the public internet; no public port on the host; the friend only ever reaches the stable overlay IP → one published-app port, with the front door + local CA + app auth behind it. The **Publishing service manages the overlay ACLs automatically** on publishing (in overlay mode) — the builder **never touches ACL syntax**; the builder's "share this app" gesture (pick the app, pick the devices/people or create an invite link) is the only surface, and the builder sees a human-readable summary of what was granted.
- **Goal 3 — internet demo, v1.1:** the **public-internet gateway** (a real "anyone with the link" demo) — deferred to v1.1. It requires a stable public address + reachability (port-forward or a public relay/VPS) + **edge auth + browser-aware TLS at the gateway** + a new trust boundary. When it lands it is the **Connectors service's network gateway**, implementing ADR-0017's stance — not a new security model. The learning cohort is served by the **overlay** in v1; a public link is v1.1.

**Goals 1 & 2 are fully served in v1; goal 3 is served via the private-mesh overlay in v1 and via a public link in v1.1.**

### 10. Security of agent-generated code — containment when it runs on the user's machine

The published thing — especially agent-generated web code — is untrusted-ish code running on the user's own machine; the primary threat surface is a compromised agent/harness (ADR-0017). Containment (v1):

1. **Every long-running published web app/API runs in an OS container** (not a VM, not bare) — per ADR-0017 §2. **One container per published app** (isolation between apps and from the platform's processes).
2. **Container network policy default-allow-but-scoped-to-need:** the app can reach the platform's own services (the AI capabilities it calls), but **no unrestricted host or LAN access** (ADR-0017 §5).
3. **A dedicated runtime user + filesystem boundary** per published app — isolated user, own data location; the host filesystem is not reachable except explicitly-shared dirs (host-filesystem isolation, ADR-0017 §2).
4. **Secrets** — any credentials the app needs come from the core's **`secrets` capability** (ADR-0003/0006), never embedded in generated code.
5. **A visible "runs agent/generated code" trust badge** on every published app that runs generated/agent code — in the dashboard and on the app — so the user always knows what they're running.

**Deferred:** stronger sandboxing (stricter per-app network policy, per-app VM isolation, the heavy Shieldstral guardrail tier) is not v1. Home scale + one container per app + scoped network + isolated user/fs + secrets-via-core + trust badge is the v1 bar. If a specific app needs more, that is an explicit, visible choice, not a hidden default.

### 11. Dashboard surfaces (ADR-0015 rendering)

- **Builder view (authoring / improvement mode):** the developer sees **their own** developments' publishing + compliance, in an editable/improving context — projects, deploy/undeploy, start/stop, update, version; the deployable-packages catalog; **compliance facts inline, as a responsibility the builder owns and can fix**. App publishing is already the Builder view's 4th builder feature (ADR-0015 §3).
- **Administrator view (read-only mode):** the **audit for everything** on the machine — ADR-0018's compliance catalog, read-only: all installed/running services, capabilities, implementations, and published apps, regardless of author, each with its compliance facts.
- **User view:** consume the apps shared with you (LAN/internet) — launchable URLs behind the front door, with the "runs agent/generated code" trust badge where relevant.

Compliance has two surfaces split by authorship and intent: **builder sees and fixes their own (authoring); admin audits everyone's read-only.**

### 12. Lifecycle — explicit, one-click, through the settled machinery

All lifecycle actions are explicit user actions (the "no automatic anything" soul, ADR-0016):

- **Publish** — the explicit gesture (from Development, or directly) that packages + deploys + exposes the thing and registers its entries.
- **Regime 1 (platform services/impls):** flows through ADR-0016 — centralized updates list, two-part package (metadata → checks → bytes), one-click update, rollback = previous version.
- **Regime 2 (generic publishables):** the separate deployable-packages catalog (GitHub + local repos) — **deploy/undeploy, start/stop**, author-versioned (its own version tag displayed, not enforced). **No** centralized updates list, **no** two-part gating.
- **Unpublish** — removes from exposure and unregisters its entries (frees the name, per ADR-0008 versioned).

## Boundary / handoffs

- **License** of a published thing → **#23** (open) — referenced as a compliance fact, not decided here.
- **Evaluation** ("does the generated app work") → **#16** (open) — a published app's conformance/health check is mechanical, not #16's "does it work well".
- **Backup** of published apps (if any) → **#22** (open).
- **Governance half** (community catalog, review levels, compliance catalog) → **ADR-0018** (#15, settled) — this ADR's compliance surface renders it; the combined chapter brings both halves together.
- **Inbound gateway TLS/edge-auth mechanics** → the Connectors v1.1 gateway (ADR-0003/0017); this ADR decides *timing* (v1.1) and that the gateway implements ADR-0017, not a new model.
- **Overlay/ACL mechanics** (Tailscale vs WireGuard) → an implementation choice for the Publishing service; the **restricted-by-default-share** property is this ADR's design decision.

## Considered options

- **Full service vs light published thing** — forcing every published artifact through the full service contract turns a simple published site into a platform-service-authoring exercise; the soul favors keeping light things light. Chose light-by-default, full contract opt-in.
- **`app` single type vs `api` + `webapp`** — Laurent sharpened the proposal: `tool` is an API optimized for LLM agentic loops, not all APIs are shaped like that. `api` (OpenAPI, code/workflow/agent-callable) and `webapp` (UI) are more honest than a single `app`. Chose two.
- **One entry per surface vs one entry per thing** — per-surface keeps "discoverable = launchable" true for each surface an agent can drive. Chose per-surface.
- **Static site as separate type vs simpler webapp** — a static site is a simpler implementation of a webapp, not a separate type. Chose one `webapp` type.
- **Rename `data_source` → `knowledgebase`?** — rejected: it is narrower than the type (drops Document's raw indexes) and collides with ADR-0011's "knowledge base". Kept `data_source`.
- **`catalog.toml` retained vs renamed `platform.toml`** — with `publish.toml` introduced, keeping `catalog.toml` muddies "catalog" (already several distinct surfaces). Renamed `platform.toml` everywhere.
- **Compliance as gatekeeping vs advisory** — a hard block fights the "author owns and understands" soul and the regulatory reality (most home apps are minimal-risk). Chose advisory: exit-early checklist, answers as docs, advice given, risk documented.
- **Public internet exposure in v1 vs v1.1** — ADR-0003/0017 already schedule the gateway at v1.1 and the stance forbids public ports on the host; overlay delivers "friends see the demo" in v1 without the weight. Chose LAN + private-mesh overlay in v1, public gateway v1.1.
- **Node-ACL overlay vs Funnel/public** — the node-ACL/private-mesh model keeps no public exposure and is restrictable to one app per device; Funnel is a public-link mechanism and belongs to the v1.1 gateway discussion. Chose node-ACL overlay for v1.
- **Shared container vs one container per app** — one container per app keeps a compromised app from touching another app's data or the platform's processes. Chose one container per app (acceptable at small scale).

## Consequences

- **Creates ADR-0019** — the publishing half of the combined Publishing & Governance service. Together with ADR-0018 (#15) it **creates `docs/spec/33-publishing-governance.md`** (the combined chapter, ADR-0013 §6/§7) in the same commit.
- **Sharpens ADR-0008** — registry entry types become `tool | api | agent | workflow | skill | data_source | webapp`; `api` = OpenAPI surface, `webapp` = UI (static site = simpler impl); one entry per surface; `tool` = LLM-optimized MCP subset; `data_source` unchanged.
- **Sharpens ADR-0018** — `catalog.toml` renamed `platform.toml` everywhere (community catalog listing file).
- **Glossary (CONTEXT.md):** add "published thing", "project", "platform.toml", "publish.toml", "deployable-packages catalog", "api entry", "webapp entry", "webMCP", "compliance checklist"; update "catalog.toml"→"platform.toml", the "capability registry" entry types, the "Development service" publishing note, the "Generation service" publishing note, the "Connectors service" gateway timing, and the "compliance catalog" to add the regulatory-posture dimension.
- **Feeds** the dashboard (`91-dashboard.md` Builder/Administrator publishing + compliance surfaces, ADR-0015 §3), the Connectors v1.1 gateway, and the spec's `33-publishing-governance.md` chapter.
- **Does NOT resolve** #16 (evaluation), #22 (backup), #23 (license) — referenced only as handoffs. One ticket per session.
