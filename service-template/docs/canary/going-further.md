---
title: Echo — going further
capability: canary
level: going-further
keywords:
  - canary
  - capabilities
  - template
mcp-tools: []
---
# Echo — going further

## Summary

The canary is the starting line: build your own capability on the same
shape, and the whole platform story — declaration, surfaces, conformance,
learning bar — carries over.

## Details

- **Replace, don't extend** — delete `capabilities/canary/` and add your
  capability module (business logic, `routes()`, UI page, OpenAPI
  fragment); re-point the assembly file and the declaration.
- **Declare it** — the `[<service>.<capability>]` section in
  `service.toml` plus its own `[...learning]` bar: four graded docs (this
  file's shape is the pattern — copy it and rewrite the body), and the
  how-an-agent-drives-me skill (copy `skills/canary/SKILL.md` and rewrite
  it; the skill's front-matter name must match the declared slug).
- **Keep the suite green** — the vendored conformance suite re-runs on
  your capability's surface; the family blocks you declare are the red
  gate until implemented.
- **Publishing** — the bar is mandatory to publish for bundled/listed
  things (ADR-0018's tiers, ADR-0024 §1).

## See also

- `CONTRIBUTING.md` — the copy-to-start ritual, step by step.
- The `study-in-depth` level — why the skeleton is shaped this way.
