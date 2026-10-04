---
title: Echo — how to use it
capability: canary
level: how-to-use
keywords:
  - echo
  - canary
  - consent
mcp-tools: []
---
# Echo — how to use it

## Summary

Echo is the service template's proof capability (ticket #71): it bounces
your text back through all three callable surfaces — the API, the agent
MCP surface, and the Echo page — and records every interaction behind the
consent flag (ADR-0026 §1).

## Details

1. **The page** — open the Echo page, type text, press Echo. The form
   carries the visible "private/secret — do not use" consent toggle; leave
   it off to let the interaction count as improvement data.
2. **The API** — `POST /v1/echo` with `{"text": "...", "consent":
   "may_use"}` (or `"private_secret"`); the response echoes the text back.
3. **From an agent** — the same operation is auto-generated as an MCP tool
   at `/mcp` (stateless JSON-RPC 2.0, per-request Bearer key); the MCP
   surface *is* the API, zero drift.
4. **The record** — `GET /v1/echo/extract` returns the recorded
   interactions through the consent gate, paginated; `private_secret`
   entries are excluded and never bypassable, and the exclusion report
   rides every page.

## See also

- `service.toml` → `[<service>.canary]` — the capability's declared
  documentation (api entry point, versions history).
- The `how-it-works` level — what the echo path does inside.
- ADR-0026 (data consent) · ADR-0008 (the registry the MCP tools ride).
