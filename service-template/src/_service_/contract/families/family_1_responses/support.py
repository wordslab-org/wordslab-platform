"""Family 1 — the per-implementation support matrix (ADR-0001 §Families.1,
under the conformance clause ADR-0004 amends in).

ADR-0004 makes a capability's API the **union of its implementation
variants**: implementations solve the same problem with different tradeoffs and
may support different slices of the family surface — a local GGUF engine may not
do audio input, a cloud provider may not return reasoning items. The contract
does not force-fit them into one identical shape; it requires the difference to
be **declared and documented** instead of discovered by a failed request.

So each implementation declares a `SupportMatrix`: which family-1 features it
actually supports, plus its documented deviations (prose, for the catalog and
the docs). The matrix is FEATURE SUPPORT — not a quality or speed ranking.
Rankings are dynamic (artificialanalysis at selection time) and must never be
stored in a declaration (ADR-0031 §5); this is the opposite kind of fact, and
the two never mix.

Where it is declared: the implementation's adapter module exports
`SUPPORT: SupportMatrix` (code, next to the adapter that must honor it). It is
NOT a key in `implementation.toml` — that declaration is a closed shape
(ADR-0031 §2/§3) and adding a support key there would contradict §5.

How it is used: `routes(..., support=...)` refuses a request that needs a
feature the selected implementation does not have (400, naming the feature),
instead of letting the engine fail obscurely; the catalog + dashboard read it to
show what an implementation can do. Output-side features (citations, reasoning,
refusals) cannot be requested — they are discovered from the response — so the
matrix's job for those is documentation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...base.errors import invalid_request

# The family-1 features an implementation may or may not support. Input-side
# features are requested explicitly; output-side ones are documented.
FEATURES = frozenset(
    {
        "vision",  # input_image
        "audio",  # input_audio
        "function_tools",
        "mcp_tools",
        "structured_outputs",  # text.format json_schema
        "citations",  # output_text annotations
        "reasoning",  # reasoning items
        "refusals",  # refusal content parts
        "streaming",  # stream: true
    }
)


@dataclass(frozen=True)
class SupportMatrix:
    """What ONE implementation of a family-1 capability supports.

    `supported` holds feature names from `FEATURES` (loud on an unknown name —
    a typo must not silently read as "unsupported"). `deviations` carries the
    documented deviations from the upstream Responses shapes (ADR-0001: "follow
    upstream OpenAI shapes; document deviations, pinned to a reference date").
    """

    supported: frozenset[str]
    deviations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        unknown = set(self.supported) - FEATURES
        if unknown:
            raise ValueError(
                f"unknown family-1 feature(s) {sorted(unknown)!r} in a support matrix; "
                f"the vocabulary is {sorted(FEATURES)!r}."
            )
        if not self.supported:
            raise ValueError(
                "a support matrix with no supported feature cannot serve the capability — "
                "declare at least one, or the implementation does not implement the family."
            )

    def supports(self, feature: str) -> bool:
        if feature not in FEATURES:
            raise ValueError(f"unknown family-1 feature {feature!r}")
        return feature in self.supported

    def gaps(self, required: set[str] | frozenset[str]) -> tuple[str, ...]:
        """The required features this implementation does NOT support, sorted —
        the shape both the request gate and the catalog report."""
        unknown = set(required) - FEATURES
        if unknown:
            raise ValueError(f"unknown family-1 feature(s) {sorted(unknown)!r}")
        return tuple(sorted(set(required) - self.supported))


def required_features(request: dict) -> frozenset[str]:
    """The features a parsed request NEEDS from its implementation.

    Only what the request explicitly asks for counts: the input modalities it
    carries, the tool kinds it declares, whether it demands a JSON schema, and
    whether it streams. Output-side features are never "requested" — a caller
    cannot ask for a citation, a refusal, or a reasoning item.
    """
    required: set[str] = set()

    for item in request.get("input", []):
        parts = item.get("content", []) if "role" in item else [item]
        for part in parts:
            part_type = part.get("type")
            if part_type == "input_image":
                required.add("vision")
            elif part_type == "input_audio":
                required.add("audio")

    for tool in request.get("tools", []):
        tool_type = tool.get("type")
        if tool_type == "function":
            required.add("function_tools")
        elif tool_type == "mcp":
            required.add("mcp_tools")

    if request.get("text", {}).get("format", {}).get("type") == "json_schema":
        required.add("structured_outputs")

    if request.get("stream"):
        required.add("streaming")

    return frozenset(required)


def ensure_supported(request: dict, matrix: SupportMatrix, *, implementation: str) -> None:
    """Refuse a request needing a feature the selected implementation lacks.

    400 `invalid_request`, not 503: the service is healthy and the request is
    well-formed — it is simply addressed at an implementation that cannot serve
    it, and the message names the missing feature so the user can re-choose
    (no silent substitution, ADR-0007 §10's explicit-implementation rule).
    """
    missing = matrix.gaps(required_features(request))
    if missing:
        raise invalid_request(
            f"Implementation {implementation!r} does not support "
            f"{', '.join(missing)} — this request needs it. Choose an "
            "implementation that declares the feature (see its support matrix)."
        )
