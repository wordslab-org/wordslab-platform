# 38 — Connectors

> **Status:** written at the resolution of wayfinder ticket "Design the Connectors service chapter (foundational; consolidate its scattered design)" (#41). **Source of truth:** ADR-0030 (this service's capability surface — the connector families, provider implementations, the audited door, guardrails, the v1.1 gateway), ADR-0017 §7/§8 (the audited door and the guardrail layer), ADR-0006 (provider registry rows, bundles' tool legs, the shared credential vault), ADR-0003 (`secrets`, action-context), ADR-0008 (connectors → `tool` entries), ADR-0007 (connector events), ADR-0019 §9 (the v1.1 inbound gateway). This chapter is the **organized build-view** — it cites, never restates. For the security concern as a whole see `20-concerns/21-security.md`; for what may be done with usage data, `20-concerns/24-data-consent.md`.

## Identity

**The Connectors service is the platform's single audited door to the outside world** (ADR-0030 §1). Everything the platform sends out to, or fetches in from, an external system passes through it — the user's own applications as much as the public web. It is the one place where data crosses the machine's boundary under the platform's own control.

Its identity is negative and precise: **no other platform component reaches an external system on the user's behalf.** The platform's own software-supply downloads (pip, model weights, the update machinery) are not connector calls, and a harness's native outbound activity is not either (ADR-0017 §7.4). What Connectors owns is every **platform-mediated** call to an external service — including, since ADR-0030 §5, the calls to external model providers.

That is why it is a **foundational (detailed)** chapter (ADR-0028 §3): it carries the platform's outbound security posture, and its design — previously scattered across ADR-0003/0006/0007/0008/0017/0019 — is consolidated in **ADR-0030**.

## User guide

### What the user sees and does

- **Connecting an account** (Administrator/Builder): each connector appears in the dashboard **with its own configuration** — credential add/rotate/revoke, what it is used for, and its approval settings, all co-located (ADR-0015 §7). There is no detached secrets page and no hidden backend choice: the **implementation** serving the connector (which provider, which search backend) is visible and chosen, like a model (ADR-0030 §2).
- **Approving a send** (User/Builder): a read-only call just happens and is logged; a **send/mutate** call asks for approval, and the grant is scoped to whoever asked — approving something for yourself does not silently authorize another agent or workflow (ADR-0017 §7.3).
- **Seeing what left the machine** (everyone, own activity; Administrator, everything): the audit trail shows every connector call with who asked, which agent or workflow chain asked, and who approved it.
- **Using managed credentials**: the user never pastes a key into a connector — the credential comes from the platform's `secrets` vault, and the same key serves the provider's model legs and tool legs (ADR-0006 §4/§5).

### Representative use cases

1. **"Have my agent look something up on the web"** (Builder) — an agent searches, extracts a page, or asks a question of the web through `connectors.web`, whose implementation (brave / tavily / searxng / a subscription's own search tool) is visible in the tool's description. Supporting: ADR-0030 §2.1/§2.2, registry `tool` entry (ADR-0008).
2. **"Do something when a new mail arrives"** (Builder) — `connectors.email` emits a *new message* event; a Workflow run starts from the `connector-event` trigger and reads the message through a normal, audited connector call. Supporting: ADR-0030 §7, ADR-0007 (triggers).
3. **"Post something to X"** (Builder) — the call needs an approval that names *this* caller; the same agent posting as someone else needs its own grant. Supporting: ADR-0030 §3, ADR-0017 §7.3.
4. **"Use the search tool that came with my subscription"** (Builder) — a provider bundle's tool leg is simply another implementation of `connectors.web`; the subscription is one card, one credential, and "what leaves the machine" reports per subscription (ADR-0006 §4).
5. **"Call a hosted model from my app"** (Builder) — the model is a cloud implementation of an Inference capability; its traffic leaves through `connectors.llm` and is logged and guarded like every other crossing, under the **privacy tier** the user chose with that model. Supporting: ADR-0030 §2.2/§5, ADR-0006, ADR-0007.
6. **"Stop personal data from leaving by accident"** (Administrator, on by default) — `connectors.guardrails` screens what goes out and what comes back, surfaces every interception with its reason, and is adjustable — never a silent filter (ADR-0017 §8).
7. **"See everything that left my platform this month"** (Administrator) — `connectors.audit`'s trail, rendered in the dashboard.
8. **"Give a colleague's app a public link"** (Builder, **v1.1**) — the public-internet gateway is `connectors.gateway`; in v1 the same need is met by the overlay share (Publishing).

## Reference

### The capability surface: a capability names the *kind*, an implementation names the *platform*

ADR-0030 §2 settles the invariant: **a capability names the kind of external system; an implementation names the actual platform.** Adding a platform is a new `implementation.toml` (cheap, community-contributable); adding a *kind* of external system is a new capability on this service (heavier, because the audited door's semantics must wrap every connector identically).

- **Tool families** (agent/workflow-callable; they register `tool` entries): `connectors.web` (brave · tavily · searxng · **a provider bundle's tool leg**) · `connectors.codeplatform` (github; gitlab) · `connectors.socialplatform` (x; instagram · discord · feishu) · `connectors.email` (outlook; gmail) · `connectors.videoplatform` (youtube; vimeo) · `connectors.modelhub` (huggingface; modelscope). Three further families are **named, unimplemented** (the post-v1 seed catalog): `connectors.browser` · `connectors.smarthome` · `connectors.music`.
- **Model-access families** — the egress paths for external model providers: `connectors.llm` · `connectors.diffusion` · `connectors.ml`, plus the task-shaped set where a real provider exists. **An implementation here *is* a provider** — ADR-0006 §2's provider row (`base_url`, credential ref, modalities, privacy tier, bundle flag), one home instead of two. These expose no agent tools: agents call models through the Inference service (ADR-0007 §2).
- **Management capabilities**: `connectors.audit` (the trail + the approval grants) and `connectors.guardrails` (both directions). No tool entries — an agent must not manage its own approvals or guardrails.
- **`connectors.gateway`** — the v1.1 inbound gateway (§ v1 and v1.1 below).
- **Tool names are `<service>.<capability>.<tool>`** — `connectors.web.search` / `.extract` / `.ask`, `connectors.codeplatform.pr_create`, `connectors.email.send`. ADR-0008's written example `connectors.web.search` is unchanged by the kind/implementation split.
- **A capability's tool set is the union of its implementations'** tools, with a documented per-implementation support matrix (ADR-0004's conformance rule, applied — not reinvented).

### The audited door

- **Every tool declares its consequence tier explicitly; there is no default.** `read-only` tools are logged-only; `send/mutate` tools require human approval. A tool cannot fall through an omission into being ungated (ADR-0030 §3).
- **Grants are caller-identity-scoped**, never platform-wide: the grant rides the action-context (user + service chain) and is checked against *that caller*; approvals are configured per connector (ADR-0017 §7.3).
- **Enforcement lives in the request path**, as a service-level layer — that is what makes this a door and not a documented intention. The registry gates discovery only (ADR-0008 §5).
- **Harness-native outbound stays outside the door**, bounded by the container network policy (ADR-0017 §5/§7.4); the audit trail covers connector-mediated outbound, and the accepted cost — no unified accept/refuse trail across harnesses — stands.
- **The model-access families are `read-only`** — the privacy tier of the chosen model is the consent, not a per-call approval (ADR-0030 §3.5).

### Guardrails

`connectors.guardrails` is the data-safety layer **at both boundaries** (ADR-0017 §8): **outbound**, filter/anonymize what a call carries out; **inbound**, screen retrieved content (web, mail, fetched documents) against **prompt injection** before it reaches an agent's context. V1 is deliberately one boundary check each way, using an **explicitly chosen model implementation** (classifier / entity-extraction model / very small LLM — the cost ceiling is the constraint). It is **on by default, visible and adjustable**, and **never silently filtered**: every interception is surfaced with its reason. The heavy Shieldstral-class tier stays optional and off by default.

### External model access through the door

The chain keeps ADR-0027's shape and gains one hop:

`llm.model` (source = `cloud:<provider>/<model>`) → depends on the **cloud-gateway engine** (protocol translation, billing adapters — unchanged) → **egresses through** `connectors.llm`'s provider implementation (ADR-0030 §5).

So the biggest outbound data flow the user has — prompts going to a hosted model — is on the same audit and guardrail path as everything else, and the action-context header is still stripped before any third-party call (ADR-0004 §10).

### Credentials

No second vault: the core's **`secrets` capability is the single master copy for provider *and* connector credentials** (ADR-0003, ADR-0006 §5), distributed push + pull-on-start with eventual consistency; keys are added/rotated/revoked **co-located with each connector's configuration** (ADR-0015 §7); at-rest protection is deliberately light with the real defense in **short credential lifetimes** (ADR-0017 §4). A connector implementation declares its credential ref — nothing more.

### Events

A capability that emits information-system events **declares them as part of its OpenAPI interface** (ADR-0030 §7) — the ordinary deterministic surface plus **family 8's HMAC webhooks** for delivery. The connector families are the v1 capabilities that do: `connectors.email` ("new message"), `connectors.web` ("new result for a saved query"), `connectors.codeplatform` ("new issue/PR"), documented per implementation. Events are **event-shaped, not content-shaped**: the content is fetched by a normal, audited call, so events never become a second unlogged egress path. What a subscriber *does* with an event belongs to ADR-0007 and the Workflow chapter (33).

### Registry presence

One way in: the **tool families register `tool` entries** (one per exposed tool, named per the grammar above, carrying the privacy label of the serving implementation). The model-access families register nothing (models are never registry entries, ADR-0008); the management capabilities register nothing. No entry type is added.

### Data consent

Pointers only, because consent is its own concern (`20-concerns/24-data-consent.md`, ADR-0026): a connector call is an **interaction carrying the consent flag**; the **audit trail is raw, user-sphere, per-service** and builder/admin reach it only through the core's filter + anonymize (#39's rule). One distinction to keep: **guardrails are data-safety at the boundary — what may physically cross; consent is reuse of usage data — what may be kept and reused afterwards.** A call can pass one and fail the other.

### v1 and v1.1

- **v1**: the six implemented tool families + the model-access families + `connectors.audit` + `connectors.guardrails`, with **no inbound path at all** — inbound exposure in v1 is entirely the Publishing & Governance service's (LAN front door + private-mesh overlay, ADR-0019 §9). ADR-0009's build order puts **Connectors(web) early** and **Connectors(rest)** after Knowledge.
- **v1.1**: `connectors.gateway`, the public-internet gateway for published things — the same service's network gateway, implementing ADR-0017's browser-aware TLS + edge-auth, not a new security model (ADR-0019 §9; deferred row in `20-concerns/27`).

### ADR cross-references

**ADR-0030 (this chapter's governing ADR — the capability surface, the door's granularity, guardrails, the gateway)** · ADR-0017 §7/§8 (audited door: logging, per-tool tier, caller-scoped approval, harness traffic outside; guardrails) · ADR-0006 (provider registry rows, bundles' tool legs, credential vault, privacy tiers, billing) · ADR-0003 (`secrets` master copy, action-context) · ADR-0008 (connectors → `tool` entries, naming) · ADR-0007 (tool-backed composition, `connector-event`, explicit implementation choice) · ADR-0004 (conformance = union of implementation variants; layer-2 implementations) · ADR-0002 (service, capabilities, callable surfaces, template) · ADR-0001 (base + family contracts, family 8 webhooks) · ADR-0015 §7 / `20-concerns/26` (co-located config and keys, dashboard surfaces) · ADR-0019 §9 / `30-services/39` (inbound exposure; the gateway's timing) · ADR-0026 / `20-concerns/24` (consent, filter, anonymize) · ADR-0027/0029 (implementation declarations; the Inference model-capability names reused by the model-access families) · ADR-0016 (versioning, declared dependencies) · ADR-0018 (contribution tiers) · ADR-0022 (license per implementation).