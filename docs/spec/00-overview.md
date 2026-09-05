# 00 — Overview: the soul, the architecture, and the cross-cutting principles

**Part of the wordslab-platform spec.** This is the Foundations overview (ADR-0013 §2): the soul, the service architecture, and the **cross-cutting principles** — security and license — which live here rather than in separate chapters. Per ADR-0013, this chapter is the organized view; each principle's authoritative detail lives in its ADR (cite-never-restate).

## The soul

Our target audience is people who want to learn to use and to **understand** how AI works — non-technical at the start, but wanting to learn in depth, own their data, and **be in control** of what the AI does. No complex setup, everything guided end to end, but **no magic and no black box**: everything manually chosen, visible, and explained step by step. We are building the **ZX Spectrum / C64 of the AI era** — so that millions can learn the AI basics at home, in schools, or in small enterprises.

Everything in this spec traces back to that soul. Three commitments run through every service and every principle:

1. **Openness** — a 100% open-source platform, and an honest, visible one.
2. **Simplicity** — the main feature; small scale, self-hosted, understandable.
3. **Control** — the user owns their data, chooses their implementations, and sees what the AI does.

## The service architecture

The platform is a set of **fully independent services** (each with its own DB, business logic, UI, and API) plus a **platform core** on each machine, all sharing one minimal uniform service contract and one template. See `10-foundations.md` for the substrate (contract, template, core, topology, resources, providers, composition, registry) and `20-services/` for the service chapters. The service catalog and build order are fixed by the v1 catalog decision (ADR-0002/0018); the settled catalog and build order are listed in the architecture overview (`docs/architecture-overview.md` §8).

## Cross-cutting principles

These principles are not chapters — they cut across every service, and each service's build spec (Part 2) complies with them.

### 1. Security — the trusted home environment

**Source of truth: ADR-0017.**

The security stance is honest and light, sized to a trusted home/small-business environment at very small scale — deliberately lighter than the enterprise stack (no Keycloak, Vault, mTLS mesh, or HSMs). The soul governs: **transparent, visible, no black box** — the user can always see and adjust what is guarded.

The principles:

- **Honest threat model** — the primary defenses target a **compromised or malicious agent/harness** and **accidental data leakage**; trusted LAN peers, untrusted anything crossing to the internet. Malware with OS-level host access is an explicit boundary (not fully defended); a stolen credential is defended by its short lifetime.
- **Host-filesystem isolation** — the platform runs in a WSL VM with no host access by default; file sharing is explicit only (a dedicated mounted directory).
- **Browser-aware TLS** — every browser-facing surface is HTTPS via the local CA; plain HTTP + Bearer for trusted machine-to-machine traffic on the LAN; TLS at the front door, over the overlay, and on every internet crossing. No mTLS.
- **Secrets at rest, deliberately light** — light static-key obfuscation (not theater-strength encryption); the real defense is **short-lived, rotated credentials**.
- **Container isolation** — OS-container isolation (not VMs) is enough; the container network policy is default-allow-but-scoped-to-need.
- **The harness is the execution authority** — the platform's security lives in backstops around it (network policy, connector audit, per-agent scoping, host-filesystem isolation), not in overriding the harness's native accept/refuse.
- **Connectors: a single audited door** — every outbound connector call logged and attributable; read-only connectors logged-only, send/mutate connectors require caller-identity-scoped human approval.
- **Guardrails = cheap data-safety** — data-safety at the outbound (leakage) and inbound (prompt-injection) boundaries, on by default and visible; the heavy moderation tier is optional and off by default.
- **Update authenticity, two supply chains** — the platform's own code is signed + checksummed; external open-source packages are gated by an audited supply-chain scan + 1-week wait.

### 2. License — the platform's component license policy

**Source of truth: ADR-0022.**

The platform is **100% open source**, but "open" is not one uniform rule. It resolves differently across the four kinds of things the platform touches: platform components, models/implementations, vendored OSS UIs, and published things. The through-line: **the platform's own components have a strict open bar; a builder's published things have a permissive-but-expressible policy; and every use must be compliant with the licenses involved.** Nothing is blanket-banned; everything must be used in a way its license permits.

The principles:

- **One policy, four kinds, per-kind rules** — components, models, vendored UIs, published things each have a tailored rule under one coherent policy (ADR-0022 §1).
- **Platform components — three computed tiers** (ADR-0018's `bundled` / `listed` / `third-party`):
  - **`bundled`** — open source, and the license must keep the platform repo itself shippable as Apache-2.0; copyleft acceptable only as a separate process that doesn't contaminate the platform's own code.
  - **`listed`** — every dependency licensed + open; the contribution repo's license consistent with its dependencies; no Apache-2.0 requirement.
  - **`third-party`** — the platform recommends the listed rules but cannot enforce them.
  - Reject **no-clear-license** and **commercial-use-forbidden / revenue-capped software libraries**; ambiguity defaults to not-acceptable; the **maintainer/admin decides** edge cases.
- **Models — the five-question compliance profile** (ADR-0022 §3): pay-to-use · research-only · commercial/revenue cap · display-model-name · **train-on-output** · fine-tune. Installable if weights are downloadable and the profile is clear; the **default catalog offers only commercial-safe weights**; restricted models are installable with explicit acknowledgment; **non-open-weights models cannot run locally**. **Hard-block any forbidden use** — no internet/LAN publishing of an app on a non-commercial model, no synthetic-data/training-dataset generation on a no-train-on-output model, no fine-tuning a no-fine-tune model.
- **Vendored OSS UIs / heavy deps** (ADR-0022 §4) — **copyleft vendoring is acceptable as a separate process**; never fork/embed; derivatives stay under the component's copyleft license; AGPL avoided when a GPL/MIT equivalent achieves the same; each component's license + process boundary documented.
- **Revenue-threshold clauses** (ADR-0022 §5) — **accepted for models** (the normal weights-license form, folded into the profile); **rejected for the platform's software libraries** (a capped library is proprietary at any real scale).
- **Published things** (ADR-0022 §6) — two regimes paralleling ADR-0019: **regime 1** (platform services/impls) inherits the strict OSS bar; **regime 2** (a builder's generic app/API/agent/tool) the **builder chooses** the license — open-source not required, but **SPDX declared and surfaced as a compliance fact**. A published thing's use must always comply with its declared license and any model licenses underneath it.
- **Audit kept current** (ADR-0022 §7) — license declared as SPDX in `service.toml`/`implementation.toml` and the registry's license tag; the **compliance catalog** is the per-machine audit view (Administrator read-only, Builder authoring); supply-chain/license scanning is part of the mechanical quality bar with the 1-week freshness gate.

## Reading this spec

Read in two passes (ADR-0013): **pass 1** = each service chapter's Part 1 (use cases, the user guide), **pass 2** = each service chapter's Part 2 (build specs). Foundations (`10-foundations.md`) and this overview come first; lifecycle (`90-lifecycle.md`) and dashboard (`91-dashboard.md`) complete the picture. Every build requirement traces back to a use case, and every chapter cites — never restates — its governing ADRs.
