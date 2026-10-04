---
title: Echo — how it works
capability: canary
level: how-it-works
keywords:
  - echo
  - canary
  - routes
  - consent
mcp-tools: []
---
# Echo — how it works

## Summary

The canary is a thin vertical slice of the template's whole architecture:
one capability module (`capabilities/canary/`) owning its routes, page and
API fragment, composed by the service's stable shell into one app with the
base contract's shared surfaces.

## Details

- **Routes** — `capabilities/canary/routes.py` builds the `/v1/echo`
  routes with a per-app interaction store passed in by the assembly file
  (`app.py`); no module-level state, so many in-process services coexist
  in one test run.
- **OpenAPI** — `api.py` contributes the capability's OpenAPI fragment;
  the service assembles one `/openapi.json` document from all fragments,
  and the MCP surface is auto-generated from that document (zero drift).
- **UI** — `page.py` renders the Echo page (FastHTML + Alpine, vendored
  assets); the consent toggle is the capability's visible consent-flag
  contract (ticket #72, ADR-0026).
- **Consent gate** — the interaction store keeps every record; the
  extract route filters `private_secret` out at the seam and reports the
  exclusion count — the never-bypassable red gate.

## See also

- The `how-to-use` level — drive it from the page, the API or an agent.
- The `study-in-depth` level — the design decisions behind the skeleton.
- `contract/base/` — the vendored contract machinery the capability rides.
