# 43 — Media transformations

> **Status:** written at the resolution of wayfinder ticket "Write the four light service chapters (Generation, Image, Audio, Media transformations)" (#45). **Source of truth:** the CONTEXT.md *Media transformations service* glossary entry, ADR-0002 (capabilities within a service), ADR-0001 (the base contract the service ships on). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Media transformations service** is the platform's **ready-to-use transformation toolbox**: it ships common, deterministic transformations across numeric/text/image/audio so the most frequent data-shaping jobs are built-in for home projects instead of re-written. It is a **catalog of capabilities** under the service (ADR-0002), not a new DSL — the capabilities are the transforms themselves.

## Capabilities

Ready-to-use transformation capabilities across modalities — the most frequent transforms built in to accelerate home projects (CONTEXT.md *Media transformations service*):

- **Numeric** — data cleaning, datetime normalization.
- **Text** — translation, summarization, language detection, guardrails, entity detection.
- **Images** — face recognition / redaction.
- **Audio** — transcription-derived transforms.
- **Cross-cutting** — moderation, anonymization.

These are the service's built-in transformations for v1; they ship on the base uniform service contract (ADR-0001), each a capability with its own business logic while sharing the service's contract surfaces and database (ADR-0002).

## ADR cross-references

ADR-0001 (the base contract the service and its capabilities ship on) · ADR-0002 (capabilities within a service — an in-process module sharing the service's contract surfaces). Mostly CONTEXT.md (*Media transformations service* and *Capability* entries).
