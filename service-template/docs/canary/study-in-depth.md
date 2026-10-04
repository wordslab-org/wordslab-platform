---
title: Echo — study in depth
capability: canary
level: study-in-depth
keywords:
  - canary
  - conformance
  - design
mcp-tools: []
---
# Echo — study in depth

## Summary

Why the canary looks the way it does: it exists to prove the template's
acceptance (copy → run the vendored suite → green) and to be replaced, so
every choice in it is a teaching example of the platform's settled rules.

## Details

- **Deliberately disposable** — a real service deletes the canary and
  keeps the shape: capability module, declaration section, docs, skill.
  Nothing in the template depends on the canary existing except its own
  tests.
- **The consent flag as contract** — the flag is not a canary feature but
  a template-level contract (ADR-0026): every user input carries it, and
  the private/secret exclusion is enforced at the extraction seam. The
  canary is just the first capability to carry it.
- **Per-app state, closed by the factory** — the interaction store is
  created in the assembly file and closed over by the routes factory;
  module-level state would leak across the suite's many in-process
  services.
- **Read the suite** — `tests/contract/` is the executable definition of
  the contract the canary satisfies; the family blocks run only for the
  families the test-side manifest lists.

## See also

- The `how-it-works` level — the moving parts.
- ADR-0002 (the template) · ADR-0031 (the declaration shape) · the
  `going-further` level — replacing the canary with your capability.
