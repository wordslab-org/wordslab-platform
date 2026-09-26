# 37 — Development

> **Status:** written at the resolution of wayfinder ticket "Design the Development service chapter (foundational, paired with Publishing & Governance)" (#44). **Source of truth:** ADR-0024 (the guided build process, §3), ADR-0019 (the project, the build→publish thread), ADR-0020 (evaluation — notebook-driven, JupyterLab as the human surface), ADR-0025 (training — notebook-driven, JupyterLab as the human surface), ADR-0008 (registry `skill` entries; AI extensions as clients of the agent service), ADR-0022 (model-license note: model-backed steps route through Inference). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Development service** is the platform's **pro-code + agentic development environment** — the platform's *build surface*. It is where a builder writes, generates, and iterates on the code and configuration that become published things. It pairs with the **Publishing & Governance** service as the platform's **build→publish thread** (ADR-0028 §6): Development produces, Publishing packages/deploys/exposes.

Its capabilities are **code-server** (VS Code + Kilo Code), **JupyterLab**, and the **agentic development workflow** (a UI embodying the modern agentic AI dev workflow — the Matt Pocock engineering skills used to develop the platform's own services). The agentic-development-workflow also **surfaces the guided build process** (ADR-0024 §3).

Development is **not model-backed**: its AI extensions are **clients of the agent service** (via the registry / tool surfaces, ADR-0008), not model-serving itself. It **opens the same workspace directories the agent service manages** — the agent workspace is shared.

## User guide

### What the user sees and does

- **Code in VS Code** — the code-server capability runs VS Code with **Kilo Code** as the embedded agent, in the browser.
- **Work in notebooks** — JupyterLab is the human surface for **notebook-driven** training and evaluation (ADR-0020 §4, ADR-0025 §2): the builder drives the Training-and-Evaluation service's capabilities from a notebook over MCP/OpenAPI.
- **Follow the guided build process** — the **agentic development workflow** surfaces the platform's versioned, first-class skill set (the Matt Pocock engineering skills adapted by the platform) plus a human-readable process guide, so a non-technical learner builds real AI applications step by step (ADR-0024 §3).
- **Work in a project** — a **project** (a GitHub or local repo) is the shared unit of Development and Publishing; at its root sit `platform.toml` and `publish.toml` (ADR-0019 §6).
- **Use the agent workspace** — persistent host directories shared with the agent service; VS Code and JupyterLab open the same directories (CONTEXT *agent workspace*).
- **Publish the result** — the build→publish handoff to the combined **Publishing & Governance** service (chapter 39).

### Representative use cases

1. **"Build a small AI app for my family"** (Builder) — follow the guided build process through the agentic development workflow: the platform-adapted skills (wayfinder, grilling, tdd, code-review…) steer the build, with evaluation designed into the flow (ADR-0024 §3).
2. **"Train and evaluate a model"** (Builder) — drive the Training-and-Evaluation service's capabilities from a **JupyterLab notebook** (the human surface), calling `train.*` / `eval.*` over MCP/OpenAPI (ADR-0020 §4, ADR-0025 §2).
3. **"Develop the platform itself"** (Builder) — use code-server (VS Code + Kilo Code) with the Matt Pocock engineering skills to develop the platform's own services.
4. **"Publish what I built"** (Builder) — hand the result of a development activity to the **Publishing & Governance** service via the **project** (ADR-0019): code (written or generated) or agent/workflow configuration becomes a published thing.

## Reference

### The capabilities (CONTEXT *Development service*)

- **code-server** — VS Code + **Kilo Code** (the code-server-embedded agent), the pro-code surface.
- **JupyterLab** — the notebook surface; the human surface for notebook-driven training and evaluation.
- **agentic development workflow** — a UI embodying the modern agentic AI dev workflow; the surface of the **guided build process** (ADR-0024 §3).

### The guided build process (ADR-0024 §3)

The **agentic development workflow** capability *is* the surface of the **guided build process** — one thing, not two. The guided build is the platform's versioned, first-class skill set for building AI applications: the **Matt Pocock engineering skills** (wayfinder/grilling/tdd/code-review/…) **adapted/whitelabelled by the platform** to call its own capabilities (Inference, evaluation via Training-and-Evaluation/ADR-0020, the agentic-development-workflow), **extended with ML + evaluation best practices** (Shankar/Husain — evaluation designed into the build flow, steering to the eval capability), with a **human-readable process documentation** teaching the process before the learner uses the skills. The skills are platform-vendored as registry `skill` entries (ADR-0008).

### Where the skill set installs — the four coding agents

The guided-build skill set is delivered as **one installed skill-package per coding agent**, in each agent's own config directory. The platform's **preferred coding agents** — the agents embedded in, or paired with, the Development surface — receive it as: **Hermes Agent** → `~/.hermes`, **Kilo Code** → `~/.kilocode`, **Pi** → `~/.pi`, **OpenCode** → `~/.agents`. code-server's embedded agent, **Kilo Code**, is the instance that carries the package in the pro-code surface (`~/.kilocode`). *(This delivery-to-the-four-agents is a standing practice, not an ADR-settled surface; the authoritative source for the skill set's content is the registry `skill` entries of ADR-0008/ADR-0024 §3.)*

### Notebook-driven training & evaluation (ADR-0020 §4, ADR-0025 §2)

JupyterLab is the human surface for both halves of the Training-and-Evaluation service: the builder drives the eval capabilities (`eval.dataset`/`simulate`/`annotate`/`judge`/`report`) and the training capabilities (`train.dataset`/`fine-tune`/`publish`) from a notebook, calling them over MCP/OpenAPI. Evaluation adds a generated annotation UI as its one non-notebook human surface; training is purely notebook-driven (no bespoke training-wizard UI in v1). This is **reference**, not Development content — the capabilities live in the Training-and-Evaluation service (chapter 36).

### The project (ADR-0019 §6)

A **project** is the shared unit of the Development and Publishing services: a **GitHub (or local) repo** backing a unit that can contain all types of publishable artifacts (code or config). At its root: **`platform.toml`** (the project's platform services/implementations, regime 1) and **`publish.toml`** (the project's generic publishable APIs/apps/agents/tools, regime 2).

### The agent workspace (CONTEXT *agent workspace*)

Development **opens the same workspace directories the agent service manages**: the **agent workspace** is a persistent host directory (the durable state of a stateful agent — files, user-installed packages) that survives container destruction and is mountable into a session's container; VS Code and JupyterLab open the same directories. Directory + quota are allocated by the platform core's `resources` capability.

### Not model-backed (CONTEXT *Development service*)

Development is **not model-backed**: its AI extensions (Kilo Code, the agentic-development-workflow's AI assistance) are **clients of the agent service** — they reach models and tools through the agent service / the registry, not by serving models themselves. This distinguishes Development from the Inference and Chat + Agents services. Any model-backed step in the learning experience routes through the **Inference service** as an explicit implementation choice carrying its privacy tier (ADR-0024 §3 consequence; ADR-0022).

### The build→publish handoff (ADR-0019)

Development lets a user create **APIs (OpenAPI)**, **tools (MCP)**, **agents (A2A or chat)**, and **UIs (HTML/HTTP)** by combining platform services. **Publishing is used by Development** to package, deploy, and expose the result of a development activity — code (written or generated) or agent/workflow configuration. The **project** is the shared unit. The publishing surface itself (runtimes, exposure, compliance, registry entries) lives in the **Publishing & Governance** chapter (39) — this chapter hands off, never restates it.

### ADR cross-references

ADR-0024 (the guided build process, §3; the model-license note) · ADR-0019 (the project, the build→publish thread) · ADR-0020 (evaluation — notebook-driven, JupyterLab as the human surface) · ADR-0025 (training — notebook-driven, JupyterLab as the human surface) · ADR-0008 (registry `skill` entries; AI extensions as clients of the agent service) · ADR-0022 (model-license note) · ADR-0028 (chapter depth; Development paired with Publishing & Governance).
