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

from contract.declaration import (
    CANONICAL_SECTIONS,
    DOC_LEVELS,
    load_implementation_toml,
    load_service_toml,
)

SERVICE_TEMPLATE = Path(__file__).resolve().parents[2]
REPO_ROOT = SERVICE_TEMPLATE.parent
IMPLEMENTATION_TEMPLATE = REPO_ROOT / "implementation-template"

# The implementation-template assertions are TEMPLATE-REPO facts: they read
# the sibling `implementation-template/` directory, which does not travel
# with a copied service (the copy-to-start ritual copies `service-template/`
# alone). Running inside a copied service they skip — the template's own
# suite stays green out of the box (ticket #71's acceptance).
requires_sibling_template = pytest.mark.skipif(
    not IMPLEMENTATION_TEMPLATE.is_dir(),
    reason="running inside a copied service — `implementation-template/` is a template-repo artifact",
)


def test_the_service_template_own_service_toml_is_valid():
    svc = load_service_toml(SERVICE_TEMPLATE / "service.toml")
    # Identity is DATA (the declaration); the suite is identity-agnostic so
    # the copy-to-start ritual's rename keeps it green (ticket #71).
    assert svc.name
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


def test_the_placement_checker_declares_no_phantom_route():
    """The placement capability ships with the template (ticket #275) as a
    DATA surface: it mounts no route and contributes no OpenAPI fragment, so
    its declared `api` entry point must be the service's own `/openapi.json`
    — a `/v1/...` path that never appears in that document would promise a
    routable capability that does not exist (ADR-0031 §2)."""
    svc = load_service_toml(SERVICE_TEMPLATE / "service.toml")
    placement = next(c for c in svc.capabilities if c.name == "placement")
    assert placement.api == "/openapi.json"
    assert placement.ui_menu == ()
    assert placement.required is False

    # the whole document is still describable — the capability is documented
    # in prose, which is where a data surface is described
    assert "data surface" in placement.description.lower()
    assert "no route" in placement.description.lower()


@requires_sibling_template
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
    paths = [SERVICE_TEMPLATE / "service.toml"]
    if IMPLEMENTATION_TEMPLATE.is_dir():
        paths.append(IMPLEMENTATION_TEMPLATE / "implementation.toml")
    for path in paths:
        text = path.read_text()
        for key in ("supported", "recommended", "ranks"):
            assert not any(
                line.strip().startswith(f"{key} ")
                or line.strip().startswith(f"{key}=")
                for line in text.splitlines()
                if not line.strip().startswith("#")
            )


# ------------------------------------------------------------- learning bar
# (ticket #75 — the shipped skeletons are asserted, not grepped: the loaders
# above already validate both declarations, so the bar's presence is real
# data; these tests assert the SHAPE of what shipped. The bar is discovered
# by layout — the files ARE the declaration.)


def test_the_service_template_bar_is_discovered_by_layout():
    svc = load_service_toml(SERVICE_TEMPLATE / "service.toml")
    # the SERVICE's own bar — its capabilities overview + UI docs
    assert svc.learning.subject == svc.name
    assert svc.learning.kind == "service"
    assert [d.level for d in svc.learning.docs] == list(DOC_LEVELS)
    assert svc.learning.skill.name == "drive-svc"
    assert svc.learning.gaps == ()
    # the shipped service-level skill covers what no capability does; the
    # service is agent-operable, and the canary is agent-operable itself
    assert svc.learning.agent_operable is True
    assert svc.learning.not_agent_operable is False
    assert svc.learning.agent_operable_subjects == ("canary", "placement")

    # the CANARY's bar — the detail of its API + UI
    bar = svc.capabilities[0].learning
    assert bar.subject == "canary"
    assert bar.kind == "capability"
    assert [d.level for d in bar.docs] == list(DOC_LEVELS)
    for doc in bar.docs:
        assert doc.title
        assert doc.keywords
        assert doc.mcp_tools == ()
        assert doc.sections == CANONICAL_SECTIONS
        assert doc.path.parent.name == "canary"
    # the how-an-agent-drives-me skill — its directory IS the registry slug
    assert bar.skill.name == "drive-canary"
    assert bar.skill.path.parent.name == "drive-canary"
    assert bar.skill.description
    assert bar.not_agent_operable is False


def test_the_template_ships_no_learning_table():
    """The bar is discovered by layout, not declared — the shipped
    declarations carry no `[learning]` table at all (the comment explaining
    the conventions is a comment, not a key)."""
    for path in (
        SERVICE_TEMPLATE / "service.toml",
        IMPLEMENTATION_TEMPLATE / "implementation.toml",
    ):
        if not path.is_file():
            continue
        keys = [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip().startswith("[") and "learning" in line
        ]
        assert keys == [], f"{path.name} still declares {keys}"


@requires_sibling_template
def test_the_implementation_template_bar_is_discovered_by_layout():
    impl = load_implementation_toml(
        REPO_ROOT / "implementation-template" / "implementation.toml"
    )
    bar = impl.learning  # the loader validated every artifact
    assert bar.subject == "qwen3-4b"
    assert bar.kind == "implementation"
    assert [d.level for d in bar.docs] == list(DOC_LEVELS)
    for doc in bar.docs:
        assert doc.sections == CANONICAL_SECTIONS
    assert bar.skill.name == "drive-qwen3-4b"
    assert bar.skill.description
    assert bar.gaps == ()