"""Declaration surface — service.toml + implementation.toml (ticket #74;
ADR-0002 §5, ADR-0018 §8, ADR-0031 — declaration model v2).

Loads and validates the two declaration files. A **service** is a set of
capabilities declared in `service.toml`; a **capability implementation** is
declared in `implementation.toml` — a service has no implementation
(ADR-0031 §1). Declarations are **data read at startup / install /
catalog-build time**: the conformance suite and the installer read them; the
service must not restate them in code.
"""

from __future__ import annotations

from .implementation_toml import (
    ContentPart,
    Dependency,
    Implementation,
    ImplementationDeclarationError,
    Requirements,
    load_implementation_toml,
)
from .model_selection import (
    GOALS,
    compute_supported,
    order_supported,
    validate_goal,
)
from .service_toml import (
    Capability,
    Service,
    ServiceDeclarationError,
    load_service_toml,
)

__all__ = [
    "GOALS",
    "Capability",
    "ContentPart",
    "Dependency",
    "Implementation",
    "ImplementationDeclarationError",
    "Requirements",
    "Service",
    "ServiceDeclarationError",
    "compute_supported",
    "load_implementation_toml",
    "load_service_toml",
    "order_supported",
    "validate_goal",
]