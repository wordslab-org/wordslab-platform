# ADR-0030 — The Connectors service capability surface (connector families, provider implementations, the audited door, guardrails, the v1.1 gateway)

**Status:** accepted (resolution of wayfinder ticket "Design the Connectors service chapter (foundational; consolidate its scattered design)", #41); **creates** `docs/architecture/30-services/38-connectors.md`; **consolidates** the Connectors design scattered across ADR-0003 (shared `secrets`, action-context), ADR-0006 (provider registry, bundles' tool legs), ADR-0007 (tool-backed composition, connector-event trigger), ADR-0008 (connectors→`tool` entries), ADR-0017 (the audited door, guardrails), ADR-0019 (the v1.1 inbound gateway) and CONTEXT.md into one place; **decides the one thing that was genuinely open** — the service's own capability surface; **evolution notes** on **ADR-0017 §7** (consequence tier: connector-level → per-tool), **ADR-0006 §1/§3** and **ADR-0027 §4** (where external-model traffic crosses the boundary); **does not amend** ADR-0001/0002/0003/0004/0007/0008/0009/0015/0016/0019/0022/0024/0026 — it cites them.

> **Evolution note (ADR-0017 §7 — the consequence tier is a per-tool declaration).** §7 tiers connectors as wholes ("read-only connectors (`web` search+fetch, `youtube` watch) are **logged-only**; **send/mutate** connectors (`x`, `github`, `outlook`, `huggingface`) require **human approval**"). This ADR draws that same line — §7's own test, "does data leave the machine / does it send or mutate" — at the **tool**, which is where a call actually happens: every tool declares its tier explicitly. The connectors named send/mutate wholesale all carry read-only operations (`github` reads issues/repos, `outlook` reads mail, `huggingface` searches models), and ADR-0007's `connector-event` trigger ("new email", "new web result") depends on reading being free of approval. §7's semantics are otherwise unchanged: grants stay **caller-identity-scoped, per config**, the dashboard still surfaces the per-call confirm where the consequence warrants it, and harness-native traffic still stays outside the door. §7's decision text is left as its historical record.

> **Evolution note (ADR-0006 §1/§3 and ADR-0027 §4 — external-model traffic crosses the boundary through the door).** Both place the **cloud gateway** as an Inference *engine implementation* fronting external providers, and that shape is unchanged. What this ADR adds is **where its network egress happens**: the gateway's outbound provider calls are **connector-mediated** — they are the model-access families of §2.2 of this ADR — so traffic to external model providers crosses the machine's boundary through the platform's single audited door, logged and guarded like every other crossing, on one credential path. Consequence: ADR-0006 §2's **provider registry row *is* a connector implementation** (§5 below). ADR-0006's bundles/credentials/billing machinery and ADR-0027's one-declaration/dependency rules hold as written.

## Context

Connectors is the platform's **single audited door to the outside world**: everything the platform sends out to, or fetches in from, an external system passes through it. #34 named it one of the nine **foundational (detailed)** service chapters (ADR-0028 §3/§6) precisely because it carries the platform's security posture — and because its design, unlike most services', had **no dedicated ADR**: its decisions were scattered.

When this ticket opened, the scattered state was:

| Home | What it settled |
|---|---|
| ADR-0017 §7/§8 (+ `20-concerns/21-security.md`) | the audited door: every call logged + attributable; tiered by consequence; caller-identity-scoped approval; harness-native traffic outside the door; guardrails at both boundaries |
| ADR-0019 §9 (+ the #37 ledger) | inbound exposure: **v1 = LAN + private-mesh overlay**; the public gateway is **v1.1** and "is the **Connectors service's network gateway**", implementing ADR-0017's TLS + edge-auth |
| ADR-0006 §2/§3/§4 | provider registry rows; **a bundle's tool leg registers as a tool and executes via Connectors**; one credential vault for provider *and* connector credentials |
| ADR-0003 | the core `secrets` capability is the single master copy; the action-context header makes outbound calls attributable |
| ADR-0008 §"Connectors bring `tool` entries" | connectors register **`tool` entries only**; the naming example `connectors.web.search` |
| ADR-0007 | `event(...)` waits on a **connector event**; `connector-event` is a v1 trigger |
| ADR-0001 family 3 + ADR-0002 §3 | stateless MCP at `/mcp`; the three callable surfaces (human / agent / deterministic) |
| CONTEXT.md | the v1 connector list (web · x · outlook · youtube · github · huggingface), the post-v1 seed catalog, the gateway timing |

What that set did **not** settle is the service's own **capability surface** — the thing a chapter must state before it can be written, and which no ADR was authorized to state for it. That is this ADR's decision; everything else it organizes and cites.

The soul governs: **no magic, no black box** — the user sees which external system is reached, by which backend, with whose credential, under whose approval, and what left the machine.

## Decision

### 1. The service is the single audited door

The Connectors service is the one place where data crosses the machine's boundary under the platform's own control. Its identity is negative and precise: **no other platform component reaches an external system on the user's behalf.** The platform's own software supply-chain downloads (pip, model weights, the update machinery) are not connector calls; a harness's native outbound activity is not either (ADR-0017 §7.4). What Connectors owns is **every platform-mediated call to an external service** — and, since §5 below, that includes the cloud model paths.

The service is a base-contract service like any other: its own UI, one auth, one `/health`, one `/api` (OpenAPI), one `/mcp`, one database — and its capability list, which is what this ADR settles.

### 2. The capability surface: a capability names the *kind*, an implementation names the *platform*

The Connectors service's capabilities divide into three roles — **tool families** (agent- and workflow-callable tools), **model-access families** (the egress paths for external model providers), and **management capabilities** (the door's own control surfaces).

The naming invariant, applied uniformly:

> **A capability names the *kind* of external system; an implementation names the *actual platform*.**

This is what makes a new platform cheap (a new `implementation.toml`) and a new *kind* of external system a service-level addition (a new capability, §2.5).

#### 2.1 Tool families

Each tool family exposes its tools to the registry as `tool` entries (§8), for agents, workflows and published things.

| Capability | v1 implementations | post-v1 implementations |
|---|---|---|
| `connectors.web` | brave · tavily · searxng · **a provider bundle's tool leg** | — |
| `connectors.codeplatform` | github | gitlab |
| `connectors.socialplatform` | x | instagram · discord · feishu |
| `connectors.email` | outlook | gmail |
| `connectors.videoplatform` | youtube | vimeo |
| `connectors.modelhub` | huggingface | modelscope |

Three further families are **named now and unimplemented** — they are CONTEXT.md's post-v1 seed catalog, given a stable name so the seed list lives in one place: `connectors.browser` (browser automation), `connectors.smarthome` (home assistant), `connectors.music` (spotify).

A **provider bundle's tool leg** (ADR-0006 §4) lands here with no special machinery: it is an **implementation of the connector family its leg belongs to** — a bundle offering web search is a `connectors.web` implementation whose `source` is the provider ref, and the one subscription credential covers it (ADR-0006 §4/§5).

#### 2.2 Model-access families — the egress paths for external model providers

External model access crosses the boundary through the door too, so it needs families. They reuse the **paradigm/task names of the Inference service's model capabilities** (ADR-0029 §1), without the `.model` suffix — Inference's `.model` says "the model itself"; here the thing named is the *door to a provider*:

| Capability | "implementations" = the providers |
|---|---|
| `connectors.llm` | openrouter · openai · anthropic · nous · an OpenAI-compatible custom endpoint (ADR-0006 §3) |
| `connectors.diffusion` | fal · openai · … |
| `connectors.ml` | … |
| `connectors.stt` · `connectors.tts` · `connectors.embeddings` · `connectors.rerank` | only where a real cloud provider exists for that task |

An implementation of a model-access family **is** a provider: `source = cloud:<provider>`, an `api_key` ref into the `secrets` vault, enabled modalities, a **privacy tier** and a bundle flag — i.e. **ADR-0006 §2's provider row**. These families register **no** entries (§8) and expose no agent tools: agents call models through the Inference service (ADR-0007 §2), not by reaching past it.

#### 2.3 Management capabilities

| Capability | Owns |
|---|---|
| `connectors.audit` | the **audit trail** (every connector call, attributable via action-context) and the **approval grants** (caller-scoped, per connector, per config) |
| `connectors.guardrails` | the data-safety layer at both boundaries (§4) |

Both are management capabilities: a human/administrative surface (UI + OpenAPI), **no tool entries** — an agent must not be able to manage its own approvals or its own guardrails. `connectors.audit` is the "what left the machine, and who approved it" view of ADR-0017 §7.5; `connectors.guardrails` is that ADR's §8 layer, placed.

#### 2.4 The inbound gateway — named, deferred to v1.1

| Capability | Status |
|---|---|
| `connectors.gateway` | **v1.1** — the public-internet gateway for published things |

ADR-0019 §9 already settles both the timing and the owner: v1 exposes published things on the LAN front door + a private-mesh overlay; the public "anyone with the link" gateway is **v1.1**, and when it lands **it is the Connectors service's network gateway**, implementing ADR-0017's browser-aware TLS + edge-auth — not a new security model. The #37 deferral ledger carries it as a deferred row. This ADR gives it its **name and its home** so the service's surface is complete on paper; its design is v1.1 work, and the exposure side stays with the Publishing & Governance service (`30-services/39`).

#### 2.5 Naming, conformance, and what a new connector costs

- **Tool names are `<service>.<capability>.<tool>`** — closing the shape ADR-0008 §"Stable name" left implicit at the third level: `connectors.web.search`, `connectors.web.extract`, `connectors.web.ask`, `connectors.codeplatform.pr_create`, `connectors.email.send`, `connectors.socialplatform.post`. ADR-0008's written example `connectors.web.search` **stays valid unchanged**, because `web` is a family name under this scheme.
- **A capability's tool set is the union of its implementations' tools**, with a documented per-implementation support matrix and documented deviations — ADR-0004's conformance rule, applied here rather than reinvented. `connectors.codeplatform` declares the tool contract; github and gitlab each support a documented subset; a capability with a single implementation simply has a full matrix.
- **Cost of extension, deliberately asymmetric:**
  - **a new platform** for an existing kind (gitlab, gmail, instagram, modelscope) = a new **`implementation.toml`** — the cheap, community-friendly contribution tier (ADR-0018 §two tiers).
  - **a new kind** of external system = a **new capability added to the Connectors service** — the heavier service-level contribution, because the audited door's semantics (tiering, logging, guardrails, approval) must wrap every connector identically and no third-party code may sit inside that wrapper.
- **A connector family declares whether it produces events** (§7) and **whether it is read-only or send/mutate per tool** (§3) in the same place it declares its tools.

### 3. The audited door: a per-tool tier, caller-scoped grants, request-path enforcement

1. **Every tool declares its consequence tier explicitly — there is no default.** `read-only` tools are **logged-only**; `send/mutate` tools require **human approval** (ADR-0017 §7.2, granularity per the evolution note above). A tool cannot inherit a tier by omission: the declaration is required, so "nothing declares this, so nothing is gated" cannot happen.
2. **Grants are caller-identity-scoped and never platform-wide.** The grant rides the action-context (user + service chain) and is checked against **that caller**: approving github for user A does not let agent B, or another workflow under A, post without its own approval (ADR-0017 §7.3, unchanged). Approvals are configured **per connector**, so one grant on `connectors.codeplatform` covers that connector's send/mutate tools.
3. **Enforcement is a service-level layer in the request path.** Every connector call passes through it — the layer is what makes this *a door* rather than an opt-in wrapper, and it is why the tier is not merely documentation. The registry gates **discovery** only (ADR-0008 §5: "once an agent is granted a tool, the tool's own service still applies its own auth/approval").
4. **Harness-native outbound stays outside the door** (ADR-0017 §7.4): a harness's own package/network activity is the agent doing its job, bounded by the container network policy. The audit trail covers **connector-mediated** outbound; the network policy covers the rest. The accepted cost stands: no unified accept/refuse trail across harnesses.
5. **Model-access families are `read-only` (logged-only), never send/mutate.** The consent that a prompt leaves the machine is the **privacy tier** of the model implementation the caller chose — ADR-0006/0007 already settle that choosing an implementation *is* the privacy decision. Gating every inference call behind a human approval would be unusable, and a security layer users switch off is theater.
6. **The trail is visible.** `connectors.audit` exposes what left the machine and who approved it; the dashboard renders it co-located with each connector's configuration (ADR-0015 §7, `20-concerns/26`) and in the activity view.

### 4. Guardrails — placed, both directions, cheap in v1

`connectors.guardrails` is ADR-0017 §8's data-safety layer, placed at the door:

- **Outbound** — filter/anonymize what a call carries out, so private/personal data does not leave the machine through a connector (and, by §5, not through a cloud model path either).
- **Inbound** — screen what comes back (web content, mail, fetched documents) against **prompt injection** before it reaches an agent's context.

V1 is deliberately **one boundary check each way**, implemented with an **explicitly chosen model implementation** — a trained classifier, an entity-extraction model, or a very small LLM, whatever is light enough to run in-line (ADR-0017 §8: the cost ceiling is the constraint, not the technique). It is **on by default, visible, and adjustable**; any interception is **surfaced with its reason, never silently filtered**. The Shieldstral-class heavy tier stays optional and off by default. More sophisticated filtering is a later, visible upgrade of the same capability — not a hidden behaviour change.

### 5. External-model egress: the chain, and what a provider row is

Two settled shapes, joined (see the ADR-0006/ADR-0027 evolution note):

```
cloud model implementation        llm.model · source = cloud:<provider>/<model>     (ADR-0027 §4)
        ↓ depends on
cloud-gateway engine implementation   llm.engine · protocol translation + billing adapters   (ADR-0027 §4/§5)
        ↓ egresses through
connector model-access implementation  connectors.llm · implementation = <provider>   (§2.2)
```

- **ADR-0027's declaration and dependency rule is untouched**: a cloud model is a model implementation that depends on the cloud-gateway engine implementation. The gateway keeps its job — uniform protocol translation, billing-mode adapters (ADR-0006 §6), per-key budget backstops — and gains one: **its outbound calls go through the door**.
- **ADR-0006 §2's provider registry row *is* a connector implementation.** Same fields, one home: `id`, `base_url`, `api_key` ref into `secrets`, enabled modalities, privacy tier, bundle flag. Adding a provider is still "adding a row, not code" — and the row now has a nameable place in the architecture.
- **One credential path for everything that leaves**: the core `secrets` vault already holds provider **and** connector credentials as a single master copy (ADR-0003, ADR-0006 §5). §5 makes that a structural fact rather than a coincidence.
- **The action-context header is still stripped before any third-party call** (ADR-0004 §10, ADR-0006 §5).

### 6. Credentials — consolidated, not re-decided

No new decision. The core's **`secrets` capability is the single master copy** for provider and connector credentials (ADR-0003, ADR-0006 §5); distribution is push + pull-on-start with eventual consistency; keys are added/rotated/revoked **co-located at each connector's own configuration** in the dashboard (ADR-0015 §7); at-rest protection is **light obfuscation with the real defense in short credential lifetimes** (ADR-0017 §4). A connector implementation declares its credential ref; it does not invent a second vault.

### 7. Events are part of the capability's OpenAPI interface

A capability that emits information-system events **declares them as part of its OpenAPI interface** — the ordinary deterministic surface (ADR-0001/0002 §3), not a special Connectors mechanism. The connector families are simply the v1 capabilities that do: `connectors.email` ("new message"), `connectors.web` ("new result for a saved query"), `connectors.codeplatform` ("new issue/PR"), each documented per implementation under ADR-0004's support-matrix rule (a provider that can neither poll nor subscribe records that it emits nothing).

- **Delivery reuses family 8's HMAC webhooks** — no event bus is invented; the subscriber's endpoint is authored where subscriptions are authored, and the **consuming** side (`event(...)`, `connector-event` triggers, run semantics) belongs to ADR-0007 and the Workflow service chapter (#43), not here.
- **Events are event-shaped, not content-shaped**: enough to identify what happened and where to fetch it. The payload's content is retrieved through a **normal, audited connector call**, so events cannot become a second, unlogged egress path — the same discipline as ADR-0017 §7.4.

### 8. Registry presence

The Connectors service touches the capability registry (ADR-0008) in exactly one way: **its tool families register `tool` entries**, one per exposed tool, named per §2.5, with the privacy label of the implementation that will serve the call. The model-access families register nothing (models are never registry entries, ADR-0008); `connectors.audit` and `connectors.guardrails` register nothing (management surfaces). ADR-0008's rule stands unamended — and §2 of this ADR does not add an entry type.

### 9. Data consent — a pointer, and one distinction

Connectors does not own consent language; the model is ADR-0026's (`20-concerns/24-data-consent.md`):

- A connector call is an **interaction carrying the consent flag**; the "private/secret — do not use" toggle rides the surface that triggers or ingests it. Any export goes through the service's own consent gate and the core `datasets` anonymize.
- The **audit trail is raw, user-sphere, per-service** — never a Document bundle or a `data_source` — and builder/admin reach it only through the core's filter + anonymize (#39's settled rule, ADR-0026/0003).
- **One distinction worth writing down, because readers conflate them:** `connectors.guardrails` is **data-safety at the boundary** — what may physically cross, at the moment it crosses. Consent is **reuse of usage data** — what may be kept and reused afterwards. Two different questions; a call can pass one and fail the other.

### 10. The v1 / v1.1 boundary

- **v1** = the six implemented tool families + the model-access families + `connectors.audit` + `connectors.guardrails`. **No inbound path at all**: inbound exposure in v1 is entirely Publishing's (LAN front door + private-mesh overlay, ADR-0019 §9).
- **v1.1** = `connectors.gateway` (the public-internet gateway), implementing ADR-0017's TLS + edge-auth stance.
- The three seed families (`browser`, `smarthome`, `music`) are named, unimplemented, and not scheduled here.

### 11. Build order

ADR-0009's order already schedules **Connectors(web)** early — after Document(parse), before Development — and **Connectors(rest)** later, after Knowledge. Cited, not changed: the web family is what the learning path reaches first (an agent that can look something up), the rest arrive with the services that consume them.

## Considered options

- **Capability per connector vs capability per connector *kind* + implementation per platform.** Naming a capability after the product (`connectors.github`, `connectors.x`, `connectors.outlook`) makes every new platform a service change and hides the fact that a user's choice is *which platform* they reach. Naming the kind (`codeplatform`, `socialplatform`, `email`, `videoplatform`, `modelhub`) and the platform in the implementation keeps one invariant, keeps `connectors.web.search` from ADR-0008 valid, and makes gitlab/gmail/modelscope cheap. Chose kind + implementation.
- **Connectors as monolithic capabilities with the backend switched internally** vs **backend as a declared implementation.** Internal switching is less to write but puts a hidden choice in the request path: the user could not see which search backend ran, and a bundle's tool leg would have no declared home. ADR-0007's explicit-implementation-choice rule argues the other way. Chose declared implementations.
- **Consequence tier per connector vs per tool.** Per-connector is simpler to state but over-asks (approval to read a public repo) and would break the `connector-event` triggers that depend on reading being free. Per-tool is the granularity ADR-0017's own test implies. Chose per-tool, declared explicitly, no default.
- **The audited door's surface as service-level code vs a capability.** ADR-0002 §"Capabilities" leaves no API outside a capability (the same reasoning that produced Inference's `models` capability), and the trail and the grants are two views of one door. Chose `connectors.audit`.
- **Trail on the base log surface only vs its own capability.** `GET /v1/logs` (ADR-0001 base) is the raw per-service log; "what left the machine, who approved it" is an attributable-outbound view that must join calls to grants. Chose a capability over a reader-side join across two surfaces.
- **Guardrails as a cross-cutting platform layer vs a Connectors capability.** A platform-wide layer would have to sit in every boundary service's request path anyway (the core cannot: ADR-0003 forbids the core in the request path), so the honest v1 home is where the boundary is. Chose `connectors.guardrails`, connector-scoped; wider placement is a later, separate concern.
- **External model traffic bypassing the door (engine-only egress) vs going through it.** Engine-only egress leaves the biggest outbound data flow outside the platform's audit and guardrail story — the one crossing the user most wants to see. Chose the door, with the gateway's job unchanged and one extra hop in the chain.
- **Events as their own mechanism vs part of the OpenAPI interface.** A dedicated event surface would be a new contract concept for one need already served by the deterministic surface + family 8's webhooks. Chose OpenAPI + webhooks.
- **Naming the v1.1 gateway now vs leaving it unnamed.** Naming it costs a table row and removes the ambiguity about where the gateway lives when v1.1 arrives; leaving it unnamed invites the next session to invent a second home. Chose to name it, defer it, and point the exposure side at Publishing.

## Consequences

- **Creates this ADR and `docs/architecture/30-services/38-connectors.md`** (this ticket's deliverable); the README catalog flips service #38 from *pending* to *written*.
- **The Connectors service's capability surface is settled**: tool families `connectors.web` · `.codeplatform` · `.socialplatform` · `.email` · `.videoplatform` · `.modelhub` (+ seed `browser` · `smarthome` · `music`); model-access families `connectors.llm` · `.diffusion` · `.ml` (+ task-shaped where a provider exists); management `connectors.audit` · `connectors.guardrails`; `connectors.gateway` (v1.1).
- **Evolution notes recorded** (no silent rewrites): ADR-0017 §7 (tier granularity), ADR-0006 §1/§3 and ADR-0027 §4 (egress through the door; a provider row is a connector implementation).
- **No dangling references from the rename**: ADR-0008's and `10-concepts/14-composing.md`'s written example `connectors.web.search` remains correct, because `web` is a family name.
- **CONTEXT.md's "Connectors service" entry is rewritten** — families × implementations, the tool-name shape, `connectors.audit` / `connectors.guardrails` / `connectors.gateway`, and the connector list re-expressed as kinds (the old "web (search + fetch)" becomes `search` / `extract` / `ask`).
- **`docs/prototypes/dashboard-flow.md` is deliberately left untouched** — it is a historical design record and its connector key list is illustrative; `20-concerns/26-dashboard.md` needs no change (it names no connectors).
- **Deliberately not decided here**: the detailed per-capability tool inventories and per-implementation support matrices (service design, at build time); the v1.1 gateway's design; the wider placement of guardrails beyond the connector boundary.
- **No new tickets are spawned by this resolution**: the gateway is v1.1 (already in the #37 ledger), events are part of the OpenAPI interface (no contract change), and consent/credentials/registry placement are all pointers.

## References / feeds

- **Consolidates** ADR-0003 (`secrets`, action-context) · ADR-0006 (provider registry, bundles' tool legs, credential vault) · ADR-0007 (tool-backed composition, `connector-event` trigger) · ADR-0008 (connectors → `tool` entries, naming) · ADR-0017 §7/§8 (the audited door, guardrails) · ADR-0019 §9 (the v1.1 gateway) · CONTEXT.md.
- **Evolution notes on** ADR-0017 §7 (per-tool consequence tier), ADR-0006 §1/§3 and ADR-0027 §4 (connector-mediated egress; provider row = connector implementation).
- **Cites** ADR-0001 (base + family contracts) · ADR-0002 (template, capabilities, callable surfaces) · ADR-0004 (conformance = union of implementation variants) · ADR-0009 §7 (Knowledge's outbound via Connectors) · ADR-0015 §7 (`20-concerns/26`) · ADR-0016 (versioning, declared dependencies) · ADR-0018 (contribution tiers) · ADR-0022 (license facts per implementation) · ADR-0024 (learning bar) · ADR-0026 (`20-concerns/24`) · ADR-0029 (Inference's model-capability names, reused by §2.2).
- **Feeds** `docs/architecture/30-services/38-connectors.md`, CONTEXT.md, and the sibling chapters that consume the door (#43 Workflow's `connector-event` triggers, #44 Development).