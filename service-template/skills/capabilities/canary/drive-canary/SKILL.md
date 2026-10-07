---
name: drive-canary
description: How an agent drives the canary capability — every operation, parameter and consent flag, over /mcp or /v1.
---
# drive-canary

The how-an-agent-drives-me skill of the canary capability (ADR-0024 §1):
a registry `skill` entry whose authored name is `<service>.skill.drive-canary`
(ADR-0008); this file is the body the owning service stores.

## How to drive the canary

- **Authenticate** — Bearer with the service's API key; every call, both
  surfaces.
- **Echo a text** — `POST /v1/echo` with `{"text": "...", "consent":
  "may_use"}` (the consent flag is REQUIRED on the input; use
  `"private_secret"` when the user marks the input private — the record
  is then excluded from every extraction). The same operation is
  available as an auto-generated MCP tool at `/mcp` (stateless JSON-RPC
  2.0, per-request Bearer).
- **Read the record** — `GET /v1/echo/extract?limit=50` (cursor
  paginated): the recorded interactions through the consent gate;
  `private_secret` entries never come back — the exclusion is never
  bypassable — and the exclusion count rides every page.
- **Health probe** — `GET /health` (unauthenticated).
- **Errors** — the 11-code error taxonomy, one JSON shape with
  `request_id`; `401 authentication_failed` without a valid key.
