# Contributing a service — the copy-to-start checklist (ADR-0002 §Contribution surface)

A new service is a folder produced by **copying `service-template/`**. No
generator CLI, no shared SDK — the contract machinery is vendored into each
service (ADR-0002 §The template.1); drift is caught by the vendored
conformance suite. A new **capability implementation** is a folder produced
by **copying `implementation-template/`** — the second template
(ADR-0031 §1); the two rituals meet inside the service repo.

## The ritual (service)

1. **Copy** — copy `service-template/` to `services/<your-service>/` (repo
   root `services/<name>/` per ADR-0002 §Decision).

2. **Rename** — rename the placeholder package
   `src/<service>/` to `src/<your-service>/`. Update `name` and the
   `tool.hatch.build.targets.wheel` `packages` entry in `pyproject.toml`, and
   re-point the `sys.path` seed in `tests/contract/conftest.py` at your
   renamed directory.

3. **Edit `service.toml`** — declare identity (name/description/version),
   the service-level `[requirements]` (disk-gb + ram-gb for your own API +
   UI code execution only), and your `[[capabilities]]` list — per
   capability: name, description, version, `api` (its API path prefix
   inside the service's single OpenAPI doc), `required` (an implementation
   MUST be provided) or optional, and `[capabilities.ui]` menu elements +
   entry points. **API families are NOT declared** — your capabilities'
   APIs implement ADR-0001's family contracts; their documentation is
   enough. **No capability-level dependencies** — implementations declare
   dependencies (step 4). Declaration files are validated at load
   (`contract/declaration/`); a malformed declaration fails at startup, not
   at request time.

   TOML ordering rule: top-level keys (`name`, `description`, `version`,
   `source`, `license`, `privacy-tier`) must precede any `[table]` header —
   in TOML everything after a table header belongs to that table.

4. **Declare capability implementations** — copy
   `implementation-template/` per implementation (a service has NO
   implementation.toml; ADR-0031 §1) into
   `services/<your-service>/implementations/<capability>/<implementation>/`
   — the implementations live in a subdirectory of the service, keyed
   `service-name/capability-name/implementation-name`. Each declares:
   `[identity]`, `capability`, `source` (`local-weights` or
   `cloud:<provider>/<model>`), SPDX `license` (model weights carry their
   ADR-0022 five-question compliance profile as license/links facts — the
   dedicated profile field is a later concern-ticket), `privacy-tier`
   (`local`/`cloud_no_data`/`cloud`), `[links]`, **`[contents]`** (named
   content parts typed `inference-engine | model | database | storage-space
   | open-source-product`; engine/database/OSS parts carry a `github` URL;
   a model part carries the `huggingface` weights URL + the
   `artificial-analysis` slug + objective facts only — disk, active/total
   parameters, VRAM at load, KV-cache per token, quantization; a
   storage-space part may propose a `default-quota-gb`, the user's
   install-time choice binds), **`[requirements]`** (the minimum to
   install AND run: disk-gb, ram-gb, cpu/gpu technologies, vram-gb), and
   generic **`[dependencies]`** — on a capability (any implementation of
   it satisfies) or on a specific implementation (that one is required),
   with optional `min-version`/`features`. Model→engine is an instance of
   that rule — no special syntax. **No `[ranks]`, no
   `[engine-dependency]`, no stored `supported`/`recommended`**
   (ADR-0031 §5): quality/speed/cost comparisons are dynamic
   (artificialanalysis at selection time); never put those keys in a
   declaration.

5. **Keep only the family modules you implement** — remove every
   `src/<your-service>/contract/families/<family>` module you do not
   implement (the vendored suite's test-side manifest records which family
   modules it exercises, #70).

6. **Implement capabilities** — add your `capabilities/` modules (business
   logic, routes, UI pages) and register their routes via
   `create_service_app(extra_routes=...)`. Routes are declared with their
   full `/v1/...` path (base item 3). Never edit `contract/base/` — it is
   always kept, never edited (ADR-0002 §The template.1).

## The ritual (capability implementation) — `implementation-template/`

A capability implementation is a folder copied from
`implementation-template/` into the service repo at
`implementations/<capability>/<implementation>/` (so a model
implementation's folder reads
`services/inference/llm.model/qwen3-4b/`). The folder contains:

- **`implementation.toml`** — the declaration (validated by the service
  template's `contract/declaration/load_implementation_toml` — the loader
  is part of the vendored contract machinery). The shape is ADR-0031 §3/§4:
  `capability`, `[identity]`, `source`, `license`, `privacy-tier`,
  `[links]`, `[contents]` (typed named parts with per-type facts),
  `[requirements]` (install-and-run minimum), generic `[dependencies]`.
- **`install/`** — the installer's recipe (how the implementation is
  installed on the machine — weights to download, engine to install,
  service to configure). The exact installer contract is the install/
  lifecycle spec's concern (#65), not the declaration's.
- **`README.md`** — human documentation (what the implementation does,
  its tradeoffs, how it compares to siblings of the same capability).

The same rules as the service ritual apply: top-level keys precede any
`[table]` header; **no `[ranks]`, no `[engine-dependency]`, no stored
`supported`/`recommended`** (ADR-0031 §5) — never put those keys in a
declaration.

## Contract rules you inherit (cite ADR-0001, don't re-derive)

- HTTP/1.1 + JSON, SSE for streaming; paths under `/v1` (items 1, 3)
- Bearer per-service API keys; 401 `authentication_failed` when absent/invalid (item 2)
- the 11-code error taxonomy; `X-Request-Id` on every response (item 4)
- cursor pagination, `?limit` (default 50, max 200) + `?cursor` (item 5)
- `GET /health` with the status enum; 200 alive/progressing, 503 cannot-serve (item 6)
- optional `Idempotency-Key` on mutating endpoints; retries return the
  original result (item 7)
- `usage` field on resource-consuming operations (item 8 — family-defined unit)

## What is not in these templates yet

The vendored conformance suite (#70), the canary capability (#71), the
consent-flag template contract (#72), the stub patterns (#73), and the nine
family modules (#76–#84) arrive as their own stage-0 tickets on top of this
base. The installer contract for `install/` recipes is #65's concern.