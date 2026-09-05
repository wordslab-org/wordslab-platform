# Data consent and handling

> **Status:** cross-cutting concern, resolved at wayfinder ticket "Design the data consent & handling / GDPR-aware usage-data model (platform core + all services)" (#31). **Source of truth:** ADR-0026, plus the ADRs it consumes/serves: core `datasets` (ADR-0003), per-service dataset-extraction surface (ADR-0002), evaluation (ADR-0020 §5), backup spheres (ADR-0021), assistant role-scoping (ADR-0024 §2), training (ADR-0025 §5). This section cites, never restates; it is the architectural home of the consent model relocated from the superseded spec framing (see also architecture §9.5, "Data spheres, consent, and backup").

## Identity

The **platform-wide, GDPR-aware model for how data may leave one user's private sphere and enter a builder's or admin's sphere, mediated through the core.** Data handling is a first-class, cross-cutting concern, not an afterthought — the platform's soul is **no magic, no black box**: everything manually chosen, visible and explained step by step, for people who want to learn *and* understand AI while **owning their data** and staying **in control**. The three-identities attribution model and the assistant's role-scoped tool access are folded in as given; this concern does not reopen the eval/training/backup/assistant decisions that already rest on it.

**Attribution.** A physical user has **three identities** — `user`, `builder`, `admin` — three **data spheres**, the units of attribution and backup. Data may leave the private (user) sphere and enter a builder's or admin's sphere **only** through the core's mediated boundary. The **generated/verified validation state** of any item is **orthogonal** to these spheres — attribution and validation are independent axes.

## The settlement (the load-bearing boundary this concern designs on)

- **Private user history** is private to its user — access/review/delete on demand, no other user sees it.
- Builders/admins access real usage only **filtered** (secret/private stripped) and **anonymized** (personal data) via the core's mediated boundary — *"better to fail to improve a fix or fix a bug than to expose a life-altering secret."*
- Per-interaction consent **defaults to "may use for improvement."**
- **Anonymization is mandatory before any trace enters a dataset** (GDPR — personal data in a project-repo dataset is illegal in Europe) and must **not** degrade evaluation/training quality.
- Genuinely un-anonymizable cases (e.g. fraud detection on national-ID-card images) are **out of v1 scope** — the user's responsibility to build a proper legal processing pipeline.

## Consent capture (ADR-0026)

- **Per-interaction consent defaults to "may use for improvement."** Every user input — every prompt, and every data/document upload, in **both the platform UI and published artifacts** the user interacts with — carries a **very visible "private/secret — do not use" toggle.** Consent governs what is *eligible* for extraction; extraction itself always applies the filter + anonymize passes below.
- **Granularity of remembering:** consent is **per interaction by default**, but a **user-written preference** may set a **remembered default per surface and per input-type** (e.g. "on Chat, default to private; on Document upload, default to may-use"). A remembered default is an **explicit user-written rule, always visible and overridable on every input** — never a silent heuristic. This keeps the platform usable for non-technical users (the default carries the common case) while the toggle is always one visible gesture away.
- **Revoke-and-delete:** at any time a user may (a) flip a remembered default, (b) **withdraw consent** on any past interaction, and (c) **delete** any past input. Withdrawal **bars that data from future extraction**; the revoke-and-delete story satisfies GDPR's review/delete obligations.

## The single mediated boundary — the core's `datasets` capability (ADR-0003)

The core's **`datasets` capability** is the **single mediated boundary** for data leaving one user's private sphere and entering a builder's/admin's sphere (ADR-0020 §5). **Split ownership:** each service implements its own **dataset-extraction UI/API**, which sends the core `datasets` capability a **standardized dataset file** (a HuggingFace-datasets-like format) that is **already filtered** — the private/secret exclusion is mandatory, regardless of the service's own options — plus any service-specific filters. The **core anonymizes before storing**, records **dataset provenance** (service, date, builder), **centralizes the platform's non-user-related logs**, and **serves/syncs** the stored datasets (to consuming services such as eval/training, and to HuggingFace after anonymization). A service knows its own trace schema best; the core stays the single gate and the single anonymizer.

The two passes are defined precisely:

- **Filter (pass 1) = the consent gate.** Exclude every interaction marked "private/secret — do not use" from any export to builder space. **Only interactions marked "may use for improvement" are eligible to pass.** This filtering is **mandatory whatever happens** — a service may add its own filters (date period, user, samples), but the private/secret exclusion is never bypassable.
- **Anonymize (pass 2) = data replacement, at the core.** Replaces **personal data AND secrets** — names, emails, phones, addresses, and passwords, tokens, API keys, ID-card numbers — performed **by the core's `datasets` capability** before the dataset is stored.

So "filter" is **eligibility** (which interactions may leave the user sphere), and "anonymize" is the **data replacement** that destroys both personal and secret content at the single core boundary.

**v1 scope — text only.** Anonymization is a **text-only capability in v1**; multimodal anonymization (images, audio) is a future version. This is consistent with the out-of-v1-scope rule below: image-based identifying content is genuinely un-anonymizable and is the user's responsibility.

### One line

The filter/anonymize machinery described here **is** the core `datasets` capability (ADR-0003), consumed by eval/training/backup/assistant (ADR-0020 §5, ADR-0021, ADR-0024 §2, ADR-0025 §5).

## GDPR & anonymization quality — mandatory before dataset entry (ADR-0026)

**Anonymization is mandatory before any trace enters a dataset** — even non-secret data, because under GDPR storing personal data in a project-repo dataset is legally "personal data" and triggers the full GDPR apparatus. The quality bar, sharpened:

- **Detect by type** — personal data is found via the declared schema fields / known PII types (the trace data-shape each service declares).
- **Replacement pools per type** — each type (name, email, phone, ID, token…) has a list of replacement values it draws from.
- **Dataset-wide replacement dictionary** — the **same original name/id always maps to the same replacement across the whole dataset** (deterministic, consistent). This is **consistent pseudonymization**: it preserves referential integrity and co-occurrence signal, so cross-record analysis, training, and evaluation still work — which is what keeps quality from degrading.
- **Best-effort = indistinguishability.** The PII-detection rate must be high enough that **when you encounter a name in the output, you cannot tell whether it was replaced or not**. This rules out placeholder-style masking (e.g. `PERSON_1`, `REDACTED`) — a placeholder is *obviously* a replacement, which both leaks the fact of replacement and lets an adversary enumerate the masked set. Replacement pools must therefore be **natural-looking and distribution-matching** (realistic names/emails, not token placeholders), with the dictionary keeping them consistent — making the anonymizer's output **indistinguishable from data that was never anonymized**, the bar GDPR recital-26 pseudonymization and a usable dataset both want.

**Quality is an explained fact, not hidden.** The builder sees what anonymization did — a **transform report** ("replaced 3 emails, 2 phone numbers, 1 API key; 0 items on the private-exclusion list"). The user can judge whether the dataset is safe and useful, and can rerun with different rules. No black box. **Quality is preserved by targeting, not blurring** — replacement is targeted and rule-driven (known PII/schema fields), not wholesale token scrambling: it removes what is *identifying* while preserving the *shape* of the data.

### The hard case — genuinely un-anonymizable capabilities are out of v1 scope

When a demanded capability genuinely can't both anonymize and stay usable — e.g. **fraud detection on national-ID-card images**, where the raw image *is* the identifying content — the platform **refuses to auto-anonymize**, tells the user it needs a **proper, legal processing pipeline**, and does **not** silently degrade. That is the "better to fail to improve a fix or fix a bug than to expose a life-altering secret" principle in action. Out of v1 scope; the user is responsible for building a compliant pipeline.

## The builder sphere is anonymize-free — the boundary holds (ADR-0026)

**Simulated/builder-injected interactions** (eval simulation, testing a deployed service/artifact) run **as the builder identity**, live in the **builder sphere**, and need **no filter/anonymize** — they are synthetic, never personal (ADR-0021; ADR-0025 §5 already rests on this). What keeps it honest:

- **Nothing real-usage (user-sphere) ever enters the builder sphere without passing the core's filter + anonymize.** The two spheres meet **only** at the mediated boundary.
- **No automatic pipeline step** carries user-sphere data into the builder sphere. There is no hidden path.
- A builder **manually pasting** raw user data (their own, or in a small-business setting, a family member's) into a workflow, eval dataset, or prompt is a **user action, flagged as such** — it is entering the builder sphere without passing the boundary. The human owns that choice, but it is **visible**, not silently accepted. **Flag, don't block.**

## The assistant's acting identity — enforced at the callable surface (ADR-0024 §2, ADR-0026)

The continual learning assistant is **literally Hermes Agent**, one workspace/state per physical user, **one identity per session** (user/builder/admin) chosen at launch by which view opened it. Tool access is consent-scoped by the sphere rules: **role=user** → only that user's own data; **role=builder** → only anonymized + non-sensitive builder-sphere data; **role=admin** → only admin data not linked to a user. Enforcement is **structural, not aspirational**:

- The **acting identity rides in the action-context** (ADR-0003: user + service chain crosses every call), set at launch and immutable for the session.
- **The assistant runs in a container with only the user's workspace mounted** — it **cannot explore the host filesystem**. Its **only path to service data is tool calls** through the platform's surfaces.
- **Therefore the services themselves enforce data-access and export rules at the callable surface** (MCP/OpenAPI tool layer). Because the harness literally has no other channel to the data, the tool-layer gate is the **sole inlet** and thus a **real control, not a declaration**: every service API checks the acting identity's sphere before returning data. The "cannot read beyond its acting role" claim is **structurally true**.
- **Any trace the harness produces is attributed to that acting identity** under this consent model (it falls in the same sphere rules).

This is consistent with ADR-0017 (harness = execution authority, platform = backstop): the platform does not claim to police harness internals — it simply **owns the only door the data comes through**. *Action-context carries the acting identity → every service's tool surface checks that identity's sphere before returning data → the container prevents any out-of-band host access.*

## Considered options (ADR-0026)

- **Remembered default per surface/input-type vs evaluate-each-interaction-fresh vs remembered globally** — fresh is maximally private but burdensome; global loses the per-surface nuance. Chose **per interaction by default + a user-written remembered default per surface/input-type**, always visible and overridable — an explicit rule, never a heuristic.
- **Core owns the full per-service anonymization rules vs services declare the trace data-shape** — chose **split ownership**: core owns the boundary + the rule catalog and does the anonymization; each service declares the data-shape/fields its traces carry so filter/anonymize can target them (mirrors ADR-0002's per-service declaration spirit).
- **Placeholder masking vs natural-distribution replacement** — chose the latter, with the **indistinguishability quality bar**.
- **Flag vs block the manual-paste side-channel** — chose **flag, don't block** — the human owns the choice, it's visible.
- **Raw vs anonymized real traces** (already settled by ADR-0020 §5) — confirmed **no raw-traces path**: real input is always the core's filtered+anonymized data.

## ADR cross-references

ADR-0002 (per-service dataset-extraction surface + declared trace data-shape) · **0003 (core `datasets` capability — filter/anonymize machinery, provenance, centralized non-user logs, serves/syncs to HF)** · 0006 (providers + privacy) · 0017 (execution authority) · 0020 §5 (evaluation) · **0021 (backup spheres)** · **0024 §2 (assistant role-scoping / acting identity)** · 0025 §5 (training) · **0026 (this concern's governing ADR — consent, log-extraction, anonymization, assistant sphere gates)**.
