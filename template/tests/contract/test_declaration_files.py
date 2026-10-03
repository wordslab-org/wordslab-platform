"""The template's own declarations are valid on disk (ticket #74).

The template ships its own `service.toml` + `implementation.toml`; if either
drifts out of the declared shape, the suite is red at the template itself —
a copied service can't start from a broken declaration.
"""

from __future__ import annotations

from pathlib import Path

from contract.declaration import (
    load_implementation_toml,
    load_service_toml,
)

TEMPLATE_ROOT = Path(__file__).resolve().parents[2]


def test_the_template_own_service_toml_is_valid():
    svc = load_service_toml(TEMPLATE_ROOT / "service.toml")
    assert svc.name == "template-service"
    assert svc.version
    assert svc.description
    assert svc.families == ()  # family modules arrive with #76–#84
    assert svc.capabilities == ()  # the canary arrives with #71


def test_the_template_own_implementation_toml_is_valid():
    impl = load_implementation_toml(TEMPLATE_ROOT / "implementation.toml")
    assert impl.kind == "service"
    assert impl.source == "local-weights"
    assert impl.license == "Apache-2.0"
    assert impl.privacy_tier == "local"
    assert impl.engine_dependency is None  # only model implementations declare one


def test_no_supported_or_recommended_keys_stored_in_template_declarations():
    for name in ("service.toml", "implementation.toml"):
        text = (TEMPLATE_ROOT / name).read_text()
        for key in ("supported", "recommended"):
            # the words appear only in the explanatory comment, never as keys
            assert f"{key} =" not in text.replace(f"# `{key}`", "")
            assert not any(
                line.strip().startswith(f"{key} ")
                or line.strip().startswith(f"{key}=")
                for line in text.splitlines()
                if not line.strip().startswith("#")
            )
