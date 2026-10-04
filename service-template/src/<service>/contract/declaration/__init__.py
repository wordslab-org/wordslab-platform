"""Declaration surface — service.toml + implementation.toml (ticket #74;
ADR-0002 §5, ADR-0018 §8, ADR-0031 — declaration model v2/v3).

Loads and validates the two declaration files. A **service** is a set of
capabilities declared in `service.toml` (own properties first, then one
documentation section per capability, `[<service-name>.<capability-name>]`);
a **capability implementation** is declared in `implementation.toml` (own
properties first, then one documentation section per content part,
`[<capability>.<content-part-type>.<content-part-name>]` — each type may
appear several times). A service has no implementation (ADR-0031 §1).
Declarations are **data read at startup / install / catalog-build time**;
the implementation-specific install function receives the typed
`Implementation` object as its configuration data.
"""

from __future__ import annotations

from .implementation_toml import (
    ContentPart,
    Dependency,
    Implementation,
    ImplementationDeclarationError,
    Requirements,
    aggregate_requirements,
    load_implementation_toml,
)
from .learning_bar import (
    CANONICAL_SECTIONS,
    DOC_LEVELS,
    BarDoc,
    DocRef,
    LearningBar,
    SkillDoc,
    SkillRef,
    load_bar_doc,
    load_skill_md,
    validate_learning,
)
from .model_selection import (
    GOALS,
    compute_supported,
    order_supported,
    validate_goal,
)
from .service_toml import (
    Capability,
    MenuItem,
    Service,
    ServiceDeclarationError,
    load_service_toml,
)

__all__ = [
    "CANONICAL_SECTIONS",
    "DOC_LEVELS",
    "GOALS",
    "BarDoc",
    "Capability",
    "ContentPart",
    "Dependency",
    "DocRef",
    "Implementation",
    "ImplementationDeclarationError",
    "LearningBar",
    "MenuItem",
    "Requirements",
    "Service",
    "ServiceDeclarationError",
    "SkillDoc",
    "SkillRef",
    "aggregate_requirements",
    "compute_supported",
    "load_bar_doc",
    "load_implementation_toml",
    "load_service_toml",
    "load_skill_md",
    "order_supported",
    "validate_goal",
    "validate_learning",
]