# ADR-0031 — Declaration model v2 (services as capability sets; contents; generic dependencies; dynamic model metrics)

**Status:** accepted (maintainer decision over the stage-0 declaration surface, recorded during ticket #74's implementation); **supersedes** ADR-0027 §1's `implementation.toml` field map (`kind`, `[engine-dependency]`, `[ranks]`) and ADR-0002 §5's declaration shape (families declared in `service.toml`; a service-kind `implementation.toml`; `[ranks]`); **amends** ADR-0001 (item 1 — families are no longer part of declared service identity), ADR-0005 (§7 — the speed-rank model-selection feed is superseded; §8 — gains user-allocated storage-space quotas), ADR-0020 (§7 — dissolved; no ranks remain), CONTEXT.md (*Model selection goal* — `balanced` retires, `performance-per-dollar` arrives). Superseded decision texts stay as their historical records.

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
- **`service.toml` describes the service; `implementation.toml` describes one capability implementation.** The template ships the service declaration plus a capability-implementation declaration template (`implementation.template.toml`) — no service-kind `implementation.toml`.

### 2. `service.toml` v2

- **Identity** — `name`, `description`, `version`.
- **Service-level `[requirements]`** — `disk-gb` + `ram-gb` for the service's own API + UI code execution: **one service-level figure**. Each capability implementation selected at install time adds its own requirements (§3) on top.
- **`[[capabilities]]`** — the capability list; each capability declares `name`, `description`, `version`, `api` (the capability's **API path prefix** inside the service's single OpenAPI doc — ADR-0001's one `/openapi.json` per service is unchanged), `required` (`true` = an implementation MUST be provided for the service to be usable; omitted/`false` = an implementation can be omitted), and `[capabilities.ui]` menu elements + entry points to integrate in the platform UI.
- **API families are NOT declared** — the capabilities' APIs implement ADR-0001's family contracts; their documentation is enough.
- **No capability-level dependencies** — the implementations declare dependencies (§4), not the service.

### 3. `implementation.toml` v2 — contents

- `capability` — the capability implemented; several implementations of the same capability are swappable at runtime (ADR-0002 §2 unchanged).
- `[identity]` (name/version/description), `license` (SPDX), `privacy-tier` (`local`/`cloud_no_data`/`cloud`), `source` (`local-weights` | `cloud:<provider>/<model>` — ADR-0027 §4 unchanged), `[links]` — as before.
- **`[contents]` replaces `kind`** — a dictionary of **named content parts**, each with a `type`: `inference-engine` · `model` · `database` · `storage-space` · `open-source-product`. An implementation may bundle several parts.
  - `inference-engine` / `database` / `open-source-product` parts require a **`github` URL**.
  - `model` parts require the **`huggingface` URL** for the weights and the **`artificial-analysis` slug** (the join key for §5's dynamic metrics), and carry **objective facts only**: disk size, active/total parameters, VRAM size at load, KV-cache size per token, quantization.
  - `storage-space` parts declare the part; the **maximum quota is the user's choice, allocated at install time**, monitored and changeable later (extends ADR-0005 §8's quota machinery with a new bookable kind; the declaration may propose a `default-quota-gb`).
- **`[requirements]`** — the minimum to install **and run** the implementation: `disk-gb`, `ram-gb`, `cpu` technologies, `gpu` technologies, `vram-gb`.

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