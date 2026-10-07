---
title: Qwen3 4B — study in depth
keywords:
  - qwen3-4b
  - design
  - facts
mcp-tools: []
---
# Qwen3 4B — study in depth

## Summary

Why the implementation layer looks the way it does: implementations are
the swappable inner world behind a service's stable shell, and everything
comparative is computed at selection time, never declared.

## Details

- **Objective facts only** — no `[ranks]`, no stored `supported`/
  `recommended`: quality/speed/cost comparisons are dynamic
  (artificialanalysis.ai at selection time), so contributors never make
  claims they can't stand behind and benchmark numbers never go stale.
- **Cloud vs local is the part type** — a `cloud-model` part carries a
  provider/model reference and its privacy tier, and consumes no machine;
  a `local-model` part carries weights and requirements. Choosing the
  implementation IS the privacy decision (ADR-0007).
- **Fit is the gate, capacity the lever** — the declared running formula
  (batch/context inputs) is checked at minimum parameters for install;
  a load that doesn't fit proposes lower settings before unloading.

## See also

- The `how-it-works` level — the mechanics.
- ADR-0031 §5 (dynamic metrics) · ADR-0006/0008 (privacy tiers).
