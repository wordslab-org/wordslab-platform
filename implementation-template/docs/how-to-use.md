---
title: Qwen3 4B — how to use it
implementation: qwen3-4b
level: how-to-use
keywords:
  - qwen3-4b
  - local-model
  - llm
mcp-tools: []
---
# Qwen3 4B — how to use it

## Summary

This implementation delivers the `llm.model` capability with the Qwen3 4B
weights, quantized Q4_K_M, served locally by its engine dependency —
picked in the model catalog, fit-gated at install.

## Details

1. **Pick it** — in the install/model UI, choose this implementation of
   `llm.model` (the fit gate checks disk/RAM/VRAM and CPU/GPU
   technologies against the machine before it installs).
2. **Call it** — through the parent capability's API: the model rides the
   capability's OpenAPI surface; agents drive it through the auto-
   generated MCP tools at `/mcp`.
3. **Trade off** — smaller siblings install where this doesn't fit; the
   objective facts (parameters, VRAM at load, KV cache) in
   `implementation.toml` feed the fit check and the size ordering.

## See also

- The capability's docs in the parent service (`docs/<capability>/`).
- The `how-it-works` level — what installing this implementation does.
- ADR-0027 (implementations) · ADR-0031 (the declaration shape).
