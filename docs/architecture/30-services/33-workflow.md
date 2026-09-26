# 33 — Workflow

> **Status:** written at the resolution of wayfinder ticket "Design the Workflow service chapter (foundational)" (#43). **Source of truth:** ADR-0007 (composition: the workflow primitive, the composition primitives, authoring, invocation-follows-the-caller, the agent→workflow graduation path, triggers & scheduling, runs, the two-tier run state, explicit implementation choice), ADR-0008 (the capability registry: the name→URL resolver for composition references; authored **workflow** entries, the `workflow.<name>` namespace), ADR-0001 (family 9 authoring, family 5 jobs, family 8 webhook, the base contract's `Idempotency-Key`), ADR-0002 (callable surfaces). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Workflow service** is the platform's **composition-and-automation service**: it composes, schedules, and triggers all platform capabilities. It is the home of the **workflow** composition primitive and of authored **workflow** registry entries.

It pairs with the **Chat + Agents** service as the platform's two composition services (ADR-0028 §6): Workflow is the **deterministic** side — cheap, simple, auditable; Chat + Agents is the **interactive / reactive** side — a flexible, costly, non-deterministic *loop* (ADR-0007 §1). The two interoperate and processes **graduate from agent → workflow** as their real-world variations become understood — explore in the agent, lock in as a workflow.

## User guide

### What the user sees and does

- **Author a workflow as Python** — the workflow *is* a Python program (the source of truth), not a DSL; authoring and editing happen in code.
- **Get help authoring from the agent-chat companion** — a guided MAF agent helps write/refine the workflow conversationally, visibly (ADR-0007 §4).
- **Read the flow without authoring it** — a **read-only visual view** shows steps and flow logic only, deliberately omitting variables and data transforms; there is **no editable canvas in v1**.
- **Trigger and schedule** — start a workflow from a trigger (manual, schedule, webhook, connector-event); each schedule declares its own overlap and catch-up policy. Mid-run it pauses on `delay` / `event` / `user_input`.
- **Watch runs and privacy** — runs are observable jobs (progress, cancel); the read-only visual view shows the privacy level of each call, so what gets called, with what, and to whom is always visible.

### Representative use cases

1. **"Send me a monthly report"** (User) — author a workflow that pulls from Document/Knowledge, drafts with a model, and emails via Connectors, scheduled on a cron with an explicit overlap/catch-up policy (ADR-0007 §7).
2. **"React when a webhook fires"** (Builder) — a webhook-triggered pipeline: a family-8 HMAC webhook starts the workflow; a side-effecting step runs under the `Idempotency-Key` so a retry never double-fires (ADR-0007 §8, ADR-0001).
3. **"Handle it when something arrives"** (User) — a **connector-event**-triggered flow (new email, new web result…) runs a pipeline that pauses on `user_input` for a human decision mid-flow (ADR-0007 §7).
4. **"Lock in what I've been doing by hand"** (Builder) — the **agent→workflow graduation**: an automation that started as a flexible agent is formalized into a deterministic, auditable workflow as its variations become understood (ADR-0007 §1).
5. **"Ask me before it publishes"** (Builder) — a run pauses on `user_input`, an async-human-input step, then resumes from its structured history without re-executing completed steps (ADR-0007 §8).

## Reference

### The workflow primitive (ADR-0007 §1/§3)

The **workflow** is the *declarative/deterministic* unit — the counterpoint to the agent loop: a graph of steps, deterministic, not flexible but cheap, simple, auditable. Family 9 `/v1/workflows`, Mistral Studio lifecycle (definition → deployment → run/schedule). **A workflow is a Python program** (the source of truth) — not a declarative DSL; Python is the teachable, debuggable primitive, honoring "Python everywhere."

### The composition primitives (ADR-0007 §3)

The tiny set of *externally-invoking* async Python functions a workflow program uses:

- **`call(...)`** — invoke a service capability; **OpenAPI-first, MCP-fallback** (an MCP-only capability).
- **`model(...)`** — raw model call with **structured output**, no natural-language interface; the Responses API (family 1).
- **`agent(...)`** — run a native (MAF) agent to completion.
- **`subworkflow(...)`** — run another workflow.
- **`delay(...)`** — wait on a timer (duration or until a time).
- **`event(...)`** — wait on an information-system event (webhook, connector event, service event).
- **`user_input(...)`** — wait on a human (input/signal) — the async-human-input run.

**Branch, loop, and transform are not primitives** — they are plain Python control flow (`if`, `for`, dict/list operations). Only the externally-invoking operations are primitives.

### Authoring (ADR-0007 §4)

Primary authoring is **Python code**. An **agent-chat companion** (a MAF agent) helps the non-technical user author/refine the workflow conversationally and visibly. A **read-only visual view** shows steps + flow logic only (no variables/data transforms) as an alternate comprehension surface — anyone can understand the flow without authoring it. **No editable canvas in v1** (Node-RED is not used as a canvas; the view is a lightweight renderer).

### Invocation follows the caller (ADR-0007 §5)

A workflow is deterministic Python → it favors **OpenAPI** for service calls (`call(...)`), the machine-optimized deterministic surface, falling back to **MCP** only where a capability exposes *only* MCP. **`model(...)`** is the **Responses API** (rich, typed, structured outputs) for when there is no natural-language interface — a deterministic structured-output transform. **`agent(...)`** is the natural-language task surface. Deterministic callers get OpenAPI; agents get MCP.

### The agent→workflow graduation path (ADR-0007 §1, ADR-0012 capture routing)

Automation often *starts* as an agent while the problem is poorly understood, and is progressively **formalized into a workflow** as the real-world variations become understood. Agent = explore (flexible, costly); workflow = lock in (deterministic, auditable). The platform supports moving a process from agent to workflow as it matures; captured **exact repeated procedures** route to the Workflow service as their destination (CONTEXT.md *capture routing*).

### Triggers & scheduling (ADR-0007 §7)

A workflow **starts** from a trigger; it **pauses mid-run** on `delay`/`event`/`user_input` — the same vocabulary on both ends. Triggers: **`manual`** (dashboard or authoring chat), **`schedule`** (cron/interval/calendar), **`webhook`** (family 8 HMAC webhook), **`connector-event`** (a connector event — new email, web result, etc.). Nothing more for v1. **Overlap & catch-up policies**: each schedule declares whether an overlapping run is skipped or allowed, and whether a missed tick catches up or is skipped — explicit, user-chosen, no hidden behavior.

### Runs, retries & idempotency (ADR-0007 §7/§8, ADR-0001)

Runs are **family-5 jobs** (queued/running/completed/failed, progress, cancel, webhook on completion) with **per-step retries with backoff**; a failed step can take an explicit on-failure path. A side-effecting step is retried under the base contract's **`Idempotency-Key`** so a retry does not double-fire; the structured history lets the platform **resume without re-executing completed steps**.

### Two-tier run state (ADR-0007 §8)

Native runs (MAF workflows; this is the structured tier) are **structured, replayable, inspectable**: run state lives in the service DB as a sequence of step events (each awaited primitive with inputs, outputs, action context); a run can be replayed, inspected, resumed, and its failure point identified — no black box. Harness-image runs (the agent tier) are **opaque and snapshotted as-is** — the platform persists the harness home, never parses it.

### Registry interplay (ADR-0008)

The **capability registry is the universal name→URL resolver** for composition references (ADR-0007 §9, ADR-0008). Workflows reference capabilities by **explicit, stable names in the Python** — `call("document.parse", ...)` — **no search** (the name is already in the program); the registry resolves name→endpoint at run time. Resolution is **floating** (stable name → current published version) or **pinned** (`workflow.monthly-brief@3`). **Workflows have NO allowlist** — they name tools deterministically in code; access is governed by the workflow's own permissions/action-context, not a registry allowlist (ADR-0008 §5). Authored **`workflow`** entries live in this service and register on **publish only** (discoverable = launchable), named **`workflow.<name>`** (ADR-0008 §8), reserved by the leader core's **name authority**.

### Explicit implementation choice / privacy (ADR-0007 §10)

Every **model-backed step explicitly names the implementation** it uses (local or cloud-gateway), chosen at authoring time (by the author or with the agent-chat assistant's help). **Privacy is a property of the chosen implementation** (labels `local` / `cloud_no_data` / `cloud`) — choosing the implementation *is* the privacy decision. **No inference policy, no automatic cloud fallback**: a refused implementation surfaces and the user re-chooses. The **read-only visual view shows the privacy level of each call**, derived directly from the chosen implementation.

### ADR cross-references

ADR-0001 (family 9 authoring shape; family 5 jobs; family 8 webhook; the base contract's `Idempotency-Key`) · ADR-0002 (callable surfaces) · ADR-0007 (workflow primitive, the composition primitives, authoring + read-only view, invocation-follows-the-caller, the agent→workflow graduation path, triggers & scheduling, runs/retries, the two-tier run state, explicit implementation choice) · ADR-0008 (registry as the name→URL resolver, authored `workflow.<name>` entries, float/pin resolution, no allowlist for workflows, name authority) · ADR-0028 (chapter depth; the two composition services).
