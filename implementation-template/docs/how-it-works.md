---
title: Qwen3 4B — how it works
keywords:
  - qwen3-4b
  - engine
  - weights
mcp-tools: []
---
# Qwen3 4B — how it works

## Summary

An implementation is DATA plus an install recipe: the declaration
describes the parts (here, one local-model part), and the install function
consumes the typed parse result to put the weights and its engine on the
machine.

## Details

- **The declaration** — `implementation.toml` carries the implementation's
  own properties (identity, license, its own code requirements, generic
  dependencies) and one documentation section per content part — here one
  `local-model` part with the weights URL, the artificial-analysis slug
  (the join key for dynamic quality/speed/cost metrics at selection time)
  and its objective facts.
- **The engine dependency** — the `[[dependencies]]` entry names
  `llm.engine`: any implementation of it satisfies (ADR-0031 §4's generic
  rule); the user never installs an engine directly — it comes with the
  model.
- **Install** — the `install/` recipe is the implementation-specific
  installer's input; the parsed declaration (the typed `Implementation`
  object) is its configuration data — no re-parsing.
- **Aggregation** — the requirements the fit gate checks are the
  sum/union of the implementation's own code requirements and its parts'.

## See also

- The `how-to-use` level — install and drive it.
- ADR-0031 §3 (part sections) · ADR-0005 (the fit machinery).
