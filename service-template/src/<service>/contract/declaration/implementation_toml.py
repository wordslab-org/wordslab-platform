"""The capability-implementation declaration loader (ticket #74; ADR-0018
§8, ADR-0027, **ADR-0031 — declaration model v2/v3**).

An `implementation.toml` describes **one capability implementation** — a
service has no implementation (ADR-0031 §1). Layout: the implementation's
own properties first, then one **documentation section per content part**,
named `<capability>.<content-part-type>.<content-part-name>` (ADR-0031 §3):

- own properties: `capability`, `license` (SPDX), `[identity]`
  (name/version/description), `[requirements]` — the implementation's OWN
  code only — and generic `[[dependencies]]` (ADR-0031 §4: on a capability
  or a specific implementation, with optional min-version/features).
- **content-part sections** — each type may appear **several times** (an
  implementation can bundle several models): `inference-engine` (github
  URL, requirements) · `local-model` (huggingface weights URL +
  artificial-analysis slug + objective facts + requirements) · `cloud-model`
  (provider/model ref + AA slug + privacy-tier; NO requirements — a cloud
  part consumes no machine) · `database` (github, requirements) ·
  `storage-space` (a required `min-quota-gb` — the minimum quota at
  install, included in the implementation's aggregate disk requirement;
  an optional `default-quota-gb` proposal — the user's install-time
  choice binds, never below the minimum) · `open-source-app` (github, requirements) · `cloud-service`
  (provider/service ref + privacy-tier; NO requirements).
- **aggregation**: the implementation's requirements are the **sum/union**
  of its own requirements and its parts' requirements (disk/ram/vram sum,
  CPU/GPU technologies union) — `Implementation.requirements`.
- **install contract**: the implementation-specific install function
  receives the typed `Implementation` object (this module's parse result)
  as its configuration data; the `ContentPart` objects are the per-part
  config.
- **the learning/operability bar** (ticket #75; ADR-0024 §1, ADR-0002 §7,
  shape per ADR-0031 §3 as amended): an own-properties `[learning]` table —
  the four graded doc levels (one Markdown artifact per level, `level` +
  `path`, relative to THIS file's directory) and exactly one of the
  how-an-agent-drives-me `skill` or the explicit "not agent-operable" note
  (no theater); the docs' front-matter names the implementation
  (`implementation:`). Validated fully when declared — a declared-but-fake
  artifact fails at load (`learning_bar.py`).

`supported`/`recommended` are **computed, never stored** (ADR-0002 §5,
ADR-0005, ADR-0031 §5): no `[ranks]`, no quality claims — model ordering
uses artificialanalysis metrics fetched at selection time by the core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomllib

from .learning_bar import LearningBar, load_learning_artifacts, validate_learning

PRIVACY_TIERS = ("local", "cloud_no_data", "cloud")

CONTENT_TYPES = (
    "inference-engine",
    "local-model",
    "cloud-model",
    "database",
    "storage-space",
    "open-source-app",
    "cloud-service",
)

CLOUD_TYPES = frozenset({"cloud-model", "cloud-service"})

LOCAL_MODEL_FACTS = (
    "disk-gb",
    "parameters-active",
    "parameters-total",
    "vram-at-load-gb",
    "kv-cache-per-token",
    "quantization",
)

CLOUD_MODEL_FACTS = (
    "parameters-active",
    "parameters-total",
    "quantization",
)

# per-type scalar keys (on top of the common description/version)
PART_TYPE_KEYS = {
    "inference-engine": ("github",),
    "local-model": ("huggingface", "artificial-analysis"),
    "cloud-model": ("provider", "model", "artificial-analysis", "privacy-tier"),
    "database": ("github",),
    "storage-space": ("min-quota-gb", "default-quota-gb"),
    "open-source-app": ("github",),
    "cloud-service": ("provider", "service", "privacy-tier"),
}

# types that may declare [requirements] (cloud parts consume no machine;
# a storage-space part's requirement IS its minimum quota — the user's
# install-time allocation is a maximum on top, never less than the minimum)
PART_TYPES_WITH_REQUIREMENTS = frozenset(
    {"inference-engine", "local-model", "database", "open-source-app"}
)

IMPLEMENTATION_TOP_LEVEL_KEYS = {
    "capability",
    "license",
    "identity",
    "requirements",
    "dependencies",
    "learning",
}


class ImplementationDeclarationError(ValueError):
    """An `implementation.toml` that violates its declared shape."""


def _err(msg: str) -> ImplementationDeclarationError:
    return ImplementationDeclarationError(msg)


def _is_capability_name(name: str) -> bool:
    """Capability names are lowercase dotted identifiers (`audio.stt`) —
    CONTEXT.md *Implementation* / ADR-0029's `<task>.model` grammar. No
    segment may be a content-part type token (it would make the part
    section path `[capability.type.name]` ambiguous)."""
    if not name:
        return False
    parts = name.split(".")
    return all(
        part.isidentifier() and part.islower() and part not in CONTENT_TYPES
        for part in parts
    )


@dataclass(frozen=True)
class Requirements:
    """The minimum to install **and run** (ADR-0031 §3): disk/RAM/VRAM,
    CPU/GPU technologies."""

    disk_gb: float
    ram_gb: float
    cpu_technologies: tuple[str, ...] = ()
    gpu_technologies: tuple[str, ...] = ()
    vram_gb: float = 0.0


EMPTY_REQUIREMENTS = Requirements(disk_gb=0.0, ram_gb=0.0)


@dataclass(frozen=True)
class ContentPart:
    """One content part, parsed from its documentation section
    `<capability>.<type>.<name>` (ADR-0031 §3). Each type may appear several
    times; per-type properties key off the part; the part's requirements
    feed the implementation's aggregate (sum/union). This object is the
    per-part configuration data handed to the install function."""

    name: str
    type: str
    description: str
    version: str
    github: str | None = None              # inference-engine / database / open-source-app
    huggingface: str | None = None         # local-model weights URL
    artificial_analysis: str | None = None  # local/cloud-model: the AA slug (dynamic-metrics join key)
    provider: str | None = None            # cloud-model / cloud-service
    model: str | None = None               # cloud-model (the provider's model id)
    service: str | None = None             # cloud-service (the provider's service id)
    privacy_tier: str | None = None         # cloud parts only (ADR-0006/0008)
    default_quota_gb: float | None = None   # storage-space proposal; the user's choice binds
    min_quota_gb: float | None = None       # storage-space minimum — required; counts as the part's disk requirement
    facts: dict = field(default_factory=dict)     # model objective facts
    requirements: Requirements | None = None     # part requirements (cloud parts: None)


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
    """One parsed `implementation.toml` — the typed object the
    implementation-specific install function receives as configuration
    data (ADR-0031 §3).

    `own_requirements` covers the implementation's own code;
    `requirements` is the **aggregate**: own + parts, quantities summed,
    technologies unioned."""

    capability: str
    name: str
    version: str
    description: str
    license: str
    own_requirements: Requirements
    requirements: Requirements
    contents: tuple[ContentPart, ...]
    dependencies: tuple[Dependency, ...]
    learning: LearningBar | None = None


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
    if not _is_capability_name(capability):
        raise _err(
            f"`capability` {capability!r} must be a lowercase dotted identifier"
            " (`audio.stt`) — the grammar of the capability it references"
        )

    _reject_unknown_top_level(raw)

    identity = raw.get("identity")
    if not isinstance(identity, dict):
        raise _err("`[identity]` table is required (name, version, description)")
    for retired, hint in (
        ("supported", "`supported` is computed from hardware facts at read time — never stored (ADR-0031 §5)"),
        ("recommended", "`recommended` is computed from the model-selection goal at read time — never stored (ADR-0031 §5)"),
        ("ranks", "`[ranks]` is removed (ADR-0031 §5) — dynamic metrics at selection time"),
    ):
        if retired in identity:
            raise _err(f"`[identity].{retired}` — {hint} — remove the key")
    unknown_identity = set(identity) - {"name", "version", "description"}
    if unknown_identity:
        raise _err(
            f"`[identity]` has unknown key(s) {sorted(unknown_identity)} —"
            " `[identity]` declares only: name, version, description"
            " (closed shape, typos fail loudly)"
        )
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
    for retired, hint in (
        ("supported", "`supported` is computed from hardware facts at read time — never stored (ADR-0031 §5)"),
        ("recommended", "`recommended` is computed from the model-selection goal at read time — never stored (ADR-0031 §5)"),
        ("ranks", "`[ranks]` is removed (ADR-0031 §5) — dynamic metrics at selection time"),
    ):
        if retired in identity:
            raise _err(f"`[identity].{retired}` — {hint}")

    license_id = raw.get("license")
    if not isinstance(license_id, str) or not license_id.strip():
        raise _err("`license` must be a non-empty SPDX string (ADR-0022)")

    own_requirements = _validate_requirements(
        raw.get("requirements"), where="[requirements]", required=False
    )
    dependencies = _validate_dependencies(raw.get("dependencies", []))
    learning = _parse_learning(raw, name, Path(path).parent)
    contents = _validate_part_sections(raw, capability)

    return Implementation(
        capability=capability,
        name=name,
        version=version,
        description=description,
        license=license_id,
        own_requirements=own_requirements,
        requirements=aggregate_requirements(own_requirements, contents),
        contents=contents,
        dependencies=dependencies,
        learning=learning,
    )


def _parse_learning(raw: dict, identity_name: str, root: Path) -> LearningBar | None:
    """The implementation's own learning/operability bar (ADR-0024 §1,
    ADR-0031 §3 as amended): own-properties block; the docs' front-matter
    names the implementation; artifacts validated at load (no theater)."""
    learning_raw = raw.get("learning")
    if learning_raw is None:
        return None
    if not isinstance(learning_raw, dict):
        raise _err("`[learning]` must be a table")
    bar = validate_learning(
        learning_raw, where="[learning]", err=ImplementationDeclarationError
    )
    return load_learning_artifacts(
        bar,
        root=root,
        about_kind="implementation",
        about=identity_name,
        where="[learning]",
        err=ImplementationDeclarationError,
    )


def _reject_unknown_top_level(raw: dict) -> None:
    """The closed-shape rule, part-section aware: a top-level key whose
    first segment starts the declared capability path is the root of a
    `[capability.type.part-name]` documentation section, not an unknown
    key. The part-section walk (`_validate_part_sections`) validates the
    rest."""
    capability = raw.get("capability")
    capability_head = capability.split(".")[0] if isinstance(capability, str) else None
    unknown = {
        key
        for key in set(raw) - IMPLEMENTATION_TOP_LEVEL_KEYS
        if capability_head is None or key.split(".")[0] != capability_head
    }
    for retired, hint in (
        (
            "kind",
            "`kind` is superseded by the content-part documentation sections"
            " `[capability.type.part-name]` (ADR-0031 §3)",
        ),
        ("ranks", "`[ranks]` is removed (ADR-0031 §5) — dynamic metrics at selection time"),
        (
            "engine-dependency",
            "`[engine-dependency]` is superseded by generic `[dependencies]` (ADR-0031 §4)",
        ),
        (
            "supported",
            "`supported` is computed from hardware facts at read time — never stored (ADR-0031 §5)",
        ),
        (
            "recommended",
            "`recommended` is computed from the model-selection goal at read time — never stored (ADR-0031 §5)",
        ),
        (
            "source",
            "`source` moved under the model parts — a `local-model` part carries the"
            " huggingface weights URL, a `cloud-model` part carries the provider/model"
            " reference (ADR-0031 §3)",
        ),
        (
            "privacy-tier",
            "`privacy-tier` moved to the cloud parts (`cloud-model`, `cloud-service`)"
            " — only a cloud part has a privacy tier (ADR-0031 §3)",
        ),
        (
            "links",
            "`[links]` is superseded by the per-part URLs (github, huggingface, provider refs)",
        ),
        (
            "contents",
            "`[contents]` is superseded by the content-part documentation sections"
            " `[capability.type.part-name]` (ADR-0031 §3)",
        ),
    ):
        if retired in unknown:
            raise _err(f"{hint} — remove the key")
    if not unknown:
        return
    known = ", ".join(sorted(IMPLEMENTATION_TOP_LEVEL_KEYS))
    raise _err(
        f"unknown top-level key(s) {sorted(unknown)} — implementation.toml"
        f" declares only: {known} plus content-part sections"
        f" `[capability.type.part-name]` (typos fail loudly, ADR-0031 §3/§4)"
    )


# ------------------------------------------------------------------ part walk


def _walk_part_sections(
    node: dict,
    capability_segments: list[str],
    declared: str,
    out: list,
) -> None:
    """Walk the nested tables of the bare TOML headers
    `[capability.type.part-name...]`, reconstructing the dotted names.

    Deterministic and loud: while the path is still inside the declared
    capability, only the declared next segment may appear — anything else is
    an unknown content-part type and fails at load. Type tokens end the
    capability path (capability names may not contain type tokens —
    `_is_capability_name`)."""
    declared_segments = declared.split(".")
    at_capability_root = len(capability_segments) == len(declared_segments)
    for key, value in node.items():
        if not isinstance(value, dict):
            continue
        if key in CONTENT_TYPES:
            if not at_capability_root:
                raise _err(
                    f"`{key}` looks like a content-part type but appears inside"
                    f" the capability path `{'.'.join(capability_segments)}` —"
                    " content-part sections are"
                    " `[<capability>.<content-part-type>.<part-name>]`"
                )
            capability = ".".join(capability_segments)
            if capability != declared:
                raise _err(
                    f"content-part section `[{'.'.join(capability_segments)}.{key}.*]`"
                    f" declares capability {capability!r} but this implementation"
                    f" declares {declared!r}"
                )
            for part_name, spec in value.items():
                if not isinstance(spec, dict):
                    raise _err(
                        f"`[{'.'.join(capability_segments + [key, part_name])}]`"
                        " must be a table"
                    )
                out.append((".".join(capability_segments), key, part_name, spec))
        elif at_capability_root:
            raise _err(
                f"unknown content-part type {key!r} — a part section is"
                f" `[<capability>.<type>.<part-name>]` with type one of"
                f" {CONTENT_TYPES} (ADR-0031 §3)"
            )
        else:
            expected = declared_segments[len(capability_segments)]
            if key != expected:
                raise _err(
                    f"unknown content-part type {key!r} — expected the declared"
                    f" capability path {declared!r}, a part section is"
                    f" `[<capability>.<type>.<part-name>]` with type one of"
                    f" {CONTENT_TYPES} (ADR-0031 §3)"
                )
            _walk_part_sections(value, capability_segments + [key], declared, out)


def _validate_part_sections(
    raw: dict, declared_capability: str
) -> tuple[ContentPart, ...]:
    found: list = []
    for key, value in raw.items():
        if key in IMPLEMENTATION_TOP_LEVEL_KEYS or not isinstance(value, dict):
            continue
        _walk_part_sections({key: value}, [], declared_capability, found)
    if not found:
        raise _err(
            "no content-part documentation sections — expected at least one"
            " `[capability.type.part-name]` section (ADR-0031 §3)"
        )
    parts: list[ContentPart] = []
    for capability, type_, part_name, spec in found:
        parts.append(_validate_part(part_name, type_, spec))
    return tuple(parts)


def _validate_part(part_name: str, type_: str, spec: dict) -> ContentPart:
    where = f"[{'.'.join([type_, part_name])}]"

    # cloud parts consume no machine hardware — loud BEFORE the generic
    # unknown-key scan so the message teaches the rule (ADR-0031 §3)
    if type_ in CLOUD_TYPES and "requirements" in spec:
        raise _err(
            f"`{where}` declares `[requirements]` — cloud parts consume no"
            " machine hardware and declare no requirements (ADR-0031 §3)"
        )

    allowed = {"description", "version"} | set(PART_TYPE_KEYS[type_])
    if type_ in PART_TYPES_WITH_REQUIREMENTS:
        allowed |= {"requirements"}
    if type_ in ("local-model", "cloud-model"):
        allowed |= {"facts"}
    unknown = set(spec) - allowed
    if unknown:
        raise _err(
            f"`{where}` has unknown key(s) {sorted(unknown)} — a `{type_}` part"
            f" declares only: {', '.join(sorted(allowed))}"
        )

    def _req_str(key: str) -> str:
        value = spec.get(key)
        if not isinstance(value, str) or not value.strip():
            raise _err(f"`{where}.{key}` must be a non-empty string")
        return value

    part = ContentPart(
        name=part_name,
        type=type_,
        description=_req_str("description"),
        version=_req_str("version"),
    )

    if type_ in ("inference-engine", "database", "open-source-app"):
        part_github = spec.get("github")
        if not isinstance(part_github, str) or not part_github.strip():
            raise _err(f"`{where}.github` is required for a `{type_}` part (ADR-0031 §3)")
        if not _is_github_url(part_github):
            raise _err(
                f"`{where}.github` must be the part's github repository URL"
                ' (e.g. "https://github.com/org/repo")'
            )
        object.__setattr__(part, "github", part_github)

    if type_ == "local-model":
        hf = spec.get("huggingface")
        if not isinstance(hf, str) or not hf.strip():
            raise _err(
                f"`{where}.huggingface` is required for a `local-model` part"
                " (the weights URL, ADR-0031 §3)"
            )
        if not _is_huggingface_url(hf):
            raise _err(
                f"`{where}.huggingface` must be the weights URL on huggingface.co"
                ' (e.g. "https://huggingface.co/Qwen/Qwen3-4B")'
            )
        slug = spec.get("artificial-analysis")
        if not isinstance(slug, str) or not slug.strip():
            raise _err(
                f"`{where}.artificial-analysis` is required for a `local-model`"
                " part (the AA slug — the join key for dynamic metrics, ADR-0031 §5)"
            )
        object.__setattr__(part, "huggingface", hf)
        object.__setattr__(part, "artificial_analysis", slug)
        object.__setattr__(part, "facts", _validate_facts(spec.get("facts", {}), LOCAL_MODEL_FACTS, where))

    elif type_ == "cloud-model":
        for key in ("provider", "model", "artificial-analysis"):
            _req_str(key)
        object.__setattr__(part, "provider", spec["provider"])
        object.__setattr__(part, "model", spec["model"])
        object.__setattr__(part, "artificial_analysis", spec["artificial-analysis"])
        object.__setattr__(part, "privacy_tier", _validate_privacy(spec, where))
        object.__setattr__(part, "facts", _validate_facts(spec.get("facts", {}), CLOUD_MODEL_FACTS, where))

    elif type_ == "cloud-service":
        for key in ("provider", "service"):
            _req_str(key)
        object.__setattr__(part, "provider", spec["provider"])
        object.__setattr__(part, "service", spec["service"])
        object.__setattr__(part, "privacy_tier", _validate_privacy(spec, where))

    elif type_ == "storage-space":
        # The minimum quota is REQUIRED and is the part's disk requirement —
        # the implementation cannot install with less; the user's
        # install-time allocation (a maximum, monitored and changeable
        # later — ADR-0005 §8) may only exceed it. The default is a proposal.
        min_quota = spec.get("min-quota-gb")
        if not isinstance(min_quota, (int, float)) or isinstance(min_quota, bool) or min_quota <= 0:
            raise _err(
                f"`{where}.min-quota-gb` is required for a `storage-space` part"
                " — a positive number: the minimum quota at install, included"
                " in the implementation's aggregate disk requirement"
                " (ADR-0031 §3)"
            )
        quota = spec.get("default-quota-gb")
        if quota is not None and (
            not isinstance(quota, (int, float)) or isinstance(quota, bool) or quota < 0
        ):
            raise _err(
                f"`{where}.default-quota-gb` must be a non-negative number — a"
                " proposal; the user's install-time choice is the bound (ADR-0031 §3)"
            )
        if quota is not None and float(quota) < float(min_quota):
            raise _err(
                f"`{where}.default-quota-gb` proposes {float(quota)} GB but"
                f" `min-quota-gb` is {float(min_quota)} GB — the proposal may"
                " not undercut the minimum"
            )
        object.__setattr__(part, "min_quota_gb", float(min_quota))
        if quota is not None:
            object.__setattr__(part, "default_quota_gb", float(quota))
        # the part's requirement IS its minimum quota — flows into the
        # implementation's aggregate disk requirement
        object.__setattr__(
            part,
            "requirements",
            Requirements(disk_gb=float(min_quota), ram_gb=0.0),
        )

    if type_ in PART_TYPES_WITH_REQUIREMENTS:
        object.__setattr__(
            part,
            "requirements",
            _validate_requirements(
                spec.get("requirements"), where=f"{where}.requirements", required=False
            ),
        )

    return part


def _is_github_url(value: str) -> bool:
    return value.startswith("https://github.com/") and len(value) > len("https://github.com/")


def _is_huggingface_url(value: str) -> bool:
    return value.startswith("https://huggingface.co/") and len(value) > len(
        "https://huggingface.co/"
    )


def _validate_privacy(spec: dict, where: str) -> str:
    tier = spec.get("privacy-tier")
    if tier not in PRIVACY_TIERS:
        raise _err(f"`{where}.privacy-tier` must be one of {PRIVACY_TIERS} (ADR-0006/0008)")
    return tier


def _validate_facts(facts: object, allowed: tuple[str, ...], where: str) -> dict:
    if not isinstance(facts, dict):
        raise _err(f"`{where}.facts` must be a table")
    for key, value in facts.items():
        if key not in allowed:
            raise _err(
                f"`{where}.facts.{key}` is not an objective model fact — allowed:"
                f" {allowed} (ADR-0031 §3: no quality claims)"
            )
        if key != "quantization" and (
            not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        ):
            raise _err(f"`{where}.facts.{key}` must be a non-negative number")
    return dict(facts)


# ------------------------------------------------------------- requirements


def _validate_requirements(req: object, *, where: str, required: bool) -> Requirements:
    if req is None:
        if required:
            raise _err(f"`{where}` table is required — the minimum to install AND run (ADR-0031 §3)")
        return EMPTY_REQUIREMENTS
    if not isinstance(req, dict):
        raise _err(f"`{where}` must be a table")
    unknown = set(req) - {"disk-gb", "ram-gb", "vram-gb", "cpu", "gpu"}
    for retired, hint in (
        ("supported", "`supported` is computed from hardware facts at read time — never stored (ADR-0031 §5)"),
        ("recommended", "`recommended` is computed from the model-selection goal at read time — never stored (ADR-0031 §5)"),
    ):
        if retired in unknown:
            raise _err(f"`{where}.{retired}` — {hint} — remove the key")
    if unknown:
        raise _err(
            f"`{where}` has unknown key(s) {sorted(unknown)} — a requirements"
            " table declares only: disk-gb, ram-gb, vram-gb, cpu, gpu"
            " (closed shape, typos fail loudly)"
        )
    for key in ("disk-gb", "ram-gb"):
        value = req.get(key, 0.0)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise _err(f"`{where}.{key}` must be a non-negative number")
    vram = req.get("vram-gb", 0.0)
    if not isinstance(vram, (int, float)) or isinstance(vram, bool) or vram < 0:
        raise _err(f"`{where}.vram-gb` must be a non-negative number")
    for key in ("cpu", "gpu"):
        tech = req.get(key, {})
        if not isinstance(tech, dict) or not all(
            isinstance(k, str) and isinstance(v, bool) for k, v in tech.items()
        ):
            raise _err(
                f"`{where}.{key}` must be a table of booleans — required"
                " technologies, yes/no per hardware capacity (ADR-0005 §1)"
            )
    return Requirements(
        disk_gb=float(req.get("disk-gb", 0.0)),
        ram_gb=float(req.get("ram-gb", 0.0)),
        cpu_technologies=tuple(t for t, needed in req.get("cpu", {}).items() if needed),
        gpu_technologies=tuple(t for t, needed in req.get("gpu", {}).items() if needed),
        vram_gb=float(vram),
    )


def aggregate_requirements(
    own: Requirements, parts: tuple[ContentPart, ...]
) -> Requirements:
    """The implementation's requirements = **sum/union** of its own code
    requirements and its parts' requirements (ADR-0031 §3): disk/ram/vram
    add up (parts are co-resident at run), CPU/GPU technologies union in
    first-declared order. Cloud parts contribute nothing (no requirements)."""
    disk = own.disk_gb
    ram = own.ram_gb
    vram = own.vram_gb
    cpu: list[str] = list(own.cpu_technologies)
    gpu: list[str] = list(own.gpu_technologies)
    for part in parts:
        req = part.requirements
        if req is None:
            continue
        disk += req.disk_gb
        ram += req.ram_gb
        vram += req.vram_gb
        for tech in req.cpu_technologies:
            if tech not in cpu:
                cpu.append(tech)
        for tech in req.gpu_technologies:
            if tech not in gpu:
                gpu.append(tech)
    return Requirements(
        disk_gb=disk,
        ram_gb=ram,
        cpu_technologies=tuple(cpu),
        gpu_technologies=tuple(gpu),
        vram_gb=vram,
    )


# ------------------------------------------------------------- dependencies


def _validate_dependencies(deps: object) -> tuple[Dependency, ...]:
    if not isinstance(deps, list):
        raise _err("`[dependencies]` must be a list of tables (ADR-0031 §4)")
    out: list[Dependency] = []
    for i, dep in enumerate(deps):
        where = f"[[dependencies]][{i}]"
        if not isinstance(dep, dict):
            raise _err(f"{where} is not a table")
        unknown = set(dep) - {"capability", "implementation", "min-version", "features"}
        if unknown:
            raise _err(
                f"{where} has unknown key(s) {sorted(unknown)} — a dependency"
                " declares only: capability, implementation, min-version, features"
                " (ADR-0031 §4)"
            )
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