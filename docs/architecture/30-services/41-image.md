# 41 — Image

> **Status:** written at the resolution of wayfinder ticket "Write the four light service chapters (Generation, Image, Audio, Media transformations)" (#45). **Source of truth:** the CONTEXT.md *Image service* glossary entry, ADR-0029 (`diffusion.model` capability name; the Inference capability surface the models ride), ADR-0027 (implementation declarations in `implementation.toml`; a model is an implementation), ADR-0022 (license: commercial-safe defaults vs license-gated models), ADR-0008 (image/video generation as a first-class agent tool, MCP via the registry `tool` entry). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Image service** is the platform's **image-and-video generation surface**, built on **diffusion models**. It generates, edits, and animates images, and generates video — the creative, diffusion-backed face of the platform rather than an LLM surface.

## Capabilities

- **generate** — text-to-image generation (CONTEXT.md *Image service*).
- **edit** — image-to-image / inpainting.
- **video** — asynchronous text/image-to-video generation (ComfyUI behind a thin MIT bridge).
- **Models as `diffusion.model` implementations** — all three ride **`diffusion.model`** capability implementations declared in each model's **`implementation.toml`** (ADR-0029, ADR-0027): **commercial-safe defaults** (FLUX.2-klein-class, Apache) plus **license-gated** models (FLUX-dev, MiniMax H3, SDXL) installable only via **explicit user acknowledgment** (ADR-0022).
- **First-class agent tool** — image/video generation is an MCP-exposed capability that becomes a registry **`tool`** entry (ADR-0008): usable as an agent tool and **integrated into the Chat + Agents UI**, plus its own **standalone gallery / prompt UI**.

## ADR cross-references

ADR-0008 (image/video generation as a capability with an MCP surface → registry `tool` entry) · ADR-0022 (commercial-safe defaults + license-gated models, explicit acknowledgment) · ADR-0027 (a model is an implementation, declared in its own `implementation.toml`) · ADR-0029 (the `diffusion.model` capability name and Inference capability surface). Mostly CONTEXT.md (*Image service* entry).
