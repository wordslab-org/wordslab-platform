"""Learning-bar tests (ticket #75; ADR-0024 §1, ADR-0002 §7, ADR-0031 §2/§3).

The learning/operability bar is DECLARED (route 1 — ADR-0024 §1: "declared
in the service template"): per capability in `service.toml`
(`[<service>.<capability>.learning]`), per implementation in
`implementation.toml` (`[learning]`). The declared shape carries:

- the **four graded doc levels** (how-to-use · how-it-works ·
  study-in-depth · going-further) — each a distinct Markdown artifact with
  its `level` in the front-matter (never one flattened document), declared
  with `level` + `path`;
- exactly one of the **how-an-agent-drives-me skill** (a registry `skill`
  entry, ADR-0008) or the explicit **"not agent-operable" note** — a fake
  skill is theater (ADR-0024 §1), so the loader rejects both-declared and
  neither-declared loudly;
- declared doc/skill files must EXIST and parse — a declared-but-fake
  artifact fails at load (no theater).

Tests run at the data seam: the loader API (`load_service_toml` /
`load_implementation_toml` raise a precise `*DeclarationError`) plus the
front-matter/doc reader, from inline TOML + Markdown written via tmp_path.
The shipped skeletons themselves are asserted in `test_declaration_files.py`.
"""

from __future__ import annotations

import textwrap

import pytest

from contract.declaration import (
    DOC_LEVELS,
    BarDoc,
    DocRef,
    LearningBar,
    Service,
    ServiceDeclarationError,
    SkillRef,
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
# no-op replace tests the unmutated fixture. Drift asserts keep the swaps
# honest.


def bar_doc_md(level: str, *, title: str = "Echo", capability: str = "canary",
               keywords: str = "  - echo\n  - consent", mcp_tools: str = "[]",
               body: str | None = None) -> str:
    """One graded doc file — canonical front-matter + section schema."""
    if body is None:
        body = (
            "# Echo\n\n"
            "## Summary\n\n"
            "Echo bounces text back through the service's three callable"
            " surfaces (API, MCP, UI).\n\n"
            "## Details\n\n"
            "The level's depth content — usage steps, internals, design or"
            " extensions depending on the level.\n\n"
            "## See also\n\n"
            "- `/v1/echo` — the api description entry point.\n"
        )
    return (
        "---\n"
        f"title: {title}\n"
        f"capability: {capability}\n"
        f"level: {level}\n"
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

SERVICE_TOML_BAR = """\
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

[svc.canary.learning]

[[svc.canary.learning.docs]]
level = "how-to-use"
path = "docs/canary/how-to-use.md"

[[svc.canary.learning.docs]]
level = "how-it-works"
path = "docs/canary/how-it-works.md"

[[svc.canary.learning.docs]]
level = "study-in-depth"
path = "docs/canary/study-in-depth.md"

[[svc.canary.learning.docs]]
level = "going-further"
path = "docs/canary/going-further.md"

[svc.canary.learning.skill]
name = "drive-canary"
path = "skills/canary/SKILL.md"
"""

DOCS_BLOCK = """\
[[svc.{cap}.learning.docs]]
level = "{level}"
path = "docs/{cap}/{level}.md"

"""


def write_service_root(tmp_path, *, toml: str | None = None,
                       doc_overrides: dict[str, str] | None = None,
                       skill_md: str = SKILL_MD, write_files: bool = True):
    """A service root: `service.toml` + the declared bar artifacts."""
    doc_overrides = doc_overrides or {}
    write(tmp_path, "service.toml", toml if toml is not None else SERVICE_TOML_BAR)
    for level in DOC_LEVELS:
        text = doc_overrides.get(level) or bar_doc_md(level)
        if write_files:
            write(tmp_path, f"docs/canary/{level}.md", text)
    if write_files:
        write(tmp_path, "skills/canary/SKILL.md", skill_md)
    return tmp_path / "service.toml"


# --------------------------------------------------- the declared bar parses


def test_the_learning_bar_declares_four_levels_and_the_skill(tmp_path):
    path = write_service_root(tmp_path)
    svc = load_service_toml(path)
    assert isinstance(svc, Service)
    canary = svc.capabilities[0]
    assert isinstance(canary.learning, LearningBar)

    # the four graded levels — distinct artifacts, one file per level
    assert [d.level for d in canary.learning.docs] == list(DOC_LEVELS)
    assert all(isinstance(d, DocRef) for d in canary.learning.docs)
    assert canary.learning.docs[0].path == "docs/canary/how-to-use.md"

    # the how-an-agent-drives-me skill — declared, the artifact discoverable
    assert isinstance(canary.learning.skill, SkillRef)
    assert canary.learning.skill.name == "drive-canary"
    assert canary.learning.skill.path == "skills/canary/SKILL.md"

    # every declared artifact parsed (the typed parse result, no re-parsing)
    assert len(canary.learning.parsed_docs) == 4
    doc = canary.learning.parsed_docs[0]
    assert isinstance(doc, BarDoc)
    assert doc.level == "how-to-use"
    assert doc.capability == "canary"
    assert doc.title
    assert "echo" in doc.keywords
    assert doc.mcp_tools == ()
    # the canonical section schema (ADR-0024 §1) — asserted by the reader


def test_a_capability_without_the_learning_section_loads(tmp_path):
    """The bar is mandatory to publish (ADR-0018's tiers), not to boot —
    third-party services stay installable (ADR-0018 §5); the contribution
    ritual (CONTRIBUTING.md) makes the bar mandatory for publishing."""
    path = write_service_root(tmp_path)
    text = path.read_text()
    i = text.index("[svc.canary.learning]")
    path.write_text(text[:i].rstrip() + "\n")
    svc = load_service_toml(path)
    assert svc.capabilities[0].learning is None


# --------------------------------------------------- the shipped bar is real


# ------------------------------------------------------- loud-rejection rules
#
# Every loud-rejection rule gets a rejection test feeding the offending key
# and asserting the specific message — a text grep of the shipped file
# proves nothing (the settled #74 lesson). Fixtures are assembled from
# named part constants; mutations swap whole blocks (drift asserts on).

SERVICE_TOML_HEAD = """\
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

SKILL_BLOCK = """\
[svc.{cap}.learning.skill]
name = "drive-canary"
path = "skills/{cap}/SKILL.md"
"""

NOTE_LINE = 'not-agent-operable = "A physical-machine panel driven by its own UI; an agent has no deterministic surface to drive."\n'


def bar_toml(*, docs: bool = True, skill_block: str | None = SKILL_BLOCK,
             note: str | None = None, learning_header: str = "[svc.canary.learning]\n\n",
             cap: str = "canary", head: str | None = SERVICE_TOML_HEAD) -> str:
    text = head or ""
    text += learning_header
    # TOML ordering: a learning key sits directly under the [learning]
    # header — after any [[docs]] / [skill] sub-table header it would be
    # swallowed into that table (the ordering pitfall).
    if note is not None:
        text += f'not-agent-operable = "{note}"\n'
    if docs:
        text += "".join(DOCS_BLOCK.format(cap=cap, level=level) for level in DOC_LEVELS)
    if skill_block is not None:
        text += skill_block.format(cap=cap)
    return text


# drift guard: the slice-1 literal and the assembled fixture must agree
assert bar_toml() == SERVICE_TOML_BAR, "fixture drift: bar_toml() != SERVICE_TOML_BAR"


def test_not_agent_operable_note_is_accepted(tmp_path):
    """AC3: the explicit note is a first-class declared value — a capability
    that genuinely can't be agent-driven records it INSTEAD of a skill
    (no theater, ADR-0024 §1)."""
    path = write_service_root(tmp_path, toml=bar_toml(skill_block=None, note="A physical panel."))
    svc = load_service_toml(path)
    bar = svc.capabilities[0].learning
    assert bar.skill is None
    assert bar.not_agent_operable == "A physical panel."
    # the docs are still validated — the note replaces the skill, not the docs
    assert len(bar.parsed_docs) == 4
    assert bar.parsed_skill is None


@pytest.mark.parametrize(
    "toml,match",
    [
        # unknown key in the learning table
        (bar_toml(learning_header="[svc.canary.learning]\nskillz = []\n\n"), "unknown key.*declares only"),
        # docs required
        (bar_toml(docs=False), "learning.docs` is required"),
        # docs not a list (no [[docs]] blocks — the scalar+AoT coexistence is
        # a TOML decode error; the loader must catch the bad TYPE first)
        (
            bar_toml(docs=False, learning_header='[svc.canary.learning]\ndocs = "docs/canary"\n\n'),
            "docs.*must be a list of tables",
        ),
        # missing level — the bar is graded, all four
        (
            bar_toml() + DOCS_BLOCK.format(cap="canary", level="how-to-use"),
            "declares `how-to-use` twice",
        ),
        (
            bar_toml().replace(DOCS_BLOCK.format(cap="canary", level="going-further"), ""),
            "missing level.*going-further",
        ),
        # unknown level token
        (
            bar_toml().replace('level = "how-to-use"', 'level = "basics"'),
            "must be one of",
        ),
        # doc entry closed shape
        (
            bar_toml().replace(
                DOCS_BLOCK.format(cap="canary", level="how-to-use"),
                DOCS_BLOCK.format(cap="canary", level="how-to-use") + "surprise = 1\n\n",
            ),
            "docs\\[0\\].*unknown key",
        ),
        # paths: relative to the declaration's directory, no escapes
        (
            bar_toml().replace('path = "docs/canary/how-to-use.md"', 'path = "/etc/canary.md"'),
            "relative to the declaration's directory",
        ),
        (
            bar_toml().replace('path = "docs/canary/how-to-use.md"', 'path = "docs/../secrets.md"'),
            "relative to the declaration's directory",
        ),
        # declared doc file missing on disk — no theater
        (
            bar_toml().replace('path = "docs/canary/how-to-use.md"', 'path = "docs/canary/absent.md"'),
            "declares doc file not found",
        ),
        # both skill and note — a fake skill is theater
        (
            bar_toml(note="A physical panel."),
            "declares both `skill` and `not-agent-operable`",
        ),
        # neither skill nor note
        (bar_toml(skill_block=None), "declares neither `skill` nor"),
        # the note must say something
        (bar_toml(skill_block=None, note="   "), "must be a non-empty string"),
        # skill entry closed shape
        (
            bar_toml(skill_block=SKILL_BLOCK + "slug = \"x\"\n"),
            "a skill entry declares only: name, path",
        ),
        # skill slug grammar (ADR-0008's user-chosen name)
        (
            bar_toml(skill_block=SKILL_BLOCK.replace("drive-canary", "Drive Canary")),
            "lowercase slug",
        ),
        # declared skill file missing on disk
        (
            bar_toml(skill_block=SKILL_BLOCK.format(cap="canary").replace('path = "skills/canary/SKILL.md"', 'path = "skills/absent/SKILL.md"')),
            "declares skill file not found",
        ),
        # skill front-matter name must match the declared slug — no drift
        (
            bar_toml(skill_block=SKILL_BLOCK.replace("drive-canary", "drive-cap")),
            "does not match the declared skill name",
        ),
    ],
)
def test_learning_declaration_rejections(tmp_path, toml, match):
    path = write_service_root(tmp_path, toml=toml)
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)


def test_skill_names_must_be_unique_within_the_service(tmp_path):
    """The authored registry entry is `<service>.skill.<name>` (ADR-0008) —
    two capabilities declaring the same slug collide at the name authority;
    the loader rejects it at load."""
    other_head = (
        SERVICE_TOML_HEAD[SERVICE_TOML_HEAD.index("[svc.canary]"):]
        .replace("[svc.canary", "[svc.other")
        .replace('api = "/v1/echo"', 'api = "/v1/other"')
    )
    other_bar = bar_toml(
        learning_header="[svc.other.learning]\n\n",
        cap="other",
        skill_block=SKILL_BLOCK,
        head=None,  # `other_head` already carries this capability's section
    )
    path = write_service_root(tmp_path, toml=bar_toml() + other_head + other_bar)
    # the second capability's artifacts: same slug, its own honest files
    write(tmp_path, "skills/other/SKILL.md", SKILL_MD)
    for level in DOC_LEVELS:
        write(
            tmp_path, f"docs/other/{level}.md",
            bar_doc_md(level, capability="other", title="Other"),
        )
    with pytest.raises(ServiceDeclarationError, match="unique within the service"):
        load_service_toml(path)


@pytest.mark.parametrize(
    "override,match",
    [
        # front-matter delimiters
        (lambda text: "\n".join(text.splitlines()[1:]), "must open with a `---`"),
        (
            lambda text: text[: text.index("mcp-tools: []\n") + len("mcp-tools: []\n")],
            "not closed",
        ),
        # unknown front-matter key
        (lambda text: text.replace("title: Echo", "title: Echo\nsurprise: x"), "unknown front-matter key"),
        # title required
        (lambda text: text.replace("title: Echo\n", ""), "front-matter `title` must be a non-empty string"),
        # exactly one of capability/implementation
        (lambda text: text.replace("capability: canary", "capability: canary\nimplementation: qwen3-4b"), "exactly one of `capability`"),
        (lambda text: text.replace("capability: canary\n", ""), "exactly one of `capability`"),
        # level token + drift between declaration and artifact
        (lambda text: text.replace("level: how-to-use", "level: basics"), "`level` must be one of"),
        (lambda text: text.replace("level: how-to-use", "level: how-it-works"), "does not match the declared level"),
        # the doc names what it documents
        (lambda text: text.replace("capability: canary", "capability: other"), "front-matter `capability` is 'other'"),
        # keywords — the doc is indexed for agents too
        (lambda text: text.replace("keywords:\n  - echo\n  - consent\n", "keywords: []\n"), "`keywords` must be a non-empty list"),
        # the canonical section schema — exact, in order (ADR-0024 §1)
        (lambda text: text.replace("## Details\n", "### Details\n"), "canonical section schema"),
        (
            lambda text: text.replace("## Details", "## TEMPTMP")
            .replace("## See also", "## Details")
            .replace("## TEMPTMP", "## See also"),
            "canonical section schema",
        ),
        (lambda text: text.replace("## See also\n", "## See also\n\n## Extra\n"), "canonical section schema exactly"),
        # the body opens with the human title
        (lambda text: text.replace("# Echo\n", ""), "must open with a `# <title>` heading"),
    ],
)
def test_doc_artifact_rejections(tmp_path, override, match):
    level = "how-to-use"
    path = write_service_root(
        tmp_path, doc_overrides={level: override(bar_doc_md(level))}
    )
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)


@pytest.mark.parametrize(
    "skill,match",
    [
        # SKILL.md front-matter closed shape
        (lambda text: text.replace("name: drive-canary", "name: drive-canary\nversion: 1"), "unknown front-matter key"),
        # description — the registry entry's one-line summary
        (
            lambda text: text.replace(
                "description: How an agent drives the canary capability — every operation, parameter and consent flag, over /mcp or /v1.\n", ""
            ),
            "front-matter `description` must be a non-empty string",
        ),
        # an empty body is a hollow artifact
        (lambda text: "\n".join(text.splitlines()[:4]) + "\n", "empty body"),
        # the SKILL.md name must be a slug
        (lambda text: text.replace("name: drive-canary", "name: Drive Canary"), "front-matter `name` must be a lowercase slug"),
    ],
)
def test_skill_artifact_rejections(tmp_path, skill, match):
    path = write_service_root(tmp_path, skill_md=skill(SKILL_MD))
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)

