"""The capability-implementation declaration loader (ticket #74; ADR-0018
§8, ADR-0027, **ADR-0031 — declaration model v2**).

An `implementation.toml` describes **one capability implementation** — a
service has no implementation (ADR-0031 §1). The field map is ADR-0031
§3/§4; its tests (`tests/contract/test_declaration.py`) document each group:

- `[identity]` (name/version/description), `capability`, `source`
  (`local-weights` | `cloud:<provider>/<model>`, ADR-0027 §4), `license`
  (SPDX), `privacy-tier` (`local`/`cloud_no_data`/`cloud`), `[links]`.
- **`[contents]`** (replaces `kind`) — named content parts, each typed
  `inference-engine | model | database | storage-space | open-source-product`.
  Per-type facts: engine/database/OSS parts carry a `github` URL; **model**
  parts carry the `huggingface` weights URL, the `artificial-analysis` slug
  (the join key for ADR-0031 §5's dynamic metrics) and **objective facts
  only** (disk size, active/total parameters, VRAM at load, KV-cache size
  per token, quantization); a `storage-space` part may propose a
  `default-quota-gb` — the user's install-time choice is the bound.
- **`[requirements]`** — the minimum to install **and run**: `disk-gb`,
  `ram-gb`, `cpu` technologies, `gpu` technologies, `vram-gb`.
- **`[dependencies]`** — generic (ADR-0031 §4): on a **capability** (any
  implementation of it satisfies) or on a **specific implementation**
  (that one is required), each with optional `min-version`/`features`
  (ADR-0016 §3's satisfy relation). Model→engine is an instance, not syntax.

`supported`/`recommended` are **computed, never stored** (ADR-0002 §5,
ADR-0005, ADR-0031 §5): no `[ranks]`, no quality claims — model ordering
uses artificialanalysis metrics fetched at selection time by the core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomllib

PRIVACY_TIERS = ("local", "cloud_no_data", "cloud")

CONTENT_TYPES = (
    "inference-engine",
    "model",
    "database",
    "storage-space",
    "open-source-product",
)

MODEL_OBJECTIVE_FACTS = (
    "disk-gb",
    "parameters-active",
    "parameters-total",
    "vram-at-load-gb",
    "kv-cache-per-token",
    "quantization",
)


class ImplementationDeclarationError(ValueError):
    """An `implementation.toml` that violates its declared shape."""


def _err(msg: str) -> ImplementationDeclarationError:
    return ImplementationDeclarationError(msg)


@dataclass(frozen=True)
class ContentPart:
    """One named entry of `[contents]` (ADR-0031 §3) — an implementation may
    bundle several parts; per-type facts key off the part."""

    name: str
    type: str
    github: str | None = None          # inference-engine / database / open-source-product
    huggingface: str | None = None     # model weights URL
    artificial_analysis: str | None = None  # the AA slug — the join key for dynamic metrics
    facts: dict = field(default_factory=dict)   # model objective facts / storage default quota


@dataclass(frozen=True)
class Requirements:
    """The minimum to install **and run** the implementation (ADR-0031 §3):
    disk/RAM, CPU/GPU technologies, VRAM."""

    disk_gb: float
    ram_gb: float
    cpu_technologies: tuple[str, ...] = ()
    gpu_technologies: tuple[str, ...] = ()
    vram_gb: float = 0.0


@dataclass(frozen=True)
class Dependency:
    """A generic dependency (ADR-0031 §4): on a capability (any
    implementation of it satisfies) or on a specific implementation (that
    one is required), with optional min-version/features — ADR-0016 §3's
    satisfy relation. Model→engine is an instance."""

    capability: str | None
    implementation: str | None
    min_version: str | None = None
    features: tuple[str, ...] = ()


@dataclass(frozen=True)
class Implementation:
    """One parsed `implementation.toml` (ADR-0031 §3/§4's field map)."""

    capability: str
    name: str
    version: str
    description: str
    source: str
    license: str
    privacy_tier: str
    links: dict[str, str]
    contents: tuple[ContentPart, ...]
    requirements: Requirements
    dependencies: tuple[Dependency, ...]


def load_implementation_toml(path: str | Path) -> Implementation:
    """Load and validate one capability-implementation declaration."""
    path = Path(path)
    if not path.is_file():
        raise _err(f"implementation declaration not found: {path}")

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    capability = raw.get("capability")
    if not isinstance(capability, str) or not capability:
        raise _err("`capability` must be a non-empty string (the capability implemented)")

    identity = raw.get("identity")
    if not isinstance(identity, dict):
        raise _err("`[identity]` table is required (name, version, description)")
    name = identity["name"] if isinstance(identity.get("name"), str) else ""
    version = identity["version"] if isinstance(identity.get("version"), str) else ""
    description = (
        identity["description"] if isinstance(identity.get("description"), str) else ""
    )
    if not name.strip() or not version.strip() or not description.strip():
        raise _err(
            "`[identity].name`, `[identity].version` and `[identity].description`"
            " must all be non-empty strings"
        )

    source = raw.get("source")
    if not isinstance(source, str) or not (
        source == "local-weights" or source.startswith("cloud:")
    ):
        raise _err(
            '`source` must be "local-weights" or "cloud:<provider>/<model>"'
            " (ADR-0027 §1: local weights → a local engine; a cloud ref →"
            " the cloud-gateway engine)"
        )

    license_id = raw.get("license")
    if not isinstance(license_id, str) or not license_id.strip():
        raise _err("`license` must be a non-empty SPDX string (ADR-0022)")

    privacy_tier = raw.get("privacy-tier")
    if privacy_tier not in PRIVACY_TIERS:
        raise _err(f"`privacy-tier` must be one of {PRIVACY_TIERS} (ADR-0006/0008)")

    links = raw.get("links", {})
    if not isinstance(links, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in links.items()
    ):
        raise _err("`[links]` must be a table of strings (release/repo/license/evaluations)")

    if "kind" in raw:
        raise _err("`kind` is superseded by `[contents]` (ADR-0031 §3) — remove the key")
    if "ranks" in raw:
        raise _err(
            "`[ranks]` is removed (ADR-0031 §5) — model quality/speed/cost"
            " comparisons are dynamic (artificialanalysis at selection time);"
            " declarations carry objective facts only"
        )
    if "engine-dependency" in raw:
        raise _err(
            "`[engine-dependency]` is superseded by generic `[dependencies]`"
            " (ADR-0031 §4) — depend on the capability or a specific"
            " implementation instead"
        )

    contents = _validate_contents(raw.get("contents"))
    requirements = _validate_requirements(raw.get("requirements"))
    dependencies = _validate_dependencies(raw.get("dependencies", []))

    return Implementation(
        capability=capability,
        name=name,
        version=version,
        description=description,
        source=source,
        license=license_id,
        privacy_tier=privacy_tier,
        links=links,
        contents=contents,
        requirements=requirements,
        dependencies=dependencies,
    )


def _validate_contents(contents: object) -> tuple[ContentPart, ...]:
    if not isinstance(contents, dict) or not contents:
        raise _err(
            "`[contents]` is required — named content parts typed"
            f" {CONTENT_TYPES} (ADR-0031 §3; replaces `kind`)"
        )
    parts: list[ContentPart] = []
    for part_name, spec in contents.items():
        if not isinstance(spec, dict):
            raise _err(f"`[contents].{part_name}` must be a table")
        type_ = spec.get("type")
        if type_ not in CONTENT_TYPES:
            raise _err(
                f"`[contents].{part_name}.type` must be one of {CONTENT_TYPES}"
                " (ADR-0031 §3)"
            )
        github = spec.get("github")
        huggingface = spec.get("huggingface")
        slug = spec.get("artificial-analysis")

        facts: dict = {}
        if type_ in ("inference-engine", "database", "open-source-product"):
            if not isinstance(github, str) or not github.strip():
                raise _err(
                    f"`[contents].{part_name}.github` is required for a"
                    f" `{type_}` part (ADR-0031 §3)"
                )
        elif type_ == "model":
            if not isinstance(huggingface, str) or not huggingface.strip():
                raise _err(
                    f"`[contents].{part_name}.huggingface` is required for a"
                    " `model` part (the weights URL, ADR-0031 §3)"
                )
            if not isinstance(slug, str) or not slug.strip():
                raise _err(
                    f"`[contents].{part_name}.artificial-analysis` is required"
                    " for a `model` part (the AA slug — the join key for"
                    " dynamic metrics, ADR-0031 §5)"
                )
            facts_raw = spec.get("facts", {})
            if not isinstance(facts_raw, dict):
                raise _err(f"`[contents].{part_name}.facts` must be a table")
            for key, value in facts_raw.items():
                if key not in MODEL_OBJECTIVE_FACTS:
                    raise _err(
                        f"`[contents].{part_name}.facts.{key}` is not an"
                        " objective model fact — allowed:"
                        f" {MODEL_OBJECTIVE_FACTS} (ADR-0031 §3: no quality claims)"
                    )
                if key != "quantization" and (
                    not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
                ):
                    raise _err(
                        f"`[contents].{part_name}.facts.{key}` must be a"
                        " non-negative number"
                    )
            facts = dict(facts_raw)
        elif type_ == "storage-space":
            quota = spec.get("default-quota-gb")
            if quota is not None and (
                not isinstance(quota, (int, float)) or isinstance(quota, bool) or quota < 0
            ):
                raise _err(
                    f"`[contents].{part_name}.default-quota-gb` must be a"
                    " non-negative number — a proposal; the user's install-time"
                    " choice is the bound (ADR-0031 §3)"
                )
            if quota is not None:
                facts["default-quota-gb"] = quota

        parts.append(
            ContentPart(
                name=part_name,
                type=type_,
                github=github if isinstance(github, str) else None,
                huggingface=huggingface if isinstance(huggingface, str) else None,
                artificial_analysis=slug if isinstance(slug, str) else None,
                facts=facts,
            )
        )
    return tuple(parts)


def _validate_requirements(req: object) -> Requirements:
    if not isinstance(req, dict):
        raise _err(
            "`[requirements]` table is required — the minimum to install"
            " AND run (ADR-0031 §3)"
        )
    for key in ("disk-gb", "ram-gb"):
        value = req.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise _err(f"`[requirements].{key}` must be a non-negative number")
    vram = req.get("vram-gb", 0.0)
    if not isinstance(vram, (int, float)) or isinstance(vram, bool) or vram < 0:
        raise _err("`[requirements].vram-gb` must be a non-negative number")
    for key in ("cpu", "gpu"):
        tech = req.get(key, {})
        if not isinstance(tech, dict) or not all(
            isinstance(k, str) and isinstance(v, bool) for k, v in tech.items()
        ):
            raise _err(
                f"`[requirements].{key}` must be a table of booleans —"
                " required technologies, yes/no per hardware capacity"
                " (ADR-0005 §1)"
            )
    return Requirements(
        disk_gb=float(req["disk-gb"]),
        ram_gb=float(req["ram-gb"]),
        cpu_technologies=tuple(t for t, needed in req.get("cpu", {}).items() if needed),
        gpu_technologies=tuple(t for t, needed in req.get("gpu", {}).items() if needed),
        vram_gb=float(vram),
    )


def _validate_dependencies(deps: object) -> tuple[Dependency, ...]:
    if not isinstance(deps, list):
        raise _err("`[dependencies]` must be a list of tables (ADR-0031 §4)")
    out: list[Dependency] = []
    for i, dep in enumerate(deps):
        where = f"[[dependencies]][{i}]"
        if not isinstance(dep, dict):
            raise _err(f"{where} is not a table")
        capability = dep.get("capability")
        implementation = dep.get("implementation")
        if (capability is None) == (implementation is None):
            raise _err(
                f"{where} declares exactly one of `capability` (any"
                " implementation of it satisfies) or `implementation`"
                " (that specific implementation is required) — ADR-0031 §4"
            )
        if capability is not None and (
            not isinstance(capability, str) or not capability.strip()
        ):
            raise _err(f"{where}.capability must be a non-empty string")
        if implementation is not None and (
            not isinstance(implementation, str) or not implementation.strip()
        ):
            raise _err(f"{where}.implementation must be a non-empty string")
        min_version = dep.get("min-version")
        if min_version is not None and (
            not isinstance(min_version, str) or not min_version.strip()
        ):
            raise _err(
                f"{where}.min-version must be a non-empty string — ADR-0016"
                " §3's declared-dependency machinery, checked as a satisfy relation"
            )
        features = dep.get("features", [])
        if not isinstance(features, list) or not all(isinstance(f, str) for f in features):
            raise _err(f"{where}.features must be a list of strings")
        out.append(
            Dependency(
                capability=capability if isinstance(capability, str) else None,
                implementation=implementation if isinstance(implementation, str) else None,
                min_version=min_version,
                features=tuple(features),
            )
        )
    return tuple(out)