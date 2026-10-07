---
title: The template service — how it works
keywords:
  - template-service
  - declaration
  - loader
  - contract
mcp-tools: []
---
# The template service — how it works

## Summary

A wordslab service is four pieces: the **declaration** (`service.toml`, read
at startup / install / catalog-build), the **vendored contract** (`contract/`
— the base HTTP/JSON surface plus the declaration loaders), the
**capabilities** (`capabilities/` — the business logic, routes and UI pages),
and the **learning bar** (this service's and each capability's graded docs +
skill, discovered by layout). This page explains how those pieces fit.

## Details

1. **The declaration is data** — `load_service_toml` validates
   `service.toml` as a closed shape (own properties, then one documentation
   section per capability) and raises a precise error on any violation; the
   service can't boot half-declared.
2. **The contract is vendored, never edited** — `contract/base/` carries the
   family conformance and the shell's helpers; the copy-to-start ritual
   copies it and leaves it alone (ADR-0002 §The template.1).
3. **Capabilities register routes** — `create_service_app(extra_routes=...)`
   mounts the capability's `/v1/...` routes on the shared app; the MCP
   surface is auto-generated from the same OpenAPI spec, so it can't drift.
4. **The learning bar is discovered, not declared** — the loader derives
   each subject's artifacts from the layout (`docs/service/`,
   `docs/capabilities/<cap>/`, `skills/...`) and audits every file it finds;
   a malformed doc fails the load, a missing one is a recorded gap.

## See also

- `CONTRIBUTING.md` — the copy-to-start ritual, step by step.
- `docs/capabilities/canary/how-it-works.md` — the same story one level down.
- ADR-0031 §2 (the declaration shape) · ADR-0001 (the family contracts) ·
  ADR-0002 (the template).
