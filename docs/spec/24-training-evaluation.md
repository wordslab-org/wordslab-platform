# 24 — Training and Evaluation

> **Status:** created at the resolution of wayfinder tickets "Define what evaluation means in the platform" (#16 / ADR-0020) and "Sharpen the Training service design" (#30 / ADR-0025). **Source of truth:** ADR-0020 (evaluation half) + ADR-0025 (training half). This chapter is the **organized build-view** — it cites, never restates. The evaluation half (eval.dataset/simulate/annotate/judge/report, Arize Phoenix) is ADR-0020's; the training half (train.dataset/fine-tune/publish, Trackio, license gates, publish→Inference) is ADR-0025's. *(Chapter numbered 24: ADR-0013/0020 first reserved `22-training.md`, but `22` became Document at #28.)*

## Identity

The **Training and Evaluation service** is the dev-side counterpart to the **Inference service** and the platform's home for **producing, improving, and measuring** models and datasets. It has **two halves**, sharing one service contract and database:

- **Training** — prepare datasets, fine-tune/train models, publish trained models back to Inference. The three model classes (LLM/VLM LoRA, diffusion adapters, classic models) are produced & improved here, notebook-driven, on the builder's machine. *(ADR-0025, #30.)*
- **Evaluation** — systematically measure the quality/behavior of a versioned published artifact. *(ADR-0020, #16.)*

The two are one service because they share the *same raw material* — **datasets** — and the same model-backed substrate: both are **notebook-driven**, both consume the **same dataset-prep / consent boundary**, both ride the **same Inference implementation catalog** for model-backed steps. Training produces/improves; evaluation measures. Neither is centralized (ADR-0003) — both run on the builder machine.

## Part 1 — Use cases (user guide)

### What the user sees and does

- **Preparing a dataset** (Builder view): gather data (import from HF / downloadable sources), version it (tied to a project), and anonymize real usage via the core's filtered+anonymized extraction. The same dataset feeds training and evaluation.
- **Fine-tuning a model** (Builder view): pick an explicit base model from the Inference catalog, pick a `train.dataset`, run a notebook that drives training over MCP/OpenAPI, and watch metrics live in Trackio. The platform's license gate refuses (with a reason) if the base model can't be fine-tuned.
- **Publishing a trained model** (Builder view): a trained adapter or classic model publishes back to **Inference** as a new implementation.
- **Evaluating a published artifact** (Builder view): run the eval pipeline (dataset → simulate → annotate → judge → report) notebook-driven, with the generated annotation UI as the one non-notebook human surface.

### Representative use cases

1. **"Teach my LLM how my family talks about cooking"** (Builder) — a LoRA/QLoRA fine-tune of an open-weights LLM on a text dataset gathered and versioned in `train.dataset`. The builder drives it from a notebook, tracks loss/accuracy in Trackio, and publishes the adapter back to Inference as a new `llm` implementation. Supporting: Development (JupyterLab), Inference (base model + served result), Trackio (metrics). License: the base model's profile must allow fine-tuning (ADR-0022, gate at `train.fine-tune`).
2. **"Fine-tune an image model on my own style photos"** (Builder) — a diffusion adapter (LoRA/DreamBooth-style) on an open-weights SD-model via the ComfyUI bridge; a small adapter that trains on modest hardware. Supporting: Inference (diffusion base), ComfyUI bridge, Trackio.
3. **"Train a small classifier to route my support emails"** (Builder) — fine-tune a classic model / pretrained backbone on a dataset; publish to Inference as an `ml` implementation. Supporting: Inference (`ml` — the classic/pretrained-model capability, ADR-0027), fastai, dataset prep.
4. **"Build an eval dataset and check my published tool is good"** (Builder) — reuse `train.dataset`'s gather/version/anonymize for an `eval.dataset`, then run simulate → annotate → judge → report on a published artifact (ADR-0020). Supporting: eval capabilities, Publishing (versioned artifact + temporary annotation UI).
5. **"Check my fine-tune is legal to use"** (Builder) — the fine-tune surface surfaces the base model's compliance profile as a fact; the platform refuses (with a reason) a no-fine-tune base model, and never allows training on a no-train-on-output model's output. Supporting: ADR-0022 profile, `train.fine-tune` gate.

## Part 2 — Build spec (organized reference + citations)

### The capability surface

**Training half (ADR-0025 §3):**
- **`train.dataset`** — dataset prep shared with evaluation: gather (HF import / downloadable), version (versioned, project-tied), anonymize (real usage only via the core's filtered+anonymized extraction). Feeding both training and evaluation.
- **`train.fine-tune`** — the fine-tune/train operation **on a model** (base model from the Inference catalog + dataset + Trackio metrics); **the ADR-0022 license gate lives here**.
- **`train.publish`** — publish a trained artifact to Inference as a new implementation (a model implementation declared in `implementation.toml`, with its engine dependency — ADR-0027/#32).

**Evaluation half (ADR-0020 §3):**
- **`eval.dataset`** · **`eval.simulate`** · **`eval.annotate`** · **`eval.judge`** · **`eval.report`** — the five-stage pipeline (dataset → simulate → open/axial coding → LLM-as-judge validated against human labels → version comparison + history in the project repo).

### Dataset prep & the data-source boundary (ADR-0025 §5, ADR-0020 §5)

- **Sources** (shared by `train.dataset` / `eval.dataset`): **anonymized core datasets** (the only real-usage path — always filtered + anonymized, no raw-traces path) · **downloaded** (HF etc.) · **synthetic** (grounded on the anonymized data's dimensions: personas + target use-cases + source documents → LLM-generated candidates → human-filtered → versioned).
- **Builder sphere** needs no anonymization (no personal data); **user sphere** reaches Training only via the core's filtered+anonymized extraction.
- The **consent model is #31 (now resolved by ADR-0026)** — Training/Evaluation consume it, never re-implement it.

### Fine-tune shapes per model class (ADR-0025 §6)

- **LLM/VLM LoRA** — LoRA/QLoRA adapter on an open-weights foundation model (VLM adds image input); session shape by reference to ADR-0001 family 9 (Tinker): `base_model` / `method: "lora"` / `rank`, programmatic `forward_backward` / `optim_step` / `save_state` / `load_state` / `sample`, publish → new model.
- **Diffusion adapter** — LoRA/DreamBooth-style adapter via the ComfyUI bridge (research `non-llm-serving.md`).
- **Classic models** — fine-tune a pretrained backbone (or full train, rarer) via fastai; small weights.

### Metrics tracking (ADR-0025 §2)

- **Trackio** (Hugging Face `gradio-app/trackio`, Apache-2.0), **vendored + run locally** as a separate process — SQLite store, no account, no SaaS, wandb-API-compatible (`import trackio as wandb`). The training-side mirror of Arize Phoenix (eval store). Notebook-friendly.

### Model routing & license (ADR-0025 §4, ADR-0022)

- Every model-backed step routes through the **Inference service as an explicit implementation choice** carrying its privacy tier (ADR-0007); no inference policy, no auto-fallback.
- The **license gate lives only at `train.fine-tune`** — explicit user-facing refusal reason, never silent. Dataset prep is allowed to gather (no inference policy). Refused: no-fine-tune base models, training on a no-train-on-output model, fine-tuning a non-open-weights model (can't run locally; cloud-only). Non-open-weights models that *do* run locally stay trainable via run-through-Inference (ADR-0007). The **compliance profile is a fact** surfaced at the fine-tune surface.

### Publish-to-Inference (ADR-0025 §7, → #32)

- A trained artifact (adapter or classic model) **always lands as an Inference implementation** via `train.publish` — the standard implementation path. A trained artifact declares as a **model implementation** (`llm.model` / `diffusion.model` / `ml.model`) in its `implementation.toml`, with its engine dependency (ADR-0027, #32); `models.toml` is retired.

### Human surface (ADR-0025 §2, ADR-0020 §4)

- **Notebook-driven** (Development's JupyterLab) for both halves — MCP/OpenAPI callable surfaces. Training has **no bespoke wizard UI**; evaluation's **generated annotation UI** is its one non-notebook human surface.

### Location & resources (ADR-0025 §8)

- Training/eval run **in the builder's workspace**, bounded by the **resource guardian (ADR-0005)**. The **full job-runner is v1.1**; #30 ships v1 = notebook-driven + dataset APIs + model upload. **Not centralized** (ADR-0003).

### ADR cross-references

ADR-0020 (**evaluation half** — eval.dataset/simulate/annotate/judge/report, Arize Phoenix, annotation UI, consent §5) · **ADR-0025 (this chapter's training half** — train.dataset/fine-tune/publish, Trackio, license gates, publish→Inference) · ADR-0002 (service template, capability pattern, learning bar) · ADR-0005 (resource guardian) · ADR-0007 (composition — explicit implementation choice, no inference policy) · ADR-0022 (model compliance profile — fine-tune/train-on-output gates) · ADR-0024 (learning experience — guided build steers to eval) · ADR-0013 (spec anatomy — chapter numbering). Contract per ADR-0001 (family 9 Tinker training sessions); data residency per ADR-0003/0004; #31 (consent, resolved by ADR-0026) + #32 (implementation declaration, resolved by ADR-0027 — model implementations in `implementation.toml`).
