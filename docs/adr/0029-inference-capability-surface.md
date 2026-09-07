# ADR-0029 — The Inference service capability surface (model capabilities, `models` management, task-shaped naming)

**Status:** accepted (resolution of wayfinder ticket "Design the Inference service chapter (and name the task-shaped capabilities: tts/stt/embeddings)", #35); **settles** the deferred task-shaped capability naming from **ADR-0027 §2**; **adds** the `models` management capability (and places the shared serving machinery inside it) to the Inference service's capability surface begun in **ADR-0027**; **clarifies** the multi-instance deployment story for Inference (ADR-0002's "multiple instances = model placement, not a new contract"); **feeds** CONTEXT.md, the concept chapter `docs/architecture/10-concepts/13-models.md`, and the service chapter `docs/architecture/30-services/31-inference.md`.

> **Amends ADR-0027 §2 in prose only.** ADR-0027 §2 deferred "task-shaped model capabilities whose model is self-contained… their detailed naming and structure is deferred to the Inference service's own design" and described them (in its Considered options) as possibly "single-level — the model *is* the implementation and carries its own engine." This ADR settles that naming. Its decision text is left as its historical record; the current rule is this ADR's. The general service-template framing sharpened here (the service as a stable shell holding capability list + API surface, capabilities wholly behind it) is recorded as an evolution note in **ADR-0002**; this ADR is Inference-scoped.

## Context

Inference is the platform's central service and the build-order-first service (ADR-0028 §3/§6), yet it had no chapter and no dedicated design ADR of its own — its shape was scattered across ADR-0002 (the unique model-serving service), ADR-0006 (provider model, billing, privacy tiers), ADR-0027 (engine/model implementation pairs), ADR-0005 (resource formulas, load/unload, reservation ledger), and the `/v1/models` lifecycle. The capability names it settles gate `implementation.toml` fields and Training's `train.publish` targets (ADR-0025 §7).

Two questions were open when this ticket opened:

1. **Task-shaped capability naming.** ADR-0027 split the paradigm model capabilities into engine/model pairs (`llm.engine`/`llm.model`, `diffusion.*`, `ml.*`) because each has a genuinely swappable engine. It deferred the task-shaped set — tts/stt/embeddings (and rerank) — "to the Inference service's own design." The earlier "single-level vs pair" framing turned out to be the wrong axis: whether a model capability owns a dedicated reusable engine capability is orthogonal to how the model capability is named.
2. **Where the model lifecycle and serving machinery live.** ADR-0001 family 5 and ADR-0002/0027 describe a `/v1/models` lifecycle shared across the model capabilities. Whether that lifecycle is a named capability, service-level infrastructure, or something else was never settled.

The soul governs: **no magic, no black box**, learn-and-understand, automation only when deterministic/obvious, ASK when ambiguous. The service's stable face should be learnable once; what sits behind it should be visible and user-chosen, never hidden.

## Decision

### 1. Every model capability is named `<task>.model`, uniformly

The Inference service names every model capability `<task>.model`. The paradigm pairs keep their names from ADR-0027 — **`llm.model`**, **`diffusion.model`**, **`ml.model`** — and the task-shaped set is named the same way, ending in `.model`:

- **`stt.model`**
- **`tts.model`**
- **`embeddings.model`**
- **`rerank.model`**

The plain task name (`stt`, `tts`, `embeddings`) is reserved for the *feature* capability on the owning consumer service (e.g. the Audio service's `audio.stt`/`audio.tts` feature capabilities), which wraps the model underneath it with real logic (audio framing, VAD, streaming, voice design). Inference names only the **model** — the runnable artifact behind such a feature. A model capability surfaces its model implementations through a family-2 "other model inference" API by reference (ADR-0001 family 2).

A trained artifact (ADR-0025 §7) publishes as a new model implementation under the relevant model capability — now including a task-shaped capability where the trained artifact is a task-shaped model (e.g. a fine-tuned STT or an embedding model), not only the three paradigms.

### 2. `.model` naming is orthogonal to engines; task-shaped models have no dedicated engine capability

Whether a model capability owns a dedicated reusable engine capability is a separate fact from its `.model` naming:

- The **three paradigm** model capabilities each have a **dedicated engine capability**: `llm.engine`, `diffusion.engine`, `ml.engine` (ADR-0027). Their model implementations declare a dependency on the matching engine capability.
- The **task-shaped** model capabilities — `stt.model`, `tts.model`, `embeddings.model`, `rerank.model` — have **no dedicated engine capability of their own**. There is no `stt.engine`, `tts.engine`, `embeddings.engine`, or `rerank.engine`. Where a task-shaped model needs a reusable runtime, it depends on the **generic `ml.engine`** capability — the same capability the `ml.model` paradigm uses. For example, embedding and reranking models commonly share a sentence-transformers runtime: **sentence-transformers is an `ml.engine` implementation** that several `embeddings.model`/`rerank.model` implementations each declare a dependency on and share (no double install — the ADR-0004/0005 dedup machinery); PyTorch-based runtimes similarly ride `ml.engine`. A self-contained task-shaped model (e.g. a lightweight STT whose runtime ships with it) carries its runtime with **no engine dependency**.

So the engine-capability set stays at **three** — `llm.engine`, `diffusion.engine`, `ml.engine` — and the model-capability set is the seven above. This keeps one teachable rule (a model capability is `*.model`; an engine capability exists only where a task class has genuinely swappable engines worth user-visible management), while task-shaped models that share a runtime lean on the generic `ml.engine` rather than proliferating dedicated engine capabilities.

### 3. `models`: the management capability that owns the lifecycle and the shared machinery

Because no service API may live outside a capability (ADR-0002 §"Capabilities (sub-services)": a capability owns its business logic, routes, and UI pages, sharing the service's one contract surface), the `/v1/models` lifecycle and the serving machinery are not free-floating service code — they live in a named management capability:

**`models`** is an Inference service capability. It owns:

- the **unified model catalog & status API** — `GET /v1/models` and per-model status, an aggregate over the model-capability implementations present on this instance;
- the **model lifecycle API** — `download` / `load` / `unload` / `delete` / `prepare`, the family-5 surface (ADR-0001 family 5, ADR-0027 §5); it **routes each lifecycle verb to the model capability that owns the named model**, by model name;
- the **shared serving machinery** — the one GPU/resource budget + resource guardian, load/unload enforcement against the reservation ledger, inference cost accounting (ADR-0005). Because any part of this that needs an API surface must live in a capability, the machinery sits in `models`, not as service-level code.

Each **model capability** (`llm.model`, `stt.model`, `tts.model`, `embeddings.model`, `rerank.model`, `diffusion.model`, `ml.model`) **implements the lifecycle for its own models** (download/load/unload/delete/metrics on the model implementations it owns), delegating internally to its engine capability when it has one. `models` is the unified router/catalog in front; the model capability is what actually executes load/unload of a model implementation.

### 4. The service is a stable shell: capability list + API surface, everything else behind

The Inference service's own implementation (like every service's) is a **stable shell**: it holds the service's UI and the shared contract entry points — `/health`, `/api` (OpenAPI), `/mcp`, one auth — **plus the stable declaration of its capability list and each capability's API description** (the `service.toml` capabilities + per-capability API surface). This shell is the stable face a user learns once and that composition/references resolve against. Everything behind the shell — which capabilities are present, which implementations realize them, which models and engines are installed — is the personalizable, swappable inner world. *(This sharpens ADR-0002's "capability owns routes and UI pages" wording: capabilities own the routes/UI of their own surface; the service's routes/UI above them are the stable shell. Recorded as a general template note in ADR-0002's evolution.)*

### 5. Several Inference instances across the fleet are independent, not a coordinating cluster

The fleet may run several Inference services on different machines (ADR-0002: "optionally several instances… instance choice is model-routing, not contract"). **These instances are independent services, not a coordinated cluster** (Option 2, chosen over Option 1):

- Each machine runs an independent Inference instance serving the models whose implementations were installed there. Its `/v1/models` reports **that instance's** catalog/status; its `/health` reports **that instance's** resources + per-model status (ADR-0001 base). Each instance manages the residency of its own models through its own resource guardian/ledger against its own machine's measured RAM/VRAM (ADR-0005) — model lifecycle is deliberately **not** centralized (ADR-0003 "deliberately NOT centralized").
- **Where a model implementation is deployed** is decided by the existing **catalog + install simulation** (ADR-0004 §5): declared resource requirements (ADR-0005 §4 install-fit) against measured hardware capacity (ADR-0005 §2), **user-confirmed** — not by a runtime coordinator. Deployment uses *declared* requirements + *measured* capacities, deterministic and offline-friendly — not a live cross-instance query.
- **Routing to the right instance** is the caller's job: choose the machine whose Inference instance holds the model it needs (registry name→URL / explicit machine choice). There is no runtime peer-coordination contract between instances.
- **The cross-machine "all models" view** is the **leader core's dashboard/catalog surface**, a **read-only aggregation** built by pull-based monitoring of each machine's `/health` + `/v1/models` (ADR-0003 monitoring, ~30–60 s cadence) — the same pull pattern that already aggregates usage and cost (ADR-0006). It is a *read* view on the leader, not a coordination layer.

Option 1 (the instances coordinate among themselves to place models on the best machine, and `/models` aggregates all machines live) is **rejected**: it invents a runtime scheduling/coordination layer between peers — the automatic, hidden cross-machine behavior the soul forbids, and a contradiction of ADR-0003's "model lifecycle is not centralized." "Multiple instances = model routing" (ADR-0002) is the caller routing to a machine, not the instances federating.

## Considered options

- **Engine/model pairs for the task-shaped set vs uniform `.model` with no dedicated engine.** Giving task-shaped capabilities their own engine capability (`stt.engine`, `embeddings.engine`, …) would either proliferate near-empty engine capabilities or falsely imply user-swappable engines for runtimes that mostly ship with the model. Uniform `*.model` naming (one teachable rule) with task-shaped models leaning on the generic `ml.engine` where they share a runtime keeps the engine set to the three that genuinely have user-visible engine choice.
- **Plain task names (`stt`, `embeddings`) on Inference vs `<task>.model`.** The plain name is the *feature* capability on the owning consumer service (Audio's `audio.stt` wraps the model with logic). Naming the Inference capability `stt` would collide with the feature concept; `stt.model` says precisely "the model underneath the feature," matching the paradigm `llm.model` pattern.
- **`models` as a named management capability vs service-level machinery vs a route on every model capability.** Because no API lives outside a capability, service-level machinery would be unplaceable. Scattering lifecycle verbs onto each model capability loses the single catalog/router face ADR-0001 family 5 describes. A `models` management capability owns the unified catalog+lifecycle+router and the shared machinery — one home for the "one resource budget + guardian" (ADR-0027 §5) that is shared across capabilities by definition.
- **Multi-instance: coordinating cluster (Option 1) vs independent instances (Option 2).** Chosen Option 2 — it follows the settled architecture (independent services ADR-0002/0003; deployment = catalog+simulation ADR-0004/0005; lifecycle not centralized ADR-0003; read aggregation on leader by pull ADR-0003/0006). Option 1's runtime peer-coordination is a hidden scheduler the soul forbids.

## Consequences

- **ADR-0027 §2's "single-level / self-contained" task-capability framing is superseded in prose** (decision text left as historical record). The task-shaped capabilities are `*.model` capabilities named **`stt.model` / `tts.model` / `embeddings.model` / `rerank.model`**, uniform with the paradigm `*.model` capabilities; they have no dedicated engine capability and lean on `ml.engine` where they share a runtime.
- **Inference's full capability set** is now: model capabilities `llm.model` · `diffusion.model` · `ml.model` · `stt.model` · `tts.model` · `embeddings.model` · `rerank.model`; engine capabilities `llm.engine` · `diffusion.engine` · `ml.engine`; management capability **`models`**. The detailed per-capability APIs, engine version lists, and provider registry rows are later Inference-service design.
- **A trained artifact can now publish to a task-shaped model capability** (ADR-0025 §7's `train.publish` target is any Inference model capability, not only the three paradigms).
- **ADR-0002** gains an evolution note recording the service-as-stable-shell refinement (capability list + API surface stable; capabilities wholly behind).
- **Glossary (CONTEXT.md):** the "Inference service" entry is updated to the full capability set incl. `models` + the four task-shaped model capabilities; "Model" and "Capability" entries clarified (service shell vs capability).
- **Concept chapter `docs/architecture/10-concepts/13-models.md`** updated: its task-shaped passage now points at the settled names; the multi-instance independent-instances story added.
- **Service chapter `docs/architecture/30-services/31-inference.md`** written (this ticket's deliverable); README flips 31 to written.

## References / feeds

- Settles: ADR-0027 §2 (deferred task-shaped naming).
- Amends/feeds: ADR-0025 §7 (train.publish target now includes task-shaped model capabilities), ADR-0028 §6 (fills the 31 slot).
- Clarifies: ADR-0002 ("multiple instances = model routing"), ADR-0003 (lifecycle not centralized; read aggregation on leader).
- Sharpens the framing recorded in ADR-0002 (service-as-stable-shell evolution note).
