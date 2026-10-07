---
title: The template service — how to use it
keywords:
  - template-service
  - overview
  - capabilities
  - dashboard
mcp-tools: []
---
# The template service — how to use it

## Summary

The template service is the copy-to-start skeleton of a wordslab service: a
set of capabilities exposed through the platform dashboard, all three
callable surfaces (API, agent MCP, UI), and this learning bar. Today it
ships two capabilities, `canary` (the Echo proof capability, ticket #71) and
`placement` (the control-placement checker, ticket #275); a real service
keeps the shell and replaces the capability set.

## Details

1. **Install it like any service** — the platform reads `service.toml`,
   resolves the capabilities, and puts this service's UI hooks in the
   dashboard menu (here: an "Echo" entry). No per-capability wiring.
2. **The dashboard surfaces** — each capability contributes menu entries
   and its own page; this service's own surface is the set of those hooks
   together (nothing else — a service has no page of its own).
3. **Read a capability's page** — the menu entry opens the capability's UI
   (here the Echo page); `service.toml`'s `[<service>.<capability>]` section
   carries its declared api entry point and versions history.
4. **Find the deeper docs** — each capability carries its own four graded
   levels (`docs/capabilities/<capability>/`); this level covers the
   service as a whole.

## See also

- `docs/capabilities/canary/` — the canary capability's own graded docs.
- `docs/capabilities/placement/` — the control-placement checker (a data
  capability: the security model's index + its invariant harness).
- `service.toml` — the declaration: own properties, then one section per
  capability.
- ADR-0002 (the service template) · ADR-0031 (the declaration shape) ·
  ADR-0024 §1 (the learning bar).
