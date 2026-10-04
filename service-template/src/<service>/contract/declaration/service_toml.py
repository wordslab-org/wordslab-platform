"""The service declaration loader (ticket #74; ADR-0002 §5, ADR-0031 §2
— v3).

`service.toml` declares the service — **a set of capabilities**
(ADR-0031 §1). Layout: the service's own properties first, then one
**documentation section per capability**, named
`[<service-name>.<capability-name>]` — the full per-capability documentation
the platform UI and the catalog render:

- own properties: identity (`name`, `description`, `version`) and one
  **service-level `[requirements]`** figure (disk-gb + ram-gb for the
  service's own API + UI code execution — each capability implementation
  selected at install time adds its own requirements on top).
- capability sections: description, version, an **api description entry
  point**, a **short description of the api functions**, an explanation of
  the **versions history**, and **UI hooks** to integrate in the general
  platform dashboard (menu elements + entry points), with a short
  description of the UI and explanations of the UI versions history.

**API families are NOT declared** — the capabilities' APIs implement
ADR-0001's family contracts; their documentation is enough (ADR-0031 §2).
**No capability-level dependencies** — the implementations declare their
dependencies (`implementation_toml.py`), not the service.

Each capability section may also declare its **learning/operability bar**
(ticket #75; ADR-0024 §1, ADR-0002 §7, shape per ADR-0031 §2 as amended):
a `[<service-name>.<capability-name>.learning]` sub-table carrying the four
graded doc levels (one Markdown artifact per level, `level` + `path`) and
exactly one of the how-an-agent-drives-me `skill` (a registry `skill`
entry, ADR-0008) or the explicit "not agent-operable" note (no theater).
Every declared artifact must exist and parse — a declared-but-fake artifact
fails at load (`learning_bar.py`). The bar is mandatory to publish
(ADR-0018's tiers), not to boot: a capability may omit `learning` while
being written; a DECLARED bar is validated fully.
"""

from __future__ import annotations

from pathlib import Path

import tomllib

from .learning_bar import (
    LearningBar,
    load_learning_artifacts,
    validate_learning,
)


class ServiceDeclarationError(ValueError):
    """A `service.toml` that violates its declared shape.

    Raised at load time — declaration errors are structural (a service can't
    boot half-declared), so the failure surfaces here, not at request time.
    """


class MenuItem:
    """One UI menu hook — a label + entry point the platform dashboard
    integrates for the capability."""

    def __init__(self, *, label: str, entry: str) -> None:
        self.label = label
        self.entry = entry


class Capability:
    """One declared capability — parsed from its documentation section
    `[<service-name>.<capability-name>]`: identity, the api description
    entry point, a short description of the api functions, the versions
    history, required/optional, and the UI hooks (menu elements + entry
    points + UI description + UI versions history)."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        version: str,
        api: str,
        api_functions: str,
        versions_history: str,
        required: bool,
        ui_menu: tuple[MenuItem, ...],
        ui_description: str,
        ui_versions_history: str,
        learning: LearningBar | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.api = api
        self.api_functions = api_functions
        self.versions_history = versions_history
        self.required = required
        self.ui_menu = ui_menu
        self.ui_description = ui_description
        self.ui_versions_history = ui_versions_history
        self.learning = learning


class Service:
    """The parsed `service.toml` — the declared side of the service shell.

    A service is a set of capabilities; it has no implementation of its own
    (ADR-0031 §1) — `requirements` covers its API + UI code execution only.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str,
        version: str,
        requirements: dict[str, float],
        capabilities: tuple[Capability, ...],
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.requirements = requirements
        self.capabilities = capabilities


def _require_str(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ServiceDeclarationError(f"`{where}.{key}` must be a non-empty string")
    return value


def _require_nonneg_number(table: dict, key: str, where: str) -> float:
    value = table.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ServiceDeclarationError(f"`{where}.{key}` must be a non-negative number")
    return float(value)


def _check_capability_name(name: str) -> None:
    """Capability names are lowercase dotted identifiers (`audio.stt`) —
    CONTEXT.md *Implementation* / ADR-0029's `<task>.model` grammar."""
    if not name or not all(part.isidentifier() and part.islower() for part in name.split(".")):
        raise ServiceDeclarationError(
            f"capability name {name!r} must be a lowercase dotted identifier"
        )


SERVICE_TOP_LEVEL_KEYS = {"name", "description", "version", "requirements"}

CAPABILITY_SECTION_KEYS = {
    "description",
    "version",
    "api",
    "api-functions",
    "versions-history",
    "required",
    "ui",
    "learning",
}

CAPABILITY_UI_KEYS = {"menu", "description", "versions-history"}


def load_service_toml(path: str | Path) -> Service:
    """Load and validate a `service.toml` (ADR-0031 §2's shape, v3).

    Validation is structural — the copy-to-start ritual's editing errors are
    caught here, not at request time. Unknown keys (typos, retired keys like
    `families`) fail loudly: a declaration is a closed shape.
    """
    path = Path(path)
    if not path.is_file():
        raise ServiceDeclarationError(f"declaration file not found: {path}")

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    name = raw.get("name")
    description = raw.get("description")
    version = raw.get("version")
    if not isinstance(name, str) or not name.strip():
        raise ServiceDeclarationError("`service.name` must be a non-empty string")

    _reject_unknown_top_level(raw, name)

    description = _require_str(raw, "description", "service")
    version = _require_str(raw, "version", "service")

    requirements_raw = raw.get("requirements", {})
    if not isinstance(requirements_raw, dict):
        raise ServiceDeclarationError("`[requirements]` must be a table")
    unknown = set(requirements_raw) - {"disk-gb", "ram-gb"}
    if unknown:
        raise ServiceDeclarationError(
            f"`[requirements]` declares disk-gb and ram-gb only (the service's"
            f" own API + UI code; implementations add their own) — unknown: {sorted(unknown)}"
        )
    requirements = {
        key: _require_nonneg_number(requirements_raw, key, "[requirements]")
        for key in ("disk-gb", "ram-gb")
    }

    capabilities = _parse_capability_sections(raw, name, Path(path).parent)
    _reject_duplicate_skill_names(capabilities, name)
    return Service(
        name=name,
        description=description,
        version=version,
        requirements=requirements,
        capabilities=capabilities,
    )


def _reject_unknown_top_level(raw: dict, service_name: str) -> None:
    """The closed-shape rule: only the own-property keys plus the
    `[<service>.<capability>]` documentation sections are legal. A dict key
    rooted at the service's own name is a documentation-section root — the
    section walk (`_parse_capability_sections`) validates the rest."""
    service_head = service_name.split(".")[0]
    unknown = {
        key
        for key in set(raw) - SERVICE_TOP_LEVEL_KEYS
        if not (isinstance(raw[key], dict) and key.split(".")[0] == service_head)
    }
    if not unknown:
        return
    if "families" in unknown:
        raise ServiceDeclarationError(
            "`families` is not declared anymore (ADR-0031 §2) — family"
            " contracts are API-documentation facts; remove the key"
        )
    if "capabilities" in unknown:
        raise ServiceDeclarationError(
            "`capabilities` is superseded by the per-capability documentation"
            f" sections `[<service-name>.<capability-name>]` (v3) — declare"
            " each capability as its own section"
        )
    # a section for ANOTHER service's capability — wrong prefix
    bad_sections = [
        key for key in set(raw) - SERVICE_TOP_LEVEL_KEYS
        if isinstance(raw[key], dict) and key.split(".")[0] != service_head
    ]
    if bad_sections:
        raise ServiceDeclarationError(
            f"unknown section(s) {sorted(bad_sections)} — capability"
            f" documentation sections are named `[{service_name}.<capability-name>]`"
            " (the service's own name is the prefix)"
        )
    raise ServiceDeclarationError(
        f"unknown top-level key(s) {sorted(unknown)} — service.toml declares"
        f" only: {', '.join(sorted(SERVICE_TOP_LEVEL_KEYS))} plus capability"
        f" sections `[{service_name}.<capability-name>]` (typos fail loudly, ADR-0031 §2)"
    )


def _reject_duplicate_skill_names(
    capabilities: tuple[Capability, ...], service_name: str
) -> None:
    """The how-an-agent-drives-me skill is a registry `skill` entry whose
    authored name is `<service>.skill.<slug>` (ADR-0008) — two capabilities
    declaring the same slug collide at the name authority; reject at load."""
    seen: dict[str, str] = {}
    for cap in capabilities:
        if cap.learning is None or cap.learning.skill is None:
            continue
        slug = cap.learning.skill.name
        if slug in seen:
            raise ServiceDeclarationError(
                f"capability `{cap.name}` declares skill {slug!r} — skill"
                f" names must be unique within the service (the authored"
                f" registry entry is `{service_name}.skill.{slug}`, already"
                f" declared by `{seen[slug]}`; ADR-0008)"
            )
        seen[slug] = cap.name


def _parse_capability_sections(
    raw: dict, service_name: str, service_root: Path
) -> tuple[Capability, ...]:
    """Parse every `[<service-name>.<capability-name>]` documentation section.

    Capability names may themselves be dotted (`audio.stt` → section
    `[audio.audio.stt]`), so the walk descends the service-name root and
    joins the remaining path segments into the capability name. A dict that
    carries capability-section keys at a path IS the capability's spec —
    the walk stops there (`[svc.a.ui]` is a's ui table, not a capability)."""
    node: object = raw
    for segment in service_name.split("."):
        if not isinstance(node, dict) or segment not in node:
            return ()  # no capability sections at all
        node = node[segment]
    if not isinstance(node, dict):
        raise ServiceDeclarationError(
            f"`[{service_name}]` must be a table — capability documentation"
            " sections are named `[{service_name}.<capability-name>]`"
        )

    capabilities: list[Capability] = []
    seen: set[str] = set()
    _walk_capability_specs(node, service_name, [], seen, capabilities, service_root)
    return tuple(capabilities)


def _walk_capability_specs(
    node: dict,
    service_name: str,
    path: list[str],
    seen: set[str],
    out: list[Capability],
    service_root: Path,
) -> None:
    for key, entry in node.items():
        if not isinstance(entry, dict):
            raise ServiceDeclarationError(
                f"`[{service_name}.{'.'.join(path + [key])}]` is not a table —"
                " under the service's own name only capability documentation"
                f" sections `[{service_name}.<capability-name>]` are declared"
                " (typos fail loudly, ADR-0031 §2)"
            )
        cap_path = path + [key]
        if set(entry) & CAPABILITY_SECTION_KEYS:
            # this dict is a capability spec — the walk stops here
            cap_name = ".".join(cap_path)
            _check_capability_name(cap_name)
            if cap_name in seen:
                raise ServiceDeclarationError(
                    f"duplicate capability declaration: {cap_name}"
                )
            seen.add(cap_name)
            out.append(
                _parse_capability_section(
                    entry, cap_name, f"{service_name}.{'.'.join(cap_path)}",
                    service_root,
                )
            )
        elif any(isinstance(v, dict) for v in entry.values()):
            # a path segment on the way to a deeper capability section
            # (dotted capability names, e.g. `[svc.audio.stt]`)
            _walk_capability_specs(entry, service_name, cap_path, seen, out, service_root)
        else:
            # a leaf table carrying no capability documentation keys — a
            # mistyped section must not vanish silently
            raise ServiceDeclarationError(
                f"`[{service_name}.{'.'.join(cap_path)}]` declares no capability"
                " documentation keys — a capability section declares:"
                f" {', '.join(sorted(CAPABILITY_SECTION_KEYS))} (typos fail"
                " loudly, ADR-0031 §2)"
            )


def _parse_capability_section(
    entry: dict, cap_name: str, section: str, service_root: Path
) -> Capability:
    unknown = set(entry) - CAPABILITY_SECTION_KEYS
    if unknown:
        if "dependencies" in unknown:
            raise ServiceDeclarationError(
                f"`[{section}]` declares `dependencies` — capability-level"
                " dependencies are not declared in service.toml; implementations"
                " declare their dependencies (ADR-0031 §2/§4)"
            )
        raise ServiceDeclarationError(
            f"`[{section}]` has unknown key(s) {sorted(unknown)} — a capability"
            f" section declares only: {', '.join(sorted(CAPABILITY_SECTION_KEYS))}"
        )

    api = _require_str(entry, "api", f"[{section}]")
    if not api.startswith("/"):
        raise ServiceDeclarationError(
            f"`[{section}].api` must be the capability's api description"
            " entry point (starting with `/`, e.g. `/v1/stt`)"
        )
    required = entry.get("required", False)
    if not isinstance(required, bool):
        raise ServiceDeclarationError(f"`[{section}].required` must be true or false")

    ui_raw = entry.get("ui", {})
    if not isinstance(ui_raw, dict):
        raise ServiceDeclarationError(f"`[{section}].ui` must be a table")
    unknown_ui = set(ui_raw) - CAPABILITY_UI_KEYS
    if unknown_ui:
        raise ServiceDeclarationError(
            f"`[{section}].ui` has unknown key(s) {sorted(unknown_ui)} — UI"
            f" hooks declare only: {', '.join(sorted(CAPABILITY_UI_KEYS))}"
        )
    menu_raw = ui_raw.get("menu", [])
    if not isinstance(menu_raw, list):
        raise ServiceDeclarationError(f"`[{section}].ui.menu` must be a list of tables")
    menu: list[MenuItem] = []
    for j, item in enumerate(menu_raw):
        if not isinstance(item, dict):
            raise ServiceDeclarationError(f"`[{section}].ui.menu[{j}]` is not a table")
        unknown_item = set(item) - {"label", "entry"}
        if unknown_item:
            raise ServiceDeclarationError(
                f"`[{section}].ui.menu[{j}]` has unknown key(s)"
                f" {sorted(unknown_item)} — a menu hook declares only: label,"
                " entry (closed shape, typos fail loudly)"
            )
        menu.append(
            MenuItem(
                label=_require_str(item, "label", f"[{section}].ui.menu[{j}]"),
                entry=_require_str(item, "entry", f"[{section}].ui.menu[{j}]"),
            )
        )

    learning_raw = entry.get("learning")
    learning: LearningBar | None = None
    if learning_raw is not None:
        if not isinstance(learning_raw, dict):
            raise ServiceDeclarationError(f"`[{section}].learning` must be a table")
        bar = validate_learning(
            learning_raw, where=f"[{section}].learning", err=ServiceDeclarationError
        )
        learning = load_learning_artifacts(
            bar,
            root=service_root,
            about_kind="capability",
            about=cap_name,
            where=f"[{section}].learning",
            err=ServiceDeclarationError,
        )

    return Capability(
        name=cap_name,
        description=_require_str(entry, "description", f"[{section}]"),
        version=_require_str(entry, "version", f"[{section}]"),
        api=api,
        api_functions=_require_str(entry, "api-functions", f"[{section}]"),
        versions_history=_require_str(entry, "versions-history", f"[{section}]"),
        required=required,
        ui_menu=tuple(menu),
        ui_description=_require_str(ui_raw, "description", f"[{section}].ui"),
        ui_versions_history=_require_str(ui_raw, "versions-history", f"[{section}].ui"),
        learning=learning,
    )
