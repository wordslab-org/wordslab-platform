---
title: The template service — study in depth
keywords:
  - template-service
  - ui-hooks
  - dashboard
  - design
mcp-tools: []
---
# The template service — study in depth

## Summary

Why the service template is shaped this way: a service is a *set of
capabilities*, not a monolith — that is what lets one service ship several
unrelated features, lets a capability be implemented by any number of
swappable implementations, and lets the platform treat UI, API and agent
surfaces as three views of the same capability. The service itself owns
almost nothing: an identity, one requirements figure for its own API + UI
code, and the UI hooks that place its capabilities in the dashboard.

## Details

1. **The UI is the platform's, not the service's** — a capability declares
   *hooks* (menu label + entry point, a UI description, a UI versions
   history); the dashboard integrates them. The service never ships its own
   chrome, so every installed service looks and navigates the same way.
2. **Requirements are layered** — the service declares what its own API + UI
   code needs; each capability implementation selected at install time adds
   its own (weights, engine, database, storage quota) on top. Installing a
   service is therefore a per-implementation decision, not a service-level
   one.
3. **The learning bar is a publish gate, not a boot gate** — a service boots
   and installs with gaps recorded; publishing it as `bundled`/`listed`
   requires the bar (ADR-0018's tiers). That is why the loader discovers and
   records rather than blocks.
4. **One source, dual-consumed** — each graded doc is read by the human
   surface *and* indexed for agents; the canonical section schema and
   front-matter are the contract that makes one file serve both.

## See also

- `docs/service/how-it-works.md` — the pieces, mechanically.
- ADR-0015 (the dashboard) · ADR-0018 (publishing tiers) · ADR-0024 §1
  (the learning bar, one source dual-consumed).
