---
name: drive-svc
description: How an agent drives the template service as a whole — what ships in it, which capability to call for what, over /mcp or /v1.
---
# drive-svc

The service-level how-an-agent-drives-me skill. The service itself exposes
nothing callable; the skills below it do. What this skill carries is the map.

## What is callable here

- **`canary`** — the Echo proof capability. `POST /v1/echo` (echoes the
  request body, carries the consent flag), `GET /v1/echo/extract` (the
  recorded interactions through the consent gate), `GET /v1/echo/ping`.
  Its own skill (`drive-canary`) carries the operation-by-operation detail.

## How to drive it

1. **Authenticate** with the service's per-service Bearer API key — the same
   key serves `/v1` (REST) and `/mcp` (the auto-generated MCP tools).
2. **Pick the capability, not the service** — a service is a set of
   capabilities; call the capability's endpoint or its MCP tool. There is no
   service-level endpoint to call.
3. **Read the capability's docs first** when the operation matters: its
   `how-to-use` level covers the user-visible steps, `how-it-works` the
   internals.
