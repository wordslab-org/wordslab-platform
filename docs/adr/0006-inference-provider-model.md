# ADR-0006 — Inference provider model (cloud access machinery)

**Status:** accepted (resolution of wayfinder ticket "Design the inference provider model"); **amends ADR-0002** (privacy-tier vocabulary) and sharpens **ADR-0005 §9** (remaining-% adapter data flow, LiteLLM backstop role); **amended by ADR-0007** (inference-policy vocabulary removed — privacy tier is a property of each explicitly chosen implementation) and **ADR-0008** (privacy-tier labels → `local` / `cloud_no_data` / `cloud`)

## Context

The platform's inference is local-first, but cloud is the fallback when local hardware is insufficient (research "Cloud Inference Fallback", canonical). This ADR is the **machinery of the external side of inference** — how the platform models cloud model providers, bring-your-own-key (BYOK), and the shared credential/billing/quota machinery that rides on top of them. It is the **cloud machinery** (#19) that sits on the local quota rules (#4 = how much), the topology (#6 = where), and the centralized platform core (#9 = control, never the request path). It is fed by the service catalog (#18: "tools as services" = the Connectors service; shared credentials vault), and it precedes the capability registry (#20), composition (#13), the dashboard (#8), and publishing (#21).

The platform's audience is non-technical people who want to understand and stay in control (the soul, map issue #1). That shapes every decision here: **no magic, no black box** — providers, credentials, spend, privacy, and what leaves the machine must all be visible, explained, and user-chosen.

Four realities extend the original research (OpenRouter default + LiteLLM gateway):
1. **BYOK** — users hold existing subscriptions/keys (OpenAI, Anthropic, Google, Meta, Qwen, DeepSeek, Kimi, GLM, HuggingFace, Ollama, Nous portal; fal for image, ElevenLabs for voice, MixedBread/LightOn for embed+rerank). The platform must accept arbitrary keys/endpoints, not just OpenRouter.
2. **Bundles** — providers offer models *and* tools in one subscription (e.g. Nous portal: LLMs + web tools + image gen + TTS/STT). The abstraction must model bundles, not just endpoints.
3. **Tools as services** — tool execution is the Connectors service (#18); its credentials ride this ticket's shared vault.
4. **Cloud access machinery** — where credentials live and rotate, cost accounting, quotas, and the gateway.

Verified current (mid-2026): LiteLLM natively covers the LLM/BYOK landscape well (OpenAI, Anthropic, Google, Meta, Qwen/Dashscope, DeepSeek, Kimi/Moonshot, GLM/Z.AI, HuggingFace, Ollama, OpenRouter, even ChatGPT-subscription via OAuth device flow), plus image gen (fal, BFL, Stability, Recraft, OpenRouter), audio (ElevenLabs, Deepgram, Riva), embeddings and rerank. Gaps: video generation (thin), MixedBread/LightOn as *named* providers (rerank not native), Nous portal (OpenAI-compatible custom row). These gaps are absorbed by the per-capability implementation model (below), not by forcing everything through LiteLLM.

## Decision

### 1. Cloud access = implementations of the Inference service's capabilities

A **cloud gateway** (machinery that fronts external model providers) is an **alternative implementation of the Inference service's capabilities** (`llm`, `diffusion`, `classic AI`) — exactly the ADR-0002/0004 implementation abstraction: layer-1 software (LiteLLM and/or direct provider SDKs) plus the platform's thin layer on top, installed/loaded/unloaded like any implementation. Because local and cloud are **implementations of the same capability surface**, a model-backed service's API and UX are near-identical whether the model runs locally or in the cloud — the choice is an implementation/routing decision, not a different API.

Cloud implementations carry extra concerns beyond a local one: **key management, optional input/output data filtering, usage limits (per unit of time or token cost), privacy guarantees**. These are part of what a cloud-gateway implementation is.

The cloud-gateway capability **installs on the leader machine only** (v1, no HA). Any machine's model-backed service can call the leader's cloud implementation over the LAN/overlay (ordinary cross-machine routing, ADR-0004); workers stay lean (no cloud-gateway software of their own). Tool gateways are **not** this ADR's concern — tool execution is the Connectors service (#18).

LiteLLM is a **swappable engine inside each cloud implementation**, not a universal hop. Where LiteLLM is strong (llm capability, much of diffusion/audio/embedding) the cloud implementation generates its `model_list`/routes from the distributed provider registry. Where it is thin (video, MixedBread/LightOn rerank, Nous portal) the capability's cloud implementation **routes direct or uses an OpenAI-compatible custom row**. The thin platform layer absorbs the mismatch.

### 2. The provider registry is a leader-core configuration

A **provider** is a platform-level resource: `id`, `base_url`, an `api_key` ref into the shared `secrets` vault, enabled modalities, **privacy tier**, and bundle flag. The **leader core "knows" the worker machines (for local compute) and the providers (for cloud compute).** The **master provider registry lives in the leader core** (a configuration alongside `secrets`/`keys`), one dashboard page to add/edit/remove a provider. Adding a provider = adding a row, not code. The core **distributes the resolved provider set** (rows + the decrypted keys from `secrets`) to the consuming services — the Inference service (model legs) and the Connectors service (bundle tool legs) — at install and on rotation, via the ADR-0003 secrets pattern (master + distribution, no call-time round-trip).

The registry is the *specification* of providers; the core distributes it but **never enforces it in the request path** — routing and enforcement stay with the consuming Inference service (ADR-0003 "deliberately NOT centralized").

### 3. BYOK: preconfigured, tested provider cards + advanced custom endpoint

The platform's added value on the provider side is **removing the pain of provider quirks**. Every popular service ships **preconfigured and thoroughly tested** (per-modality quirks, parameter normalization, endpoint shapes baked in) — the user just enters a key into a pre-made card. Each template is **verified against the provider's real current API** before shipping (never invented — copied proven shapes, checked online). Adding an arbitrary **OpenAI-compatible endpoint is an advanced feature**, not the normal path.

- **Entry:** a BYOK provider is added from the dashboard's provider page as a "custom provider" row: `base_url` + an API key (stored in the vault) + optional declared model names + a privacy tier.
- **Validation:** one **probe call** (a minimal request against `base_url` with the key for the declared modality) runs at add-time, so a typo'd key/endpoint fails immediately with a clear "key or endpoint rejected by provider" message — not silently at first real use.
- **Scope:** **admin-wide keys in v1** (the admin adds providers; any service/user can use them, subject to per-service caps from #4). Per-user keys are **deferred** — the provider row carries an optional `owner` (empty = shared) so the model leaves room.
- **Mapping:** an OpenAI-compatible custom provider becomes a row in LiteLLM's `model_list` (or a direct route where LiteLLM is thin), handled transparently by the consuming cloud implementation.

### 4. Bundles = one provider row with capability-tagged legs

A **bundle** (one subscription covering models *and* tools, e.g. Nous portal) is **one provider row whose legs are tagged by capability**: `{modality: llm}`, `{modality: diffusion}`, `{modality: tool (web search)}`, … Model legs feed the Inference service as **model implementations declared in `implementation.toml`** (`source` = provider ref); **tool legs register as MCP tools in the capability registry (#20) and execute via the Connectors service (#18)**. **One credential covers all legs.** The registry distributes the row to both the Inference service and the Connectors service; each keeps only the legs it owns. The dashboard shows one subscription card (not two entries the user must rejoin), and "what leaves the machine" reports per-subscription across both services.

### 5. Credentials: one shared vault, push + pull-on-start, eventual consistency

The core's **`secrets` capability is the single master copy for BOTH provider and connector credentials** (ADR-0003 + #18). Distribution is:
- **Push** on install and on rotation to all currently reachable services (leader's own + workers that are up), and
- **Pull-on-start**: a service (especially on a worker that may have been down during a rotation) **pulls the current credential set from the leader's `secrets`/provider registry at service startup** before serving; if the leader is unreachable at boot, the service starts on its **last cached copy** and reconciles on the next successful pull.

This is **not a call-time round-trip** (pull is at boot, not per-request), so it does not violate ADR-0003's "no call-time round-trip." Rotation is expected to be **frequent** (e.g. monthly GitHub tokens), so **eventual consistency** (a service may hold a stale key until its next boot) is the honest operating model; a rotated-out key simply fails auth at the provider side, surfaced clearly.

**At-rest protection** of credential copies is **#14's** job, explicitly not solved here. The **action-context header is never sent to third-party providers** (ADR-0004 §10) — the cloud implementation strips it before the outbound call.

### 6. Accounting: two exclusive billing modes

A cloud provider bills a capability **one way or the other, never both**:

- **Metered (per-token / per-call):** the service *can* attribute money per request → it records `usage.cost` locally (forward data flow: service → core). The **leader core pulls + aggregates** (ADR-0003 `stats` pattern: pull-based, hourly cached snapshots) into spend per service/user/provider, attributed via action context. **Enforcement** of "can I route to cloud?" is the **local distributed money cap** (per-service monthly cap from #4), with **LiteLLM's per-key hard budget as the enforcement backstop** — even if a service's local cap were bypassed, the gateway physically caps spend per virtual key. This backstop exists **only where the route goes through LiteLLM**; direct-routed capabilities (video, MixedBread rerank, Nous) have no gateway-level hard cap and rely solely on the service's local cap (stated honestly, not hidden).
- **Opaque subscription (fixed price, capped per unit of time):** the service **cannot compute money from a request** — it counts **tokens only**. The only money-ish fact is the **% remaining** of the provider-owned pool, known only to the provider. The source of truth is the **provider**: the **leader core pulls the remaining-% from the provider** via an adapter (across its time scales — daily/weekly/monthly window until next reset) and aggregates it (**data flow reversed**: provider → core). Because the red-line is aggregated in the core, the core **distributes the current remaining-%/red-line status down** to consuming services (push + pull-on-start, same as credentials) so each service still enforces "can I route to cloud?" locally at call time without a call-time round-trip. The service counts tokens locally and feeds those up; the red-line comes down. (The remaining-% adapter caches on a cadence + opportunistically on usage/limit headers or 429s — no per-call round-trip, per ADR-0005 §9.)

At the cap, cloud-routed calls return `429 resource_exhausted` with resource `cloud-spend` (ADR-0005 §9, amends ADR-0001). The two dimensions (money cap, remaining-% red-line) are **exclusive per capability** — a provider is billed one way or the other, never both.

### 7. Privacy: three-tier taxonomy, documented + user-chosen

There are **exactly three privacy tiers**, a property of each implementation (model implementation / provider leg), describing where data goes and with what guarantee. The **canonical labels platform-wide** are **`local` / `cloud_no_data` / `cloud`** (ADR-0008; friendlier, still unambiguous — these replace the earlier `own machines / ZDR / other` names, semantics unchanged):

1. **`local`** — your own machines: local, *or* a cloud host joined to your **private overlay network** (data never leaves your control; "own machine" = wherever your private network is).
2. **`cloud_no_data`** — a cloud service with **Zero Data Retention** (ZDR / `data_collection: deny`).
3. **`cloud`** — a cloud service with **any other policy** (retention, training, etc.).

The tier is **documented, prominently and everywhere it matters**: on the **API and MCP documentation** for that implementation (prominent), **discoverable** through the API and MCP **description** (so it is machine-readable — surfaced in the capability registry #20 and tool discovery), and **displayed on the UI** when the user uses that service.

The **user chooses implementations manually and is warned** about the privacy guarantees. The platform does **not** silently auto-route around a tier; its enforcement is **visibility + user decision** — no magic, no black box. *(Replaces ADR-0002's `default`/`no-retention`/`no-training` privacy-tier vocabulary; the earlier *inference policy* for routing (`local-only`/`local-then-cloud`/`cloud-only`) is abolished by ADR-0007 — the *privacy tier* is this three-tier data-class taxonomy on each implementation, and implementation choice is explicit.)*

### 8. Boundary

State in the resolution comment: **#4 = how much** (local quota rules, ADR-0005 §9); **#19 = cloud machinery** (providers, credentials, billing, cloud-gateway implementations, remaining-% adapters); **#14 = at-rest protection**; **#20 = tool registration**; **#13 = composition config**; **#18/Connectors = tool execution + its credentials**; the core never proxies calls (ADR-0003).

## Considered options

- **Cloud access as capability implementations (chosen) vs a sibling layer-1 gateway process vs LiteLLM embedded per service** — the implementation abstraction reuses ADR-0002/0004: one capability surface for local and cloud (near-identical UX/API), one install footprint, and the thin layer absorbs LiteLLM's coverage gaps per capability. A sibling process would invent a new component; per-service embedding would duplicate heavy machinery and scatter the spend/credential picture.
- **Provider registry in the leader core (chosen) vs a config file owned by the Inference service** — the registry is a platform-wide concept paired 1:1 with credentials (already core-owned); one dashboard management surface; "add a provider = add a row" as one master row set pushed out. The core distributes but never enforces.
- **Preconfigured + tested provider templates (chosen) vs a blank registry the user fills** — removing provider-quirk pain is the platform's added value; templates are verified against each provider's real current API. Arbitrary OpenAI-compatible endpoints remain as an advanced option.
- **Admin-wide keys in v1, per-user deferred (chosen) vs per-user keys now** — simplicity at home scale; the `owner` field leaves the door open.
- **Bundle = one provider row with capability-tagged legs (chosen) vs two separate provider entries** — one credential, one dashboard card, transparent per-subscription reporting; each service keeps only its own legs.
- **Push + pull-on-start distribution (chosen) vs push-only vs per-call vault** — push-only leaves offline workers stale indefinitely (rotation is frequent, e.g. monthly GitHub tokens); per-call violates ADR-0003. Pull-on-start catches stragglers at boot without a request-path round-trip; eventual consistency is the honest model.
- **Two exclusive billing modes (chosen) vs a single unified cost ledger** — a subscription's cost is not derivable per request, so a unified ledger would be fiction; the remaining-% is pulled from the provider (reversed flow) and the red-line distributed down for local enforcement.
- **LiteLLM per-key budget as enforcement backstop (chosen) vs as primary ledger** — its real role is a hard money-cap safety net behind the service's local cap (ADR-0005 §9), only where routes go through LiteLLM; it is not the accounting source of truth.
- **Three-tier privacy, user-chosen (chosen) vs auto-enforcement routing** — auto-routing around tiers is a hidden behavior the soul forbids; documented tiers + informed manual choice gives the user the decision. Replaces the earlier `default`/`no-retention`/`no-training` vocabulary.

## Consequences

- **Amends ADR-0002** — the per-service privacy-tier vocabulary (`default`/`no-retention`/`no-training`) is replaced by the three-tier data-class taxonomy on each implementation.
- **Sharpens ADR-0005 §9** — the two cloud-spend dimensions are *exclusive per capability* (metered vs opaque subscription); the remaining-% data flow is reversed (provider → core) with the red-line distributed down; LiteLLM's per-key budget is the enforcement backstop, not the ledger.
- **Expands** "Design the integrated UI (dashboard)" (#8 — cloud provider cards, spend/remaining-% gauges, privacy-tier display, preconfigured-provider entry), "Design the composition model" (#13 — provider/tool configuration shape), "Design the capability registry & search/load service" (#20 — privacy tier discoverable in the MCP description), and "List and scope the v1 service catalog" (#18 — Connectors draws tool-leg credentials from the shared vault).
- **Feeds** "Define the security model for the trusted home environment" (#14 — at-rest protection of credential copies), "Design the model management layer" (#4 — distributed local caps consume the accounting), the spec anatomy (#12), and the glossary (CONTEXT.md).
- **Glossary (CONTEXT.md):** inference provider (cloud-gateway implementation), provider registry (leader-core config), privacy tier (three-tier data-class taxonomy), cloud-spend, bundle legs.
