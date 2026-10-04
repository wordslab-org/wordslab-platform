"""The learning/operability bar's declared artifacts (ticket #75; ADR-0024
§1, ADR-0002 §7, **ADR-0031 §2/§3 — declaration shape v3, amended**).

The bar is **declared, auditable, not aspirational** (ADR-0024 §1): the
declaration carries the four graded doc levels (each a distinct Markdown
artifact with its `level` in the front-matter — never one flattened
document) and exactly one of the **how-an-agent-drives-me `skill`** (a
registry `skill` entry, ADR-0008) or the explicit **"not agent-operable"
note** — a fake skill is theater, so both-declared and neither-declared
fail loudly.

Every declared artifact must **exist and parse**: structured Markdown with
the canonical front-matter (title, capability/implementation, level,
keywords, MCP tool references) + the canonical section schema
(`## Summary` / `## Details` / `## See also`, in this order — the schema is
the one schema of the dual-consumed docs, ADR-0024 §1). A
declared-but-malformed artifact is a fake artifact — loud rejection at
load, same posture as the closed declaration shape.

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
    "capability",
    "implementation",
    "level",
    "keywords",
    "mcp-tools",
}

SKILL_FRONT_MATTER_KEYS = {"name", "description"}  # required keys — the
# front-matter is otherwise OPEN (ADR-0008: frontmatter + instructions +
# linked files; extra keys are the registry's metadata)

LEARNING_KEYS = {"docs", "skill", "not-agent-operable"}

DOC_REF_KEYS = {"level", "path"}

SKILL_REF_KEYS = {"name", "path"}

_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class DocRef:
    """One declared graded doc — its level + its path (relative to the
    declaration's directory)."""

    level: str
    path: str


@dataclass(frozen=True)
class SkillRef:
    """The declared how-an-agent-drives-me skill: the registry skill slug
    (the authored entry is `<service>.skill.<name>`, ADR-0008) + the path
    of its SKILL.md body."""

    name: str
    path: str


@dataclass(frozen=True)
class LearningBar:
    """The parsed learning/operability bar declaration (ADR-0024 §1).

    `docs` carries all four graded levels; exactly one of `skill` /
    `not_agent_operable`. `parsed_docs`/`parsed_skill` are the validated
    artifacts (the typed parse result — the consumers index and mount
    through the registry, ADR-0008, without re-parsing)."""

    docs: tuple[DocRef, ...]
    skill: SkillRef | None
    not_agent_operable: str | None
    parsed_docs: tuple["BarDoc", ...] = ()
    parsed_skill: "SkillDoc | None" = None


@dataclass(frozen=True)
class BarDoc:
    """One parsed graded doc: the canonical front-matter + the section
    headings (the canonical schema's, in file order)."""

    title: str
    capability: str | None
    implementation: str | None
    level: str
    keywords: tuple[str, ...]
    mcp_tools: tuple[str, ...]
    sections: tuple[str, ...]


@dataclass(frozen=True)
class SkillDoc:
    """One parsed SKILL.md — front-matter (name, description) + the
    instruction body."""

    name: str
    description: str


# ------------------------------------------------------------- the bar table


def parse_learning_table(
    raw: dict, *, root: Path, about_kind: str, about: str,
    where: str, err,
) -> LearningBar | None:
    """Parse one declaration's `[learning]` table — the shape both loaders
    share (service_toml and implementation_toml): absent → None; not a
    table → loud; validated closed shape; artifacts loaded and
    cross-checked (ADR-0024 §1, ADR-0031 §2/§3 as amended)."""
    learning_raw = raw.get("learning")
    if learning_raw is None:
        return None
    if not isinstance(learning_raw, dict):
        raise err(f"`{where}` must be a table")
    bar = validate_learning(learning_raw, where=where, err=err)
    return load_learning_artifacts(
        bar, root=root, about_kind=about_kind, about=about, where=where, err=err
    )


def validate_learning(raw: object, *, where: str, err) -> LearningBar:
    """Validate one `learning` table's declared shape (closed shape, typos
    fail loudly — the closed-shape scan runs BEFORE the per-field checks).
    `err` is the caller's DeclarationError class."""
    if not isinstance(raw, dict):
        raise err(f"`{where}` must be a table")
    unknown = set(raw) - LEARNING_KEYS
    if unknown:
        raise err(
            f"`{where}` has unknown key(s) {sorted(unknown)} — the learning/"
            f" operability bar declares only: {', '.join(sorted(LEARNING_KEYS))}"
            " (ADR-0024 §1, closed shape, typos fail loudly)"
        )

    docs_raw = raw.get("docs")
    if docs_raw is None:
        raise err(
            f"`{where}.docs` is required — the bar's documentation category:"
            " the four graded levels (ADR-0024 §1), declared one entry per"
            " level"
        )
    if not isinstance(docs_raw, list):
        raise err(f"`{where}.docs` must be a list of tables (one per level)")
    docs: list[DocRef] = []
    seen_levels: set[str] = set()
    for i, ref in enumerate(docs_raw):
        ref_where = f"{where}.docs[{i}]"
        if not isinstance(ref, dict):
            raise err(f"`{ref_where}` is not a table")
        unknown_ref = set(ref) - DOC_REF_KEYS
        if unknown_ref:
            raise err(
                f"`{ref_where}` has unknown key(s) {sorted(unknown_ref)} — a"
                f" doc entry declares only: {', '.join(sorted(DOC_REF_KEYS))}"
                " (closed shape, typos fail loudly)"
            )
        level = ref.get("level")
        if level not in DOC_LEVELS:
            raise err(
                f"`{ref_where}.level` must be one of {DOC_LEVELS} — the bar"
                " is graded by depth (ADR-0024 §1), one artifact per level"
            )
        if level in seen_levels:
            raise err(
                f"`{ref_where}` declares `{level}` twice — the bar is graded:"
                " one artifact per level, four levels"
            )
        seen_levels.add(level)
        docs.append(DocRef(level=level, path=_validate_rel_path(ref, "path", ref_where, err)))

    missing = [level for level in DOC_LEVELS if level not in seen_levels]
    if missing:
        raise err(
            f"`{where}.docs` is missing level(s) {missing} — the bar is"
            f" graded, not flattened: all four levels {DOC_LEVELS}"
            " (ADR-0024 §1)"
        )

    skill_raw = raw.get("skill")
    note = raw.get("not-agent-operable")
    if skill_raw is not None and note is not None:
        raise err(
            f"`{where}` declares both `skill` and `not-agent-operable` — a"
            " capability that genuinely can't be agent-driven records the"
            " explicit note INSTEAD of a skill; a fake skill is theater"
            " (ADR-0024 §1)"
        )
    if skill_raw is None and note is None:
        raise err(
            f"`{where}` declares neither `skill` nor `not-agent-operable` —"
            " declare the how-an-agent-drives-me skill (a registry `skill`"
            " entry, ADR-0008) or the explicit \"not agent-operable\" note"
            " (no theater, ADR-0024 §1)"
        )

    skill: SkillRef | None = None
    if skill_raw is not None:
        if not isinstance(skill_raw, dict):
            raise err(f"`{where}.skill` must be a table (name, path)")
        unknown_skill = set(skill_raw) - SKILL_REF_KEYS
        if unknown_skill:
            raise err(
                f"`{where}.skill` has unknown key(s) {sorted(unknown_skill)} —"
                f" a skill entry declares only: {', '.join(sorted(SKILL_REF_KEYS))}"
                " (closed shape, typos fail loudly)"
            )
        name = skill_raw.get("name")
        if not isinstance(name, str) or not _SLUG_RE.fullmatch(name):
            raise err(
                f"`{where}.skill.name` must be a lowercase slug (a-z, digits,"
                " hyphens) — the registry skill entry's user-chosen name; the"
                " authored entry is `<service>.skill.<name>` (ADR-0008)"
            )
        skill = SkillRef(name=name, path=_validate_rel_path(skill_raw, "path", f"{where}.skill", err))

    if note is not None:
        if not isinstance(note, str) or not note.strip():
            raise err(
                f"`{where}.not-agent-operable` must be a non-empty string —"
                " the honest note explaining WHY the capability can't be"
                " agent-driven (no theater, ADR-0024 §1)"
            )

    return LearningBar(
        docs=tuple(docs),
        skill=skill,
        not_agent_operable=note if isinstance(note, str) else None,
    )


def _validate_rel_path(ref: dict, key: str, where: str, err) -> str:
    value = ref.get(key)
    if not isinstance(value, str) or not value.strip():
        raise err(f"`{where}.{key}` must be a non-empty string")
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise err(
            f"`{where}.{key}` must be a path relative to the declaration's"
            f" directory — got {value!r}"
        )
    return value


# ------------------------------------------------------- artifact validation


def load_learning_artifacts(
    bar: LearningBar,
    *,
    root: Path,
    about_kind: str,
    about: str,
    where: str,
    err,
) -> LearningBar:
    """Resolve every declared bar artifact against the declaration's
    directory and validate it (declared files must exist and parse — a
    declared-but-fake artifact fails at load, no theater). Cross-checks:
    each doc's front-matter `level` matches its declared level and its
    `capability`/`implementation` field names the declaring subject; the
    skill's SKILL.md front-matter `name` matches the declared slug."""
    parsed_docs: list[BarDoc] = []
    for ref in bar.docs:
        parsed_docs.append(
            load_bar_doc(
                root / ref.path,
                err=err,
                where=f"{where}.docs[{ref.level}]",
                level=ref.level,
                about_kind=about_kind,
                about=about,
            )
        )
    parsed_skill = None
    if bar.skill is not None:
        parsed_skill = load_skill_md(
            root / bar.skill.path,
            err=err,
            where=f"{where}.skill",
            name=bar.skill.name,
        )
    return LearningBar(
        docs=bar.docs,
        skill=bar.skill,
        not_agent_operable=bar.not_agent_operable,
        parsed_docs=tuple(parsed_docs),
        parsed_skill=parsed_skill,
    )


def load_bar_doc(
    path: Path, *, err, where: str, level: str | None = None,
    about_kind: str | None = None, about: str | None = None,
) -> BarDoc:
    """Load + validate one graded doc (structured Markdown, canonical
    front-matter + section schema, ADR-0024 §1)."""
    path = Path(path)
    if not path.is_file():
        raise err(f"`{where}` declares doc file not found: {path}")
    text = path.read_text(encoding="utf-8")
    front, body = _split_front_matter(text, where, err)

    unknown = (set(front.scalars) | set(front.lists)) - DOC_FRONT_MATTER_KEYS
    if unknown:
        raise err(
            f"`{where}` ({path.name}) has unknown front-matter key(s)"
            f" {sorted(unknown)} — the canonical front-matter declares only:"
            f" {', '.join(sorted(DOC_FRONT_MATTER_KEYS))} (ADR-0024 §1,"
            " closed shape, typos fail loudly)"
        )

    capability = front.scalars.get("capability")
    implementation = front.scalars.get("implementation")
    if (capability is None) == (implementation is None):
        raise err(
            f"`{where}` ({path.name}) front-matter names what it documents —"
            " exactly one of `capability` (a service capability's doc) or"
            " `implementation` (an implementation's doc) (ADR-0024 §1)"
        )
    title = front.scalars.get("title")
    if not isinstance(title, str) or not title.strip():
        raise err(f"`{where}` ({path.name}) front-matter `title` must be a non-empty string")
    level_value = front.scalars.get("level")
    if level_value not in DOC_LEVELS:
        raise err(
            f"`{where}` ({path.name}) front-matter `level` must be one of"
            f" {DOC_LEVELS} — the bar is graded by depth (ADR-0024 §1)"
        )
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

    doc = BarDoc(
        title=title,
        capability=capability,
        implementation=implementation,
        level=level_value,
        keywords=tuple(keywords),
        mcp_tools=tuple(mcp_tools),
        sections=sections,
    )
    if level is not None and doc.level != level:
        raise err(
            f"`{where}` ({path.name}) front-matter level {doc.level!r} does"
            f" not match the declared level {level!r} — one artifact per"
            " level, no drift between declaration and artifact"
        )
    if about_kind is not None and getattr(doc, about_kind) != about:
        raise err(
            f"`{where}` ({path.name}) front-matter `{about_kind}` is"
            f" {getattr(doc, about_kind)!r} but the declaration declares"
            f" {about!r} — the doc names what it documents (ADR-0024 §1)"
        )
    return doc


def load_skill_md(path: Path, *, err, where: str, name: str | None = None) -> SkillDoc:
    """Load + validate the how-an-agent-drives-me skill body (a registry
    `skill` entry's SKILL.md — frontmatter + instructions, ADR-0008)."""
    path = Path(path)
    if not path.is_file():
        raise err(f"`{where}` declares skill file not found: {path}")
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
            " user-chosen name (ADR-0008)"
        )
    description = front.scalars.get("description")
    if not isinstance(description, str) or not description.strip():
        raise err(
            f"`{where}` ({path.name}) front-matter `description` must be a"
            " non-empty string — the registry entry's one-line, prompt-facing"
            " summary (ADR-0008)"
        )
    if not body.strip():
        raise err(
            f"`{where}` ({path.name}) has an empty body — a skill is"
            " instructions; a hollow body is a fake artifact (no theater,"
            " ADR-0024 §1)"
        )
    if name is not None and skill_name != name:
        raise err(
            f"`{where}` ({path.name}) front-matter name {skill_name!r} does"
            f" not match the declared skill name {name!r} — no drift between"
            " declaration and artifact"
        )
    return SkillDoc(name=skill_name, description=description)


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
