"""The learning/operability bar's artifacts — DISCOVERED BY LAYOUT
(ticket #75; ADR-0024 §1, ADR-0002 §7; ADR-0031 §2/§3 as amended).

The bar is **declared by the layout and audited at load**: no TOML
sub-table lists the artifacts. The loader derives them from path + name
conventions and validates what it finds:

    docs/<level>.md            the graded docs — one file per level
    skills/<slug>/SKILL.md     the how-an-agent-drives-me skill

`<level>` is one of the four graded depths (how to use · how it works ·
study in depth) — the FILENAME is the level, so a level can never drift
from its declaration. The skill's DIRECTORY NAME is the registry slug (the
authored entry is `<service>.skill.<slug>`, ADR-0008); its front-matter
carries the one-line `description` the registry loads the skill by.

The conventions, per subject (each `*_rel` is relative to the declaring
directory):

    service         docs/service/<level>.md
                    skills/service/<slug>/SKILL.md
    capability      docs/capabilities/<capability>/<level>.md
                    skills/capabilities/<capability>/<slug>/SKILL.md
    implementation  docs/<level>.md      (the implementation's own dir)
                    skills/<slug>/SKILL.md

**No skill in the expected directory** is the convention's honest record —
but what it MEANS differs by level, deliberately:
a **capability** without a skill is not-agent-operable (no deterministic
surface to drive); a **service** without one has no skill *above* its
capabilities and stays agent-operable if any capability is (the
service-level skill covers only what no single capability does); an
**implementation** without one adds nothing specific on top of the
capability's skill — nothing is missing.

Every artifact FOUND must exist and parse: structured Markdown with the
canonical front-matter (title, keywords — the doc is indexed for agents
too — and optional MCP tool references) and the canonical section schema
(`## Summary` / `## Details` / `## See also`, in this order). A malformed
artifact is a fake artifact — loud rejection at load. Artifacts that are
simply ABSENT are not errors: the bar is mandatory to publish (ADR-0018's
tiers), not to boot, so they are recorded as `gaps`.

This module is loader-agnostic: the loaders inject their own error class
(`err`) so every rejection surfaces as a precise `*DeclarationError`
(the settled #74 contract).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DOC_LEVELS = ("how-to-use", "how-it-works", "study-in-depth", "going-further")

CANONICAL_SECTIONS = ("Summary", "Details", "See also")

DOC_FRONT_MATTER_KEYS = {
    "title",
    "keywords",
    "mcp-tools",
}

SKILL_FRONT_MATTER_KEYS = {"name", "description"}  # required keys — the
# front-matter is otherwise OPEN (ADR-0008: a skill is frontmatter +
# instructions + linked files; extra keys are the registry's metadata)

_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

DOCS_DIR = "docs"
SKILLS_DIR = "skills"
SKILL_FILE = "SKILL.md"


@dataclass(frozen=True)
class BarDoc:
    """One discovered graded doc: its level (from the filename), the
    canonical front-matter, the section headings (the canonical schema's, in
    file order) and its path relative to the declaring directory."""

    level: str
    title: str
    keywords: tuple[str, ...]
    mcp_tools: tuple[str, ...]
    sections: tuple[str, ...]
    path: Path


@dataclass(frozen=True)
class SkillDoc:
    """One discovered SKILL.md — the registry slug (its directory name), the
    one-line prompt-facing `description` the registry loads it by, and its
    path relative to the declaring directory."""

    name: str
    description: str
    path: Path


@dataclass(frozen=True)
class LearningBar:
    """One subject's discovered learning/operability bar (ADR-0024 §1).

    `docs` holds the graded docs that were FOUND (one per level at most);
    `gaps` names the artifacts still missing (the bar is mandatory to
    publish, not to boot). `skill` is None when no
    `skills/<slug>/SKILL.md` exists — and what that MEANS depends on the
    subject's level, which is exactly the difference between the three:

    - a **service** with no skill is not agent-operable **as a whole** — but
      it stays agent-operable where its capabilities are: the service-level
      skill only carries what no single capability covers, so its absence
      means "no skill above the capabilities", not "no agent surface at
      all". `agent_operable_subjects` holds the capabilities that are;
    - a **capability** with no skill is genuinely **not agent-operable** —
      there is no deterministic surface to drive;
    - an **implementation** with no skill adds **nothing specific** on top
      of the capability's skill — the capability's instructions cover it.
    """

    subject: str
    kind: str = "capability"
    docs: tuple[BarDoc, ...] = ()
    skill: SkillDoc | None = None
    gaps: tuple[str, ...] = ()
    agent_operable_subjects: tuple[str, ...] = ()

    @property
    def agent_operable(self) -> bool:
        """An agent surface exists: an own skill, or (for a service) at
        least one agent-operable capability beneath it."""
        return self.skill is not None or bool(self.agent_operable_subjects)

    @property
    def not_agent_operable(self) -> bool:
        """The subject genuinely has no agent surface.

        Only ever True for a **capability** (no deterministic surface to
        drive) or for a **service** whose capabilities are all
        not-agent-operable and which ships no service-level skill. For an
        implementation it is always False: the capability's skill covers it,
        so nothing is missing.
        """
        if self.skill is not None:
            return False
        if self.kind == "capability":
            return True
        if self.kind == "service":
            return not self.agent_operable_subjects
        return False  # implementation — additive, never a gap in the surface

    def level(self, level: str) -> BarDoc | None:
        """The doc discovered at `level`, or None (a gap)."""
        return next((doc for doc in self.docs if doc.level == level), None)


# ------------------------------------------------------- discovery by layout


def discover_learning_bar(
    root: Path, *, docs_rel: Path, skills_rel: Path, subject: str,
    kind: str, where: str, err,
) -> LearningBar:
    """Derive one subject's bar from the layout and audit every artifact
    found (ADR-0024 §1 — the layout declares, the load audits).

    `root` is the declaring directory (the service's or implementation's own
    directory); `docs_rel` / `skills_rel` are the subject's conventional
    subtrees relative to it; `kind` is `service` | `capability` |
    `implementation` (it decides what a MISSING skill means — see
    `LearningBar`).
    """
    root = Path(root)
    docs: list[BarDoc] = []
    gaps: list[str] = []
    for level in DOC_LEVELS:
        found = root / docs_rel / f"{level}.md"
        if found.is_file():
            docs.append(
                load_bar_doc(
                    found, err=err, level=level,
                    where=f"{where} (convention {docs_rel}/{level}.md)",
                )
            )
        else:
            gaps.append(f"docs: {docs_rel}/{level}.md")

    skill = discover_skill(root, skills_rel=skills_rel, where=where, err=err)
    if skill is None:
        gaps.append(f"skill: {skills_rel}/<name>/{SKILL_FILE}")

    return LearningBar(
        subject=subject, kind=kind, docs=tuple(docs), skill=skill,
        gaps=tuple(gaps),
    )


def discover_skill(root: Path, *, skills_rel: Path, where: str, err) -> SkillDoc | None:
    """The subject's how-an-agent-drives-me skill: the single
    `skills_rel/<slug>/SKILL.md` under its skills subtree. None when the
    subtree is absent or holds no skill — the not-agent-operable convention.
    More than one is an ambiguity rejected loudly: a subject ships exactly
    one skill."""
    base = Path(root) / skills_rel
    found = sorted(
        child / SKILL_FILE
        for child in (base.iterdir() if base.is_dir() else ())
        if child.is_dir() and _SLUG_RE.fullmatch(child.name)
        and (child / SKILL_FILE).is_file()
    )
    if not found:
        return None
    if len(found) > 1:
        raise err(
            f"`{where}` ({skills_rel}) holds {len(found)} skills"
            f" ({', '.join(p.parent.name for p in found)}) — a subject ships"
            " exactly one how-an-agent-drives-me skill, its directory name is"
            " the registry slug (ADR-0008)"
        )
    return load_skill_md(found[0], err=err, where=f"{where} ({skills_rel})")


# ------------------------------------------------------- artifact validation


def load_bar_doc(path: Path, *, err, where: str, level: str | None = None) -> BarDoc:
    """Load + validate one graded doc (structured Markdown, canonical
    front-matter + section schema, ADR-0024 §1).

    `level` is the level the doc was FOUND at (its filename) — the filename
    IS the level, so a `level:` front-matter key would be a duplicate
    declaration, not part of the canonical front-matter.
    """
    path = Path(path)
    if not path.is_file():
        raise err(f"`{where}` doc file not found: {path}")
    doc_level = level if level is not None else path.stem
    if doc_level not in DOC_LEVELS:
        raise err(
            f"`{where}` ({path.name}) is not a graded level — the bar is"
            f" graded by depth {DOC_LEVELS}; the FILENAME is the level"
            " (ADR-0024 §1)"
        )
    text = path.read_text(encoding="utf-8")
    front, body = _split_front_matter(text, where, err)

    unknown = (set(front.scalars) | set(front.lists)) - DOC_FRONT_MATTER_KEYS
    if unknown:
        raise err(
            f"`{where}` ({path.name}) has unknown front-matter key(s)"
            f" {sorted(unknown)} — a graded doc's canonical front-matter"
            f" declares only: {', '.join(sorted(DOC_FRONT_MATTER_KEYS))}"
            " (ADR-0024 §1, closed shape, typos fail loudly)"
        )

    title = front.scalars.get("title")
    if not isinstance(title, str) or not title.strip():
        raise err(f"`{where}` ({path.name}) front-matter `title` must be a non-empty string")
    keywords = front.lists.get("keywords")
    if not keywords or not all(isinstance(k, str) and k.strip() for k in keywords):
        raise err(
            f"`{where}` ({path.name}) front-matter `keywords` must be a"
            " non-empty list of strings — the doc is authored to be indexed"
            " for agents too (ADR-0024 §1: one source, dual-consumed)"
        )
    mcp_tools = front.lists.get("mcp-tools", [])
    if not all(isinstance(t, str) and t.strip() for t in mcp_tools):
        raise err(
            f"`{where}` ({path.name}) front-matter `mcp-tools` must be a list"
            " of strings — the capability's MCP tool references (registry"
            " entries, ADR-0008)"
        )

    h1, sections = _validate_body(body, where, path.name, err)
    if h1[2:].strip() != title:
        raise err(
            f"`{where}` ({path.name}) H1 and front-matter title disagree:"
            f" {h1[2:].strip()!r} vs {title!r} — human title and indexable"
            " title agree (one source, ADR-0024 §1)"
        )

    return BarDoc(
        level=doc_level,
        title=title,
        keywords=tuple(keywords),
        mcp_tools=tuple(mcp_tools),
        sections=sections,
        path=path,
    )


def load_skill_md(path: Path, *, err, where: str) -> SkillDoc:
    """Load + validate the how-an-agent-drives-me skill body (a registry
    `skill` entry's SKILL.md — frontmatter + instructions, ADR-0008). Its
    directory name IS the registry slug; the front-matter carries the
    one-line `description` the registry loads it by."""
    path = Path(path)
    if not path.is_file():
        raise err(f"`{where}` skill file not found: {path}")
    text = path.read_text(encoding="utf-8")
    front, body = _split_front_matter(text, where, err)
    # an OPEN front-matter (ADR-0008: a skill is frontmatter + instructions
    # + linked files): the bar requires the discoverable `name` +
    # `description`; extra keys (version, linked files, ...) are the
    # registry's metadata, not an error.
    skill_name = front.scalars.get("name")
    if not isinstance(skill_name, str) or not _SLUG_RE.fullmatch(skill_name):
        raise err(
            f"`{where}` ({path.name}) front-matter `name` must be a lowercase"
            " slug (a-z, digits, hyphens) — the registry skill entry's"
            " user-chosen name; the authored entry is"
            " `<service>.skill.<name>` (ADR-0008)"
        )
    description = front.scalars.get("description")
    if not isinstance(description, str) or not description.strip():
        raise err(
            f"`{where}` ({path.name}) front-matter `description` must be a"
            " non-empty string — the one-line, prompt-facing summary the"
            " registry loads a skill by, so it can be discovered without"
            " loading the body (ADR-0008)"
        )
    if not body.strip():
        raise err(
            f"`{where}` ({path.name}) has an empty body — a skill is"
            " instructions; a hollow body is a fake artifact (no theater,"
            " ADR-0024 §1)"
        )
    if skill_name != path.parent.name:
        raise err(
            f"`{where}` ({path.name}) front-matter name {skill_name!r} does"
            f" not match its directory name {path.parent.name!r} — the"
            " directory name IS the registry slug (ADR-0008), no drift"
            " between the layout and the artifact"
        )
    return SkillDoc(name=skill_name, description=description, path=path)


# ----------------------------------------------------------- markdown parsing


@dataclass
class _FrontMatter:
    scalars: dict = field(default_factory=dict)
    lists: dict = field(default_factory=dict)


def _split_front_matter(text: str, where: str, err):
    """Split `---`-delimited front-matter from the body, parsing the
    front-matter as a FLAT closed shape: `key: value` scalars and `key:`
    blocks of `- item` list lines. Anything else fails loudly — a silent
    mis-parse would make a malformed doc look valid."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise err(
            f"`{where}` must open with a `---` front-matter delimiter —"
            " structured Markdown with a canonical front-matter (ADR-0024 §1)"
        )
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise err(f"`{where}` front-matter is not closed with a `---` line") from None

    front = _FrontMatter()
    current_list: str | None = None
    for line in lines[1:close]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current_list is None:
                raise err(
                    f"`{where}` front-matter list item {stripped!r} outside a"
                    " `key:` block — front-matter lines are `key: value`"
                    " scalars or `- item` entries under a list key"
                )
            front.lists[current_list].append(stripped[2:].strip())
            continue
        if ":" not in stripped:
            raise err(
                f"`{where}` front-matter line {stripped!r} is not `key: value`"
                " — front-matter is a flat closed shape: `key: value` scalars"
                " or `- item` list entries"
            )
        key, _, value = stripped.partition(":")
        key, value = key.strip(), value.strip()
        if value == "":
            if key in front.lists or key in front.scalars:
                raise err(f"`{where}` front-matter declares `{key}` twice")
            current_list = key
            front.lists[current_list] = []
            continue
        if value == "[]":
            if key in front.lists or key in front.scalars:
                raise err(f"`{where}` front-matter declares `{key}` twice")
            current_list = None
            front.lists[key] = []
            continue
        current_list = None
        if key in front.scalars or key in front.lists:
            raise err(f"`{where}` front-matter declares `{key}` twice")
        front.scalars[key] = value
    body = "\n".join(lines[close + 1:])
    return front, body


def _validate_body(body: str, where: str, name: str, err):
    """The canonical section schema: the body opens with a `# <title>` H1
    and carries exactly the canonical H2 sections, in order (ADR-0024 §1 —
    the one schema of the dual-consumed docs)."""
    lines = body.splitlines()
    if not any(line.strip() for line in lines):
        raise err(f"`{where}` ({name}) has an empty body")
    # fence-aware: a `## ` line inside a ``` fence is quoted content, not
    # a section — otherwise a doc quoting Markdown rejects itself
    sections, in_fence = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith("## "):
            sections.append(line.strip()[3:].strip())
    sections = tuple(sections)
    first = next(line for line in lines if line.strip())
    if not first.startswith("# "):
        raise err(
            f"`{where}` ({name}) body must open with a `# <title>` heading"
            " — structured Markdown, human title and indexable title agree"
        )
    if sections != CANONICAL_SECTIONS:
        raise err(
            f"`{where}` ({name}) body must follow the canonical section"
            " schema exactly:"
            f" {' · '.join(f'## {s}' for s in CANONICAL_SECTIONS)} (in this"
            f" order, ADR-0024 §1) — found: {list(sections)}"
        )
    return first, sections
