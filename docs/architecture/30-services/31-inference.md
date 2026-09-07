# 31 — Inference

> **Status:** written at the resolution of wayfinder ticket "Design the Inference service chapter (and name the task-shaped capabilities: tts/stt/embeddings)" (#35). **Source of truth:** ADR-0027 (engine/model capability pairs, `implementation.toml`, cloud gateway as an engine), ADR-0029 (this service's full capability surface — the task-shaped `*.model` naming, the `models` management capability, multi-instance deployment), ADR-0006 (provider model, billing, privacy tiers), ADR-0005 (resource formulas, load/unload, reservation ledger), ADR-0002 (the unique model-serving service; the service-as-stable-shell), ADR-0001 (family 1/2/5 contract surfaces). This chapter is the **organized build-view** — it cites, never restates. For the concept view — where models come from, and the privacy decision that comes with each — see `10-concepts/13-models.md`.

## Identity

**The Inference service is the platform's unique model-serving service** (ADR-0002): every model-backed service rides it over HTTP. It serves models of every kind the platform manages — LLMs/VLMs, diffusion (image/video), classic ML, speech (STT/TTS), embeddings, and rerank — each through a **model capability**, backed by **engines** that are themselves implementations. It is the model-serving *spine* the platform is built on: the build-order-first service, and the destination a trained model always publishes back to (ADR-0025 §7).

The service is a **stable shell** (ADR-0029 §4, ADR-0002 evolution): its own implementation holds the service UI and the shared contract entry points (`/health`, `/api`/OpenAPI, `/mcp`, one auth) plus the stable declaration of its capability list and each capability's API surface. What is behind the shell — the capabilities present, their model/engine implementations, what's installed where — is the visible, swappable, user-chosen inner world. No black box.

**Multiple instances mean model placement, not a new contract** (ADR-0002). The fleet may run several Inference services on different machines; they are **independent services, not a coordinating cluster** (ADR-0029 §5). Each instance serves the models installed on its machine; where a model is deployed is the catalog + install simulation's job (ADR-0004/0005); the cross-machine "all models" view is a read-only aggregation on the leader core by pull (ADR-0003).

## The capability surface

Inference's capabilities are the model capabilities (each `<task>.model`), the three engine capabilities, and one management capability. Every model capability surfaces its model implementations through the appropriate contract family (ADR-0001); `models` owns the unified lifecycle/catalog and the shared serving machinery (ADR-0029 §3).

| Capability | Kind | What it serves | Family / notes |
|---|---|---|---|
| `llm.model` | model | LLM/VLM models | family 1 Responses API (was `llms`) |
| `diffusion.model` | model | diffusion image/video models | family 2 images/videos (ComfyUI behind a thin MIT bridge) |
| `ml.model` | model | classic / pretrained models (classify/detect/segment/extract/predict) | family 2 predict-style (renames `classic AI`) |
| `stt.model` | model | speech-to-text models | family 2 `/v1/audio/transcriptions` by reference |
| `tts.model` | model | text-to-speech models | family 2 `/v1/audio/speech` by reference |
| `embeddings.model` | model | embedding models | family 2 `/v1/embeddings` by reference |
| `rerank.model` | model | reranking models | family 2 (TEI / mixedbread-style by reference) |
| `llm.engine` | engine | Ollama / vLLM / sglang, or the cloud gateway | swappable engine for `llm.model` |
| `diffusion.engine` | engine | ComfyUI | swappable engine for `diffusion.model` |
| `ml.engine` | engine | classic-ML / PyTorch runtimes (incl. sentence-transformers) | shared runtime for `ml.model` *and* reusable task-shaped runtimes |
| `models` | management | unified model catalog + lifecycle API + the shared serving machinery | family 5; routes by model name |

### Model capabilities are `*.model`; engines are separate only where genuinely swappable

Every model capability is named `<task>.model`, uniformly (ADR-0029 §1). The three **paradigm** model capabilities (`llm.model`/`diffusion.model`/`ml.model`) each own a **dedicated engine capability** (ADR-0027) because each has genuinely user-swappable engines. The **task-shaped** model capabilities — `stt.model`, `tts.model`, `embeddings.model`, `rerank.model` — have **no dedicated engine capability** (ADR-0029 §2): there is no `stt.engine`/`tts.engine`/`embeddings.engine`/`rerank.engine`. Where a task-shaped model shares a reusable runtime it depends on the generic **`ml.engine`** capability — e.g. sentence-transformers is an `ml.engine` implementation shared by several `embeddings.model`/`rerank.model` implementations (no double install, ADR-0004/0005). A self-contained task-shaped model carries its runtime with no engine dependency.

The plain task name (`stt`, `tts`, `embeddings`) is the *feature* capability on the owning consumer service — e.g. the Audio service's `audio.stt`/`audio.tts` feature capabilities wrap the model with real logic (audio framing, VAD, streaming, voice design). Inference names only the **model underneath** such a feature (ADR-0029 §1). Other services' model-backed capabilities depend on an Inference model implementation — `llm.model`/`diffusion.model`/`ml.model`, and now the task-shaped ones — as their substrate (ADR-0027 §6).

### The engine is an implementation the user sees but never installs directly

Engines are **layer-2 implementations** (ADR-0027 §3), not layer-1 service-lifetime software: replaceable, versioned artifacts (ADR-0016 Tier-1), pulled automatically as a model's dependency. A model `implementation.toml` declares its engine requirement — the engine capability and a minimum engine version (+ required optional features) — via ADR-0016's declared-dependency machinery. An engine with no model depending on it has no reason to be present; it is installed once per machine and shared by the models that depend on it (ADR-0027 §3, ADR-0004/0005). The user sees engines in the catalog/impl-picker (nothing hidden) but never installs or updates them directly.

### The cloud gateway is the engine for cloud models

Cloud access is the same shape as local (ADR-0006/0027 §4): the **cloud gateway** (LiteLLM and/or direct provider SDKs, plus a thin platform layer) is an **engine implementation** (`llm.engine`/`diffusion.engine`/`ml.engine`) that fronts external providers and carries no model of its own. A **cloud model** is a model implementation with `source = cloud:<provider>/<model>` that depends on the cloud-gateway engine — exactly as a local model depends on Ollama. Local and cloud use one uniform declaration and dependency rule. The gateway installs on the leader only (v1); any machine's model-backed service calls it over the LAN/overlay (ADR-0006 §1).

## The `models` management capability: lifecycle + the shared machinery

The unified `/v1/models` lifecycle and the shared serving machinery live in the **`models`** management capability (ADR-0029 §3) — because no service API lives outside a capability, the machinery is not free-floating service code.

- **Catalog & status** — `GET /v1/models` and per-model status, an aggregate over the model-capability implementations present on this instance (family 5, ADR-0001). `/health` reports per-model status (ADR-0001 base).
- **Lifecycle routing** — `download` / `load` / `unload` / `delete` / `prepare`; `models` **routes each verb by model name to the model capability that owns that model**. The model capability executes the lifecycle on its own implementations, delegating internally to its engine when it has one.
- **Shared serving machinery** — the **one GPU/resource budget + resource guardian**, load/unload enforcement against the **reservation ledger**, and **inference cost accounting** (ADR-0005). This machinery is shared across all of Inference's capabilities by definition (ADR-0027 §5) and therefore sits in `models`, not per-capability.

Residency is governed by ADR-0005: models book their running formula against measured free RAM/VRAM on load and release on unload; the working set (desired) vs resident (loaded) distinction, the idle sweep, and pressure unloads ask the user when genuinely ambiguous, never auto-evict silently; weights are **cached in RAM** for fast load/unload on demand. When a load can't fit, the platform proposes lower parameters first, then unload, and on refusal returns `429 resource_exhausted` — the user then re-chooses an implementation (e.g. a cloud one) explicitly, with **no automatic inference-policy fallback** (ADR-0005, ADR-0007).

## How a model-backed service or caller uses Inference

A model-backed service (or workflow, agent, or app) reaches Inference over HTTP (ADR-0002). The caller chooses an **explicit implementation** — the model (local or cloud) it wants — and the choice *is* the privacy decision (ADR-0007): every implementation carries one of three privacy tiers (`local`/`cloud_no_data`/`cloud`, ADR-0006/0008), documented prominently and displayed on the UI. The caller routes to the machine whose Inference instance holds its model (ADR-0029 §5). Because local and cloud are implementations of the same capability surface, the API and UX are near-identical either way (ADR-0006 §1).

Provider configuration — preconfigured provider cards, bring-your-own-key, provider bundles (models + tools in one subscription), the shared `secrets` vault, and the two billing modes with the `cloud-spend` red-line — is the provider machinery of ADR-0006, administered on the leader core and distributed (push + pull-on-start) to the consuming Inference instances. See `10-concepts/13-models.md` for that concept view.

## Publish-back from Training

A trained artifact **always publishes back as a new Inference model implementation** via Training's `train.publish` (ADR-0025 §7): an LLM/VLM LoRA or diffusion adapter is an `llm.model`/`diffusion.model` implementation on its base model's engine; a classic model is an `ml.model` implementation; and with the task-shaped capabilities settled (ADR-0029 §1), a fine-tuned STT/TTS, an embedding model, or a reranker can publish as `stt.model`/`tts.model`/`embeddings.model`/`rerank.model` respectively. The published model carries its engine dependency like any model.

## ADR cross-references

ADR-0001 (family 1 Responses API, family 2 other-model inference by reference, family 5 model lifecycle) · ADR-0002 (the unique model-serving service; service-as-stable-shell) · ADR-0003 (model lifecycle not centralized; pull-based read aggregation on leader) · ADR-0004 (deployment = catalog + install simulation; layer-2 engines) · ADR-0005 (resource requirements + running formula, reservation ledger, load/unload policy, resource guardian, cloud-spend quota) · ADR-0006 (provider model: cloud gateway, registry, BYOK, bundles, credentials, two billing modes, three privacy tiers) · ADR-0007 (privacy is a property of the chosen implementation; no inference-policy fallback) · ADR-0008 (privacy-tier labels) · ADR-0016 (versioning tiers; declared dependencies) · ADR-0022 (model license compliance profile) · ADR-0025 §7 (train.publish → new Inference model implementation) · ADR-0027 (engine/model capability pairs; `implementation.toml`; cloud gateway as engine; `/v1/models` as the surface over model implementations) · **ADR-0029 (this chapter's governing ADR — full capability surface, task-shaped naming, `models` management capability, multi-instance deployment)**.
