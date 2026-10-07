---
title: The control-placement map — going further
keywords:
  - placement
  - verification
  - sweeper
  - consumers
mcp-tools: []
---
# The control-placement map — going further

## Summary

The map and the harness are the seam the rest of the security verification is
built on. Going further means *consuming* them — adding a runtime stance, a
stub environment surface, or a per-control lane — not extending the map
itself.

## Details

1. **The verification substrate (#276)** consumes this map and this stub set
   and adds what this checker deliberately leaves out: the stub *harness*
   (its native accept/refuse surface), the stub host-OS/LAN surfaces, and
   the **posture registry** where each control's runtime *stance* is
   recorded. If you are adding a control's stance, that is #276's surface.
2. **The seven per-control lanes (#277–#283)** each verify one lane's stance
   and record it in the registry: isolation, container network policy,
   secrets at rest, the door, guardrails, TLS, update authenticity. They
   verify exactly the controls this map places — if a lane needs a control
   the map does not carry, the map is what changes (with ADR-0017 as the
   source), never a private list in the lane.
3. **The sweeper (#85)** re-runs `sweep_placement()` per service as each
   lands — the dev-side mirror of the conformance sweeper, so placement is
   re-verified continuously rather than rediscovered at the end.
4. **The coherence bar (#284)** reads the whole model back through the
   registry as one sweep and adds the auditable narrative (the honest
   non-goals among it). It is the capstone the lanes gate, not a second
   placement checker.
5. **The sibling checkers stay siblings.** The consent-placement checker
   (#285, ADR-0026) and the per-user export/restore contract checker (#269,
   ADR-0021 §3) are the same *shape* against different governing documents.
   They are deliberately not generalized into one framework here — if you
   build the third one, read this ticket's PR as prior art rather than
   refactoring this module into a shared engine unasked.

## See also

- `docs/capabilities/placement/study-in-depth.md` — the home decision and the
  placement-versus-mechanism split, argued in full.
- ADR-0017 · spec #66 · #275 (this ticket) · #276 (the verification
  substrate) · #284 (the coherence bar) · `service-template/CONTRIBUTING.md`
  (the copy-to-start ritual the map travels with).
