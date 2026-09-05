# What a service is

A Wordslab installation is a **fleet of machines** (your PCs, possibly a rented cloud box) running a set of components. The central abstraction of the platform is a pair of concepts — *service* and *capability*, and beside them *implementation* — that everything else is built on. **Source of truth:** ADR-0001 (the uniform service contract), ADR-0002 (the service template), ADR-0004 (implementations layer), and ADR-0027 (engine/model capability pairs and `implementation.toml`); this chapter cites those ADRs, never restates them.

*What surrounds the services — the platform core, the bootstrap layer, and the topology of leader and workers — is covered in the next concept chapter.*

## Services: the unit of independence

**Services** are independent, composable components (chat, document, image, inference, …). Each service has **its own database, business logic, UI, and API**, and can run fully standalone — on this machine, another machine, or in the cloud. Services are the **unit of independence; there is no shared monolith** (ADR-0001 §Context).

Because independence is real, a service's own authentication is self-contained: per-service API keys are generated at install and stored and validated by the service itself — no central round-trip. A service therefore works standalone, cross-machine, or in the cloud. There are **no user accounts inside services** — users and authentication are platform-core concerns (ADR-0001, base contract item 2).

## The uniform service contract

The platform's promise is *"all service APIs look alike and share the same concepts."* The contract is a **conformance checklist**: a service is a platform service when it implements the base contract and the families its function requires. Everything not on the list is free — business endpoints, model-specific request bodies, UI, DB, deployment. It is **one base contract applying to every service API, plus nine family contracts that a service opts into according to its function** (ADR-0001 §Decision).

### The base contract (every service API, always)

Every service speaks the same **base contract**: HTTP/1.1 + JSON + SSE, OpenAPI at `/openapi.json`, per-service Bearer keys, `/v1` versioning, one fixed 11-code error taxonomy, cursor pagination, `/health`, optional idempotency, and `usage` on responses (ADR-0001):

- **Transport & self-description** — HTTP/1.1 + JSON only; SSE (`text/event-stream`) for streaming; REST-ish plural kebab-case paths under `/v1/<resource>[/{id}]`; every service exposes its OpenAPI 3.1 doc at `/openapi.json`. No gRPC, no binary, no HTTP/2 requirement. Service identity (name, version, families) is reported by `/health` — no separate manifest.
- **Auth** — `Authorization: Bearer` only, with **per-service API keys** generated at install and stored/validated by the service itself (no central round-trip; a service works standalone, cross-machine, or in the cloud). No user accounts inside services — users/auth are platform-core concerns. `401 authentication_failed` when absent or invalid.
- **Versioning** — the `/v1` path prefix. Additive changes are backward-compatible within a major; breaking changes mean a new major prefix (`/v2`), with the old major kept as long as the service chooses.
- **Errors** — every response carries `X-Request-Id`; error bodies are `{"error": {"type", "message", "resource"?}, "request_id"}`. A **fixed 11-code taxonomy**: 400 `invalid_request` · 401 `authentication_failed` · 403 `permission_denied` · 404 `not_found` · 409 `conflict` · 413 `request_too_large` · 429 `resource_exhausted` (with `resource`: `vram`/`ram`/`disk`/`gpu`/`cloud-spend`…) · 500 `internal_error` · 503 `busy` · 503 `unavailable` · 504 `timeout`. No rate limiting in v1 (429 means resource exhaustion, nothing else), no 422, no per-endpoint error enums.
- **Pagination** — cursor-based only: `?limit` (default 50, max 200) + `?cursor`; responses `{"items": [...], "next_cursor": "<opaque>"}`. No page numbers, no offset; cursors are never parsed by clients.
- **Health** — `GET /health` → `{"status", "service", "version", "resources", "models"?}`, with a status enum from `starting` to `down`, `resources` = used/total per host, and `models` for model-backed services.
- **Idempotency** — an optional `Idempotency-Key` header on mutating endpoints; the service dedupes retries and returns the original result.
- **Usage accounting** — responses from operations that consumed a resource (model inference, tool call, cloud round-trip) carry a `usage` field; the unit is family-defined. Services record usage in their own DB; the core aggregates through service APIs — there is no central usage pipeline.

### Nine opt-in family contracts

On top of the base, nine **opt-in family contracts** copy proven industry shapes by reference: the OpenAI **Responses API** (LLM inference), **stateless MCP** (agent tools), **Realtime/WebRTC** (voice), async jobs + model lifecycle, batch, resumable uploads, HMAC webhooks, and authoring/training sessions (ADR-0001). Where an industry shape is copied by reference, the rule is to follow it and document deviations, pinned to a reference date — rather than force-fitting every implementation into one identical shape. A capability's API is the **union of its implementation variants**: the family contract documents which implementation supports what (a per-implementation support matrix and documented deviations).

### Three callable surfaces

The consequence of the uniform contract: **everything in the platform is callable three ways — human UI, agent MCP, deterministic OpenAPI — and any tool that speaks these industry protocols speaks to Wordslab services without adaptation** (ADR-0001 base item 9, amended by ADR-0002):

- a **human surface** — the service's own workflow-oriented UI;
- an **agent surface** — stateless MCP at `/mcp`, with MCP tools **auto-generated from the OpenAPI spec** by default (zero drift — the MCP surface *is* the API, machine-translated); service authors override with hand-written `@tool` definitions where the machine-optimized API needs an English-friendly interface;
- a **deterministic surface** — the OpenAPI REST API itself.

## The service template

A new service is a **folder copied from `template/`** — **no generator, no SDK** (ADR-0002). Inside, a service is a set of in-process **capabilities**: modules that own their business logic, models, routes, and UI pages while sharing the service's **one contract surface, one auth, one `/health`, one OpenAPI, and one SQLite database** (namespaced tables per capability). MCP tools are **auto-generated from the OpenAPI spec** (zero drift). The **UI stack is vendored FastHTML + Alpine.js — no CDN**, because a home LAN may be offline. The base contract machinery is vendored too — a self-contained contract in `src/<service>/contract/` — so services stay fully independent, with drift caught by a conformance suite; contract changes flow ADR → template → services.

## Capability vs implementation

This pair is the platform's central abstraction (ADR-0002, ADR-0004, sharpened by ADR-0027):

- A **capability** is *what the platform can do* (e.g. `image.generate`, `llm.chat`, `stt`). It has an API that is the **union of its implementations' variants**.
- An **implementation** is *one concrete way to do it*, with tradeoffs (size/speed/performance). Implementations declare **resource requirements** and get downloaded, loaded, and unloaded. **Models are implementations.**

ADR-0027 sharpened the model-backed paradigm capabilities into **engine/model capability pairs**: `llm.engine` + `llm.model`, `diffusion.engine` + `diffusion.model`, `ml.engine` + `ml.model`. An engine (Ollama, vLLM, ComfyUI, the cloud gateway) is itself an implementation — one the user sees but never installs directly; it is pulled automatically as a model's dependency.

Every implementation — **service, capability, model, engine** — is declared the same way, in its own **`implementation.toml`**, symmetric with `service.toml` (ADR-0027). This is the platform's **one declaration mechanism**: a model declares its engine dependency (the engine capability and a minimum version), so local and cloud models ride one uniform rule — the cloud gateway is the engine implementation for cloud models exactly as Ollama is the engine for local ones.

⚑ *ADR-0004 still textually lists engines as layer-1 substrate; ADR-0027 reversed this (engines are layer-2 implementations) with only a parenthetical amendment in 0004. Read ADR-0027 as canonical.*
