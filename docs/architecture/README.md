# Wordslab Platform — Architecture

The **architecture document** for the wordslab-platform: a 100% open-source home-scale AI platform for AI enthusiasts at home and in small businesses who want to own their intelligence. This document explains **how the platform is put together and why** — the concepts, the general architecture, and the cross-cutting concerns. It is written to be read by the platform's own audience: non-technical users who want to understand, and the developers/agents who implement.

> **What this is, and is not.** This is a **detailed architecture document**: detailed at the level of platform concepts, the general architecture, and the cross-cutting concerns, and light on the internals of most services. It is **not** a per-service buildable specification. The authoritative detail for any single decision lives in the **ADRs** (`../adr/`, the source of truth); this document **organizes and cites, never restates**. Where this document and an ADR disagree, the ADR wins.

## The soul, first

Start at [00-soul.md](00-soul.md) — the target audience, the three commitments (openness, simplicity, control), and the phrase that explains most of the architecture: **no magic, no black box**. When you wonder "why isn't this automatic?", the answer is almost always the soul.

## How to read this document

The chapters walk the platform in dependency order — from the concept of a service, to the machine it runs on, to where models come from, to how things compose, to the distinctive data side, then the cross-cutting concerns, then the service catalog:

| Region | What you learn |
|---|---|
| `00-soul.md` | The soul, audience, and design principles |
| `10-concepts/` | The platform's concepts & general architecture |
| `11-what-is-a-service.md` | Service · capability · implementation · contract · template |
| `12-the-machine.md` | Core · bootstrap · topology · resources · front door |
| `13-models.md` | Where models come from: Inference · engines · providers · privacy |
| `14-composing.md` | Agents vs workflows · the registry |
| `15-knowledge.md` | The data side: Document · Knowledge · memory · consent |
| `16-building-and-publishing.md` | Develop → publish → lifecycle |
| `20-concerns/` | Cross-cutting concerns (each its own chapter) |
| `21-security.md` | The trusted home environment (ADR-0017) |
| `22-license.md` | One policy, four kinds (ADR-0022) |
| `23-learning-and-operability.md` | Learning bar · continual assistant · guided build (ADR-0024) |
| `24-data-consent.md` | GDPR-aware data handling (ADR-0026) |
| `25-lifecycle-and-updates.md` | Install · update · backup (ADR-0014/0016/0021) |
| `26-dashboard.md` | The integrated dashboard (ADR-0015) |
| `30-services/` | The service catalog — one chapter per service |

Readers who want the service catalog first can go straight to `30-services/`; readers who want to understand the architecture should read `00-soul.md` then `10-concepts/` in order.

## The service catalog

The v1 platform is **13 services**, grouped by what they do for the user. Every service chapter states its identity and capabilities and cites its governing ADRs. Chapters marked **pending** are not yet physically written; each lists the ticket that will produce it.

**Detailed (foundational) chapters** — the services that carry the platform's architecture, or that were already written deep:

| # | Service | Status |
|---|---|---|
| 31 | Inference | pending — written by ticket #35 |
| 32 | Chat + Agents | pending — grilling ticket |
| 33 | Workflow | pending — grilling ticket |
| 34 | [Document](30-services/34-document.md) | written (relocated) |
| 35 | [Knowledge](30-services/35-knowledge.md) | written (relocated) |
| 36 | [Training and Evaluation](30-services/36-training-and-evaluation.md) | written (relocated) |
| 37 | Development | pending — grilling ticket |
| 38 | Connectors | pending — grilling ticket (foundational) |
| 39 | [Publishing & Governance](30-services/39-publishing-and-governance.md) | written (relocated) |

**Light chapters** — identity + a few capabilities + pointer to design ADRs (content/consumer services):

| # | Service | Status |
|---|---|---|
| 40 | Generation | pending — light entry (batch task) |
| 41 | Image | pending — light entry (batch task) |
| 42 | Audio | pending — light entry (batch task) |
| 43 | Media transformations | pending — light entry (batch task) |

## Conventions

- **ADR = source of truth.** Every chapter's build/decision detail is backed by its cited ADR(s) in `../adr/`. A chapter never states anything as authoritative that isn't in its cited ADR — it organizes and re-presents at the right level.
- **No magic, no black box** applies to the document too: everything is visible, structured, and explained.
- **Relocation over loss.** No settled fact already written in the ADRs, CONTEXT.md, or the earlier architecture overview is dropped; it lives in the chapter where it belongs.
- **Chapter depth:** concept and cross-cutting chapters are detailed; most service chapters are light (identity + capabilities + ADR pointers). A service that carries the architecture (the foundational nine) is detailed.
- **Vocabulary:** chapters use CONTEXT.md terms exclusively (service, capability, implementation, callable surfaces, document bundle, explicit implementation choice, review queue, generated/verified, data spheres, …). See `../CONTEXT.md`.

## The ADRs (source of truth)

Every decision lives in `../adr/` — numbered ADR-0001…0028 (0001 minimal uniform service contract, 0002 service template, 0003 platform core, 0004 topology, 0005 resources, 0006 inference providers, 0007 composition, 0008 capability registry, 0009 Document/Knowledge split, 0010 DocETL engine, 0011 grounding, 0012 memory/capture, 0013 spec anatomy — *tree superseded by ADR-0028*, 0014 installer, 0015 dashboard, 0016 update/versioning, 0017 security, 0018 governance, 0019 publishing, 0020 evaluation, 0021 backup, 0022 license, 0023 Document/Knowledge sharpening, 0024 learning experience, 0025 training, 0026 data consent, 0027 implementation-declaration, 0028 architecture document). ADR-0028 supersedes ADR-0013's *tree mechanics* (this architecture document replaces the old numbered spec tree); ADR-0013's surviving content conventions carry into this README.
