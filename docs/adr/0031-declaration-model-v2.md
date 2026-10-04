# ADR-0031 — Declaration model v2 (services as capability sets; contents; generic dependencies; dynamic model metrics)

**Status:** accepted (maintainer decision over the stage-0 declaration surface, recorded during ticket #74's implementation); **supersedes** ADR-0027 §1's `implementation.toml` field map (`kind`, `[engine-dependency]`, `[ranks]`) and ADR-0002 §5's declaration shape (families declared in `service.toml`; a service-kind `implementation.toml`; `[ranks]`); **amends** ADR-0001 (item 1 — families are no longer part of declared service identity), ADR-0005 (§7 — the speed-rank model-selection feed is superseded; §8 — gains user-allocated storage-space quotas), ADR-0020 (§7 — dissolved; no ranks remain), CONTEXT.md (*Model selection goal* — `balanced` retires, `performance-per-dollar` arrives). **Amended in place during #74 (v3, maintainer precision): §2 and §3 rewritten — declarations carry full documentation sections (`[<service>.<capability>]`, `[<capability>.<type>.<part-name>]`, each part type repeatable), `source` moved under the model parts (`local-model`/`cloud-model`), per-part `[requirements]` with sum/union aggregation, parts as install-function configuration data; §3's implementation path keying corrected to `services/<service>/implementations/<capability>/<implementation>/`. The v2 texts of §2/§3 are the superseded historical records.** **Amended during #75 (the learning/operability bar's declaration shape): §2 and §3 gain the bar — a `[<service>.<capability>.learning]` sub-table / an own-properties `[learning]` table declaring the four graded doc levels (one Markdown artifact per level, `level` + relative `path`, all four, each once) and exactly one of the how-an-agent-drives-me `skill` (a registry `skill` entry, ADR-0008; the authored entry `<service>.skill.<name>`) or the explicit "not agent-operable" note (no theater); every declared doc/skill artifact must exist and parse — structured Markdown with the canonical front-matter (title, capability/implementation, level, keywords, mcp-tools) and the canonical section schema; the bar is mandatory to publish (ADR-0018's tiers), not to boot.** Superseded decision texts stay as their historical records.

## Context

The v1 declaration model (ADR-0002 §5 sharpened by ADR-0018/0027, embodied in ticket #74) had four frictions, found during its first implementation:

1. **Services were given "implementations" in the same sense as capabilities** (`kind = "service"`), blurring the platform's central layering. A service is a *set of capabilities*; its code is the capabilities' APIs plus a UI over them. Business logic a service appears to need (e.g. managing machine resources for implementations) is itself a capability with implementations — nothing else is special.
2. **Families were declared in `service.toml`** — duplicating a fact the capabilities' API documentation already states. ADR-0001's family contracts exist to keep service APIs aligned; they are taxonomy, not identity.
3. **`[ranks]` (accuracy/speed) could not be honest**: implementation contributors develop independently, so no contributor can credibly rank against another's work; and even standard benchmarks evolve, so numbers from models released in different months are not comparable. Absolute declared values + a dynamic comparison at selection time fix both.
4. **`[engine-dependency]` was special-case syntax** where a generic rule — depend on a capability (any implementation of it) or on a specific implementation — already covers model→engine and every other case.

## Decision

### 1. A service is a set of capabilities; no service-level implementation

- A **service** is a set of **capabilities**. The service's code is a set of APIs — the capabilities' APIs — and a UI based on these APIs.
- A service has **no implementation** in the capability sense. Any business logic is isolated in a capability and its implementations (ADR-0002's "capabilities own routes/UI" unchanged; ADR-0029 §3's `models` management capability is the canonical example).
- **`service.toml` describes the service; `implementation.toml` describes one capability implementation.** The repo ships **two templates** (per the maintainer's ruling): **`service-template/`** (the service ritual: contract machinery, `service.toml`, tests) and **`implementation-template/`** (the capability-implementation ritual: a skeleton `implementation.toml`, `install/` recipe home, `README.md`). No service-kind `implementation.toml`.

### 2. `service.toml` v2/v3

- **Layout: own properties first, then one documentation section per capability**, named `<service-name>.<capability-name>`.
- **Identity** — `name`, `description`, `version`.
- **Service-level `[requirements]`** — `disk-gb` + `ram-gb` for the service's own API + UI code execution: **one service-level figure**. Each capability implementation selected at install time adds its own requirements (§3) on top.
- **Per-capability full documentation** (in `[<service>.<capability>]`): `description`, `version`, `api` (the capability's **API description entry point** inside the service's single OpenAPI doc — ADR-0001's one `/openapi.json` per service is unchanged), `api-functions` (a short description of the api functions), `versions-history` (explanation of the versions history), `required` (`true` = an implementation MUST be provided for the service to be usable; omitted/`false` = an implementation can be omitted).
- **Per-capability UI documentation** (in `[<service>.<capability>.ui]`): `menu` (the UI hooks to integrate in the general platform dashboard — label + entry-point elements), `description` (a short description of the UI), `versions-history` (the UI versions history).
- **API families are NOT declared** — the capabilities' APIs implement ADR-0001's family contracts; their documentation is enough.
- **No capability-level dependencies** — the implementations declare dependencies (§4), not the service.
- **Per-capability learning/operability bar** *(added by #75)*: the `[<service>.<capability>.learning]` sub-table — the bar declared per ADR-0024 §1 / ADR-0002 §7: `docs` = one entry per graded level (`level` ∈ `how-to-use | how-it-works | study-in-depth | going-further` + a relative `path`; all four levels, each exactly once — the bar is graded, not flattened), and exactly one of `skill` (the how-an-agent-drives-me skill: `name` = the registry skill slug, the authored entry is `<service>.skill.<name>`, ADR-0008; `path` = its SKILL.md body) or `not-agent-operable` (the honest note explaining why the capability genuinely can't be agent-driven — never a fake skill). Every declared doc/skill artifact must exist and parse — structured Markdown with the canonical front-matter (title, capability/implementation, level, keywords, mcp-tools) and the canonical section schema; a declared-but-fake artifact fails at load (no theater). The bar is mandatory to publish (ADR-0018's tiers), not to boot: a capability may omit the table while being written; a declared table is validated fully.

### 3. `implementation.toml` v2/v3 — contents as documented part sections

- `capability` — the capability implemented; several implementations of the same capability are swappable at runtime (ADR-0002 §2 unchanged). An implementation lives **in a subdirectory of its service**, keyed `service-name/capability-name/implementation-name` (e.g. `services/inference/implementations/llm.model/qwen3-4b/`) — copied from `implementation-template/`.
- **Layout: own properties first, then one documentation section per content part**, named `<capability>.<content-part-type>.<content-part-name>`. **Each type may appear several times** (an implementation can bundle several models, several engines, ...). The implementation's own properties: `capability`, `[identity]` (name/version/description), `license` (SPDX), `[requirements]` (its OWN code only), and generic `[[dependencies]]` (§4).
- Part types and per-type properties: `inference-engine` (github URL, requirements) · `local-model` (huggingface weights URL + artificial-analysis slug + objective facts + requirements) · `cloud-model` (provider/model ref + AA slug + privacy-tier; NO requirements) · `database` (github, requirements) · `storage-space` (**required `min-quota-gb`** — the minimum quota at install, included in the implementation's aggregate disk requirement; optional `default-quota-gb` proposal, the user's install-time choice binds, never below the minimum — extends ADR-0005 §8) · `open-source-app` (github, requirements) · `cloud-service` (provider/service ref + privacy-tier; NO requirements). `source` moved under the model parts; `privacy-tier` is a cloud-part property; `[links]` superseded by the per-part URLs.
  - `local-model` parts carry **objective facts only**: disk size, active/total parameters, VRAM size at load, KV-cache size per token, quantization.
  - **Cloud parts consume no machine hardware and declare no requirements**; `privacy-tier` (`local`/`cloud_no_data`/`cloud`, ADR-0006/0008) is required on cloud parts only.
- **`[requirements]` aggregation** — the implementation's requirements are the **sum/union** of its own code requirements and its parts' requirements: disk/ram/vram sum, CPU/GPU technologies union, computed at load (`aggregate_requirements`).
- **Install contract** — the implementation-specific install function receives a **typed python object representing the full contents of the toml file** (the loader's parse result); the parsed content parts are its per-part configuration data.

### 4. Generic dependencies

An implementation may depend on:

- **a capability** — any implementation of that capability satisfies it; or
- **a specific implementation** — that implementation is required.

Each dependency may carry `min-version` and `features` (ADR-0016 §3's satisfy relation, unchanged as machinery). **Model→inference-engine is an instance of this rule, not special syntax** — `[engine-dependency]` is superseded. The engine capabilities themselves (`llm.engine`, `diffusion.engine`, `ml.engine`, ADR-0029 §1–2) are untouched.

### 5. Model metrics: declared facts + dynamic comparison

- **`[ranks]` is removed.** Model implementations declare objective facts only (§3).
- **At model-selection time** the platform fetches current quality metrics from **artificialanalysis.ai** — intelligence index (Elo), speed, cost — always fresh (cache expiry ≤ 1 day); offline → all values unknown; models not found there → unknown.
- **Selection** = filter by `supported` (machine hardware + available cloud subscriptions, computed per ADR-0005 §4 — never stored), then **order** by the model-selection goal: **`performance`** (intelligence index/Elo) · **`speed`** · **`cost`** · **`size`** (declared disk) · **`performance-per-dollar`** (performance ÷ cost — **replaces `balanced`**). Unknown values order **last** in every ranking.
- The **AA client lives in the core's implementation-selection code** (the core service's capability implementations), not the template. A **`benchmark-provider` connector type** comes later (Connectors) — also useful for the platform helper agent finding the best model for a task; the HuggingFace connector (already specified) can supply license and documentation about the models.

## Considered options

- **Ranks vs dynamic metrics** — dynamic: comparable at a point in time, zero quality claims in declarations, no cross-contributor credit problem, no benchmark drift. Ranks removed.
- **Families declared vs documented** — documented: `service.toml` stays the stable shell (identity, capabilities, UI); family contracts are API-documentation facts. The conformance suite's family parameterization moves to a test-side manifest (#70).
- **`kind` vs `[contents]`** — contents: an implementation can bundle several typed parts, and per-type facts (github/HF/AA URLs, quota) key off the part, not the whole.
- **Special engine-dependency vs generic dependencies** — generic: one rule for every dependency; model→engine is an instance. And no capability-deps in `service.toml`: the implementation knows its real dependencies; the service shell doesn't.

## Consequences

- PR #293 is reworked in place to the v2 shape; #74's acceptance criteria updated.
- ADR-0020 §7 dissolves (no ranks remain to keep separate from evaluation); ADR-0005 §7's speed-rank feed is superseded; §8 gains storage-space quotas.
- #70 parameterizes via a test-side manifest; #117's `/v1/models` ordering consumes dynamic metrics; #47 story 13's goal enum updates (`performance-per-dollar` replaces `balanced`).
- New work surfaced as tickets: the core's artificialanalysis fetch + ordering at implementation selection; the benchmark-provider connector; storage-space quota machinery (install-time allocation, monitor/change).
- CONTEXT.md glossary: *service.toml*, *implementation.toml*, *Model selection goal* rewritten; *content part*, *storage quota* added.