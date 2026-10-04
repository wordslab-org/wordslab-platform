"""The templates' own declarations are valid on disk (ticket #74).

Two templates ship in the repo (ADR-0031 §1): `service-template/` (the
service ritual) and `implementation-template/` (the capability-
implementation ritual, living at the repo root). If either's declaration
drifts out of the declared shape, the suite is red at the template itself —
a copied service or implementation can't start from a broken declaration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
    # The canary ships with the template (ticket #71) — the proof capability.
    canary = svc.capabilities[0]
    assert canary.name == "canary"
    assert canary.api == "/v1/echo"
    assert canary.required is False
    assert canary.ui_menu[0].entry == "/echo"


def test_the_implementation_template_toml_is_valid():
    """The copy-per-implementation skeleton validates through the same
    loader a contributor's copied file will use."""
    impl = load_implementation_toml(
        REPO_ROOT / "implementation-template" / "implementation.toml"
    )
    assert impl.capability == "llm.model"
    assert impl.license == "Apache-2.0"
    part = impl.contents[0]
    assert part.type == "local-model"
    assert part.name == "qwen3-4b"
    assert part.huggingface.startswith("https://huggingface.co/")
    assert part.artificial_analysis
    assert impl.own_requirements.disk_gb == 0.2
    # aggregation: own + parts (sum/union)
    assert impl.requirements.disk_gb == pytest.approx(0.2 + part.facts["disk-gb"])
    assert impl.requirements.vram_gb == part.requirements.vram_gb
    assert any(p.type == "local-model" for p in impl.contents)  # not all-cloud
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