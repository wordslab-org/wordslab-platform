# Composing: agents, workflows, and the registry

> Owning services: **Chat + Agents** (30-services/32) and **Workflow** (30-services/33).

## Agents vs workflows (ADR-0007)

The composition model defines **two interoperable primitives** — distinct, never one a special case of the other, but interoperating bidirectionally:

- An **agent** is the *interactive/reactive* unit: a reusable, versioned definition (model + system prompt + tools + skills) — a **loop**. Flexible, costly, non-deterministic, no guarantees. It is the *interactive loop* primitive.
- A **workflow** is the *declarative* unit: a graph of steps, **deterministic** — a *deterministic DAG*. Not flexible, but cheap, simple, auditable.

They answer different needs (a reactive loop vs a deterministic DAG); merging forces one to absorb the other's semantics. So they stay separate but **interoperate bidirectionally**: a workflow step can run an agent to completion; an agent can invoke a workflow as a tool.

**The agent→workflow graduation path is load-bearing:** automation often *starts* as an agent while the problem is poorly understood, and is progressively **formalized into a workflow** as the real-world variations become understood. Agent = explore (flexible, costly); workflow = lock in (deterministic, auditable). The platform supports moving a process from agent to workflow as it matures.

### The agent loop: MAF is the platform-native loop; harness images are bring-your-own-loop

- **MAF** (in-process, Python, stateless, structured sessions in the service DB) is **the platform-native agent loop** — the composition primitive this model defines. It is structured, inspectable, attributable (action context), provider/privacy-aware, and MCP-tool-uniform — the properties a composition needs and no vendored harness can give (their internals are opaque and outside our control). MAF earns its existence as the *composition primitive* (composability, observability, controllability) — **not** by claiming to be a more capable agent than the vendored harnesses.
- **Containerized harness images** (Hermes Agent, OpenCode, Pi) are **bring-your-own-loop**: second-class for composition, driven as *workspace-session runners* for real agentic work. They are opaque (harness home, two-tier sessions) and can **lend tool implementations** to MAF where useful — no walled garden.

### Workflow = a Python program (the source of truth)

A workflow definition **is plain Python** — not a declarative DSL, no Node-RED. Python is the ZX Spectrum of this effort: the honest, teachable primitive, with a rich authoring/debugging ecosystem. It honors "Python everywhere."

**The composition primitives** are a tiny set of async Python functions — the only *externally-invoking* operations:

| Primitive | What it does | Surface |
|---|---|---|
| `call(...)` | Invoke a service capability | **OpenAPI first, MCP fallback** (MCP-only services) |
| `model(...)` | Raw model call, **structured output**, no natural-language interface | Responses API |
| `agent(...)` | Run a native (MAF) agent to completion | Agent loop (which calls model + tools) |
| `subworkflow(...)` | Run another workflow | Studio lifecycle |
| `delay(...)` | Wait on a timer (duration or until a time) | — |
| `event(...)` | Wait on an information-system event (webhook, connector event, service event) | — |
| `user_input(...)` | Wait on a human (input/signal) — the async-human-input run | — |

**Branch, loop, and transform are not primitives** — they are plain Python control flow (`if`, `for`, dict/list operations). Only the externally-invoking operations need to be primitives.

*Authoring:* the workflow is authored and edited as Python; an agent-chat companion (a MAF agent) helps the non-technical user write/refine it conversationally, visibly. A **read-only visual view** shows the flow (steps + flow logic *only*, deliberately omitting variables and data transforms) as an alternate comprehension surface — anyone can *understand* the flow without authoring it. **No editable canvas in v1.**

### Invocation follows the caller

**The surface follows the caller** (ADR-0007 §5):

- A **workflow** is deterministic Python → it favors **OpenAPI** for service calls (`call(...)`), the machine-optimized deterministic surface. It falls back to **MCP** only where a capability exposes *only* MCP (a third-party MCP server, a connector tool).
- An **agent** loop is an LLM → it calls tools via **MCP** (the natural-language tool surface).
- **`model(...)`** is the **Responses API** — the rich, typed inference surface (streaming, structured outputs) for when there is **no natural-language interface**: a deterministic structured-output transform (extraction, classification) with a JSON schema.

Deterministic callers get OpenAPI; agents get MCP.

### Explicit implementation choice — privacy is a property of the chosen implementation

The **inference policy** (`local-only` / `local-then-cloud` / `cloud-only`) is **abolished as a concept platform-wide** — not in the service contract, not in composition, not in routing/fallback (ADR-0007 §10). In its place, the model is simply:

- Every **model-backed step explicitly names the implementation it uses** (local or cloud-gateway), chosen at authoring time (by the author or with the agent-chat assistant's help). The choice is explicit and visible.
- **Privacy is a property of the chosen implementation** (the ADR-0006 three-tier taxonomy, labels `local` / `cloud_no_data` / `cloud`). Choosing the implementation *is* choosing the privacy. **There is no privacy override, no privacy rule, no "strictest wins," no routing policy** — the author names an implementation, and that's the whole story.
- The **read-only visual view shows the privacy level of each call**, derived directly from the chosen implementation.
- **No automatic cloud fallback.** If a chosen implementation is refused (fit / resource / quota) or unavailable, the platform **surfaces the refusal and the user re-chooses** (e.g., deliberately picks a cloud-gateway implementation). It never silently routes or falls back on the user's behalf.

## The capability registry (ADR-0008)

The registry is the discovery/name layer over the callable surfaces — the index an agent searches, the resolver a workflow's stable names go through, and the catalog the dashboard renders. ADR-0007 named it the **universal name→URL resolver** for all composition references: workflows reference capabilities by explicit stable names in the Python (`call("document.parse", ...)`) — **no search**; agents *discover* names via a search/load tool **within an allowlist**.

### A thin index + name authority on the leader core

The registry is a **thin discovery index + name authority on the leader core**, a control-plane capability (alongside `secrets`/`keys`/`catalog`). The core **registers nothing itself** and **never enforces it in the request path** (ADR-0003 "deliberately NOT centralized") — it is the map; services own the territory.

- Distribution mirrors the credentials pattern: entries are **pushed** on install/change, **pull-on-start** reconciles stragglers, eventual consistency (a cached index may be briefly stale; the source of truth is the leader).
- The registry is a **thin discovery index — never a store of payloads.** Each entry holds only: `id` · `type` · **one-line description** (with privacy label) · **a reference to the owning service**. The **full definition lives in the owning service** and is fetched on demand. `load(entry_id)` = the registry resolves the reference → fetches the full definition from the owning service.

### Seven entry types — models are not registry entries

Entries are one of **seven types** — `tool | api | agent | workflow | skill | data_source | webapp` (the last two types, `api` and `webapp`, added by ADR-0019). **Models are not entries.** The registry indexes the *capability you invoke*, never the model that powers it:

- **LLMs** are the agent's reasoning substrate — never a discoverable leaf (chosen at planning time). Truly out.
- **Other model types** (image gen, STT/TTS, embeddings, classic models) are exposed as *capabilities* that get an MCP surface → become **tool** entries. The registry indexes "image_generate" (the callable capability), not "FLUX.2-klein" (the implementation). Models are **implementation metadata** on a tool entry, never standalone leaves.
- A capability's name may include the model name **by user choice** when the model is the main component (e.g. "FLUX.2 image generator", "Whisper STT") — a naming preference for human discoverability, not a violation of "models out."

**Choosing a model is a planning decision, not a context-loading lookup.**

The seven types:

- **tool** — MCP tool surface, backed by a service's capability or a bundle's tool leg (executed via Connectors).
- **agent** — the agent definition (model, system prompt, accessible tool set, preloaded subset); lives in the Chat + Agents service.
- **workflow** — a workflow definition (the Python program / Studio deployment); lives in the Workflow service.
- **skill** — a SKILL.md body (frontmatter + instructions + linked files); lives in the Chat + Agents service.
- **data_source** — an index/collection produced by the **Document service** (raw document-set indexes) **or the Knowledge service** (ontologies, concept graphs, knowledge bases).
- **api** *(added by ADR-0019)* — a **published** programmatic interface (**OpenAPI**): a published thing's deterministic surface, called by code/workflows (`call("…")`) or by an agent.
- **webapp** *(added by ADR-0019)* — a **published** web UI, drivable by a human and (via the **webMCP** protocol) manipulable by an agent. A static site is a simpler implementation of `webapp`, not a separate type.

Published things register **one entry per surface actually exposed** (an app may register an `api` and/or a `tool` and/or a `webapp`), because "discoverable = launchable" holds per surface. `tool` remains the LLM-optimized MCP surface — a specialized kind of API, not a separate thing from `api`.

### Entry shape — progressive disclosure

**One-line description** — the discoverable, prompt-facing summary; what sits in the system prompt (preloaded subset) and what search returns:

```
<name> · <type> · one-line summary · <privacy label> (where applicable)
```

e.g. `web.search — tool — Search the web and return ranked results — cloud_no_data`. Compact (~50 tokens) because it fills the prompt.

**Full definition** — pulled on demand via `load(entry_id)` from the **owning service**: tool → the service's MCP `tools/list` surface; workflow → the Workflow service; skill → the Chat + Agents service; agent → the agent definition; data_source → the Document/Knowledge service; api/webapp → the Publishing service (the owning service for published things). Every full definition carries **provenance** (service, capability, surface). **One-level load for v1.**

### Name authority and per-agent scoping

**Name grammar** (ADR-0008 §8) — stable names are only stable if **one authority guarantees uniqueness**:

- Capability/tool entries → `<service>.<capability>` — e.g. `document.parse`, `audio.stt`, `connectors.web.search`.
- Authored entries (agent/workflow/skill) → `<service>.<kind>.<user-chosen-name>`.
- Data sources → `document.<collection>` / `knowledge.<kb>`.
- Canonical resolution name (what composition `call()`s): `<service>.<capability>` — *without* implementation. The implementation is chosen **separately at authoring time** as an explicit planning decision.

The **leader core's registry is the name authority** (a control-plane role). At **registration time** it **validates** the name against the grammar, **reserves** it, and **rejects collisions** with `409 conflict` so a second claimant can never shadow an existing name. This is validation/reservation at registration — **not request-path enforcement**.

**Per-agent scoping is enforced server-side** (ADR-0007 §9, ADR-0008 §5). The **accessible tool set lives in the agent definition** (the allowlist) — *not* in the registry. The registry's search/load tool **reads the caller's agent definition** (by agent id from action context) at search time, extracts the accessible set, and **scopes the query server-side**: `search(query)` returns **only entries within the agent's accessible set** (the agent can never even *see* tools outside its allowlist); `load(entry_id)` **refuses** ids outside the accessible set (a guessed/replayed id cannot bypass). The **preloaded subset** (subset of accessible) is loaded into the system prompt by the harness, not by a runtime search. **Workflows have no allowlist** — a workflow's `call("document.parse", ...)` uses an explicit stable name already in the program; no discovery/search path, no risk.
