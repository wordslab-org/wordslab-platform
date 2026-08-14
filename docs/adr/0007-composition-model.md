# ADR-0007 — Composition model (workflows & agents)

**Status:** accepted (resolution of wayfinder ticket "Design the composition model"); **amends ADR-0001** (family 9 authoring shape detail), **ADR-0002** (removes the inference policy from the service declaration; callable-surface mapping), **ADR-0004/0005** (resource refusal → surface + user re-chooses, not inference-policy fallback), **ADR-0006** (§7 routing-vs-privacy contrast removed; privacy-tier labels → `local`/`cloud_no_data`/`cloud`); **registry mechanics realized by ADR-0008** (thin index + name authority, per-agent scoping, name→URL resolution); DocETL/entity-resolution homes re-scoped by the **Document/Knowledge split (#26)**

## Context

The platform's core promise: "run and compose a local version of all the main AI services to create powerful workflows or agents." This ADR is the composition model — the primitives (workflow, agent), the user-facing authoring mechanism, how services are invoked inside a composition, and triggers/scheduling. It sits on the settled catalog (#18: the **Workflow service** and **Chat + Agents service** are composition's home), the service contract (ADR-0001), the callable surfaces (ADR-0002), the provider model (#19, ADR-0006), the resource layer (#4, ADR-0005), and the topology (#6, ADR-0004). It is the inverse of the enterprise studies' L4 orchestration layer: the same concepts, radically lighter execution, cut to home scale.

The soul shapes everything: **no magic, no black box** — composed workflows/agents must show *what they call, with what, and to whom*; triggers/scheduling visible and user-editable; remembered choices = explicit user-written decisions, never hidden heuristics. Our audience learns and understands AI; a composition is something to *read*, not a black box to trust.

## Decision

### 1. Two primitives: agent and workflow — distinct but interoperable, with a graduation path

- **Agent** — the *interactive/reactive* unit: a reusable, versioned definition (model + system prompt + tools + skills), a **loop**. Flexible, costly, non-deterministic, no guarantees. Family 9 `/v1/agents`, Mistral Studio Agents & Conversations shape.
- **Workflow** — the *declarative* unit: a graph of steps, **deterministic**. Not flexible, but cheap, simple, auditable. Family 9 `/v1/workflows`, Studio lifecycle (definition → deployment → run/schedule).

They are **separate primitives**, not one a special case of the other. But they **interoperate bidirectionally**: a workflow step can run an agent to completion; an agent can invoke a workflow as a tool.

**The graduation path (load-bearing):** automation often *starts* as an agent while the problem is poorly understood, and is progressively **formalized into a workflow** as the real-world variations become understood. Agent = explore (flexible, costly); workflow = lock in (deterministic, auditable). The platform supports moving a process from agent to workflow as it matures.

### 2. The agent loop: MAF is the platform-native primitive; harness images are bring-your-own-loop

- **MAF** (in-process, Python, stateless, structured sessions in the service DB) is **the native agent loop this model defines as the composition primitive**. It is structured, inspectable, attributable (action context), provider/privacy-aware, and MCP-tool-uniform — the properties a composition needs and no vendored harness can give (their internals are opaque and outside our control).
- **Containerized harness images** (Hermes Agent, OpenCode, Pi) are **bring-your-own-loop**: second-class for composition, driven as *workspace-session runners* for real agentic work. They are opaque (harness home, two-tier sessions per #18) and can **lend tool implementations** to MAF where useful — no walled garden.

MAF earns its existence as the *composition primitive* (composability, observability, controllability) — **not** by claiming to be a more capable agent than the vendored harnesses.

### 3. Workflow = a Python program (the source of truth)

A workflow definition **is plain Python** — not a declarative DSL. Python is the ZX Spectrum of this effort: the honest, teachable primitive, with a rich authoring/debugging ecosystem. It honors "Python everywhere" and copies the Mistral workflows shape (workflows *are* Python) without the enterprise worker/deployment machinery.

**The composition primitives** are a tiny set of async Python functions (the only *externally-invoking* operations):

| Primitive | What it does | Surface |
|---|---|---|
| `call(...)` | Invoke a service capability | **OpenAPI first, MCP fallback** (MCP-only services) |
| `model(...)` | Raw model call, **structured output**, no natural-language interface | Responses API (family 1) |
| `agent(...)` | Run a native (MAF) agent to completion | Agent loop (which calls model + tools) |
| `subworkflow(...)` | Run another workflow | Studio lifecycle |
| `delay(...)` | Wait on a timer (duration or until a time) | — |
| `event(...)` | Wait on an information-system event (webhook, connector event, service event) | — |
| `user_input(...)` | Wait on a human (input/signal) — the async-human-input run | — |

**Branch, loop, and transform are not primitives** — they are plain Python control flow (`if`, `for`, dict/list operations). Only the externally-invoking operations need to be primitives.

### 4. Authoring mechanism

- **Primary: Python code.** The workflow is authored and edited as Python.
- **An agent-chat companion (a MAF agent) helps author it** — the non-technical user is not left alone with code; a guided agent helps write/refine the workflow conversationally, visibly.
- **A read-only visual representation** shows the flow (steps + flow logic *only*, deliberately omitting variables and data transforms) as an alternate comprehension surface — anyone can *understand* the flow without authoring it.
- **No editable canvas in v1.** (Node-RED is therefore not used as a canvas; the read-only view is a lightweight renderer, not a vendored no-code editor.)

### 5. How services are invoked inside a composition — the surface follows the caller

- **A workflow is deterministic Python → it favors OpenAPI** for service calls (`call(...)`). OpenAPI is the machine-optimized deterministic surface. It falls back to **MCP** only where a capability exposes *only* MCP (a third-party MCP server, a connector tool).
- **An agent loop is an LLM → it calls tools via MCP** (the natural-language tool surface).
- **`model(...)` is the Responses API** — the rich, typed inference surface (streaming, structured outputs) for when there is **no natural-language interface**: a deterministic structured-output transform (extraction, classification) with a JSON schema.
- **`agent(...)` runs a native agent** — the natural-language task surface (open-ended, loop, tools, memory).

### 6. Documents: DocETL pipelines as an abstract request to the Document service

**DocETL is to unstructured data what SQL is to structured data.** A workflow builds a **DocETL pipeline expression natively in Python** (the Frame-API chain), serializes it as an **abstract request**, and sends it to the **Document/Knowledge service** *(the home is being split by #26 — Document owns source/filter/retrieval operators; Knowledge owns entity linking/grounding/aggregation/facts — see "Design the document transformation engine (DocETL pipelines as an abstract request)")*, which **optimizes and executes it where the data lives** (data locality) — the "database engine for unstructured data" (remote LINQ-to-SQL / OData analogue). The *request programming* is native Python in the workflow; the *engine* (optimizer + execution) is the Document/Knowledge service's.

DocETL's LLM-powered operators route their model calls through the **Inference service** as **explicit implementation choices** (#13 §10), never a raw external key. The optimized plan it produces is **visible** (no black box).

Hand-in-hand: **entity resolution / concept repository / knowledge-graph building** grounds extracted entities to canonical concept/entity IDs (design ticket: "Design entity resolution, the concept repository & knowledge-graph building") — a Document-service capability that gives indexed documents a structured grounding layer.

### 7. Triggers & scheduling

A workflow **starts** from a trigger; it **pauses mid-run** on `delay`/`event`/`user_input` — the same vocabulary on both ends.

- **Triggers:** `manual` (dashboard or authoring chat), `schedule` (cron/interval/calendar), `webhook` (family 8 HMAC webhook), `connector-event` (a connector event — new email, web result, etc.). Nothing more for v1 (a file change is a connector-event; an API call is a webhook).
- **Overlap & catch-up policies:** each schedule declares whether an overlapping run is skipped or allowed, and whether a missed tick catches up or is skipped — the Mistral `ScheduleDefinition` shape. Explicit, user-chosen, no hidden behavior.
- **Runs are family-5 jobs:** queued/running/completed/failed, progress, cancel, webhook on completion; **per-step retries with backoff**; a failed step can take an explicit on-failure path.

### 8. State, persistence & idempotency — the two-tier split

- **Native runs** (MAF workflows and native agents) are **structured, replayable, and inspectable**: run state lives in the service DB as a sequence of step events (each awaited primitive with inputs, outputs, action context). A run can be replayed, inspected, resumed, and its failure point identified — no black box. (Mistral event-history model, home-scale; not the OSS-heavy Temporal worker machinery.)
- **Harness-image runs** are **opaque and snapshotted as-is** (the #18 two-tier decision; the platform persists the harness home, never parses it).
- **Retries & idempotency:** a run is a family-5 job; a side-effecting step is retried under the base contract's `Idempotency-Key` so a retry does not double-fire; the structured history lets the platform resume without re-executing completed steps.

### 9. Discovery & the capability registry (#20)

The **capability registry is the universal name→URL resolver** for all composition references (ADR-0008: thin index + name authority on the leader core; entries `tool | agent | workflow | skill | data_source`).

- **Workflow:** references capabilities by **explicit, stable names in the Python** (`call("document.parse", ...)`). The registry resolves name→endpoint at run time. **No search** — the name is already in the program.
- **Agent:** *discovers* names via the registry **search/load tool** — but **only within an allowlist**: the agent definition declares (a) the **accessible tool set** (which registry tools the agent may search and invoke) and (b) the **preloaded subset** (a subset of accessible, systematically loaded into the system prompt). The registry enforces the accessible set **server-side** on both search and load (the allowlist lives in the agent definition; the registry reads it at search time). (This is both control and security; feeds #14.)

The `agent` entry *format* (accessible + preloaded tool lists) is this model's; the registry *mechanics* are #20's.

### 10. Provider/privacy — explicit implementation choice; no inference policy, anywhere

**The inference policy (`local-only` / `local-then-cloud` / `cloud-only`) is abolished as a concept platform-wide** — not in the service contract (ADR-0002), not in composition, not in routing/fallback. In its place, the model is simply:

- Every **model-backed step explicitly names the implementation it uses** (local or cloud-gateway), chosen at authoring time (by the author or with the agent-chat assistant's help). The choice is explicit and visible.
- **Privacy is a property of the chosen implementation** (the ADR-0006 three-tier taxonomy, labels `local` / `cloud_no_data` / `cloud`). Choosing the implementation *is* choosing the privacy. **There is no privacy override, no privacy rule, no "strictest wins," no routing policy** — the author names an implementation, and that's the whole story.
- The **read-only visual view shows the privacy level of each call**, derived directly from the chosen implementation.
- **No automatic cloud fallback.** If a chosen implementation is refused (fit / resource / quota) or unavailable, the platform **surfaces the refusal and the user re-chooses** (e.g., deliberately picks a cloud-gateway implementation). It never silently routes or falls back on the user's behalf.

### 11. Boundary

- **#13 owns:** composition primitives, authoring mechanism, invocation surface, triggers & scheduling, run-state model, and the `agent` entry format.
- **#20 owns:** the registry *mechanics* (index, search/load, per-agent scoping).
- **#18 owns:** the hosting services (Workflow + Chat + Agents) and the catalog.
- **#19 / ADR-0006 own:** the provider registry, provider rows, implementation-selection machinery, privacy-tier taxonomy. #13 consumes them as explicit implementation choice.
- **#14 owns:** container network policy, harness accept/refuse, connector audit/approval (execution safety).
- **#21 owns:** publishing (definition → published).
- **#4 / ADR-0005 own:** model load/fit/refusal and cloud-spend quotas — with the amendment that refusal *surfaces + user re-chooses* (no inference-policy fallback).
- **ADR-0003:** the core never executes composition (unchanged).
- **Document service (new tickets):** the DocETL engine, and entity resolution / concept repository / knowledge-graph building.

## Considered options

- **Agent = special case of workflow (or vice versa) vs distinct-and-interoperable** — the two answer different needs (reactive loop vs deterministic DAG); merging forces one to absorb the other's semantics. Interop + the graduation path keep both simple and honest.
- **Harness images as the primary loop vs MAF as the primitive** — vendored harnesses are opaque and outside the platform's control, so they cannot serve as a compositional primitive (structured, attributable, provider-aware). MAF is built to be the primitive; harnesses stay as workspace runners.
- **Declarative DSL vs Python** — a DSL is a bespoke language nobody knows (a black box until learned); Python is the teachable, debuggable, ecosystem-rich primitive, and matches "Python everywhere" and the Mistral shape.
- **MCP-everywhere for workflows vs OpenAPI-first/MCP-fallback** — a deterministic Python workflow should use the deterministic machine surface (OpenAPI); MCP is the LLM tool surface. Surface follows the caller.
- **Generic `wait` vs explicit `delay`/`event`/`user_input`** — a single wait hides what it waits for; explicit primitives keep triggers visible and attributable.
- **DocETL in-process vs as an abstract request to an engine** — shipping the plan (not the documents) to an optimizing engine where the data lives gives data locality and the optimizer's accuracy/cost rewrites, with the optimized plan visible. This is the SQL/LINQ-to-SQL analogue.
- **Inference policy + per-step privacy override vs explicit implementation choice** — any routing/override rule is a hidden behavior the soul forbids. Explicit implementation choice makes the privacy decision the *visible act of picking an implementation*, with nothing to resolve behind the user's back.

## Consequences

- **Amends ADR-0002:** removes the `inference policy` from the service declaration (`service.toml`); callable-surface mapping clarified (OpenAPI = deterministic surface for workflows, MCP = LLM tool surface).
- **Amends ADR-0004/0005:** resource refusal surfaces and the user re-chooses an implementation; no inference-policy cloud fallback.
- **Amends ADR-0006:** §7's routing-vs-privacy contrast is removed — privacy tier is a property of each implementation, chosen explicitly; there is no inference policy.
- **Amends ADR-0001:** family 9 authoring shape — the agent definition carries accessible + preloaded tool lists; workflows are Python programs with the §3 primitive set.
- **Creates** two Document-service design tickets: the DocETL engine (abstract-pipeline request), and entity resolution / concept repository / knowledge-graph building.
- **Feeds:** the capability registry (#20 — agent entry format, per-agent scoping), the dashboard (#8 — workflow authoring UI, read-only visual view, privacy-per-call display, run observability), publishing (#21 — Studio deploy-style), the spec anatomy (#12).
- **Glossary (CONTEXT.md):** agent/workflow primitives + graduation path, composition primitive, MAF native loop, abstract request, accessible tool set, preloaded tool subset, explicit implementation choice.
