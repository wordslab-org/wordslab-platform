# ADR-0025 — Training half of the Training and Evaluation service

**Status:** accepted (resolution of wayfinder ticket "Sharpen the Training service design", #30); **creates** the Training and Evaluation spec chapter `docs/spec/24-training-evaluation.md`; **resolves** the chapter deferred by ADR-0020 §"Deferred chapter"; **amends** the chapter-number reference recorded in ADR-0013/0020 (`22-training.md` → `24-training-evaluation.md`, `22` being taken by Document at #28); **consumes** the data-consent-and-handling model (its own graduated ticket, #31 — **now resolved by ADR-0026**) and the model compliance profile (ADR-0022); **references** #32 (implementation-declaration reconciliation — **now resolved by ADR-0027**: a trained artifact declares as a model implementation in `implementation.toml`); **feeds** the map's destination.

## Context

The Training service was renamed **Training and Evaluation** by ADR-0013 §6, and ADR-0020 (from #16) settled the **evaluation** half: five sibling capabilities (`eval.dataset` · `eval.simulate` · `eval.annotate` · `eval.judge` · `eval.report`), notebook-driven, Arize Phoenix as the vendored+local eval store. ADR-0020 explicitly **deferred the spec chapter** pending the Training grilling. This ticket (#30) settles the **training half** — the training & fine-tuning capabilities, dataset prep, and how a trained model publishes back to the Inference service — and with it fills the whole Training and Evaluation chapter.

The soul shapes every decision, as it did for evaluation: **no magic, no black box** — training is a builder-driven, notebook-centric, visible activity where every model-backed step is an explicit implementation choice and every result is human-checked before it matters. Home scale is the deliberate inverse of enterprise MLOps (no job orchestrators, no labeling workforce, no experiment-tracking SaaS).

The settled shape it must design on (not re-derived): v1 = **notebook-driven + dataset APIs + model upload**, full job-runner deferred to v1.1 (existing catalog-scope shape, ADR-0001/0002, CONTEXT "Training and Evaluation service"). Training = the dev-side counterpart to the Inference service: train/fine-tune/evaluate all three model classes (LLM LoRA, diffusion adapters, classic models), dataset prep, publish trained models → Inference service.

## Decision

### 1. What training is

**Training** is the dev-side counterpart to the **Inference service**: preparing datasets, fine-tuning or training models, and publishing the result back to Inference — an on-demand, builder-run activity on the builder's own machine. Where Inference *serves* models (prod), Training *produces* and *improves* them. Training is the third of the three model-backed capabilities exercised through the Inference implementation catalog, alongside inference and evaluation.

- **Where it appears:** the **Builder view** of the dashboard, launched via **notebooks** (the Development service's JupyterLab). Notebooks are the **human surface** — as they are for evaluation (ADR-0020 §4).
- **How minimal:** entirely home-scale — a single builder, on their own machine, in an evening. A LoRA adapter or classic-model fine-tune trains on modest hardware bounded by the resource guardian (ADR-0005). No enterprise job runner, no MLOps platform, no experiment SaaS.
- **Full job-runner** (scheduled / managed training jobs) is **deferred to v1.1**. v1 is catalog-scope: notebook-driven + dataset APIs + model upload.

Training is **deliberately NOT centralized** (ADR-0003) — it lives in the Training and Evaluation service on the builder's machine, not the core.

### 2. The human surface & where trained artifacts live

- **No bespoke training wizard UI.** The human surface is the **notebook** (the Development service's JupyterLab), exactly as for evaluation. The builder drives training from a notebook that calls the service's capabilities over MCP/OpenAPI. There is **no training-wizard web UI in v1**.
- Difference from evaluation: evaluation adds a generated, task-specific **annotation UI** as its one non-notebook human surface (ADR-0020 §3); **training adds no such human surface — it is purely notebook-driven**.
- **Where trained artifacts and datasets live:** **HuggingFace repos** (the preferred home for medium/large model weights and datasets — far better suited than GitHub for large binary artifacts) **or the local workspace** (the project / a data location). For small artifacts the local workspace suffices; for weights/datasets that outgrow it, the builder pushes to a HF repo (in the builder sphere — see §5).
- **Metrics tracking during training: Trackio** (Hugging Face `gradio-app/trackio`, Apache-2.0) — **vendored and run locally** as a separate process, the training-side mirror of Arize Phoenix for evaluation. It is **local-first** (SQLite store, no account, no SaaS), **lightweight**, notebook-friendly, and **wandb-API-compatible** (`import trackio as wandb`), which is teachable and lets learners transfer skills. It was chosen for being an *alive, most-popular* open-source local alternative to W&B: the panel vetoed **Aim** as stale (last release >1 yr old); **MLflow** was the robust standard but a heavier full-MLOps suite. Trackio fits the soul (SQLite-everywhere, local-first, no black box) and the HF model/dataset ecosystem. As Apache-2.0 vendored **as a separate process** (like Phoenix, ComfyUI), it keeps the bundled repo Apache-2.0 (ADR-0022).

### 3. The capability decomposition

Training is several distinct tools, so — like evaluation (ADR-0020) — it is **sibling capabilities** of the Training and Evaluation service (ADR-0002 in-process capability pattern), each with its own business logic, routes, and UI pages, sharing the service's contract surfaces and database. The training half's capabilities:

- **`train.dataset`** — dataset prep, shared with evaluation: **gather** (import from HF / downloadable sources), **version** (versioned datasets tied to a project), and **anonymize** (real-usage data anonymized before it enters a dataset). Feeds **both training and evaluation**. See §5.
- **`train.fine-tune`** — the fine-tune/train operation **on a model**: an explicit base model (from the Inference implementation catalog) + a dataset + tracked metrics. The ADR-0022 license gate lives here. See §4/§6.
- **`train.publish`** — publish a trained artifact back to the Inference service as a **new implementation** of the relevant capability. See §7.

The distinction from evaluation's capabilities: `eval.*` *measure* a versioned published artifact; `train.*` *produce or improve* models and datasets. Dataset prep (`train.dataset`) is the shared gather/version/anonymize surface both halves consume.

### 4. The license gates — only at the fine-tune step

The **model compliance profile** (ADR-0022 §3) is given; this ticket owns *where* Training enforces the terms, not the terms. Per the settled decision, the **gate lives only at the fine-tune step**, returning an explicit user-facing refusal reason (never a silent drop). **Dataset preparation is allowed to gather** — it does not pre-judge what the gathered data might be used for (which would be an inference policy, against ADR-0007, and would break dataset prep's reuse across training and evaluation).

- **At `train.fine-tune`**, the platform **refuses** (with a clear, user-facing reason) when the base model's profile forbids the action:
  - **No fine-tuning a model that forbids it** (profile question 5).
  - **No training / synthetic-data generation on a no-train-on-output model** (profile question 4) — enforced here because dataset prep is allowed to gather, but the *train step against such a model* is blocked.
  - **Non-open-weights models cannot run locally** — they cannot be fine-tuned locally; they are reachable only as cloud implementations whose terms are part of the same profile.
- **Non-open-weights models that *do* run locally stay trainable** via the explicit run-through-Inference choice (ADR-0007) — the platform hard-blocks nothing the ADR allows.
- The profile is a **compliance fact** surfaced with each base model at the fine-tune surface — the user always sees the terms they are building on, no black box.
- Anything *not* forbidden is permitted (subject to display-the-model-name where required, question 3).

This placement is deliberately narrow and simple: dataset prep stays a neutral, reusable gather/version/anonymize surface; the single refusal point is the moment the platform actually *creates a trained model*.

### 5. Dataset prep & the data-source boundary

`train.dataset` (shared with evaluation via the same data-consent model) **gathers, versions, and anonymizes** data, feeding **both training and evaluation**. The load-bearing boundary (settled by ADR-0020 §5 and assumed by #31):

- **Real-usage data reaches Training ONLY as anonymized datasets** from the core's `datasets` capability / log-extraction — **no raw-traces path**. A builder/admin never receives un-filtered, un-anonymized real usage.
- **Synthetic data** is grounded on those anonymized dimensions (personas + target use-cases + source documents → LLM-generated candidates → human-filtered → versioned dataset).
- **Builder sphere** (simulated interactions / builder-injected data) runs as the builder identity — **no filter/anonymize needed** (ADR-0021 #22: the builder sphere holds no personal data; builder traces need no anonymization).
- **User sphere** reaches Training **only** via the core's filtered+anonymized extraction — never raw.
- The **consent model itself is #31 (now resolved by ADR-0026)** — Training *consumes* the settled attribution; it does not design the consent rules.

So `train.dataset`'s sources mirror `eval.dataset`'s (ADR-0020 §5): **anonymized core datasets** (the only real-usage path) · **downloaded** (HF etc.) · **synthetic** (grounded on the anonymized data's dimensions). Training consumes **builder-sphere and anonymized real data only**; trained artifacts are builder-sphere artifacts (§2) — which is why they can live in HF repos or the workspace without anonymization: no personal data ever entered training.

### 6. The fine-tune shapes per model class

Fine-tune is an **operation ON a model** — the third model-backed capability alongside inference and evaluation, exercising the same Inference implementation catalog. The three model classes map to distinct shapes:

- **LLM / VLM LoRA** — parameter-efficient fine-tune of an open-weights foundation model **via LoRA/QLoRA adapters** on a text (and, for VLM, image+text) dataset; the result is a small **LoRA adapter**, not a full re-train — it trains on modest hardware. The session shape follows the settled contract (ADR-0001 family 9, Tinker API by reference): training *sessions* (`base_model`, `method: "lora"`, `rank`), programmatic steps (`forward_backward`, `optim_step`, `save_state`/`load_state`, `sample`), publish weights → new model. LLM and VLM are the same LoRA mechanism; a VLM adds image input alongside text.
- **Diffusion adapter** — fine-tune of an open-weights diffusion/Stable-Diffusion model, typically via a small adapter (LoRA / DreamBooth-style); the result is an **adapter**. Engineered through the ComfyUI bridge already settled for diffusion inference (research `non-llm-serving.md`; ComfyUI behind a thin MIT bridge, ADR-0022/0017).
- **Classic models** — often **fine-tuning a pretrained model/backbone** rather than full from-scratch training (full training the rarer case); the result is the **small model weights** (classifier / regressor / embedding), fitting easily in a HF repo. The fastai approach (from the catalog-scope shape, CONTEXT "Training and Evaluation service") fits most classic-model fine-tunes.

Common to all three: an explicit **source base model** chosen from the Inference implementation catalog, a **dataset** from `train.dataset`, and **metrics tracked in Trackio**.

### 7. Publish trained models → Inference (the #32 boundary)

A trained model **always publishes back as a new implementation of the relevant Inference capability** — via `train.publish`:

- An **LLM/VLM LoRA or diffusion adapter** on a base model → the published artifact is an **implementation of Inference** (a served endpoint wrapping base-model + adapter).
- A **classic model** (classifier / regressor / embedding) → also an **implementation of Inference**, for the capability that covers such outputs.

So a trained artifact always lands as an **Inference implementation** under the standard implementation path (`implementation.toml`). The reconciliation of `implementation.toml` vs `models.toml` is **resolved by #32 (ADR-0027)**: a trained artifact is declared as a new **model implementation** (`llm.model` / `diffusion.model` / `ml.model`) in its `implementation.toml`, carrying its **engine dependency** like any model — an LLM/VLM LoRA or diffusion adapter is a `llm.model`/`diffusion.model` implementation on its base model's engine (min version), and a classic model is an `ml.model` implementation. `models.toml` is retired. `train.publish` records the publish target (the model capability) and the engine dependency; the precise declaration syntax is the standard `implementation.toml` shape (ADR-0002 §5, ADR-0027).

### 8. Training location & the v1.1 job-runner boundary

Fine-tune/train runs **in the builder's workspace** — a builder-space operation in the Training and Evaluation service, not a separate hosting service. The **resource guardian (ADR-0005)** bounds memory/GPU during training; a LoRA adapter trains on modest hardware. The **full job-runner** (scheduled / managed training jobs — a job queue making training a first-class managed job with a schedule) is **deferred to v1.1**. #30's v1 chapter ships the catalog-scope, notebook-driven + dataset APIs + model-upload shape.

### 9. Training and Evaluation as one service

The two halves share the service's contract surfaces and database. Training composes with evaluation without conflict — both are **notebook-driven**, both consume the **same dataset prep / consent boundary**, both ride the **same Inference implementation catalog** for model-backed steps, and both are **not centralized** (train like eval runs on the builder machine). The evaluation half is fully settled by ADR-0020; this ADR is the training half; the chapter `24-training-evaluation.md` assembles both into one coherent build-view.

## Deferred chapter

Per ADR-0013 §6/§7 (the maintenance loop), this resolution creates the consuming spec chapter **`docs/spec/24-training-evaluation.md`** (the Training and Evaluation chapter) in the same commit, resolving the deferral recorded by ADR-0020 §"Deferred chapter". The chapter covers the **whole** Training and Evaluation service — Training half (this ADR) + Evaluation half (ADR-0020) — as the organized build-view.

**Chapter-number amendment.** ADR-0013 §6 and ADR-0020 §"Deferred chapter" named the chapter `docs/spec/22-training.md`. `22` was subsequently taken by **`22-document.md`** at #28 (Document/Knowledge sharpening). The Training and Evaluation chapter therefore lands at **`24-training-evaluation.md`**, a free number in the service range, consistent with the existing non-contiguous numbering (22-document, 25-knowledge, 33-publishing-governance). This ADR records the renumbering; references to `22-training.md` as the Training and Evaluation chapter are superseded by `24-training-evaluation.md`.

**Feeds spec chapter `docs/spec/24-training-evaluation.md` (Training and Evaluation) — filled at this ticket's resolution.**

## Graduated tickets (consumed, not resolved)

- **#31 — "Design the data consent & handling / GDPR-aware usage-data model"** — the data-consent-and-handling model Training consumes (§5). #31 is now **resolved by ADR-0026**; Training follows its boundary, does not re-implement it.
- **#32 — "Clarify the implementation-declaration model: reconcile models.toml vs implementation.toml"** — how a trained model (an Inference implementation) is *declared*. #32 is **resolved by ADR-0027**: a trained artifact publishes as a model implementation (`llm.model` / `diffusion.model` / `ml.model`) in `implementation.toml`, with its engine dependency.

## Reference documents

- **ADR-0020** (evaluation half of this service; dataset-consent §5; deferred chapter). **ADR-0022** (model compliance profile — license gates). **ADR-0001** (contract — family 9 Tinker-by-reference training sessions). **ADR-0005** (resource management — resource guardian). **ADR-0007** (composition — explicit implementation choice, no inference policy). **ADR-0013** (spec anatomy — chapter numbering). **ADR-0024** (learning experience — guided build steers to eval). **#31** (resolved by ADR-0026) / **#32** (resolved by ADR-0027). Research: `research/non-llm-serving.md` (diffusion serving / ComfyUI bridge). CONTEXT "Training and Evaluation service".

## Considered options

- **A training-wizard UI vs notebook-driven** — a bespoke training UI fights the settled notebook-driven v1 shape and adds a second human surface; evaluation's sole non-notebook surface (the annotation UI) is a special case of a HITL review step, not parallel for training. Chose **notebook-driven, no bespoke training UI** (§2).
- **Aim vs MLflow vs Trackio for metrics tracking** — Aim was the soul-aligned choice but was vetoed as stale (last release >1 yr old); the user asked for an alive, most-popular tool. MLflow is the robust standard (Linux Foundation, local-file-store at home scale) but a heavier full-MLOps suite. Trackio (Hugging Face, Apache-2.0) is alive, local-first (SQLite, no account), lightweight, wandb-API-compatible (teachable), and fits SQLite-everywhere + the HF model/dataset ecosystem. Chose **Trackio, vendored + local** (§2).
- **License gates at dataset-prep AND fine-tune vs only at fine-tune** — gating at dataset-prep makes prep pre-judge what gathered data is for (an inference policy, ADR-0007) and breaks prep's reuse across training and evaluation. Chose the **narrow single gate at fine-tune only**, each with an explicit user-facing refusal reason (§4).
- **Fine-tune as a model-backed capability vs a separate system** — a trained model is served through Inference and exercises the explicit implementation choice; chose **fine-tune as an operation ON a model** through the Inference catalog (§6).
- **Full model re-train vs parameter-efficient adapters** — home scale + modest hardware favor adapters. LLM/VLM LoRA and diffusion adapters by default; classic fine-tunes of pretrained backbones (§6).
- **Publish to Inference as a new implementation vs a separate trained-model registry vs a models.toml override** — a trained artifact serves through Inference, so it is an *implementation* of the relevant model capability; the declaration relationship of models.toml/implementation.toml is resolved by #32/ADR-0027 (models.toml retired; trained artifact = a model implementation in `implementation.toml`).

## Consequences

- **Creates ADR-0025** — the training half of the Training and Evaluation service.
- **Creates** the spec chapter `docs/spec/24-training-evaluation.md` — the whole Training and Evaluation chapter (training + evaluation), resolving ADR-0020's deferred chapter.
- **Amends** the chapter-number reference (ADR-0013 §6, ADR-0020 §"Deferred chapter": `22-training.md` → `24-training-evaluation.md`) — `22` being Document.
- **Consumes** (not resolves) the data-consent model (#31) and the implementation-declaration reconciliation (#32 — now resolved by ADR-0027).
- **Glossary (CONTEXT.md):** add training, fine-tune, dataset prep, Trackio; update the Training and Evaluation gloss to the settled shape; mark #30 resolved.
- **Feeds** the dashboard (Builder-view training surface via notebooks), Development (notebook-driven JupyterLab), Inference (#32 — a trained model publishes as a model implementation), and the new chapter.
- **References, does not resolve:** the data-consent model (#31 — now resolved by ADR-0026); the implementation declaration (models.toml vs implementation.toml, #32 — now resolved by ADR-0027); eval (ADR-0020, settled); license (ADR-0022, settled).