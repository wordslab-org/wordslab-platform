"""The templates' own declarations are valid on disk (ticket #74).

Two templates ship in the repo (ADR-0031 §1): `service-template/` (the
service ritual) and `implementation-template/` (the capability-
implementation ritual, living at the repo root). If either's declaration
drifts out of the declared shape, the suite is red at the template itself —
a copied service or implementation can't start from a broken declaration.
"""

from __future__ import annotations

import shutil
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
# data; these tests assert the SHAPE of what shipped.)


def test_the_service_template_bar_is_declared_and_discoverable():
    svc = load_service_toml(SERVICE_TEMPLATE / "service.toml")
    bar = svc.capabilities[0].learning  # the loader validated every artifact
    assert bar is not None
    # the four graded levels — one artifact per level (ADR-0024 §1)
    assert [d.level for d in bar.docs] == list(DOC_LEVELS)
    for ref, doc in zip(bar.docs, bar.parsed_docs):
        assert doc.level == ref.level
        assert doc.capability == "canary"
        assert doc.implementation is None
        assert doc.title
        assert doc.keywords
        assert isinstance(doc.mcp_tools, tuple)
        assert doc.sections == CANONICAL_SECTIONS
    # the how-an-agent-drives-me skill — declared AND discoverable on disk
    assert bar.skill is not None
    assert bar.not_agent_operable is None
    assert bar.parsed_skill.name == bar.skill.name
    assert bar.parsed_skill.description
    assert (SERVICE_TEMPLATE / bar.skill.path).is_file()


def test_the_service_template_ships_the_not_agent_operable_pattern(tmp_path):
    """AC3: the note pattern is a first-class declared value — accepted
    where declared (the shipped example documents it as a comment; the
    loader accepts it, tested on a fixture copy)."""
    text = (SERVICE_TEMPLATE / "service.toml").read_text()
    assert "#     not-agent-operable = \"...\"" in text  # the commented pattern
    skill_block = """\
[template-service.canary.learning.skill]
name = "drive-canary"
path = "skills/canary/SKILL.md"
"""
    assert skill_block in text, "fixture drift"
    # TOML ordering: the note sits directly under the [learning] header —
    # after a [[docs]] header it would be swallowed into that table
    header = "[template-service.canary.learning]\n"
    assert header in text, "fixture drift"
    note = text.replace(
        header,
        header
        + 'not-agent-operable = "A physical-machine panel driven by its own UI;'
        ' an agent has no deterministic surface to drive."\n',
    ).replace(skill_block, "")
    # the loader resolves paths relative to the declaration's directory —
    # copy the shipped artifacts next to the fixture copy
    shutil.copytree(SERVICE_TEMPLATE / "docs", tmp_path / "docs")
    shutil.copytree(SERVICE_TEMPLATE / "skills", tmp_path / "skills")
    path = tmp_path / "service.toml"
    path.write_text(note)
    svc = load_service_toml(path)
    bar = svc.capabilities[0].learning
    assert bar.skill is None
    assert bar.not_agent_operable
    assert len(bar.parsed_docs) == 4


@requires_sibling_template
def test_the_implementation_template_bar_is_declared_and_discoverable():
    impl = load_implementation_toml(
        REPO_ROOT / "implementation-template" / "implementation.toml"
    )
    bar = impl.learning  # the loader validated every artifact
    assert bar is not None
    assert [d.level for d in bar.docs] == list(DOC_LEVELS)
    for ref, doc in zip(bar.docs, bar.parsed_docs):
        assert doc.level == ref.level
        assert doc.implementation == "qwen3-4b"
        assert doc.capability is None
        assert doc.sections == CANONICAL_SECTIONS
    assert bar.skill is not None
    assert bar.parsed_skill.name == bar.skill.name
    assert (IMPLEMENTATION_TEMPLATE / bar.skill.path).is_file()