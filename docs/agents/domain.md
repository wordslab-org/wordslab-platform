# Domain docs: single-context

`CONTEXT.md` at the repo root is the project's glossary / ubiquitous language. `docs/adr/` holds architectural decision records.

Consumer rules:

- Skills that need vocabulary read `CONTEXT.md` before proposing terms.
- Terms get added to `CONTEXT.md` the moment they crystallise — never batched, never as a spec.
- `CONTEXT.md` is a glossary and nothing else: no implementation details, no specs, no scratch pads.
- Hard-to-reverse decisions with genuine alternatives go in `docs/adr/` (one file per ADR, numbered).
