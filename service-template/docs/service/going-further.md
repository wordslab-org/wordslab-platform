---
title: The template service — going further
keywords:
  - template-service
  - capabilities
  - contribution
  - extensions
mcp-tools: []
---
# The template service — going further

## Summary

The template is a starting point, not a framework to extend in place. Going
further means *using* it: copy `service-template/`, replace the canary with
your own capabilities, and fill in the learning bar for what you actually
ship. This level collects the directions that leave the template behind.

## Details

1. **Write your own capability** — a capability is your business logic plus
   routes (`/v1/...`) plus a UI page; declare it as a
   `[<service>.<capability>]` section and add its `docs/capabilities/<name>/`
   levels as you go. The canary shows the smallest complete shape.
2. **Add an implementation** — a capability gets its concrete deliveries from
   implementations (a model, an engine, a database) copied from
   `implementation-template/`; implementations declare their own
   requirements, and the platform picks one per install.
3. **Exercise family conformance** — list the ADR-0001 family numbers your
   service implements in `tests/contract/families/manifest.toml` and keep
   those blocks; the suite is red until the family's surface is implemented.
4. **Keep the placement checker** — the template ships the control-placement
   map (`contract/placement_map.toml`) and its invariant harness; it indexes
   ADR-0017's security model and travels with the copy, so the platform's
   placement claim is re-verified per service as each lands. A service that
   places a security control adds it to the **map** (citing the ADR), never
   as private code.
5. **Publish it** — publishing as `bundled`/`listed` requires the learning
   bar (ADR-0018's tiers); before that, gaps are only recorded. The copy
   ritual, the declaration rules and the contract's base items are all in
   `CONTRIBUTING.md`.

## See also

- `CONTRIBUTING.md` — the full copy-to-start ritual and the inherited rules.
- ADR-0002 (the service template) · ADR-0018 (publishing tiers) ·
  ADR-0017 (the security model the placement map indexes) ·
  ADR-0001 (the family contracts).
