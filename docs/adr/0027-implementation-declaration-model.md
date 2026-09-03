# ADR-0027 — Implementation-declaration model (engines and models as implementations; `implementation.toml`)

**Status:** accepted (resolution of wayfinder ticket #32, "Clarify the implementation-declaration model: reconcile models.toml vs implementation.toml"); **amends ADR-0002** (the service template's declaration section — one declaration mechanism, `implementation.toml`, for every implementation including models; `models.toml` retired to a historical note), **ADR-0004** (the two-level installation: serving engines are layer-2 *implementations*, not layer-1 service-lifetime software), **ADR-0006** (cloud: a cloud model is an implementation depending on a cloud-gateway engine implementation), and **ADR-0018** (sharpened). **Amended by** — none; supersedes the pre-#32 naming. **Feeds** the map's destination and future Inference-service design.

## Context

The service template's declaration mechanism evolved over three ADRs, leaving two names (`models.toml` vs `implementation.toml`) coexisting inconsistently across the docs:

1. **ADR-0002 (as written)** declared a **per-capability `models.toml`** — the models a capability supports, with `supported`/`recommended` computed from hardware + goal.
2. **ADR-0004** generalized "model" into "**implementation**"; models (llm/vlm weights) became one kind of implementation, declared per capability. Serving **engines** (Ollama, ComfyUI, PyTorch…) were named as **layer-1 software** — installed once per machine.
3. **ADR-0018** formalized a named **`implementation.toml`** per implementation, symmetric with `service.toml`.

The two names coexisted in ADR-0003, 0006, 0013, 0022, 0024, 0025, the spec chapters, and CONTEXT.md. This ADR lands on one unambiguous model: **there is one declaration mechanism (`implementation.toml`); `models.toml` is retired** (kept only as the historical "former name" note in ADR-0002's evolution). In resolving the naming it also settles a structural question the settled ADRs had left implicit: **the relation between serving engines and the models they serve.**

The design is governed by the platform's soul — no magic, no black box, everything visible and human-checkable, home scale. The user should not have to care about inference engines; but nothing is hidden either.

## Decision

### 1. One declaration mechanism: `implementation.toml`

Every implementation — **service, capability, model, engine** — is declared in its own `implementation.toml`, symmetric with `service.toml`. `models.toml` is **retired as a current file**: a model is an implementation and is declared in its own `implementation.toml`. The per-capability "which implementations exist" aggregate is **derived** from the capability's implementations (and its `supported`/`recommended` are computed, never stored — ADR-0005). `models.toml` appears **only** as a historical note in ADR-0002's evolution, never as a current file. The field-level mapping from the old `models.toml` to `implementation.toml` is one-to-one:

| Old `models.toml` content (ADR-0002 as written, ADR-0003, 0006, 0022) | Where it lives now (`implementation.toml`) |
|---|---|
| per-capability model list | per-model `implementation.toml` (a model is an implementation of a model capability) |
| identity / name | `identity` (name, version, description) |
| `source` (local weights, or cloud provider ref) | `source` — `local-weights` (→ depends on a local engine) or `cloud:<provider>/<model>` (→ depends on the cloud-gateway engine) |
| license | `license` (SPDX; model weights carry the ADR-0022 five-question compliance profile) |
| links (release / repo / license / evaluations) | `links` |
| download & disk sizes | resource profile — `disk` at install |
| resource profile (VRAM formula inputs — weights GB, KV cache per token at recommended KV quant, overhead GB, batch/context params; RAM; compute) | resource profile — install + **running formula** (ADR-0005 §1) |
| max-capacity inputs (context length, batch, document size) | `max-capacity` inputs, capped by hardware at load, lowerable by config |
| accuracy & speed ranks within the capability's list | `ranks` (accuracy/speed within the capability's model list) |
| input/output modalities | `modalities` |
| `supported`/`recommended` (computed, never stored) | still computed from hardware + goal — never in the file |
| — (engines were implicit/layer-1) | a **declared engine dependency** (family + min version) on the model's `implementation.toml` |

### 2. Capabilities split into engine and model capabilities

The Inference service's model-backed paradigm capabilities split into **two distinct capabilities each**, one for the engine and one for the models it serves, each with its own set of `implementation.toml` declarations:

- **`llm.engine`** / **`llm.model`** (was the `llms` capability)
- **`diffusion.engine`** / **`diffusion.model`** (was the `diffusion` capability)
- **`ml.engine`** / **`ml.model`** (renames the former `classic AI` capability)

These three are the paradigm pairs that have real swappable engines (Ollama / vLLM / sglang for llm; ComfyUI for diffusion; a classic-ML runtime for ml).

Task-shaped model capabilities whose model is self-contained (no separate swappable engine) are **single-level** — the model *is* the implementation and carries its own engine — but their detailed naming and structure is **deferred to the Inference service's own design**, not settled here. (Formerly-discussed tts/stt/embeddings live in that deferred set; #32 does not name them.)

### 3. The engine is an implementation (layer 2), a dependency of the model

- **Serving engines are layer-2 implementations** (ADR-0004's layer 2 — install-fit-gated, resource-accounted, versioned as artifacts per ADR-0016 Tier-1), **not** layer-1 service-lifetime software. This reverses the ADR-0002/0004/0005 framing that named Ollama/ComfyUI/PyTorch as layer-1 substrate. Rationale: inference engines move fast; tying them to a service's install lifetime would pin the whole service to one engine snapshot. An engine is a replaceable, versioned artifact.
- An engine implementation belongs to an **engine capability** (`llm.engine`, etc.).
- **A model depends on the engine.** Every model `implementation.toml` declares its engine requirement — the engine capability (`llm.engine`, …) and a **minimum engine version** (+ required optional features) — using ADR-0016's already-settled **declared-dependency** machinery (per-capability-API minimum version, checked as a satisfy relation). A model will not run without a satisfying engine.
- **The user sees engine implementations** (they appear in the catalog / UI / impl-picker — nothing hidden, no black box) **but never installs or updates them directly**: they are **pulled automatically as dependencies** when a model that requires them is installed or updated. An engine with no model depending on it has no reason to be present. This is automation only of the deterministic kind (dependency resolution), and the engine's presence is always visible and removable.

### 4. Cloud models ride the same mechanism

A **cloud model** is an `llm.model` (etc.) implementation with `source = cloud:<provider>/<model>`, and it depends on the **cloud-gateway engine implementation** (`llm.engine` = the gateway / LiteLLM). The cloud gateway is **not a model** and carries no model of its own — it is the **engine** for cloud models, exactly as Ollama is the engine for local ones. Provider models ride on top as model implementations. Local and cloud therefore use **one uniform declaration mechanism and one dependency rule**; ADR-0006's "cloud access = an implementation of the Inference capability" is preserved by reclassifying the gateway as an engine implementation and the individual cloud models as the model implementations that depend on it. ADR-0006's provider registry / bundles machinery (one provider row, one credential) still holds — a bundle's provider models surface as model implementations under that provider.

### 5. Shared, service-level machinery (unchanged)

GPU allocation, inference cost accounting, the **one resource budget + resource guardian** (ADR-0005), and the single contract surface all remain on the **Inference service**, shared across its capabilities — they are not per-engine. The **`/v1/models` lifecycle** (download / load / unload / prepare) is no longer a service-level "engine registry": it becomes the surface over the **model-capability implementations** (`llm.model`, `diffusion.model`, `ml.model`) — an implementation-choice surface. What the user downloads, loads, unloads, prepares is a model implementation; the engine behind it is resolved as its dependency.

### 6. Trained models and task capabilities

A trained artifact (ADR-0025 §7) **always publishes as a new Inference model implementation** (`llm.model`, `diffusion.model`, or `ml.model`) under the standard `implementation.toml` path, carrying its engine dependency like any model. This resolves the #32 forward reference in ADR-0025. Other services' model-backed capabilities (audio, document, …) keep depending on an Inference model implementation (`llm.model` / `ml.model`); their structure is not re-examined here.

## Considered options

- **`models.toml` retired vs kept alongside `implementation.toml`** — retired: models are one kind of implementation, so keeping a parallel `models.toml` would split one teachable rule into two declaration mechanisms. A per-capability aggregate is derived, not a separate file.
- **Engine as layer-1 substrate vs layer-2 implementation** — layer-2: engines move fast and are versioned artifacts; tying them to service lifetime pins the service to one engine snapshot and hides an installable/updatable thing. Layer-2 also makes the engine a model dependency (auto-installed, never user-managed), satisfying "user doesn't care about the engine" without hiding it.
- **Single-level model capabilities vs engine/model split for task capabilities (tts etc.)** — single-level for task-shaped models (self-contained, no swappable engine); deferred naming. Not settled here.
- **Cloud gateway as a competing model implementation vs as the cloud engine** — as the engine: one uniform rule (every model depends on an engine, local or cloud), no special case, ADR-0006's gateway-as-implementation reclassified cleanly.

## Consequences

- **`models.toml` is retired** everywhere as a current file — ADRs 0003, 0006, 0013, 0022, 0024, 0025, the spec chapters, and CONTEXT.md are swept to `implementation.toml`, keeping `models.toml` only as the historical "former name" note in ADR-0002's evolution.
- **ADR-0002 §5** (template declaration) is rewritten: one declaration mechanism, engines + models both `implementation.toml`, model → engine dependency.
- **ADR-0004's two-layer installation** is amended: engines are layer-2 implementations, not layer-1 substrate. Layer-1 = services/capabilities software only.
- **ADR-0006** is reconciled: the cloud gateway is the engine implementation; provider models are model implementations depending on it.
- **ADR-0025 §7** forward reference is resolved: a trained artifact is a new model implementation.
- **The Inference service's capability set** is now `llm.engine`/`llm.model`, `diffusion.engine`/`diffusion.model`, `ml.engine`/`ml.model` (+ deferred task capabilities). The detailed per-capability APIs, cloud registry rows, and engine version lists are **later Inference-service design**, not this ticket.
- **Glossary (CONTEXT.md):** `models.toml` retires; engine implementation, model implementation, cloud-gateway engine, `llm.model`/`llm.engine` etc. clarified.
- **No double install:** an engine is installed once per machine and shared by the models that depend on it (ADR-0004/0005's shared-path + dedup machinery unchanged).

## References / feeds

- Amends: ADR-0002 (§5 declaration), ADR-0004 (§2/§3 two-layer), ADR-0006 (§1 cloud-as-implementation), ADR-0018 (sharpened), ADR-0013 (level-C reference → `implementation.toml`), ADR-0025 (§7 forward ref resolved).
- Supersedes the stale naming in: ADR-0003, ADR-0006, ADR-0013, ADR-0022, ADR-0024.
- Feeds: the map's destination; future Inference-service design (the detailed capability/impl surface).
