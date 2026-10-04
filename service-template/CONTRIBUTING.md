# Contributing a service — the copy-to-start checklist (ADR-0002 §Contribution surface; declaration shape v3 per ADR-0031)

A new service is a folder produced by **copying `service-template/`**. No
generator CLI, no shared SDK — the contract machinery is vendored into each
service (ADR-0002 §The template.1); drift is caught by the vendored
conformance suite. A new **capability implementation** is a folder produced
by **copying `implementation-template/`** (ADR-0031 §1); the two rituals
meet inside the service repo.

## The ritual (service)

1. **Copy** — copy `service-template/` to `services/<your-service>/` (repo
   root `services/<name>/` per ADR-0002 §Decision).

2. **Rename** — rename the placeholder package
   `src/<service>/` to `src/<your-service>/`. Update `name` and the
   `tool.hatch.build.targets.wheel` `packages` entry in `pyproject.toml`, and
   re-point the `sys.path` seed in `tests/contract/conftest.py` at your
   renamed directory.

3. **Edit `service.toml`** — layout: **the service's own properties first**
   (identity: `name`, `description`, `version`; one service-level
   `[requirements]` — disk-gb + ram-gb for your own API + UI code execution
   only), **then one documentation section per capability**, named
   `[<service-name>.<capability-name>]`. Each capability section carries the
   FULL documentation: `description`, `version`, `api` (the api description
   entry point, e.g. `/v1/stt`), `api-functions` (a short description of the
   api functions), `versions-history`, `required` (an implementation MUST be
   provided) or optional, and a `[<service>.<capability>.ui]` sub-table
   with the **UI hooks to integrate in the general platform dashboard**:
   `menu` (label + entry-point elements), `description` (a short description
   of the UI), and `versions-history` (the UI versions history). **API
   families are NOT declared** — your capabilities' APIs implement
   ADR-0001's family contracts; their documentation is enough. **No
   capability-level dependencies** — implementations declare dependencies.
   Declaration files are validated at load (`contract/declaration/`);
   unknown keys fail loudly — a malformed declaration fails at startup,
   not at request time.

   TOML ordering rule: top-level keys (`name`, `description`, `version`)
   must precede any `[table]` header — in TOML everything after a table
   header belongs to that table.

   **The learning/operability bar** (ADR-0024 §1, ADR-0002 §7; declaration
   shape per ADR-0031 §2 as amended): each capability section may carry a
   `[<service>.<capability>.learning]` sub-table declaring
   - the **four graded doc levels** — `[[<service>.<capability>.learning.docs]]`
     with `level` (`how-to-use` · `how-it-works` · `study-in-depth` ·
     `going-further` — all four, each exactly once; graded, not flattened)
     and `path` (relative to `service.toml`) — each a distinct Markdown
     artifact with the **canonical front-matter** (`title`, `capability`,
     `level`, `keywords`, `mcp-tools`) and the **canonical section schema**
     (`## Summary` / `## Details` / `## See also`, in this order) — one
     source, dual-consumed by the human surface and the agent indexer;
   - **exactly one of**: the **how-an-agent-drives-me skill**
     (`[<service>.<capability>.learning.skill]` — `name`: the registry
     skill slug, unique within the service; the authored registry entry is
     `<service>.skill.<name>`, ADR-0008; `path`: its SKILL.md body —
     front-matter `name`/`description` + instructions) or the explicit
     **`not-agent-operable` note** (the honest why for a capability that
     genuinely can't be agent-driven — never a fake skill, no theater).
   The loader validates every declared artifact (it must exist and parse —
   a declared-but-fake artifact fails at load) and keeps a service bootable
   while the bar is being written: **the bar is mandatory to publish**
   (`bundled`/`listed`; tracked-gaps for `third-party`, ADR-0018), so
   declare it for every capability you publish.

4. **Declare capability implementations** — copy
   `implementation-template/` per implementation (a service has NO
   implementation.toml; ADR-0031 §1) into
   `services/<your-service>/implementations/<capability>/<implementation>/`
   — the implementations live in a subdirectory of the service, keyed
   `service-name/capability-name/implementation-name`. Layout: **the
   implementation's own properties first** (`capability`, `license` (SPDX),
   `[identity]` (name/version/description), `[requirements]` — its OWN code
   only — and generic `[[dependencies]]`: on a capability (any
   implementation of it satisfies) or on a specific implementation (that
   one is required), with optional `min-version`/`features`), **then one
   documentation section per content part**, named
   `[<capability>.<content-part-type>.<content-part-name>]`. **Each type may
   appear several times** (an implementation can bundle several models).
   Part types: `inference-engine` (github URL, requirements) · `local-model`
   (huggingface weights URL + artificial-analysis slug + objective facts +
   requirements) · `cloud-model` (provider/model ref + AA slug +
   `privacy-tier`; NO requirements — a cloud part consumes no machine) ·
   `database` (github, requirements) · `storage-space` (a **required
   `min-quota-gb`** — the minimum quota at install, included in the
   implementation's aggregate disk requirement; an optional
   `default-quota-gb` proposal, the user's install-time choice binds,
   never below the minimum) ·
   `open-source-app` (github, requirements) · `cloud-service`
   (provider/service ref + privacy-tier; NO requirements). **The
   implementation's requirements are the sum/union** of its own
   requirements and its parts' requirements (disk/ram/vram sum, cpu/gpu
   technologies union), computed at load. **No `[ranks]`, no
   `[engine-dependency]`, no `source`/`privacy-tier`/`[links]` at
   implementation level** (moved into the parts), **no stored
   `supported`/`recommended`** (ADR-0031 §5): quality/speed/cost
   comparisons are dynamic (artificialanalysis at selection time); never
   put those keys in a declaration.

   **The implementation's own learning/operability bar** (ADR-0024 §1;
   ADR-0031 §3 as amended): an own-properties `[learning]` table — the
   same shape as the capability bar (step 3): the **four graded doc
   levels** in `[[learning.docs]]` entries (paths relative to the
   implementation directory; each artifact's canonical front-matter names
   THIS implementation — `implementation: <name>` — not a capability) plus
   **exactly one of** the how-an-agent-drives-me skill (`[learning.skill]`,
   a registry `skill` entry, ADR-0008) or the explicit
   `not-agent-operable` note. Validated by the same loader machinery.

   The implementation-specific install function receives the **typed
   `Implementation` object** (the loader's parse result) as its
   configuration data — no re-parsing.

5. **Keep only the family blocks you exercise** — the vendored suite's
   family conformance lives in `tests/contract/families/` as blocks named
   `f<N>_<slug>/`, parameterized by the **test-side manifest**
   `tests/contract/families/manifest.toml` (the maintainer ruling on #70:
   families are NOT declared in `service.toml`, ADR-0031 §2 — your tests
   declare which families they exercise, as explicit data next to the
   tests, no probing, no magic). Edit the manifest's `families = [...]` to
   list the ADR-0001 family numbers your service implements, keep those
   blocks, delete the rest. A listed family with no block on disk — or an
   unknown/malformed entry — fails the suite loudly; an unlisted block never
   runs. A listed block is red until the family's surface is implemented —
   that is the conformance gate, never bypassed.

6. **Implement capabilities** — add your `capabilities/` modules (business
   logic, routes, UI pages) and register their routes via
   `create_service_app(extra_routes=...)`. Routes are declared with their
   full `/v1/...` path (base item 3). Never edit `contract/base/` — it is
   always kept, never edited (ADR-0002 §The template.1).

## The ritual (capability implementation) — `implementation-template/`

A capability implementation is a folder copied from
`implementation-template/` into the service repo at
`services/<service>/implementations/<capability>/<implementation>/`. The
folder contains:

- **`implementation.toml`** — the declaration (validated by the service
  template's `contract/declaration/load_implementation_toml` — the loader
  is part of the vendored contract machinery). The shape is ADR-0031 §3/§4
  v3: own properties (`capability`, `[identity]`, `license`,
  `[requirements]`, `[[dependencies]]`), then per-part documentation
  sections `[<capability>.<type>.<part-name>]` (each type may appear
  several times; per-type properties and per-part `[requirements]`; the
  parts are the configuration data for the install function), plus the
  own-properties `[learning]` bar table (ADR-0024 §1; ADR-0031 §3 as
  amended — the four graded docs levels + the skill or the note).
- **`docs/`** — the four graded bar docs (canonical front-matter + section
  schema, ADR-0024 §1 / #75).
- **`skills/SKILL.md`** — the how-an-agent-drives-me skill body
  (a registry `skill` entry, ADR-0008).
- **`install/`** — the installer's recipe (how the implementation is
  installed on the machine — weights to download, engine to install,
  service to configure). The exact installer contract is the install/
  lifecycle spec's concern (#65), not the declaration's.
- **`README.md`** — human documentation (what the implementation does,
  its tradeoffs, how it compares to siblings of the same capability).

The same rules as the service ritual apply: own properties before any
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
base-contract stub-factory (`tests/support/stubs.py`), the consent-flag
template contract (#72 — the flag on every user input, the never-bypassable
private/secret extraction exclusion, the consent stub interaction), and the
composition stub patterns (#73 — the `StubEngine` behind the family-1/2/5
seam returning deterministic canned model output, the family-5 model catalog
and its lifecycle operations (`download`/`load`/`unload`/`prepare`), and the
`StubRegistry` name→URL resolver that `call`/`model`/`agent` composition
references resolve against) are in; the nine family modules with their full
conformance blocks (#76–#84) arrive as their own stage-0 tickets on top of
this base. The installer contract for `install/` recipes is #65's concern.
