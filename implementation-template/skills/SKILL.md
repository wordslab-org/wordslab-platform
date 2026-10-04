---
name: drive-qwen3-4b
description: How an agent drives this llm.model implementation — pick it in the model catalog, call it through the capability's API.
---
# drive-qwen3-4b

The how-an-agent-drives-me skill of this implementation (ADR-0024 §1): a
registry `skill` entry whose authored name is `<service>.skill.drive-qwen3-4b`
(ADR-0008); this file is the body the owning service stores.

## How to drive this implementation

- **Selection is explicit** — the implementation is chosen by name in the
  model catalog (or referenced by a workflow's `model` composition
  primitive with structured output); there is no automatic fallback
  (ADR-0007).
- **Fit comes first** — install is gated by the fit check (disk/RAM/VRAM +
  technologies); a non-fitting implementation is refused, not degraded.
- **Driving is the capability's surface** — call it through the parent
  capability's OpenAPI API or its auto-generated MCP tools; parameters
  and consent flags are the capability's, not this file's.
- **Privacy is declared** — the implementation carries its privacy tier;
  choosing it is the privacy decision — surface the tier to the user.
