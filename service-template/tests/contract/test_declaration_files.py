"""The templates' own declarations are valid on disk (ticket #74).

Two templates ship in the repo (ADR-0031 §1): `service-template/` (the
service ritual) and `implementation-template/` (the capability-
implementation ritual, living at the repo root). If either's declaration
drifts out of the declared shape, the suite is red at the template itself —
a copied service or implementation can't start from a broken declaration.
"""

from __future__ import annotations

from pathlib import Path

from contract.declaration import load_implementation_toml, load_service_toml

SERVICE_TEMPLATE = Path(__file__).resolve().parents[2]
REPO_ROOT = SERVICE_TEMPLATE.parent


def test_the_service_template_own_service_toml_is_valid():
    svc = load_service_toml(SERVICE_TEMPLATE / "service.toml")
    assert svc.name == "template-service"
    assert svc.version
    assert svc.description
    assert svc.requirements["disk-gb"] > 0
    assert svc.requirements["ram-gb"] > 0
    assert svc.capabilities == ()  # the canary arrives with #71


def test_the_implementation_template_toml_is_valid():
    """The copy-per-implementation skeleton validates through the same
    loader a contributor's copied file will use."""
    impl = load_implementation_toml(
        REPO_ROOT / "implementation-template" / "implementation.toml"
    )
    assert impl.capability == "llm.model"
    assert impl.source == "local-weights"
    assert impl.license == "Apache-2.0"
    assert impl.privacy_tier == "local"
    part = impl.contents[0]
    assert part.type == "model"
    assert part.huggingface.startswith("https://huggingface.co/")
    assert part.artificial_analysis
    assert impl.requirements.disk_gb >= part.facts["disk-gb"]
    assert impl.dependencies[0].capability == "llm.engine"


def test_no_service_implementation_toml_in_the_service_template():
    """ADR-0031 §1: a service is a set of capabilities and has NO
    implementation — the service template must not ship one."""
    assert not (SERVICE_TEMPLATE / "implementation.toml").exists()
    assert not (SERVICE_TEMPLATE / "implementation.template.toml").exists()


def test_no_supported_recommended_or_ranks_keys_in_template_declarations():
    for path in (
        SERVICE_TEMPLATE / "service.toml",
        REPO_ROOT / "implementation-template" / "implementation.toml",
    ):
        text = path.read_text()
        for key in ("supported", "recommended", "ranks"):
            assert not any(
                line.strip().startswith(f"{key} ")
                or line.strip().startswith(f"{key}=")
                for line in text.splitlines()
                if not line.strip().startswith("#")
            )