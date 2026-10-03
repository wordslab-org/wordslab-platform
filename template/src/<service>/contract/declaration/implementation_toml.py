"""The implementation-declaration loader (ticket #74; ADR-0027, ADR-0018 §8).

Every implementation — **service, capability, model, engine** — is declared
in its own `implementation.toml`, symmetric with `service.toml` (ADR-0027 §1;
`models.toml` is retired). Field-for-field, what a declaration carries
(ADR-0027 §1's mapping table, ADR-0002 §5 sharpened):

| group | fields |
|---|---|
| identity | `identity.name` / `identity.version` / `identity.description` |
| source | `source` — `local-weights` (→ a local engine) or `cloud:<provider>/<model>` (→ the cloud-gateway engine) |
| license | `license` — SPDX; model weights carry the ADR-0022 five-question compliance profile |
| links | `[links]` — release / repo / license / evaluations |
| sizes | `sizes.download_gb` / `sizes.disk_gb` (disk at install — ADR-0005 §1) |
| resource profile | `[resource-profile]` — install requirements + the **running formula** (ADR-0005 §1/§2) |
| max capacity | `[max-capacity]` — context length, batch, document size (capped by hardware at load, lowerable by config) |
| ranks | `[ranks]` — accuracy/speed within the capability's list |
| modalities | `modalities` — input/output |
| privacy tier | `privacy-tier` — `local` / `cloud_no_data` / `cloud` (ADR-0006/0008) |
| engine dependency | `[engine-dependency]` — engine capability + min version + required optional features (ADR-0016 declared-dependency machinery) |

`supported`/`recommended` are **computed, never stored** (ADR-0002 §5,
ADR-0005): they never appear in this file — `model_selection.py` derives
them from the machine's hardware + the model-selection goal at read time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomllib

PRIVACY_TIERS = ("local", "cloud_no_data", "cloud")
SOURCES = ("local-weights", "cloud")

KINDS = ("service", "capability", "model", "engine")


class ImplementationDeclarationError(ValueError):
    """An `implementation.toml` that violates its declared shape."""


def _err(msg: str) -> ImplementationDeclarationError:
    return ImplementationDeclarationError(msg)


@dataclass(frozen=True)
class ResourceProfile:
    """ADR-0005 §1's two requirement states, verbatim.

    - **at install** — `disk_gb` (weights + execution code, = `sizes.disk_gb`
      mirrored here for the fit test) plus required **technologies**
      (yes/no per hardware capacity — AVX2/AVX512, tensor-core generation,
      FP8/NVFP4, …).
    - **when running** — the **running formula**: the declared configurable
      variables (batch/concurrency, context length, document/media length,
      with min/max ranges) and the formula estimating RAM/VRAM/disk from
      them. Resident weights are part of the running estimate — there is no
      separate "loaded" number.
    """

    disk_gb: float
    technologies: dict[str, bool] = field(default_factory=dict)
    variables: dict[str, dict[str, float]] = field(default_factory=dict)
    formula: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineDependency:
    """The declared engine requirement of a model implementation
    (ADR-0027 §3, ADR-0016 §3): the engine capability, a minimum API
    version, and the required optional features — checked as a satisfy
    relation."""

    capability: str
    min_version: str
    features: tuple[str, ...] = ()


@dataclass(frozen=True)
class Implementation:
    """One parsed `implementation.toml` (ADR-0027 §1's field map)."""

    kind: str
    capability: str
    name: str
    version: str
    description: str
    source: str
    license: str
    links: dict[str, str]
    sizes: dict[str, float]              # download_gb / disk_gb
    resource_profile: ResourceProfile
    max_capacity: dict[str, float]       # context / batch / document size
    ranks: dict[str, int]                # accuracy / speed within the capability's list
    modalities: dict[str, list[str]]     # input / output
    privacy_tier: str
    engine_dependency: EngineDependency | None  # models only


def load_implementation_toml(path: str | Path) -> Implementation:
    """Load and validate one `implementation.toml` (ADR-0027 §1's shape)."""
    path = Path(path)
    if not path.is_file():
        raise _err(f"implementation declaration not found: {path}")

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    kind = raw.get("kind")
    if kind not in KINDS:
        raise _err(f"`kind` must be one of {KINDS} (service | capability | model | engine)")

    capability = raw.get("capability")
    if not isinstance(capability, str) or not capability:
        raise _err("`capability` must be a non-empty string")

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

    links = raw.get("links", {})
    if not isinstance(links, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in links.items()
    ):
        raise _err("`[links]` must be a table of strings (release/repo/license/evaluations)")

    sizes = _validate_sizes(raw.get("sizes"))
    resource_profile = _validate_resource_profile(raw.get("resource-profile"), sizes)
    _validate_max_capacity(raw.get("max-capacity"))
    ranks = _validate_ranks(raw.get("ranks"))
    modalities = _validate_modalities(raw.get("modalities"))

    privacy_tier = raw.get("privacy-tier")
    if privacy_tier not in PRIVACY_TIERS:
        raise _err(f"`privacy-tier` must be one of {PRIVACY_TIERS} (ADR-0006/0008)")

    engine_dependency = _validate_engine_dependency(raw, kind, source)

    return Implementation(
        kind=kind,
        capability=capability,
        name=name,
        version=version,
        description=description,
        source=source,
        license=license_id,
        links=links,
        sizes=sizes,
        resource_profile=resource_profile,
        max_capacity=raw.get("max-capacity", {}),
        ranks=ranks,
        modalities=modalities,
        privacy_tier=privacy_tier,
        engine_dependency=engine_dependency,
    )


def _validate_sizes(sizes: object) -> dict[str, float]:
    if not isinstance(sizes, dict):
        raise _err("`[sizes]` table is required (download_gb / disk_gb)")
    for key in ("download_gb", "disk_gb"):
        value = sizes.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise _err(f"`[sizes].{key}` must be a non-negative number (GB, ADR-0005 §1)")
    return {k: float(v) for k, v in sizes.items() if k in ("download_gb", "disk_gb")}


def _validate_resource_profile(profile: object, sizes: dict[str, float]) -> ResourceProfile:
    if not isinstance(profile, dict):
        raise _err("`[resource-profile]` table is required (ADR-0005 §1/§2)")

    disk_gb = profile.get("disk_gb", sizes["disk_gb"])
    if not isinstance(disk_gb, (int, float)) or isinstance(disk_gb, bool) or disk_gb < 0:
        raise _err("`[resource-profile].disk_gb` must be a non-negative number (GB)")

    technologies = profile.get("technologies", {})
    if not isinstance(technologies, dict) or not all(
        isinstance(k, str) and isinstance(v, bool) for k, v in technologies.items()
    ):
        raise _err("`[resource-profile].technologies` must be a table of booleans (ADR-0005 §1)")

    variables = profile.get("variables", {})
    if not isinstance(variables, dict):
        raise _err("`[resource-profile].variables` must be a table")
    for var, spec in variables.items():
        if not isinstance(spec, dict) or set(spec) != {"min", "max"}:
            raise _err(
                f"`[resource-profile].variables.{var}` must be a table with exactly"
                " `min` and `max` (the configurable variables are the fit lever,"
                " ADR-0005 §1)"
            )
        for bound in spec.values():
            if not isinstance(bound, (int, float)) or isinstance(bound, bool):
                raise _err(f"`[resource-profile].variables.{var}` bounds must be numbers")

    formula = profile.get("formula", {})
    if not isinstance(formula, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in formula.items()
    ):
        raise _err(
            "`[resource-profile].formula` must be a table of strings — the"
            " expressions estimating RAM/VRAM/disk from the variables"
            " (ADR-0005 §1's running formula)"
        )
    for resource in formula:
        if resource not in ("ram_gb", "vram_gb", "disk_gb"):
            raise _err(
                f"formula key {resource!r} must be ram_gb / vram_gb / disk_gb"
                " (ADR-0001 item 4 / ADR-0005 §1's resource names)"
            )

    return ResourceProfile(
        disk_gb=float(disk_gb),
        technologies=dict(technologies),
        variables=variables,
        formula=dict(formula),
    )


def _validate_max_capacity(max_capacity: object) -> None:
    if max_capacity is None:
        return
    if not isinstance(max_capacity, dict):
        raise _err("`[max-capacity]` must be a table (context / batch / document size)")
    for key, value in max_capacity.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise _err(
                f"`[max-capacity].{key}` must be a non-negative number — max"
                " capacity is capped by hardware at load and lowerable by config"
                " (ADR-0004/0005)"
            )


def _validate_ranks(ranks: object) -> dict[str, int]:
    ranks = ranks or {}
    if not isinstance(ranks, dict):
        raise _err("`[ranks]` must be a table (accuracy / speed within the capability's list)")
    for key in ranks:
        if key not in ("accuracy", "speed"):
            raise _err(f"rank key {key!r} must be `accuracy` or `speed`")
        value = ranks[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise _err(f"`[ranks].{key}` must be a positive integer (1 = best in the capability's list)")
    return dict(ranks)


def _validate_modalities(modalities: object) -> dict[str, list[str]]:
    modalities = modalities or {}
    if not isinstance(modalities, dict):
        raise _err("`[modalities]` must be a table (input / output)")
    for key, value in modalities.items():
        if not isinstance(value, list) or not all(isinstance(m, str) for m in value):
            raise _err(f"`[modalities].{key}` must be a list of strings")
    return dict(modalities)


def _validate_engine_dependency(raw: dict, kind: str, source: str) -> EngineDependency | None:
    dep = raw.get("engine-dependency")
    if kind != "model":
        if dep is not None:
            raise _err(
                "`[engine-dependency]` is declared by model implementations only"
                " (ADR-0027 §1; engines and services/capabilities do not declare one)"
            )
        return None
    if not isinstance(dep, dict):
        raise _err(
            "a model implementation MUST declare `[engine-dependency]` — the"
            " engine capability + minimum version (ADR-0027 §3; a model will"
            " not run without a satisfying engine)"
        )
    capability = dep.get("capability")
    if not isinstance(capability, str) or not capability:
        raise _err("`[engine-dependency].capability` must be a non-empty string")
    if source == "local-weights" and capability == "cloud-gateway.engine":
        raise _err(
            "a `local-weights` model cannot depend on the cloud-gateway engine —"
            " `source = \"cloud:<provider>/<model>\"` declares cloud models"
            " (ADR-0027 §4)"
        )
    min_version = dep.get("min_version")
    if not isinstance(min_version, str) or not min_version.strip():
        raise _err(
            "`[engine-dependency].min_version` must be a non-empty string —"
            " ADR-0016 §3's declared-dependency machinery (min version +"
            " required optional features), checked as a satisfy relation"
        )
    features = dep.get("features", [])
    if not isinstance(features, list) or not all(isinstance(f, str) for f in features):
        raise _err("`[engine-dependency].features` must be a list of strings")
    return EngineDependency(capability, min_version, tuple(features))