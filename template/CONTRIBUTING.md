# Contributing a service — the copy-to-start checklist (ADR-0002 §Contribution surface)

A new service is a folder produced by **copying `template/`**. No generator
CLI, no shared SDK — the contract machinery is vendored into each service
(ADR-0002 §The template.1); drift is caught by the vendored conformance suite.

## The ritual

1. **Copy** — copy `template/` to `services/<your-service>/` (repo root
   `services/<name>/` per ADR-0002 §Decision).

2. **Rename** — rename the placeholder package
   `src/<service>/` to `src/<your-service>/`. Update `name` and the
   `tool.hatch.build.targets.wheel` `packages` entry in `pyproject.toml`, and
   re-point the `sys.path` seed in `tests/contract/conftest.py` at your
   renamed directory.

3. **Edit `service.toml`** — declare identity (name/version/description),
   the **families** you implement (ADR-0001's nine; a plain CRUD service
   keeps base alone), your capabilities, and your UI nav. Both declaration
   files are validated at load (`contract/declaration/`); a `service.toml`
   naming an unknown family fails at startup, not at request time.

   TOML ordering rule: top-level keys (`name`, `version`, `source`,
   `license`, `privacy-tier`) must precede any `[table]` header — in TOML
   everything after a table header belongs to that table.

4. **Declare implementations** — ship one `implementation.toml` per
   implementation (ADR-0002 §5, ADR-0027 §1): identity, `source`
   (`local-weights` or `cloud:<provider>/<model>`), SPDX license
   (models carry the ADR-0022 five-question compliance profile), links,
   sizes, `[resource-profile]` (ADR-0005 §1's install + running-formula
   shape), `[max-capacity]`, `[ranks]`, `[modalities]`, `privacy-tier`
   (`local`/`cloud_no_data`/`cloud`), and — model implementations only —
   `[engine-dependency]`. `template/implementation.toml` is the service-kind
   example. **`supported`/`recommended` are computed, never stored**
   (ADR-0005): never put those keys in a declaration.

5. **Delete undeclared families** — remove every
   `src/<your-service>/contract/families/<family>` module your
   `service.toml` does not declare. Deleting an undeclared family must not
   break anything; the vendored suite runs families per declaration.

6. **Implement capabilities** — add your `capabilities/` modules (business
   logic, routes, UI pages) and register their routes via
   `create_service_app(extra_routes=...)`. Routes are declared with their
   full `/v1/...` path (base item 3). Never edit `contract/base/` — it is
   always kept, never edited (ADR-0002 §The template.1).

## Contract rules you inherit (cite ADR-0001, don't re-derive)

- HTTP/1.1 + JSON, SSE for streaming; paths under `/v1` (items 1, 3)
- Bearer per-service API keys; 401 `authentication_failed` when absent/invalid (item 2)
- the 11-code error taxonomy; `X-Request-Id` on every response (item 4)
- cursor pagination, `?limit` (default 50, max 200) + `?cursor` (item 5)
- `GET /health` with the status enum; 200 alive/progressing, 503 cannot-serve (item 6)
- optional `Idempotency-Key` on mutating endpoints; retries return the
  original result (item 7)
- `usage` field on resource-consuming operations (item 8 — family-defined unit)

## What is not in this ticket's template yet

The vendored conformance suite (#70), the canary capability (#71), the
consent-flag template contract (#72), the stub patterns (#73), and the nine
family modules (#76–#84) arrive as their own stage-0 tickets on top of this
base.
