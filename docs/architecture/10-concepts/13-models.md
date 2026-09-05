# Models, inference, and privacy

> **Status:** relocated from `docs/architecture-overview.md` §6 (and the §4.3 capability-vs-implementation material) as part of the architecture restructure (ticket #34, amending the old ADR-0013 spec tree). **Source of truth:** ADR-0006 (inference provider model — the cloud machinery), ADR-0027 (implementation-declaration model — `implementation.toml`, engines and models as implementations), ADR-0002 (the unique model-serving service), ADR-0007 §10 (privacy is a property of the chosen implementation), ADR-0008 (privacy-tier labels). This chapter is the concept view: **where models come from, and the privacy decision that comes with each one.** For the service itself — its identity, its capability surface, its model lifecycle — see **section 30-services/31 (the Inference service chapter)**.

The Inference service is a service in its own right (a full service chapter, 30-services/31). This concept chapter explains the abstraction that gives it its shape: models and the engines that serve them are *implementations*, and the same mechanism reaches local and cloud, which makes privacy a property of the implementation you choose — not a platform routing rule.

---

## The Inference service is the unique model-serving service

**The Inference service is the unique model-serving service.** Every model-backed service rides it over HTTP; multiple instances mean model placement, not a new contract (ADR-0002). Whether a model runs locally or in the cloud, a model-backed service's API and UX are near-identical — because local and cloud are **implementations of the same capability surface**, the choice is an implementation decision, not a different API (ADR-0006).

GPU allocation, inference cost accounting, the one resource budget + resource guardian (ADR-0005), and the single contract surface all remain on the **Inference service**, shared across its capabilities — they are not per-engine (ADR-0027 §5).

---

## Capabilities split into engine and model pairs (ADR-0027)

The Inference service's model-backed paradigm capabilities split into **two distinct capabilities each**, one for the engine and one for the models it serves, each with its own set of `implementation.toml` declarations (ADR-0027 §2):

- **`llm.engine`** / **`llm.model`** (was the `llms` capability)
- **`diffusion.engine`** / **`diffusion.model`** (was the `diffusion` capability)
- **`ml.engine`** / **`ml.model`** (renames the former `classic AI` capability)

These three are the paradigm pairs that have real swappable engines (Ollama / vLLM / sglang for llm; ComfyUI for diffusion; a classic-ML runtime for ml). Task-shaped model capabilities whose model is self-contained (no separate swappable engine) are **single-level** — the model *is* the implementation and carries its own engine — but their detailed naming and structure is deferred to the Inference service's own design, not settled in ADR-0027 (formerly-discussed tts/stt/embeddings live in that deferred set) (ADR-0027 §2).

This sharpening sits on top of the platform's central abstraction (ADR-0002, 0004): a **capability** is *what the platform can do* (e.g. `image.generate`, `llm.chat`, `stt`), with an API that is the union of its implementations' variants; an **implementation** is *one concrete way to do it*, with tradeoffs (size/speed/performance). Implementations declare resource requirements and get downloaded, loaded, and unloaded. **Models are implementations** (ADR-0027, sharpening ADR-0002/0004).

---

## Engines are implementations the user sees but never installs

An engine (Ollama, vLLM, ComfyUI, the cloud gateway) is itself an implementation — one the user sees but never installs or updates directly; it is **pulled automatically as a model's dependency** (ADR-0027 §3).

- **Serving engines are layer-2 implementations** (ADR-0004's layer 2 — install-fit-gated, resource-accounted, versioned as artifacts per ADR-0016 Tier-1), **not** layer-1 service-lifetime software. Rationale: inference engines move fast; tying them to a service's install lifetime would pin the whole service to one engine snapshot. An engine is a replaceable, versioned artifact (ADR-0027 §3).
- An engine implementation belongs to an **engine capability** (`llm.engine`, etc.).
- **A model depends on the engine.** Every model `implementation.toml` declares its engine requirement — the engine capability and a **minimum engine version** (+ required optional features) — using ADR-0016's declared-dependency machinery (per-capability-API minimum version, checked as a satisfy relation). A model will not run without a satisfying engine (ADR-0027 §3).
- **The user sees engine implementations** (they appear in the catalog / UI / impl-picker — nothing hidden, no black box) **but never installs or updates them directly**: they are pulled automatically as dependencies when a model that requires them is installed or updated. An engine with no model depending on it has no reason to be present. This is automation only of the deterministic kind (dependency resolution), and the engine's presence is always visible and removable (ADR-0027 §3).
- **No double install:** an engine is installed once per machine and shared by the models that depend on it (ADR-0027, ADR-0004/0005 shared-path + dedup machinery unchanged).

⚑ *ADR-0004 still textually lists engines as layer-1 substrate; ADR-0027 reversed this (engines are layer 2 — where layer 1 = services/capabilities software only) with only a parenthetical amendment in 0004. Read 0027 as canonical.*

---

## `implementation.toml`: one declaration mechanism

Every implementation — **service, capability, model, engine** — is declared the same way, in **`implementation.toml`**, symmetric with `service.toml`. `models.toml` is **retired as a current file**: a model is an implementation and is declared in its own `implementation.toml`. The per-capability "which implementations exist" aggregate is **derived** from the capability's implementations (and its `supported`/`recommended` are computed, never stored — ADR-0005). `models.toml` appears only as a historical "former name" note in ADR-0002's evolution, never as a current file (ADR-0027 §1).

Two of the model's declaration fields deserve emphasis, because they carry the cloud and privacy story (ADR-0027 §1):

- **`source`** — `local-weights` (→ depends on a local engine) or `cloud:<provider>/<model>` (→ depends on the cloud-gateway engine).
- **`license`** — SPDX; model weights carry the ADR-0022 five-question compliance profile.

The **`/v1/models` lifecycle** (download / load / unload / prepare) is no longer a service-level "engine registry": it becomes the surface over the **model-capability implementations** (`llm.model`, `diffusion.model`, `ml.model`) — an implementation-choice surface. What the user downloads, loads, unloads, prepares is a model implementation; the engine behind it is resolved as its dependency (ADR-0027 §5). A trained artifact (ADR-0025 §7) always publishes as a new Inference model implementation under the standard `implementation.toml` path, carrying its engine dependency like any model; other services' model-backed capabilities (audio, document, …) keep depending on an Inference model implementation (`llm.model` / `ml.model`) (ADR-0027 §6).

---

## Cloud access is the same shape as local

**Cloud access is the same shape as local** (ADR-0006): the **cloud gateway is an engine implementation** (reclassified by ADR-0027) fronting external providers (OpenRouter, OpenAI, Anthropic, …). A **cloud model** is an `llm.model` (etc.) implementation with `source = cloud:<provider>/<model>`, and it depends on the **cloud-gateway engine implementation** (`llm.engine` = the gateway / LiteLLM). The cloud gateway is **not a model** and carries no model of its own — it is the **engine** for cloud models, exactly as Ollama is the engine for local ones. Provider models ride on top as model implementations. Local and cloud therefore use **one uniform declaration mechanism and one dependency rule**; ADR-0006's "cloud access = an implementation of the Inference capability" is preserved by reclassifying the gateway as an engine implementation and the individual cloud models as the model implementations that depend on it (ADR-0027 §4). The cloud-gateway capability installs on the leader machine only (v1, no HA); any machine's model-backed service can call the leader's cloud implementation over the LAN/overlay (ordinary cross-machine routing, ADR-0004) (ADR-0006 §1).

Cloud implementations carry extra concerns beyond a local one: **key management, optional input/output data filtering, usage limits (per unit of time or token cost), privacy guarantees**. These are part of what a cloud-gateway implementation is (ADR-0006 §1). LiteLLM is a swappable engine inside each cloud implementation, not a universal hop — where it is thin (video, MixedBread/LightOn rerank, Nous portal) the capability's cloud implementation routes direct or uses an OpenAI-compatible custom row (ADR-0006 §1). The action-context header is never sent to third-party providers (ADR-0004 §10) — the cloud implementation strips it before the outbound call (ADR-0006 §5).

---

## The provider registry is leader-core configuration

**The provider registry is leader-core configuration** — *add a provider = add a row, not code* — with preconfigured, tested provider cards, bring-your-own-key, and provider bundles (models + tools in one subscription) (ADR-0006 §2/§3). A **provider** is a platform-level resource: `id`, `base_url`, an `api_key` ref into the shared `secrets` vault, enabled modalities, **privacy tier**, and bundle flag. The leader core "knows" the worker machines (for local compute) and the providers (for cloud compute). The **master provider registry lives in the leader core** (a configuration alongside `secrets`/`keys`), one dashboard page to add/edit/remove a provider. Adding a provider = adding a row, not code. The core **distributes the resolved provider set** (rows + the decrypted keys from `secrets`) to the consuming services — the Inference service (model legs) and the Connectors service (bundle tool legs) — at install and on rotation (ADR-0006 §2). The registry is the *specification* of providers; the core distributes it but **never enforces it in the request path** — routing and enforcement stay with the consuming Inference service (ADR-0003 "deliberately NOT centralized") (ADR-0006 §2).

The platform's added value on the provider side is removing the pain of provider quirks: every popular service ships **preconfigured and thoroughly tested** (per-modality quirks, parameter normalization, endpoint shapes baked in) — the user just enters a key into a pre-made card, each template verified against the provider's real current API before shipping. **BYOK** is how users bring existing subscriptions/keys (OpenAI, Anthropic, Google, Meta, Qwen, DeepSeek, Kimi, GLM, HuggingFace, Ollama, Nous portal; fal for image, ElevenLabs for voice, MixedBread/LightOn for embed+rerank); the platform accepts arbitrary keys/endpoints, not just OpenRouter. Adding an arbitrary **OpenAI-compatible endpoint is an advanced feature**, not the normal path (ADR-0006 §3). Validation: one **probe call** runs at add-time so a typo'd key/endpoint fails immediately with a clear "key or endpoint rejected by provider" message — not silently at first real use. Scope: **admin-wide keys in v1** (the admin adds providers; any service/user can use them, subject to per-service caps); per-user keys are deferred — the provider row carries an optional `owner` (empty = shared) so the model leaves room (ADR-0006 §3).

---

## Provider bundles: models + tools, one subscription

A **bundle** (one subscription covering models *and* tools, e.g. the Nous portal) is **one provider row whose legs are tagged by capability**: `{modality: llm}`, `{modality: diffusion}`, `{modality: tool (web search)}`, … Model legs feed the Inference service as **model implementations declared in `implementation.toml`** (`source` = provider ref); **tool legs register as MCP tools in the capability registry and execute via the Connectors service** — the single audited door to the outside world. **One credential covers all legs.** The registry distributes the row to both the Inference service and the Connectors service; each keeps only the legs it owns. The dashboard shows one subscription card (not two entries the user must rejoin), and "what leaves the machine" reports per-subscription across both services (ADR-0006 §4).

> *Vocabulary note:* the tool legs' home is the **Connectors service** — the single audited door to the outside world (web, X, Outlook, YouTube, GitHub, HuggingFace). Provider bundles are why the provider machinery and the connector machinery share one credential vault. *(merged from ADR-0006 §3/#18 and the §8 catalog.)*

---

## Credentials: one shared vault in the core

**Credentials live in the core's `secrets` vault**, distributed at install/rotation. The core's **`secrets` capability is the single master copy for BOTH provider and connector credentials** (ADR-0003). Distribution is **push + pull-on-start** with eventual consistency:

- **Push** on install and on rotation to all currently reachable services (leader's own + workers that are up), and
- **Pull-on-start**: a service (especially on a worker that may have been down during a rotation) pulls the current credential set from the leader's `secrets`/provider registry at service startup before serving; if the leader is unreachable at boot, the service starts on its last cached copy and reconciles on the next successful pull.

This is **not a call-time round-trip** (pull is at boot, not per-request), so it does not violate ADR-0003's "no call-time round-trip". Rotation is expected to be frequent (e.g. monthly GitHub tokens), so eventual consistency (a service may hold a stale key until its next boot) is the honest operating model; a rotated-out key simply fails auth at the provider side, surfaced clearly (ADR-0006 §5). At-rest protection of credential copies is ADR-0020/0021 territory, explicitly not solved here (ADR-0006 §5/#14).

---

## Privacy is a property of the chosen implementation

**Privacy is a property of the chosen implementation** (ADR-0007 §10). Every implementation carries one of **exactly three privacy tiers**, a property of each implementation (model implementation / provider leg), describing where data goes and with what guarantee. The canonical labels platform-wide are **`local` / `cloud_no_data` / `cloud`** (ADR-0008):

1. **`local`** — your own machines: local, *or* a cloud host joined to your **private overlay network** (data never leaves your control; "own machine" = wherever your private network is).
2. **`cloud_no_data`** — a cloud service with **Zero Data Retention** (ZDR / `data_collection: deny`).
3. **`cloud`** — a cloud service with **any other policy** (retention, training, etc.).

The platform **abolished the inference policy** — there is **no `local-then-cloud` routing, no automatic fallback, anywhere**. **Choosing the implementation *is* the privacy decision**, and the **UI warns rather than routes**. The platform does **not** silently auto-route around a tier; its enforcement is **visibility + user decision** — no magic, no black box (ADR-0006 §7, ADR-0007).

The tier is **documented, prominently and everywhere it matters**: on the **API and MCP documentation** for that implementation (prominent), **discoverable** through the API and MCP **description** (so it is machine-readable — surfaced in the capability registry and tool discovery), and **displayed on the UI** when the user uses that service (ADR-0006 §7).

*(Evolution: the privacy tier is a three-tier data-class taxonomy on each implementation, and implementation choice is explicit; the earlier per-service privacy-tier vocabulary (`default`/`no-retention`/`no-training`) and any inference-policy routing are superseded — the inference policy is abolished by ADR-0007, and the tier labels settled on `local` / `cloud_no_data` / `cloud` by ADR-0008.)*

---

## Historical names (evolution notes)

Two ADRs keep their pre-sharpening names as historical record, so reading them needs this key (ADR-0027 / CONTEXT.md are canonical):

- **ADR-0001's** decision text keeps its historical name **"the unique LLM inference service"** — now annotated by an evolution note (recorded in the #33 sweep).
- **ADR-0006's** decision body likewise keeps its pre-0027 capability names (**`llm` / `diffusion` / `classic AI`**) as historical record.
- **`models.toml`** (ADR-0002 as written, and carried into ADR-0003, 0006, 0013, 0022, 0024, 0025, the spec chapters, and CONTEXT.md) is retired in favor of **`implementation.toml`**, kept only as a historical "former name" note (ADR-0027 §1).
- **Engines** were once framed as layer-1 substrate (ADR-0002/0004/0005); ADR-0027 reclassified them as layer-2 implementations and model dependencies (see the ⚑ above).

Read **ADR-0027 / CONTEXT.md** as canonical for all of these.

---

## ADR cross-references

ADR-0001 (base contract; the "unique LLM inference service") · ADR-0002 (capability vs implementation; unique model-serving service) · ADR-0004 (layer 2 = implementations) · ADR-0005 (resource requirements, cloud-spend quota) · ADR-0006 (inference provider model: cloud gateway, provider registry, BYOK, bundles, credentials, privacy tiers) · ADR-0007 §10 (privacy is a property of the chosen implementation; inference policy abolished) · ADR-0008 (privacy-tier labels; capability registry) · ADR-0016 (versioning tiers, declared dependencies) · ADR-0022 (model license compliance profile) · ADR-0025 §7 (trained artifacts as model implementations) · ADR-0027 (`implementation.toml`; engine/model capability pairs).
