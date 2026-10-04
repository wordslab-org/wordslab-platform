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
[[svc.canary.learning.docs]]
level = "{level}"
path = "docs/canary/{level}.md"

"""


def write_service_root(tmp_path, *, toml: str = SERVICE_TOML_BAR,
                       doc_overrides: dict[str, str] | None = None,
                       skill_md: str = SKILL_MD, write_files: bool = True):
    """A service root: `service.toml` + the declared bar artifacts."""
    doc_overrides = doc_overrides or {}
    write(tmp_path, "service.toml", toml)
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
