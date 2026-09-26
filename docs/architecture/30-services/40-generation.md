# 40 — Generation

> **Status:** written at the resolution of wayfinder ticket "Write the four light service chapters (Generation, Image, Audio, Media transformations)" (#45). **Source of truth:** the CONTEXT.md *Generation service* glossary entry (the output-side counterpart to Document), ADR-0019 (publishing a generated website → the Publishing & Governance service's publishing surface), ADR-0007 (workflow-assisted generation reuses the Workflow service's composition primitive), ADR-0002 (callable surfaces — generation composes the other services' capabilities). This chapter is the **organized build-view** — it cites, never restates.

## Identity

The **Generation service** is the platform's *creation* surface — the **output-side counterpart to the Document service**. Where Document ingests, indexes, and retrieves raw content, Generation produces **documents, reports, and websites** from it. It invents nothing itself: it **reuses all the other services** — connectors for sources, agents for drafting, the Workflow service for reusable pipelines, the Document service for dataroom/references, and Inference for models — and combines them for the user.

## Capabilities

- **Interactive open authoring** — an interactive, open writing experience for **one-shot** documents/reports/websites (CONTEXT.md *Generation service*), the mode for a single piece of output.
- **Workflow-assisted generation** — **user-built, workflow-assisted** generation for **recurrent** needs (e.g. a monthly GitHub-activities summary), reusing the Workflow service as the reusable pipeline (ADR-0007).
- **Authoring as HTML/CSS artifacts** — content is drafted as **HTML/CSS artifacts**, then **exported to docx / xlsx / pptx / pdf**.
- **Publishing** — publishing a generated **website** flows to the combined **Publishing & Governance service**'s publishing surface (ADR-0019; a generated static site is the *static site / document* published shape), not something Generation does itself.

## ADR cross-references

ADR-0002 (callable surfaces — Generation composes the other services' capabilities over them) · ADR-0007 (workflow-assisted generation reuses the Workflow service's composition and scheduling) · ADR-0019 (published static site / document — Generation's HTML/CSS artifacts as a published shape; publishing lives in the Publishing & Governance service). Mostly CONTEXT.md (*Generation service* entry).
