# ADR-0008 — Capability registry & search/load service

**Status:** accepted (resolution of wayfinder ticket "Design the capability registry & search/load service"); **realizes ADR-0007 §9** (registry = universal name→URL resolver; per-agent scoping) and **ADR-0006** (privacy tier discoverable in the description; bundle tool legs); **relabels the privacy-tier vocabulary** across ADR-0006/0007/0002/0004 and CONTEXT.md to `local / cloud_no_data / cloud`; **sharpened by ADR-0019** (entry types extended to seven: adds `api` and `webapp` for published things; one entry per exposed surface)

## Context

Every agent loop and workflow discovers and invokes the platform's capabilities through **one searchable index**: the capability registry. It is the discovery/name layer over the callable surfaces (ADR-0002) — the index an agent searches, the resolver a workflow's stable names go through, and the catalog the dashboard renders. It is the direct handoff from composition (ADR-0007 §9), which named it the **universal name→URL resolver** for all composition references: workflows reference capabilities by explicit stable names in the Python (`call("document.parse", ...)`) — **no search**; agents *discover* names via a search/load tool **within an allowlist**. The registry's *mechanics* (index, search/load, per-agent scoping, registration, name resolution) are this ADR's; the `agent` entry *format* is #13's (ADR-0007).

The provider model (ADR-0006) adds a discoverability constraint: **privacy tier is visible up front** on every entry backed by a cloud implementation or a bundle's tool leg, so a discoverer (agent or human) sees the data-handling guarantee before choosing. Bundle tool legs register here and **execute via the Connectors service** — the registry is a discovery index, never an executor. **Models are deliberately not in the registry** (ADR-0007 §10): choosing a local vs cloud-gateway implementation is an explicit planning decision, not a context-loading lookup.

The soul shapes everything: **no magic, no black box** — discovery must show *what exists, what it does, where data goes, and who executes it*; per-agent scope is enforced server-side (control + security); stable names are reserved by an authority so `call("document.parse", ...)` always resolves to the same thing.

## Decision

### 1. The registry is a thin discovery index + name authority on the leader core

- **The authoritative registry index lives in the leader core** as a control-plane capability (alongside `secrets`/`keys`/`catalog`). The core **registers nothing itself** and **never enforces it in the request path** (ADR-0003 "deliberately NOT centralized") — it is the map; services own the territory.
- Distribution mirrors ADR-0006's credentials pattern: entries are **pushed** on install/change, **pull-on-start** reconciles stragglers, and the operating model is **eventual consistency** (a cached index may be briefly stale; the source of truth is the leader).
- The **registry is a *thin* discovery index — never a store of payloads.** Each entry holds only: `id` · `type` · **one-line description** (with privacy label) · **a reference to the owning service**. The **full definition lives in the owning service** and is fetched on demand. `load(entry_id)` = the registry resolves the reference → fetches the full definition from the owning service.

### 2. Entry types — seven typed entries (v1, sharpened by ADR-0019)

`tool | api | agent | workflow | skill | data_source | webapp`. **Models are not entries.** The registry indexes the *capability you invoke*, never the model that powers it:
- **LLMs** are the agent's reasoning substrate — never a discoverable leaf (chosen at planning time, ADR-0007 §10). Truly out.
- **Other model types** (image gen, STT/TTS, embeddings, classic models) are exposed as *capabilities* that get an MCP surface → become **tool** entries. The registry indexes "image_generate" (the callable capability), not "FLUX.2-klein" (the implementation). Models are **implementation metadata** on a tool entry, never standalone leaves.
- **A capability's name may include the model name by user choice** when the model is the main component (e.g. "FLUX.2 image generator", "Whisper STT") — a naming preference for human discoverability, not a violation of "models out."

**Connectors bring `tool` entries** (web search, fetch, x/twitter… — callable tools with audit/approval). A connector can *feed* a data source (fetch → index → data_source), but the connector itself registers tools. **Workspaces/environments stay out** — they are execution state/resources allocated by the `resources` capability and mounted into sessions, not discoverable capabilities.

**The seven types:**
- **tool** — MCP tool surface (ADR-0001 family 3: `{id, name, one-line, endpoint, tools: [{name, one-line}]}`), backed by a service's capability or a bundle's tool leg (executed via Connectors).
- **agent** — the #13 agent definition (model, system prompt, accessible tool set, preloaded subset); lives in the Chat + Agents service.
- **workflow** — a workflow definition (the Python program / Studio deployment); lives in the Workflow service.
- **skill** — a SKILL.md body (frontmatter + instructions + linked files); lives in the Chat + Agents service.
- **data_source** — an index/collection produced by the **Document service** (raw document-set indexes) **or the Knowledge service** (ontologies, concept graphs, knowledge bases — after the Document/Knowledge split, #26).
- **api** *(added by ADR-0019)* — a **published** programmatic interface (**OpenAPI**): a published thing's deterministic surface, called by code/workflows (`call("…")`) or by an agent, but not necessarily shaped for an LLM agentic loop. Backed by a published thing's own HTTP surface (ADR-0019 §3/§4).
- **webapp** *(added by ADR-0019)* — a **published** web UI, drivable by a human and (via the **webMCP** protocol) manipulable by an agent. **A static site is a simpler implementation of `webapp`**, not a separate type. A published thing that is only a human-facing site and is never agent-driven needs no entry (a plain dashboard link).

*Published things register **one entry per surface actually exposed** (an app may register an `api` and/or a `tool` and/or a `webapp`), because "discoverable = launchable" holds per surface (ADR-0019 §4). `tool` remains the LLM-optimized MCP surface — a specialized kind of API, not a separate thing from `api`.*

### 3. Entry shape — progressive disclosure

**One-line description** — the discoverable, prompt-facing summary; what sits in the system prompt (preloaded subset) and what search returns. Shape:

```
<name> · <type> · one-line summary · <privacy label> (where applicable)
```

e.g. `web.search — tool — Search the web and return ranked results — cloud_no_data`. Compact (~50 tokens) because it fills the prompt.

**Full definition** — pulled on demand via `load(entry_id)` from the **owning service**:
- **tool** → the service's MCP `tools/list`/tool endpoint (name, description, `inputSchema`, resolving endpoint, executing service — e.g. Connectors for bundle tool legs, privacy label repeated).
- **workflow** → the workflow object in the **Workflow service** (registry holds description + reference).
- **skill** → the SKILL.md body + metadata in the **Chat + Agents service** (registry holds description + reference).
- **agent** → the #13 agent definition in the **Chat + Agents service**.
- **data_source** → the index/collection details in the **Document / Knowledge service**.
- **api / webapp** *(added by ADR-0019)* → the published thing's invocation surface (OpenAPI for `api`; the webMCP/UI surface for `webapp`), in the **Publishing service** (the owning service for published things).

Every full definition carries **provenance** (service, capability, surface) so the catalog UI can render the hierarchy. **One-level load for v1** — `load` pulls the full definition; a full definition may itself reference further sub-resources (skill linked files, workflow steps) fetched as needed, but there is no multi-level load protocol in v1.

### 4. Search/load protocol — a hardcoded core primitive

The registry exposes a standard pair:
- `search(query)` → **one-line descriptions** of matching entries, **scoped to the caller** (below). Compact, prompt-fillable.
- `load(entry_id)` → the **full definition**, fetched from the owning service via the reference.

**The search/load tool is a hardcoded core primitive** — a built-in MAF tool pointing at the core's registry surface. This is a **bootstrap necessity**: you cannot discover the discovery tool, so it is not itself a registry entry. For workflows there is **no search** — they reference explicit stable names in the Python, resolved by the registry's name→URL role.

### 5. Per-agent scoping — enforced server-side, allowlist lives in the agent definition

- The **accessible tool set lives in the agent definition** (Chat + Agents service, the #13 format) — *not* in the registry. The registry's search/load tool **reads the caller's agent definition** (by agent id from action context) at search time, extracts the accessible set, and **scopes the query server-side**:
  - `search(query)` returns **only entries within the agent's accessible set** — the agent can never even *see* tools outside its allowlist;
  - `load(entry_id)` **refuses** ids outside the accessible set (a guessed/replayed id cannot bypass).
- The **preloaded subset** (subset of accessible) is loaded into the system prompt by the harness, not by a runtime search.
- Scoping is enforced at the **registry/search surface** (the gate for *discovery*), not in the request path of the underlying service — once an agent is granted a tool, the tool's own service still applies its own auth/approval (Connectors audit, etc.). Keeps the core out of the request path (ADR-0003).
- **Workflows have no allowlist.** A workflow's `call("document.parse", ...)` uses an explicit stable name already in the program — no discovery/search path, no risk (the human decides deterministically which tool is called). Access is governed by the workflow's own permissions/action-context, not a registry allowlist.

### 6. Registration — owning services register; authored entries on publish

- **Who registers what:** the **owning service** registers its entries (ADR-0003 "services register", never the core, never scraping):
  - **tool** → the owning service's MCP tool surfaces;
  - **agent / workflow / skill** → the **Chat + Agents** service (and **Workflow** service for workflows) registers authored entries;
  - **data_source** → the **Document** / **Knowledge** service registers its indexes/collections;
  - **bundle tool legs** → register as tool entries identifying **Connectors** as the executing service;
  - **api / webapp** *(added by ADR-0019)* → the **Publishing service** registers published things on publish.
- **When:** **at install** (a service comes up, pushes its catalog), **on change** (capability added/removed; agent/skill/workflow published/updated/deleted), **pull-on-start** (consumers refresh at boot). **Authored entries (agent/workflow/skill) and published things (api/webapp, via the Publishing service) register on publish only** (Studio deploy-style, ADR-0001 family 9) — a draft is not discoverable; **discoverable = launchable**. Drafts stay private to their author's editing surface.
- The registry is **populated by registration, never by scraping.**

### 7. Two roles, one index — search/discovery AND name→URL resolution

The registry is simultaneously:
- **(a) the search index** for agents (scoped search/load), and
- **(b) the name→URL resolver** for workflows (explicit stable names → endpoint) and for agent tool references once a tool is chosen.

An entry's stable `id`/`name` maps to its resolving endpoint + owning service. **One registry, two consumption modes** — *discovery* (agents, scoped) and *resolution* (workflows, explicit, no scope needed since the name is chosen deterministically).

### 8. Namespaces & name authority — stable names are reserved

Stable names are only stable if **one authority guarantees uniqueness**. Name grammar (namespaced, hierarchical):
- **Capability/tool entries** → `<service>.<capability>` — e.g. `document.parse`, `audio.stt`, `connectors.web.search`. The service is the top-level namespace; capabilities are unique within a service (the catalog fixes service names, so the top level is naturally unique).
- **Authored entries** (agent/workflow/skill) → `<service>.<kind>.<user-chosen-name>` — e.g. `chat.summarizer` (an agent), `workflow.monthly-brief`, `skill.document-qa`. Kind + slug, unique within the service's authored namespace.
- **Data sources** → `document.<collection>` / `knowledge.<kb>`.
- **Full name grammar (catalog & human browse, all levels):** `<service>.<capability>.<implementation>` — e.g. `image.generate.flux2`. The implementation is a **visible level** in the catalog hierarchy and in a capability's entry (its list of implementations, each with its privacy label).
- **Canonical resolution name (what composition `call()`s and an agent resolves):** `<service>.<capability>` — *without* implementation. `call("audio.stt", ...)` names the capability; the implementation is chosen **separately at authoring time** as an explicit planning decision (ADR-0007 §10). You'd only pin an implementation in the name to make one capability instance per implementation (e.g. `image.generate.flux2` distinct from `image.generate.sdxl`).

**Authority:** the **leader core's registry is the name authority** (a control-plane role, consistent with ADR-0003). At **registration time** it **validates** the name against the grammar, **reserves** it (creating the unique entry record), and **rejects collisions** with `409 conflict` so a second claimant can never shadow an existing name. A **published name is the stable, immutable reference** workflows and agents resolve against; un-publishing frees it (versioned). This is **validation/reservation at registration — not request-path enforcement** — within the core's "centralize control, never the request path" role.

### 9. Versions — float or pin; retention is best-effort

- Every entry carries a **version**. Authored entries (agent/workflow/skill) are **immutable published snapshots** (the family-9 Studio lifecycle: definition → deployment → publish); capability/tool entries carry their **owning service's version**.
- **Resolution floats or pins:**
  - **floating** — `call("document.parse")` / `agent("summarizer")` → resolves to the currently-published/default version (for capabilities, the running service; for authored, the published pointer). Stable *name*, current *version*.
  - **pinned** — an explicit version qualifier, `workflow.monthly-brief@3` or `call("document.parse@1.2")` → resolves to that **immutable snapshot**. Pinned references are reproducible.
- The registry stores each entry's **version history**; `search`/`load` return version-aware one-lines; the catalog UI shows versions and lets you browse/pin.
- **Version retention is best-effort** — a service with a complex code or model implementation may not be able to keep previous versions available, so the registry records **what is retained per entry** (full history where feasible, current-only where not). Versioning must **not** require full history of every entry.

### 10. Three consumption modes — implementations are the selectable unit

Search operates at the **capability** level, but **implementations are the selectable unit** across all three modes:

1. **Agent search** — an agent searches a *capability* → the result is the capability **plus its implementations** (each with its privacy label `local`/`cloud_no_data`/`cloud`); the agent **explicitly picks the implementation** best suited to the task. Visible, named choice — the agent-side explicit implementation choice, no hidden auto-routing. Scoped by the agent's allowlist.
2. **Workflow** — the author **directly references a specific implementation** at authoring time (`call("audio.stt", implementation=...)` or the implementation in the name). Deterministic, pinned by the author.
3. **Dependency declaration** — a service declares a dependency; the **end user chooses the implementation** via a dynamically-populated list in the UI (the registry's search surfaces the choices). Ties into the dependency-graph/activity model (#6/#4): **capability = the dependency unit, implementation = the user's choice.**

### 11. Dependency declaration — loose (capability) OR specific (implementation), both valid

A service can declare a dependency either way; both are legitimate:

- **Loose (capability-scoped)** — service Z declares a dependency on a *capability* (`document.parse`, `llm.chat`). It needs **at least one implementation** of that capability; the **end user picks which** (and which fits) at install/use time, from the registry's dynamically-populated list, privacy labels shown. This contributes a *choice* to the placement simulation.
- **Specific (implementation-scoped)** — service Z declares a dependency on a **specific implementation** (`image.generate.flux2`, `llm.chat.llama3-8b`). This is a **hard fit constraint** (ADR-0004 §4 fit gate): the named implementation **must fit** the target machine, or the dependency is **unsatisfiable** → the service is degraded / cannot run until a machine hosts something that fits. The user does **not** silently substitute a different implementation at install. If it won't fit, the platform **surfaces the refusal and the user explicitly re-chooses** (loosen to a capability dependency, or place on a different machine) — never a silent swap. This contributes a *requirement* the simulation must satisfy.

Both map onto the resolution-name grammar: the loose form names `<service>.<capability>`; the specific form names `<service>.<capability>.<implementation>` (the same grammar as the workflow author pinning an implementation). The specific pin is honored as a hard constraint; the only escape is an explicit user re-choice — consistent with the "no hidden fallback" soul.

### 12. Boundary

State in the resolution comment: **#20 = registry mechanics** (index, search/load, per-agent scoping, registration, name→URL resolution, name authority); **#13 = the agent entry format** (done, ADR-0007); **#18 = the hosting services + Connectors execution**; **#19 = privacy-tier discoverability** (constraint) + **privacy-label relabel**; **#26 = Document/Knowledge split** (data_source entries from both); **#14 = security** (harness accept/refuse, connector approval); **#8 = dashboard** (browse/search UI). The core never executes composition / never enforces in the request path (ADR-0003).

## Considered options

- **Thin registry (chosen) vs a store of payloads** — the registry holds descriptions + references; the owning service holds full definitions. Keeps the core from ever being a store of data/execution — exactly ADR-0003's "deliberately NOT centralized." `load` fetches from the owning service.
- **Five typed entries (chosen) vs the original four** — `workflow` is added alongside `tool | agent | skill | data_source` because workflows are composed/invoked/discovered like the rest; models stay out entirely.
- **Server-side per-agent scoping (chosen) vs client-side filtering** — the accessible set lives in the agent definition; the registry enforces it on both search and load so an agent can never even see out-of-allowlist entries. Control boundary, not a filter.
- **Core as name authority at registration (chosen) vs services self-validating with the core only arbitrating on conflict** — the core's single registration point guarantees global uniqueness for cross-machine/multi-author references; reservation/validation at registration stays within "centralize control, never the request path."
- **Implementation visible in the name, out of the default resolution name (chosen) vs always in the resolution name** — keeps the catalog hierarchy human-browsable while preserving "implementation chosen at authoring, not by registry lookup" (ADR-0007 §10); a deliberate per-implementation split is still possible.
- **Float-or-pin version resolution (chosen) vs versionless** — authored entries need reproducibility; floating gives the stable-name, current-version default; version retention is explicitly best-effort (a complex code/model implementation may not retain history).
- **Registration-on-publish for authored entries (chosen) vs on save/draft** — discoverable = launchable; drafts stay private, so the registry never fills with half-finished, un-launchable entries.

## Consequences

- **Relabels the privacy-tier vocabulary platform-wide**: `local / cloud_no_data / cloud` replace `own machines / ZDR / other` (ADR-0006 §7, ADR-0007 §10, ADR-0002, ADR-0004, CONTEXT.md). Semantics unchanged — friendlier, still unambiguous, canonical everywhere.
- **Realizes ADR-0007 §9**: the registry is the universal name→URL resolver; per-agent scoping (accessible set + preloaded subset) enforced server-side; workflow references resolve by explicit stable name, no search.
- **Realizes ADR-0006**: privacy label is in the one-line description AND the full definition; bundle tool legs register as tool entries executed via Connectors; models stay out.
- **Expands** "Design the integrated UI (dashboard)" (#8 — registry browse/search UI, version/pin browsing, privacy labels, per-agent scoping display), "Define the security model" (#14 — server-side scoping as the control boundary; harness accept/refuse; connector approval), "Split the Document service into Document + Knowledge" (#26 — data_source entries produced by both).
- **Feeds** "Design the single-click installer" (#7 — registration on install), "Design the update & versioning flow" (#10 — version retention/float-pin), the spec anatomy (#12 — this chapter lands in the spec).
- **Glossary (CONTEXT.md):** capability registry (thin index + name authority), registry entry (seven typed entries: tool/api/agent/workflow/skill/data_source/webapp), one-line description, full definition (owning service), search/load tool (hardcoded core primitive), accessible tool set, preloaded subset, per-agent scoping, name authority, stable name, float/pin resolution, dependency declaration (loose/specific), privacy labels (`local`/`cloud_no_data`/`cloud`).
