"""The consent-flag template contract — ADR-0026 §1/§2 as template-level
machinery (ticket #72): the two consent states, the per-interaction default,
and the never-bypassable consent gate.

Vendored, never edited (ADR-0002 §The template.1): every user input surface
carries the consent flag — the default is "may use for improvement" and the
private/secret state is the visible "do not use" toggle (ADR-0026 §1); any
extraction surface applies `consent_gate` before anything leaves the user
sphere — only `may_use` interactions are eligible to pass, and the gate has
no parameter that could admit a private/secret or unset interaction
(ADR-0026 §2 pass 1: the private/secret exclusion is never bypassable).
"""

from __future__ import annotations

# The two ADR-0026 §1 consent states, machine forms of the ADR's wording:
# "may use for improvement" and "private/secret — do not use".
MAY_USE = "may_use"
PRIVATE_SECRET = "private_secret"
CONSENT_STATES = (MAY_USE, PRIVATE_SECRET)

# Per-interaction default (ADR-0026 §1): consent defaults to "may use for
# improvement"; the private/secret toggle is the explicit user gesture.
DEFAULT_CONSENT = MAY_USE

# The exclusion reasons the gate reports (ADR-0026 §2: the exclusion is
# reported, not hidden). An interaction whose state is missing or unknown is
# excluded as `unset` — fail-closed: a lost flag never gains eligibility.
UNSET = "unset"


def resolve_consent(value: object) -> str:
    """Resolve one DECLARED consent state.

    A declared state → itself; anything else — including an explicit JSON
    `null` — → `ValueError`: consent never silently normalizes an unknown
    mark into an eligible state (ADR-0026 §2, fail-closed). Callers turn
    the error into the contract's 400 `invalid_request` (base item 4). An
    ABSENT flag is the caller's case: the ADR-0026 §1 default
    (`DEFAULT_CONSENT`) applies, never this function.
    """
    if value in CONSENT_STATES:
        return value
    raise ValueError(
        f"Unknown consent state {value!r}: expected 'may_use' or 'private_secret' (ADR-0026 §1)."
    )


def consent_gate(interactions) -> tuple[list[dict], dict[str, int]]:
    """Filter = the consent gate (ADR-0026 §2 pass 1): the eligibility pass
    every extraction surface applies before anything leaves the user sphere.

    Only `may_use` interactions are eligible to pass; `private_secret` and
    state-less interactions are excluded, counted by reason. The gate has NO
    parameter that could admit an excluded interaction — a service may add
    its own filters on top (date period, user, samples, per the ADR), but
    the private/secret exclusion is never bypassable.
    """
    eligible: list[dict] = []
    excluded: dict[str, int] = {}
    for interaction in interactions:
        state = interaction.get("consent")
        if state == MAY_USE:
            eligible.append(dict(interaction))
        else:
            reason = state if state in CONSENT_STATES else UNSET
            excluded[reason] = excluded.get(reason, 0) + 1
    return eligible, excluded
