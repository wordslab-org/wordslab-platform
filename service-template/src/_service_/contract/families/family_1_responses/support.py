"""Family 1 — the per-implementation support matrix (ADR-0001 §Families.1,
under the conformance clause ADR-0004 amends in).

ADR-0004 makes a capability's API the **union of its implementation
variants**: implementations solve the same problem with different tradeoffs and
may support different slices of the family surface — a local GGUF engine may not
do audio input, a cloud provider may not return reasoning items. The contract
does not force-fit them into one identical shape; it requires the difference to
be **declared and documented** instead of discovered by a failed request.

So each implementation declares a `SupportMatrix`: which family-1 features it
actually supports, plus its documented deviations from the upstream shapes
(ADR-0001 §Families.1: "follow upstream OpenAI shapes; document deviations,
pinned to a reference date"). The matrix is FEATURE SUPPORT — not a quality or
speed ranking. Rankings are dynamic (artificialanalysis at selection time) and
must never be stored in a declaration (ADR-0031 §5); this is the opposite kind
of fact, and the two never mix.

Where it is declared: the implementation's adapter module exports
`SUPPORT: SupportMatrix` — code, next to the adapter that must honor it, and
next to the `docs/<level>.md` that explains it. It is NOT a key in
`implementation.toml`: that declaration is a closed shape (ADR-0031 §3), and a
support key there would reopen the ranking door §5 closes.

How it is used: `routes(..., support=...)` refuses a request that needs a
feature the selected implementation does not have (400, naming the feature),
instead of letting the engine fail obscurely. Output-side features (citations,
reasoning, refusals) cannot be requested — they are discovered from the
response — so for those the matrix is documentation: it tells a reader what the
implementation is known to produce, and nothing gates on it.

Deliberately NOT a feature: `streaming`. The typed event sequence is produced by
the module itself (see `events.py`), so every implementation that serves this
route streams — gating it would refuse a request the module always serves.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...base.errors import invalid_request

# The family-1 features an implementation may or may not support. Input-side
# features are requested explicitly and gate the request; output-side ones can
# only be documented.
FEATURES = frozenset(
    {
        "vision",  # input_image
        "audio",  # input_audio
        "function_tools",  # tools[].type == "function"
        "mcp_tools",  # tools[].type == "mcp"
        "structured_outputs",  # text.format json_schema
        "citations",  # output_text annotations (output-side)
        "reasoning",  # reasoning items (output-side)
        "refusals",  # refusal content parts (output-side)
    }
)


@dataclass(frozen=True)
class SupportMatrix:
    """What ONE implementation of a family-1 capability supports.

    `supported` holds feature names from `FEATURES` (loud on an unknown name — a
    typo must not silently read as "unsupported"). An EMPTY set is legal and
    meaningful: plain text input and plain text output are the always-supported
    base of family 1, so a small local model with no vision, no tools and no
    structured outputs declares `supported=frozenset()` and is a legitimate
    variant (ADR-0004: the API is the union of its variants, not their
    intersection — a text-only implementation is one member, not a broken one).
    `deviations` carries the documented deviations from the upstream shapes;
    `reference_date` pins them to the upstream reference they were checked
    against, as ADR-0001 §Families.1 requires ("follow upstream OpenAI shapes;
    document deviations, pinned to a reference date").
    """

    supported: frozenset[str]
    deviations: tuple[str, ...] = ()
    reference_date: str = ""

    def __post_init__(self) -> None:
        unknown = set(self.supported) - FEATURES
        if unknown:
            raise ValueError(
                f"unknown family-1 feature(s) {sorted(unknown)!r} in a support matrix; "
                f"the vocabulary is {sorted(FEATURES)!r}."
            )
        if self.deviations and not self.reference_date:
            raise ValueError(
                "deviations must be pinned to the reference they were checked against "
                "(ADR-0001 §Families.1) — set reference_date."
            )

    def supports(self, feature: str) -> bool:
        if feature not in FEATURES:
            raise ValueError(f"unknown family-1 feature {feature!r}")
        return feature in self.supported

    def gaps(self, required: set[str] | frozenset[str]) -> tuple[str, ...]:
        """The required features this implementation does NOT support, sorted —
        the shape both the request gate and the docs report."""
        unknown = set(required) - FEATURES
        if unknown:
            raise ValueError(f"unknown family-1 feature(s) {sorted(unknown)!r}")
        return tuple(sorted(set(required) - self.supported))


def _features_of_parts(parts) -> set[str]:
    """The features a list of content parts / items needs — recursing into a
    tool result, whose `output` may itself carry an image or audio part. A media
    part hidden inside a tool result must gate exactly like one sent directly,
    or an engine that declared no `vision` receives an image."""
    required: set[str] = set()
    for part in parts:
        part_type = part.get("type")
        if part_type == "input_image":
            required.add("vision")
        elif part_type == "input_audio":
            required.add("audio")
        elif part_type == "function_call_output":
            output = part.get("output")
            if isinstance(output, list):
                required |= _features_of_parts(output)
    return required


def required_features(request: dict) -> frozenset[str]:
    """The features a parsed request NEEDS from its implementation.

    Only what the request explicitly asks for counts: the input modalities it
    carries, the tool kinds it declares, and whether it demands a JSON schema.
    Output-side features are never "requested" — a caller cannot ask for a
    citation, a refusal, or a reasoning item — and neither is streaming, which
    every implementation of this route provides.
    """
    required: set[str] = set()

    for item in request.get("input", []):
        parts = item.get("content", []) if "role" in item else [item]
        required |= _features_of_parts(parts)

    for tool in request.get("tools", []):
        tool_type = tool.get("type")
        if tool_type == "function":
            required.add("function_tools")
        elif tool_type == "mcp":
            required.add("mcp_tools")

    if request.get("text", {}).get("format", {}).get("type") == "json_schema":
        required.add("structured_outputs")

    return frozenset(required)


def ensure_supported(request: dict, matrix: SupportMatrix, *, implementation: str = "") -> None:
    """Refuse a request needing a feature the selected implementation lacks.

    400 `invalid_request`, not 503: the service is healthy and the request is
    well-formed — it is simply addressed at an implementation that cannot serve
    it, and the message names the missing feature so the user can re-choose
    (no silent substitution, ADR-0007 §10's explicit-implementation rule).
    """
    missing = matrix.gaps(required_features(request))
    if missing:
        subject = f"Implementation {implementation!r}" if implementation else "This implementation"
        raise invalid_request(
            f"{subject} does not support {', '.join(missing)} — this request needs it. "
            "Choose an implementation that declares the feature (see its support matrix)."
        )
