---
title: The control-placement map — study in depth
keywords:
  - placement
  - invariants
  - homes
  - scope
  - verification-lanes
mcp-tools: []
---
# The control-placement map — study in depth

## Summary

The security model's testable claim is placement-first: every threat frame
has a control, every control has exactly one home. That is not provable by
reading the ADR — it is provable by an index checked continuously. This level
explains the two judgement calls the checker makes (where it lives, and what
counts as a control) and the boundary between *that* a control is placed and
*how* it behaves.

## Details

1. **The home decision: the foundation, i.e. the template.** The map and the
   harness are vendored in `service-template/` because the template is the
   surface every service copies and the place the sweeper re-runs — the same
   reasoning as the conformance suite and the learning bar. The
   counter-argument is real: the map describes *platform services*
   (Connectors, the core, Chat + Agents, Media transformations, the
   installer, the lifecycle), none of which is a service built from the
   template, so a copy of the platform's security map ships inside every
   service. The resolution is the split the template already uses: the
   **checker is vendored** (like the conformance suite), and the **map is
   the platform-level data that checker reads**. A copy is inert until a
   service reads it, and it is exactly what lets placement be re-verified
   per service from the first service on.
2. **What counts as a control — and what does not.** A control is one
   ADR-0017 *decides*. The ADR's Context takes the trust-model basics as
   given (machine identity keys, the overlay, the `keys`/`secrets` split,
   per-agent registry scoping, the cloud action-context boundary) — those
   are cross-referenced, not placed, and the seven per-control verification
   lanes (#277–#283) verify exactly the set this map places. §6 is included
   for the same reason: it states the platform does *not* intercept the
   harness and enumerates backstops that are placed under their own
   sections, so it names no control of its own.
3. **One control, one home — including where §8 settles two sites.**
   ADR-0017 §8 places the guardrail layer across sites (the moderation model
   in Inference's classic-AI capability, builtin transforms in Media
   transformations, policy hooks in the agent loop and at the outbound
   door). That is *several controls, each with its own home* — never one
   control with two entries. So "no control is re-implemented in two places"
   is checked two ways: a control id landed twice, and §8's guardrail layer
   landing twice on one of its sites. A service legitimately hosts several
   *distinct* controls (Connectors hosts the door's audit, tier, approval
   and its guardrail hook), which is why the invariant is about a control's
   identity and the guardrail layer, not about counting homes.
4. **Placement, not mechanism — no double-testing.** The harness asserts
   *that* each control is placed and which frames it backs; it never asserts
   *how* a control behaves. The stubs stand in for the owning services at
   their contract surfaces only. Each mechanism is tested once, in its
   owner: the door's gating in #50/#55, the container policy in #48, the
   at-rest copies in #62, the transforms in #58, the update flow in #65, the
   stances in #63. The runtime **stance** of each control (does the policy
   actually block a LAN wander?) is the later lanes' — the posture registry
   that records it is #276's, not this checker's.
5. **The honest non-goals are not a narrative here.** §1's
   host-OS-malware frame is representable as a declared `boundary`, the
   minimum the frame invariant needs. The rest of the honest model (the disk
   thief, no unified accept/refuse trail, the heavy guardrail tier off by
   default) is recorded where it belongs — #276/#282 as model state, #284 as
   the reviewable narrative.

## See also

- `docs/capabilities/placement/going-further.md` — what consumes this
  checker next.
- ADR-0017 (the security model, end to end including its two evolution
  notes) · spec #66 (the security model spec) · #275 (the ticket) ·
  `docs/agents/build-order.md` (the testability rule that mandates it).
