"""Learning-bar tests (ticket #75; ADR-0024 §1, ADR-0002 §7, ADR-0031 §2/§3).

The learning/operability bar is **DISCOVERED BY LAYOUT and audited at load**
(ADR-0024 §1 — declared, auditable, not aspirational): no TOML sub-table
lists the artifacts. Path + name conventions do the declaring, and the
loader audits what it finds:

- the **four graded doc levels** (how-to-use · how-it-works ·
  study-in-depth · going-further) — one Markdown artifact per level, the
  FILENAME is the level, so a level can never drift from its declaration;
- the **how-an-agent-drives-me skill** — `skills/<slug>/SKILL.md`, its
  directory name IS the registry slug (ADR-0008), its front-matter carrying
  the one-line `description` the registry loads it by;
- **no skill in the expected directory** is the honest record, and what it
  MEANS differs by level (no theater, ADR-0024 §1) — a CAPABILITY with none
  is not-agent-operable, a SERVICE with none has no skill *above* its
  capabilities, an IMPLEMENTATION with none adds nothing specific;
- every artifact FOUND exists and parses — a malformed artifact is a fake
  artifact (loud rejection at load); missing artifacts are `gaps`, not
  errors (the bar is mandatory to publish, ADR-0018, not to boot).

The conventions, per subject:

    service         docs/service/<level>.md   skills/service/<slug>/SKILL.md
    capability      docs/capabilities/<cap>/<level>.md
                    skills/capabilities/<cap>/<slug>/SKILL.md
    implementation  docs/<level>.md           skills/<slug>/SKILL.md

Tests run at the data seam: the loader API (`load_service_toml` /
`load_implementation_toml` raise a precise `*DeclarationError`) plus the
layout discovery, from inline TOML + Markdown written via tmp_path. The
shipped skeletons are asserted in `test_declaration_files.py`.
"""

from __future__ import annotations

import textwrap

import pytest

from contract.declaration import (
    CANONICAL_SECTIONS,
    DOC_LEVELS,
    BarDoc,
    ImplementationDeclarationError,
    LearningBar,
    Service,
    ServiceDeclarationError,
    SkillDoc,
    load_bar_doc,
    load_implementation_toml,
    load_service_toml,
)


def write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))
    return path


# ------------------------------------------------------------- fixture parts
#
# Build fixtures from NAMED part constants (never chained `.replace()`): a
# no-op replace tests the unmutated fixture. The mutations swap whole
# artifacts, so a rejection case can never silently become a happy path.


def bar_doc_md(level: str, *, title: str = "Echo",
               keywords: str = "  - echo\n  - consent", mcp_tools: str = "[]",
               body: str | None = None) -> str:
    """One graded doc file — canonical front-matter + section schema. The
    LEVEL is the filename; a `level:` front-matter key would be a duplicate
    declaration (there is a rejection test for exactly that)."""
    if body is None:
        body = (
            f"# {title}\n\n"
            "## Summary\n\n"
            "Echo bounces text back through the service's three callable"
            " surfaces (API, MCP, UI).\n\n"
            "## Details\n\n"
            "The level's depth content — usage steps, internals or design"
            " depending on the level.\n\n"
            "## See also\n\n"
            "- `/v1/echo` — the api description entry point.\n"
        )
    return (
        "---\n"
        f"title: {title}\n"
        "keywords:\n"
        f"{keywords}\n"
        f"mcp-tools: {mcp_tools}\n"
        "---\n"
        f"{body}"
    )


SKILL_MD = """\
---
name: drive-canary
description: How an agent drives the canary capability — every operation, \
parameter and consent flag, over /mcp or /v1.
---
# drive-canary

Authenticate with the service's Bearer key, then drive the canary through
`POST /v1/echo` (or the auto-generated MCP tool at `/mcp`): the body carries
`text` and the consent flag (`may_use` default / `private_secret`).
"""

SERVICE_TOML = """\
name = "svc"
description = "d"
version = "1.0.0"

[requirements]
disk-gb = 0.1
ram-gb = 0.1

[svc.canary]
description = "d"
version = "0.1.0"
api = "/v1/echo"
api-functions = "d"
versions-history = "d"
required = false

[svc.canary.ui]
description = "d"
versions-history = "d"
"""


def write_service_root(tmp_path, *, toml: str = SERVICE_TOML,
                       doc_overrides: dict[str, str] | None = None,
                       skill_md: str | None = SKILL_MD, write_files: bool = True):
    """A service root: `service.toml` + the conventional bar artifacts."""
    doc_overrides = doc_overrides or {}
    write(tmp_path, "service.toml", toml)
    if write_files:
        for level in DOC_LEVELS:
            write(
                tmp_path, f"docs/capabilities/canary/{level}.md",
                doc_overrides.get(level) or bar_doc_md(level),
            )
        if skill_md is not None:
            write(tmp_path, "skills/capabilities/canary/drive-canary/SKILL.md", skill_md)
    return tmp_path / "service.toml"


# --------------------------------------------------- the bar is discovered


def test_the_bar_is_discovered_by_layout(tmp_path):
    """The capability's docs + skill are found by convention — the
    declaration carries no [learning] table (there is nothing to declare)."""
    path = write_service_root(tmp_path)
    svc = load_service_toml(path)
    assert isinstance(svc, Service)
    assert "[learning]" not in path.read_text()
    canary = svc.capabilities[0]
    assert isinstance(canary.learning, LearningBar)
    assert canary.learning.subject == "canary"

    # the four graded levels — one artifact per level, the filename IS it
    assert [d.level for d in canary.learning.docs] == list(DOC_LEVELS)
    assert all(isinstance(d, BarDoc) for d in canary.learning.docs)
    assert canary.learning.docs[0].path.name == "how-to-use.md"
    assert canary.learning.level("how-to-use").title == "Echo"

    # the how-an-agent-drives-me skill — discovered, the directory IS the slug
    assert isinstance(canary.learning.skill, SkillDoc)
    assert canary.learning.skill.name == "drive-canary"
    assert canary.learning.skill.description.startswith("How an agent drives")
    assert canary.learning.skill.path.name == "SKILL.md"

    assert canary.learning.gaps == ()
    assert canary.learning.not_agent_operable is False


def test_the_service_level_bar_is_discovered_too(tmp_path):
    """ADR-0024 §1: every SERVICE carries the bar as well — its capabilities
    overview + its UI doc (the service's own API + UI), at docs/service/."""
    path = write_service_root(tmp_path)
    for level in DOC_LEVELS:
        write(tmp_path, f"docs/service/{level}.md",
              bar_doc_md(level, title="The Echo service"))
    write(tmp_path, "skills/service/drive-svc/SKILL.md",
          SKILL_MD.replace("drive-canary", "drive-svc"))
    svc = load_service_toml(path)
    assert svc.learning.subject == "svc"
    assert [d.level for d in svc.learning.docs] == list(DOC_LEVELS)
    assert svc.learning.skill.name == "drive-svc"
    assert svc.learning.gaps == ()


def test_a_subject_with_no_bar_loads_with_gaps(tmp_path):
    """The bar is mandatory to publish (ADR-0018's tiers), not to boot — a
    service still loads while the bar is being written; the missing artifacts
    are recorded as gaps. The missing SERVICE-level skill is NOT a gap: a
    service-level skill is not required (maintainer, #75) — the service has
    no agent-operable capability either, so it is honestly not agent-operable."""
    path = write_service_root(tmp_path, write_files=False)
    svc = load_service_toml(path)
    assert svc.learning.skill is None
    assert svc.learning.kind == "service"
    assert svc.learning.agent_operable_subjects == ()
    assert svc.learning.not_agent_operable is True
    assert sum(1 for g in svc.learning.gaps if g.startswith("docs:")) == 4
    assert not any(g.startswith("skill:") for g in svc.learning.gaps)
    assert svc.capabilities[0].learning.docs == ()


def test_no_skill_directory_is_the_not_agent_operable_case(tmp_path):
    """By convention: no skill in the expected directory IS the
    not-agent-operable case for a CAPABILITY — no declaration, no fake skill
    (no theater)."""
    path = write_service_root(tmp_path, skill_md=None)
    svc = load_service_toml(path)
    bar = svc.capabilities[0].learning
    assert bar.skill is None
    assert bar.kind == "capability"
    assert bar.not_agent_operable is True
    assert bar.agent_operable is False
    assert len(bar.docs) == 4  # the docs are still discovered + audited
    assert any(g.startswith("skill:") for g in bar.gaps)


def test_the_three_levels_read_a_missing_skill_differently(tmp_path):
    """The SAME absence means three different things (ADR-0024 §1):

    - service, no service-level skill but an agent-operable capability →
      still agent-operable overall (the capability's skill covers it);
    - capability, no skill → genuinely not agent-operable;
    - implementation, no skill → nothing specific in addition; never a gap
      in the surface (False).
    """
    # (a) capability skill present → the service is agent-operable overall
    path = write_service_root(tmp_path)
    svc = load_service_toml(path)
    assert svc.learning.skill is None  # no service-level skill shipped
    assert svc.learning.kind == "service"
    assert svc.learning.agent_operable_subjects == ("canary",)
    assert svc.learning.agent_operable is True
    assert svc.learning.not_agent_operable is False


def test_a_service_with_no_agent_operable_capability_is_not_agent_operable(tmp_path):
    """A service shipping no service-level skill AND whose capabilities are
    all not-agent-operable is not agent-operable as a whole."""
    path = write_service_root(tmp_path, skill_md=None)
    svc = load_service_toml(path)
    assert svc.learning.agent_operable_subjects == ()
    assert svc.learning.agent_operable is False
    assert svc.learning.not_agent_operable is True


def test_a_service_level_skill_makes_the_service_agent_operable_on_its_own(tmp_path):
    """The service-level skill carries what no single capability covers — a
    service with one is agent-operable even with no agent-operable
    capability beneath it."""
    path = write_service_root(tmp_path, skill_md=None)
    for level in DOC_LEVELS:
        write(tmp_path, f"docs/service/{level}.md",
              bar_doc_md(level, title="The service"))
    write(tmp_path, "skills/service/drive-svc/SKILL.md",
          SKILL_MD.replace("drive-canary", "drive-svc"))
    svc = load_service_toml(path)
    assert svc.learning.skill.name == "drive-svc"
    assert svc.learning.agent_operable is True
    assert svc.learning.not_agent_operable is False
    assert svc.capabilities[0].learning.not_agent_operable is True  # it still is


# ------------------------------------------------------------ implementation
#
# The same rules, per implementation: the implementation's own directory
# holds docs/<level>.md + skills/<slug>/SKILL.md (ADR-0031 §3).


IMPL_TOML = """\
capability = "llm.model"
license = "Apache-2.0"

[identity]
name = "qwen3-4b"
version = "2026-05"
description = "A 4B LLM served locally."

[requirements]
disk-gb = 0.2
ram-gb = 0.3

[[dependencies]]
capability = "llm.engine"
min-version = "0.5.0"

[llm.model.local-model.qwen3-4b]
description = "The Qwen3 4B weights, quantized Q4_K_M."
version = "2026-05"
huggingface = "https://huggingface.co/Qwen/Qwen3-4B"
artificial-analysis = "qwen-3-4b"

[llm.model.local-model.qwen3-4b.requirements]
disk-gb = 2.5
ram-gb = 0.2
"""

IMPL_SKILL_MD = """\
---
name: drive-qwen3-4b
description: How an agent drives this llm.model implementation — pick it in \
the model catalog, call it through the capability's API.
---
# drive-qwen3-4b

Select this implementation (fit-gated), then drive it through the parent
capability's OpenAPI/MCP surface; parameters and consent flags are the
capability's.
"""


def write_impl_root(tmp_path, *, toml: str = IMPL_TOML,
                    doc_overrides: dict[str, str] | None = None,
                    skill_md: str | None = IMPL_SKILL_MD,
                    write_files: bool = True):
    doc_overrides = doc_overrides or {}
    write(tmp_path, "implementation.toml", toml)
    if write_files:
        for level in DOC_LEVELS:
            write(
                tmp_path, f"docs/{level}.md",
                doc_overrides.get(level) or bar_doc_md(level, title="Qwen3 4B"),
            )
        if skill_md is not None:
            write(tmp_path, "skills/drive-qwen3-4b/SKILL.md", skill_md)
    return tmp_path / "implementation.toml"


def test_the_implementation_bar_is_discovered_by_layout(tmp_path):
    """The implementation's own directory is the convention root: docs/ +
    skills/<slug>/ (ADR-0031 §3 as amended). The subject is the declared
    identity name, not the directory name (the copy ritual may not rename)."""
    root = tmp_path / "impl"
    root.mkdir()
    impl = load_implementation_toml(write_impl_root(root))
    assert isinstance(impl.learning, LearningBar)
    assert impl.learning.subject == "qwen3-4b"
    assert [d.level for d in impl.learning.docs] == list(DOC_LEVELS)
    assert impl.learning.docs[0].path.name == "how-to-use.md"
    assert impl.learning.skill.name == "drive-qwen3-4b"
    assert impl.learning.gaps == ()
    # the bar is the implementation's OWN — requirements unchanged
    assert impl.requirements.disk_gb == pytest.approx(0.2 + 2.5)


def test_an_implementation_with_no_skill_adds_nothing_specific(tmp_path):
    """An implementation is ADDITIVE: no skill means nothing specific on top
    of the capability's skill — never a gap in the agent surface, so
    `not_agent_operable` is False (unlike a capability's)."""
    root = tmp_path / "qwen3-4b"
    root.mkdir()
    impl = load_implementation_toml(write_impl_root(root, skill_md=None))
    assert impl.learning.kind == "implementation"
    assert impl.learning.skill is None
    assert impl.learning.agent_operable is False  # no own skill…
    assert impl.learning.not_agent_operable is False  # …but nothing missing
    assert len(impl.learning.docs) == 4


def test_an_implementation_with_no_bar_loads_with_gaps(tmp_path):
    """An implementation's missing skill is NOT a gap — it adds nothing
    specific on top of the capability's skill (maintainer, #75) — so only
    the four missing docs are recorded."""
    root = tmp_path / "qwen3-4b"
    root.mkdir()
    impl = load_implementation_toml(write_impl_root(root, write_files=False))
    assert impl.learning.docs == ()
    assert impl.learning.skill is None
    assert len(impl.learning.gaps) == 4  # the four docs — not the skill
    assert not any(g.startswith("skill:") for g in impl.learning.gaps)


# ------------------------------------------------------- loud-rejection rules
#
# Every loud-rejection rule gets a test feeding the offending artifact and
# asserting the specific message — a text grep of the shipped file proves
# nothing (the settled #74 lesson).


@pytest.mark.parametrize(
    "override,match",
    [
        # front-matter delimiters
        (lambda text: "\n".join(text.splitlines()[1:]), "must open with a `---`"),
        (
            lambda text: text[: text.index("mcp-tools: []\n") + len("mcp-tools: []\n")],
            "not closed",
        ),
        # unknown front-matter key — the canonical shape is closed
        (lambda text: text.replace("title: Echo", "title: Echo\nsurprise: x"), "unknown front-matter key"),
        # the level is the FILENAME — declaring it too is an unknown key
        (lambda text: text.replace("title: Echo", "title: Echo\nlevel: how-to-use"), "unknown front-matter key"),
        # title required
        (lambda text: text.replace("title: Echo\n", ""), "front-matter `title` must be a non-empty string"),
        # keywords — the doc is indexed for agents too
        (lambda text: text.replace("keywords:\n  - echo\n  - consent\n", "keywords: []\n"), "`keywords` must be a non-empty list"),
        # the canonical section schema — exact, in order (ADR-0024 §1)
        (lambda text: text.replace("## Details\n", "### Details\n"), "canonical section schema"),
        (lambda text: text.replace("## See also\n", "## See also\n\n## Extra\n"), "canonical section schema exactly"),
        # the body opens with the human title
        (lambda text: text.replace("# Echo\n", ""), "must open with a `# <title>` heading"),
        # a front-matter key declared twice fails loudly — no silent reset
        (lambda text: text.replace("title: Echo\n", "title: Echo\nmcp-tools: []\n"), "declares `mcp-tools` twice"),
        (
            lambda text: text.replace(
                "keywords:\n  - echo\n  - consent\n",
                "keywords:\n  - echo\n\nkeywords:\n  - consent\n",
            ),
            "declares `keywords` twice",
        ),
        # the H1 must AGREE with the indexable front-matter title
        (lambda text: text.replace("# Echo\n", "# Something Else\n"), "H1 and front-matter title disagree"),
        # a nested YAML map silently flattens — reject the indented line
        (
            lambda text: text.replace("title: Echo\n", "title: Echo\nmetadata:\n  author: x\n"),
            "is indented but is not a `- item` list entry",
        ),
    ],
)
def test_doc_artifact_rejections(tmp_path, override, match):
    level = "how-to-use"
    path = write_service_root(
        tmp_path, doc_overrides={level: override(bar_doc_md(level))}
    )
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)


def test_only_the_graded_filenames_are_docs(tmp_path):
    """A stray `docs/capabilities/canary/notes.md` is not a doc at all (never
    discovered) — but `load_bar_doc` still rejects an unknown level when
    asked directly, so the convention can't silently accept a bad name."""
    path = write_service_root(tmp_path)
    write(tmp_path, "docs/capabilities/canary/notes.md", bar_doc_md("how-to-use"))
    svc = load_service_toml(path)
    assert [d.level for d in svc.capabilities[0].learning.docs] == list(DOC_LEVELS)
    with pytest.raises(ServiceDeclarationError, match="is not a graded level"):
        load_bar_doc(
            tmp_path / "docs/capabilities/canary/notes.md",
            err=ServiceDeclarationError, where="(direct)",
        )


def test_a_fenced_code_block_heading_is_not_a_section(tmp_path):
    """A `## ` line inside a ``` fence is content, not a section — the
    schema scan must be fence-aware, or a doc quoting Markdown rejects
    itself."""
    level = "how-to-use"
    fenced = bar_doc_md(level) + "\n```markdown\n## Example\nx = 1\n```\n"
    path = write_service_root(tmp_path, doc_overrides={level: fenced})
    svc = load_service_toml(path)
    assert svc.capabilities[0].learning.level(level).sections == CANONICAL_SECTIONS


@pytest.mark.parametrize(
    "skill,match",
    [
        # description — the one-line summary the registry loads a skill by
        (
            lambda text: text.replace(
                "description: How an agent drives the canary capability — "
                "every operation, parameter and consent flag, over /mcp or /v1.\n",
                "",
            ),
            "front-matter `description` must be a non-empty string",
        ),
        # an empty body is a hollow artifact
        (lambda text: "\n".join(text.splitlines()[:4]) + "\n", "empty body"),
        # the front-matter name must be a slug
        (lambda text: text.replace("name: drive-canary", "name: Drive Canary"), "front-matter `name` must be a lowercase slug"),
        # the DIRECTORY name IS the registry slug — no drift
        (lambda text: text.replace("name: drive-canary", "name: drive-other"), "does not match its directory name"),
    ],
)
def test_skill_artifact_rejections(tmp_path, skill, match):
    path = write_service_root(tmp_path, skill_md=skill(SKILL_MD))
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)


def test_a_skill_front_matter_may_carry_registry_metadata(tmp_path):
    """ADR-0008: a skill is frontmatter + instructions + linked files — the
    bar only requires the discoverable `name` + `description`; extra keys
    (version, linked files, ...) are the registry's metadata, not an error."""
    skill_md = SKILL_MD.replace(
        "description: How an agent drives",
        "version: 1\ndescription: How an agent drives",
    )
    path = write_service_root(tmp_path, skill_md=skill_md)
    svc = load_service_toml(path)
    assert svc.capabilities[0].learning.skill.name == "drive-canary"


def test_two_skills_under_one_subject_are_rejected(tmp_path):
    """A subject ships exactly ONE how-an-agent-drives-me skill — a second
    directory makes the registry slug ambiguous; reject loudly."""
    path = write_service_root(tmp_path)
    write(tmp_path, "skills/capabilities/canary/drive-other/SKILL.md",
          SKILL_MD.replace("drive-canary", "drive-other"))
    with pytest.raises(ServiceDeclarationError, match="holds 2 skills"):
        load_service_toml(path)


def test_a_mis_named_skill_directory_is_rejected(tmp_path):
    """The directory name IS the registry slug (ADR-0008) — a skill directory
    whose name is not a legal slug is rejected, not silently skipped (a
    silently-skipped skill would be a bar artifact that never loads)."""
    path = write_service_root(tmp_path)
    write(tmp_path, "skills/capabilities/canary/Drive-Canary/SKILL.md",
          SKILL_MD.replace("drive-canary", "Drive-Canary"))
    with pytest.raises(ServiceDeclarationError, match="directory name IS the registry slug"):
        load_service_toml(path)


def test_skill_names_must_be_unique_within_the_service(tmp_path):
    """The authored registry entry is `<service>.skill.<slug>` (ADR-0008) —
    the service-level skill colliding with a capability's (or two
    capabilities' colliding) is rejected at load."""
    path = write_service_root(tmp_path)
    for level in DOC_LEVELS:
        write(tmp_path, f"docs/service/{level}.md",
              bar_doc_md(level, title="The Echo service"))
    # the SERVICE-level skill reuses the capability's slug
    write(tmp_path, "skills/service/drive-canary/SKILL.md", SKILL_MD)
    with pytest.raises(ServiceDeclarationError, match="unique within the service"):
        load_service_toml(path)


def test_a_learning_table_is_no_longer_declared(tmp_path):
    """The bar is not declared in the manifest anymore — a `[learning]`
    sub-table is an unknown key, and the loader says so (the layout is the
    declaration)."""
    path = write_service_root(tmp_path, toml=SERVICE_TOML + "\n[svc.canary.learning]\n")
    with pytest.raises(ServiceDeclarationError, match="unknown key"):
        load_service_toml(path)


def test_a_malformed_implementation_artifact_rejects(tmp_path):
    """The implementation side audits what it finds exactly like the service
    side — a malformed doc is a fake artifact (no theater)."""
    root = tmp_path / "qwen3-4b"
    root.mkdir()
    path = write_impl_root(
        root,
        doc_overrides={
            "how-to-use": bar_doc_md("how-to-use", title="Qwen3 4B").replace(
                "## Details\n", "### Details\n"
            )
        },
    )
    with pytest.raises(ImplementationDeclarationError, match="canonical section schema"):
        load_implementation_toml(path)
