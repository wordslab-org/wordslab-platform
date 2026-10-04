---
title: Qwen3 4B — going further
implementation: qwen3-4b
level: going-further
keywords:
  - qwen3-4b
  - implementations
  - training
mcp-tools: []
---
# Qwen3 4B — going further

## Summary

From this skeleton to a real implementation: replace the example parts
with your artifact's, keep the declaration honest, and publish back
through the platform's flows.

## Details

- **Ship a variant** — copy this folder per implementation to
  `services/<service>/implementations/<capability>/<implementation>/`,
  edit `implementation.toml` (identity, license, parts, dependencies) and
  the `install/` recipe; several implementations of one capability are
  swappable at runtime.
- **Bundle parts** — a type may appear several times (an implementation
  bundling several models); requirements aggregate automatically.
- **Train and publish back** — a fine-tune of this model publishes as a
  NEW implementation of the same capability (ADR-0025 §7's
  `train.publish`).
- **Keep the bar** — the four graded docs (this skeleton) and the
  how-an-agent-drives-me skill travel with your implementation; they are
  mandatory to publish (ADR-0018's tiers).

## See also

- `CONTRIBUTING.md` in the service template — the two rituals meeting.
- The `study-in-depth` level — why declarations stay factual.
