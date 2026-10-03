"""The service's self-declaration loader (ticket #74; ADR-0002 §5).

`service.toml` declares — per ADR-0002 §5: identity (name/version/description),
the **families declared** (ADR-0001's nine; a plain CRUD service keeps base
alone), the **capabilities** the service implements, and the **UI nav**.
`families`/`capabilities`/`nav` are **data**: families arrive with the
stage-0 family-module tickets (#76–#84); capabilities arrive with #71's
canary capability — the template ships `[]` so the copy-to-start ritual
replaces the placeholders.

`supported` (with `recommended`) do not appear here — that is the
implementations' computed vocabulary (ADR-0005, never stored,
`model_selection.py`).
"""

from __future__ import annotations

from pathlib import Path

import tomllib

# ADR-0001's nine family names, verbatim in declaration order. The
# family-module tickets (#76–#84) name their modules with these tokens.
DECLARED_FAMILIES = (
    "llm-inference",        # family 1 — LLM & agents inference (Responses API)
    "model-inference",      # family 2 — other model inference (by reference)
    "tool-services",        # family 3 — stateless MCP
    "realtime",             # family 4 — realtime voice (WebRTC primary)
    "jobs-model-lifecycle", # family 5 — async jobs & model lifecycle
    "batch",                # family 6
    "uploads",              # family 7
    "webhooks",             # family 8
    "authoring-management", # family 9
)


class Service:
    """The parsed `service.toml` — the declared side of the service shell.

    `families` is the family-declaration the copy-to-start ritual edits;
    the vendored conformance suite reads it to parameterize which family's
    tests run (ticket #70).
    """

    def __init__(
        self,
        *,
        name: str,
        version: str,
        description: str,
        families: tuple[str, ...],
        capabilities: tuple[str, ...],
        nav: tuple[dict, ...],
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.families = families
        self.capabilities = capabilities
        self.nav = nav


class ServiceDeclarationError(ValueError):
    """A `service.toml` that violates its declared shape.

    Raised at load time — declaration errors are structural (a service can't
    boot half-declared), so the failure surfaces here, not at request time.
    """


def _require_str(table: dict, key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ServiceDeclarationError(f"`{where}.{key}` must be a non-empty string")
    return value


def _require_str_list(table: dict, key: str, where: str) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ServiceDeclarationError(f"`{where}.{key}` must be a list of strings")
    return value


def load_service_toml(path: str | Path) -> Service:
    """Load and validate a `service.toml`.

    Validation is the ADR-0001/0002 shape (an unknown family is the
    copy-to-start ritual's editing error, caught here, not at request time).
    """
    path = Path(path)
    if not path.is_file():
        raise ServiceDeclarationError(f"declaration file not found: {path}")

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    name = _require_str(raw, "name", "service")
    version = _require_str(raw, "version", "service")
    description = _require_str(raw, "description", "service")

    families = _require_str_list(raw, "families", "service")
    unknown = [f for f in families if f not in DECLARED_FAMILIES]
    if unknown:
        raise ServiceDeclarationError(
            f"unknown family names {unknown} — the nine names live in ADR-0001"
            f" §Family contracts; valid: {', '.join(DECLARED_FAMILIES)}"
        )
    if len(set(families)) != len(families):
        raise ServiceDeclarationError("duplicate family declaration")

    capabilities = _require_str_list(raw, "capabilities", "service")
    for cap in capabilities:
        _check_capability_name(cap)

    nav_raw = raw.get("ui", {}).get("nav", [])
    if not isinstance(nav_raw, list):
        raise ServiceDeclarationError("`[ui].nav` must be a list of tables")
    nav = []
    for i, entry in enumerate(nav_raw):
        if not isinstance(entry, dict):
            raise ServiceDeclarationError(f"nav entry #{i} is not a table")
        label = _require_str(entry, "label", f"nav[{i}]")
        target = _require_str(entry, "target", f"nav[{i}]")
        nav.append({"label": label, "target": target})

    return Service(
        name=name,
        version=version,
        description=description,
        families=tuple(families),
        capabilities=tuple(capabilities),
        nav=tuple(nav),
    )


def _check_capability_name(cap: str) -> None:
    """Capability names are lowercase dotted identifiers (`audio.stt`) —
    CONTEXT.md *Implementation* / ADR-0027's `<task>.model` grammar."""
    if not cap or not all(part.isidentifier() and part.islower() for part in cap.split(".")):
        raise ServiceDeclarationError(
            f"capability name {cap!r} must be a lowercase dotted identifier"
        )
