# ADR-0022 — The platform's component license policy (cross-cutting Foundations principle)

**Status:** accepted (resolution of wayfinder ticket "Define the platform's component license policy", #23); **amends none**; **sharpens ADR-0018** (the quality bar's license check now has a concrete policy) and **ADR-0019** (a published thing's license is a compliance fact with defined handling); **creates** the `00-overview.md` Foundations chapter (with ADR-0017's security principle); **feeds** "Design the Training service" (#30 — training/synthetic-data/fine-tune operations are gated by model-license terms) and the "data consent & handling" model (#31 — model-license compliance facts surface alongside usage consent); **references but does NOT resolve** #28, #29, #30, #31.

## Context

The soul fixes the platform as a **100% open-source** system for a non-technical audience: *"OSS components and models only"*. The standing requirement (registered while resolving "Design the multi-machine topology", #6 / ADR-0004 §12) states: every library and model used by the platform must have a **clear open-source license**; revenue-threshold restrictions are acceptable (e.g. "< $10M/month"); **nothing without a clear license or with commercial use forbidden**.

But "OSS only" is not a single uniform rule. It resolves differently across four distinct kinds of things the platform touches, and the soul itself creates a tension: the **platform's own stack is strictly open**, yet the platform exists to **teach people to build** — and a builder may legitimately want to keep a creation proprietary, license it freely, or share it openly. Prior tickets have already sketched this shape: ADR-0018's community-catalog quality bar includes a license check (→ #23), ADR-0019 treats a published thing's license as a compliance fact (→ #23), ADR-0008/0017 carry license tags in the registry and the supply-chain bar, and research (`research/model-serving.md`, `research/non-llm-serving.md`) flagged the **non-commercial model landmines** — model weights have licenses that are *not* standard OSI software licenses and need their own treatment.

This ticket settles the policy: which license families are acceptable for each kind of thing, how the audit is recorded and kept current, and who decides edge cases. Per ADR-0013 §2/§6, license (like security) is a **cross-cutting principle that lives in `00-overview.md` Foundations — not a separate chapter**. That chapter has been deferred until both cross-cutting principles (security, ADR-0017; license, this ADR) were resolved; this ticket creates it.

## Decision

### 1. One policy, four kinds, per-kind rules

The license policy is a **single coherent stance** applied across four kinds of things, with rules that differ per kind because what each thing *is* differs:

- **(a) Platform components** — the community-catalog review bar (ADR-0018): what license a listed/bundled service or implementation may carry.
- **(b) Models / implementations** — model *weights* have non-OSI licenses (revenue-threshold, non-commercial, research-only) that need their own treatment.
- **(c) Vendored OSS UIs / heavy dependencies** — proven OSS front-ends and engines (Open WebUI, code-server, JupyterLab, Arize Phoenix, ComfyUI, MAF harness images, Ollama, llama.cpp, LiteLLM, DocETL) vendored as separate processes, each with its own license — some copyleft.
- **(d) Published things** — what a builder's published app/API/agent/tool may be licensed as, and how it is surfaced as a compliance fact.

The through-line: **the platform's own components have a strict open bar; a builder's published things have a permissive-but-expressible policy; and every use must be compliant with the licenses involved.** Nothing is blanket-banned; everything must be used in a way its license permits.

### 2. Platform components — three computed tiers, per-tier rules

Component license rules map onto ADR-0018's **computed review-status levels** (`bundled` / `listed` / `third-party` — status is derived from where the code lives, never declared). Each tier has a different bar:

- **`bundled`** (implemented in the `wordslab-platform` repo itself, ships with the platform): must be **open source**, and its license must keep **the platform repo itself shippable as Apache-2.0** (the org's own license, `github` skill). A **copyleft** component (e.g. GPL-3.0) is therefore acceptable **only if its use does not contaminate the platform's own code** — i.e. it is a **separate process**, never forked, embedded, or linked into the platform's source. (Research #17's stance: ComfyUI GPL-3.0 behind a thin MIT bridge is fine; embedding/forking it would not be.) This is the strictest bar.
- **`listed`** (implemented in another repo, referenced in the official catalog): every dependency must have a **clear license and be open**, and the **contribution repo's license must be consistent with its dependencies' licenses**. **No Apache-2.0 requirement** at this tier — a listed component may be GPL/AGPL/MPL or permissive, provided the whole dependency graph is open and consistently licensed.
- **`third-party`** (implemented elsewhere, not referenced by the official catalog, not reviewed): the platform can only **recommend** the listed-tier rules; it **cannot enforce** them. Such entries carry the "unreviewed" attribution (ADR-0018 §5) and a visible license declaration.

**Rejection rule (all tiers of the platform's own stack):** reject components with **no clear license** or with **commercial-use-forbidden / revenue-cap** terms for *software libraries* — a capped library is effectively proprietary at any real scale and a latent trap (see §5). Reject-on-ambiguity: an unclear/unidentifiable license is treated as **not acceptable** until clarified.

**Edge cases** are decided **solo-first by the maintainer/admin** (Laurent), with the rule recorded for contributors — matching ADR-0018's governance. Ambiguity defaults to *not acceptable* until the maintainer rules otherwise.

### 3. Models / implementations — the five-question compliance profile

Model **weights licenses are not OSI software licenses**. Instead of forcing them into the software-license frame, the policy captures each model's terms in a **five-question compliance profile**, recorded per model (in the registry's license tag, ADR-0008/0017; surfaced in `implementation.toml`):

1. **Pay-to-use** — do we need to pay a license or subscription to use the model?
2. **Use restriction** — (a) is the model restricted to **research use only**? (b) is **commercial use** allowed, and up to what revenue without a license?
3. **Attribution** — are we required to **display the model name** on any app built on top of it?
4. **Train-on-output** — *(most important)* can we use the model's **output to train and improve other models** (generate training datasets / synthetic data)?
5. **Fine-tune** — are we allowed to **fine-tune** the model?

**Acceptable-to-install rule:** a model is installable if its weights are downloadable and it has a **clear, machine-readable compliance profile**. The **default catalog offers only commercial-safe weights** (per research #17: Apache/MIT/CC-BY/RAIL-M-commercial — e.g. FLUX.1-schnell, Wan, LTX, Kokoro, CosyVoice2, faster-whisper). **Restricted models** (non-commercial, revenue-capped, research-only — e.g. FLUX-dev, SDXL/SD3.5, XTTS-v2, F5-TTS, HunyuanVideo) remain installable **via explicit user acknowledgment** of their profile. **Non-open-weights models cannot run locally** (they don't have local weights); they can only be reached as cloud implementations, whose terms are part of the same profile.

**Hard-block at the action boundary — everything is possible, but always compliant.** The platform does not just warn; it **blocks** any action a model's license forbids, at the point of use:

- **No internet (or LAN) publishing of an app built on a model that forbids commercial use** — refused by the Publishing service's compliance gate (ADR-0019).
- **No generation of training datasets / synthetic data with a model that forbids training on its output** (question 4) — refused by the Training service / dataset prep.
- **No fine-tuning of a model that forbids it** (question 5) — refused by the Training service.
- **No local run of non-open-weights models.**

Everything *not* forbidden is permitted, subject to the profile (e.g. display-the-model-name where required, question 3). The profile is a **compliance fact** surfaced alongside each model, so a user always knows the terms they are building on — no black box.

### 4. Vendored OSS UIs / heavy dependencies — copyleft as separate process

The platform vendors proven OSS front-ends and engines as **separate processes** (ADR-0002/0017 already treat heavy deps and vendored UIs as separate processes). The stance on **copyleft** vendoring:

- **Vendoring copyleft is acceptable.** Running copyleft software as its own separate process — communicating over its HTTP API, never forked/embedded/derived into the platform's own code — keeps the platform's Apache-2.0 intact (per GNU GPL guidance: independent programs talking over normal interfaces are not derivative works; research #17 confirms ComfyUI's maintainers' guidance to the same effect).
- **Rules:** (a) never fork/embed the copyleft component's code into the platform repo — it stays a separate process; (b) any **derivative** of it (e.g. custom ComfyUI nodes in `custom_nodes/`) must **stay under the component's copyleft license** — we do not ship proprietary custom nodes; (c) **AGPL** candidates are treated like GPL — acceptable as a separate process, but **avoided when a GPL or MIT equivalent achieves the same** (research #17: prefer ComfyUI-GPL over A1111/SwarmUI-AGPL); (d) each vendored component's **license + process boundary** is **documented** in the compliance inventory.
- Everything recommended in research #17 is already permissive (MIT/Apache-2.0/BSD/CC-BY) or GPL-as-separate-process (ComfyUI). No vendored dependency in the v1 plan carries an unacceptable license.

### 5. Revenue-threshold clauses — accepted for models, rejected for the platform's software libraries

The standing requirement's example ("< $10M/month") comes from the **model** world. The policy sharpens the line:

- **Models:** revenue-threshold and non-commercial terms are the **normal** way weight licenses are written. **Accepted** — they fold into the five-question profile (question 2b) as a compliance fact that drives the hard-block on forbidden uses.
- **Software libraries (the platform's own stack):** a library with a revenue cap or commercial-use-forbidden term is effectively **proprietary at any real scale** and a **latent trap** (it looks open until a project crosses the threshold). **Rejected** for bundled/listed components and their dependencies.

This sharpens the standing requirement rather than contradicting it — its revenue example is a weights-license phenomenon.

### 6. Published things — the builder chooses, surfaced as a compliance fact

The subtle one. The two poles meet here: the **platform's own stack is strictly OSS**, but the platform **teaches people to build** and does not force their creations open. The policy parallels ADR-0019's two publishing regimes:

- **Regime 1 — platform services/implementations** (the "extend the platform" path): inherit the **strict OSS bar** (§2). They become platform citizens, so they must satisfy the `bundled`/`listed` component rules — open, clear SPDX, consistent dependencies.
- **Regime 2 — generic published things** (a builder's app/API/agent/tool — the small-scale family/demo/learning things): **the builder chooses the license**; **open-source is not required** (the platform doesn't force a learner's creations open). But a **license must be declared (SPDX)** and is **surfaced as a compliance fact** in the compliance catalog (ADR-0019 §8) so consumers know what they're running. The platform **encourages openness** (it is a learning/showcase platform) but does not require it.

**The hard constraint:** a published thing's **actual use must be compliant with its own declared license and any model licenses underneath it** — e.g. you cannot publish an internet demo of an app whose model forbids commercial use (§3's hard-block). Declaring a license never waives compliance with the terms underneath.

### 7. Where it lands + how the audit is kept current

- **Spec home:** the license principle lives in **`docs/spec/00-overview.md`** (Foundations, ADR-0013 §2/§6) — created this resolution, carrying both the license principle (this ADR) and the security principle (ADR-0017, previously the sole deferred principle). This is the source of the *principles*; the ADR is the source of *detail* (cite-never-restate, ADR-0013 §7).
- **Audit surface:** the **compliance catalog** (ADR-0018 §10) is the per-machine audit view — each installed/running service, capability, implementation, and published app carries its **license as a compliance fact** (declared SPDX), alongside version/update status, privacy tier, supply-chain scan, resource usage, and computed review status. Surfaced in the dashboard's **Administrator** (read-only audit) and **Builder** (authoring, own developments) views.
- **Recording:** license is declared as **SPDX** in `service.toml` / `implementation.toml` (ADR-0002/0018) and in the registry's license tag (ADR-0008); the community-catalog listing records carry the license (ADR-0018 §8). **Supply-chain / license scanning** is part of the mechanical quality bar (ADR-0017 §9) with the 1-week freshness gate (ADR-0016/0017) — the audit is kept current by the update/scan machinery, not a one-off review.

## Boundary / handoffs

- **Training operations** (dataset/synthetic-data generation, fine-tuning) are gated by each model's train-on-output / fine-tune terms → **#30** (open) — expanded with an "Updated by #23" note recording that Training's dataset-prep and fine-tune capabilities must respect the model-license profile. NOT resolved here.
- **Model-license compliance facts** surface alongside usage **consent** in the data-consent model → **#31** (open) — referenced, not resolved here.
- **Community-catalog quality bar** → ADR-0018 (settled); this ADR gives the license check its concrete policy (§2).
- **Published-things license as compliance fact** → ADR-0019 (settled); this ADR defines how it is handled (§6).
- **Security principle** → ADR-0017 (settled); the same `00-overview.md` carries both.

## Considered options

- **Uniform OSS-only rule vs per-kind rules** — a single "OSS only" rule cannot honestly govern models (non-OSI weight licenses) or published things (builders keep creations proprietary). Chose one policy, four kinds, per-kind rules.
- **Three component tiers vs one bar** — ADR-0018 already computes `bundled`/`listed`/`third-party`; one bar would either over-gate listed components (Apache-2.0 requirement) or under-gate bundled ones (copyleft contamination). Chose per-tier rules.
- **Copyleft banned vs accepted-as-separate-process** — banning copyleft excludes proven tools (ComfyUI); embedding it would contaminate the Apache-2.0 repo. Chose separate-process acceptance with the no-fork/derivative-stays-copyleft rule.
- **Models: blanket-reject non-commercial vs install-with-acknowledgment + hard-block-uses** — blanket rejection loses real models users want; unguarded acceptance breaks compliance. Chose install-with-acknowledgment + hard-block on forbidden uses.
- **Warn vs hard-block on forbidden model uses** — a warning is easy to ignore and inverts the "always compliant" goal. Chose **hard-block** at the action boundary (Laurent's explicit call).
- **Force open published things vs builder-chooses** — forcing openness fights the teaching/showcase soul; requiring openness silently would hide proprietary things. Chose builder-chooses + mandatory SPDX declaration + surfaced compliance fact.
- **Revenue caps accepted for all vs split** — the standing requirement's example is a weights-license form; applying it to libraries creates a latent trap. Chose: accepted for models, rejected for the platform's software libraries.

## Consequences

- **Creates ADR-0022** — the platform-wide component license policy; a cross-cutting Foundations principle.
- **Creates `docs/spec/00-overview.md`** — the Foundations chapter, carrying the license principle (this ADR) and the security principle (ADR-0017), ending the deferral.
- **Sharpens ADR-0018** — the quality bar's license check now has a concrete policy (per-tier rules, SPDX declaration, scanning).
- **Sharpens ADR-0019** — a published thing's license: builder-chooses (regime 2) or strict OSS (regime 1), SPDX declared, surfaced as a compliance fact, use must comply with underlying terms.
- **Feeds #30** (Training: train-on-output/fine-tune gating) and **#31** (model-license compliance facts alongside consent). Does NOT resolve them.
- **Glossary (CONTEXT.md):** add "license policy", "model compliance profile", "compliance fact" (license), and update the Standing Requirements "License policy" line to point at this ADR.
- **Feeds the map's destination** — the Foundations principle is part of the complete, buildable spec.
