"""The nine family contract modules (ADR-0001 §Family contracts, ADR-0002 §The
template.1).

The base contract (`contract/base/`) applies to every service; the families are
the API-alignment contracts a service opts into by implementing the ones its
function needs. All nine ship in the template as self-contained modules — a
capability keeps the module it implements and deletes the rest (CONTRIBUTING.md
step 5), so a CRUD service carries no inference machinery and no dead code.

Shipped so far: `family_1_responses`. Families 2–9 arrive as their own stage-0
tickets (#77–#84) — the suite's family blocks (`tests/contract/families/`) are
red on purpose until then, and the manifest ships empty so they never run
silently.
"""

__all__: list[str] = []
