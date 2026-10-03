"""The service declaration loader (ticket #74; ADR-0002 §5, ADR-0031 §2).

`service.toml` declares the service — **a set of capabilities**
(ADR-0031 §1): identity (name/description/version), one **service-level
`[requirements]`** figure (disk-gb + ram-gb for the service's own API + UI
code execution — each capability implementation selected at install time
adds its own requirements on top), and the **`[[capabilities]]`** list —
per capability: name, description, version, `api` (the capability's API
path prefix inside the service's single OpenAPI doc), `required` (an
implementation MUST be provided) or optional, and `[capabilities.ui]`
menu elements + entry points to integrate in the platform UI.

**API families are NOT declared** — the capabilities' APIs implement
ADR-0001's family contracts; their documentation is enough (ADR-0031 §2).
**No capability-level dependencies** — the implementations declare their
dependencies (`implementation_toml.py`), not the service.
"""

from __future__ import annotations

from pathlib import Path

import tomllib


class ServiceDeclarationError(ValueError):
    """A `service.toml` that violates its declared shape.

    Raised at load time — declaration errors are structural (a service can't
    boot half-declared), so the failure surfaces here, not at request time.
    """


class Capability:
    """One declared capability — the stable shell's per-capability face
    (ADR-0029 §4): identity, API path prefix, required/optional flag, and
    the UI menu elements + entry points the platform UI integrates."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        version: str,
        api: str,
        required: bool,
        ui: tuple[dict, ...],
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.api = api
        self.required = required
        self.ui = ui


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


def load_service_toml(path: str | Path) -> Service:
    """Load and validate a `service.toml` (ADR-0031 §2's shape).

    Validation is structural — the copy-to-start ritual's editing errors are
    caught here, not at request time.
    """
    path = Path(path)
    if not path.is_file():
        raise ServiceDeclarationError(f"declaration file not found: {path}")

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    name = _require_str(raw, "name", "service")
    description = _require_str(raw, "description", "service")
    version = _require_str(raw, "version", "service")

    if "families" in raw:
        raise ServiceDeclarationError(
            "`families` is not declared anymore (ADR-0031 §2) — family"
            " contracts are API-documentation facts; remove the key"
        )

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

    caps_raw = raw.get("capabilities", [])
    if not isinstance(caps_raw, list):
        raise ServiceDeclarationError("`[[capabilities]]` must be a list of tables")
    capabilities: list[Capability] = []
    seen: set[str] = set()
    for i, entry in enumerate(caps_raw):
        where = f"[[capabilities]][{i}]"
        if not isinstance(entry, dict):
            raise ServiceDeclarationError(f"{where} is not a table")
        cap_name = _require_str(entry, "name", where)
        _check_capability_name(cap_name)
        if cap_name in seen:
            raise ServiceDeclarationError(f"duplicate capability declaration: {cap_name}")
        seen.add(cap_name)
        api = _require_str(entry, "api", where)
        if not api.startswith("/"):
            raise ServiceDeclarationError(
                f"`{where}.api` must be the capability's API path prefix"
                " (starting with `/`, e.g. `/v1/stt`)"
            )
        required = entry.get("required", False)
        if not isinstance(required, bool):
            raise ServiceDeclarationError(f"`{where}.required` must be true or false")
        ui_raw = entry.get("ui", {}).get("menu", [])
        if not isinstance(ui_raw, list):
            raise ServiceDeclarationError(f"`{where}[ui].menu` must be a list of tables")
        ui = []
        for j, item in enumerate(ui_raw):
            if not isinstance(item, dict):
                raise ServiceDeclarationError(f"{where}[ui].menu[{j}] is not a table")
            ui.append(
                {
                    "label": _require_str(item, "label", f"{where}[ui].menu[{j}]"),
                    "entry": _require_str(item, "entry", f"{where}[ui].menu[{j}]"),
                }
            )
        capabilities.append(
            Capability(
                name=cap_name,
                description=_require_str(entry, "description", where),
                version=_require_str(entry, "version", where),
                api=api,
                required=required,
                ui=tuple(ui),
            )
        )

    return Service(
        name=name,
        description=description,
        version=version,
        requirements=requirements,
        capabilities=tuple(capabilities),
    )