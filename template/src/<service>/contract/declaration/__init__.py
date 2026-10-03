"""Declaration surface — service.toml + implementation.toml (ticket #74).

Loads and validates the template's two declaration files (ADR-0002 §5,
ADR-0018 §8, ADR-0027). A declaration is **data read at startup / install /
catalog-build time**: the conformance suite and the installer read it; the
service must not restate it in code.
"""

from __future__ import annotations

from .implementation_toml import (
    Implementation,
    ImplementationDeclarationError,
    ResourceProfile,
    load_implementation_toml,
)
from .model_selection import (
    GOALS,
    compute_recommended,
    compute_supported,
    validate_goal,
)
from .service_toml import (
    DECLARED_FAMILIES,
    Service,
    ServiceDeclarationError,
    load_service_toml,
)

__all__ = [
    "DECLARED_FAMILIES",
    "GOALS",
    "Implementation",
    "ImplementationDeclarationError",
    "ResourceProfile",
    "Service",
    "ServiceDeclarationError",
    "compute_recommended",
    "compute_supported",
    "load_implementation_toml",
    "load_service_toml",
    "validate_goal",
]
