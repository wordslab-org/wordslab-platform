"""The nine family contract modules (ADR-0001 §Family contracts, ADR-0002 §The
template.1).

The base contract (`contract/base/`) applies to every service; the families are
the API-alignment contracts a service opts into by implementing the ones its
function needs. ADR-0002 §1 ships all nine as self-contained modules in the
template — a capability keeps the module it implements and deletes the rest
(CONTRIBUTING.md step 5), so a CRUD service carries no inference machinery and
no dead code.

Landed so far: `family_1_responses` (#76). Families 2–9 arrive as their own
stage-0 tickets (#77–#84) — until then their conformance blocks are red on
purpose, and the suite's manifest ships empty so nothing runs silently.
"""

__all__: list[str] = []
