"""Declaration-surface tests (ticket #74; ADR-0002 §5, ADR-0018 §8,
**ADR-0031 — declaration model v2**).

The declaration surface is **data** — tests assert the parsed shape and the
validation contract (a bad declaration fails a load with a precise error,
never a syntax crash at request time), plus the ADR-0031 §5 read-time rules:
`supported` is computed from hardware facts (never stored), ordering takes
externally-supplied dynamic metrics with unknown-last semantics, and no
declaration carries quality claims.
"""

from __future__ import annotations

import textwrap

import pytest

from contract.declaration import (
    ContentPart,
    Dependency,
    Implementation,
    ImplementationDeclarationError,
    Requirements,
    Service,
    ServiceDeclarationError,
    compute_supported,
    load_implementation_toml,
    load_service_toml,
    order_supported,
    validate_goal,
)


def write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(content))
    return path


# ---------------------------------------------------------------- service.toml


def test_template_service_toml_loads_with_the_v2_shape(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "template-service"
        description = "The service template — copy-to-start skeleton."
        version = "0.1.0"

        capabilities = []

        [requirements]
        disk-gb = 0.01
        ram-gb = 0.05
        """,
    )
    svc = load_service_toml(path)
    assert isinstance(svc, Service)
    assert svc.name == "template-service"
    assert svc.description == "The service template — copy-to-start skeleton."
    assert svc.version == "0.1.0"
    assert svc.requirements == {"disk-gb": 0.01, "ram-gb": 0.05}
    assert svc.capabilities == ()


def test_service_toml_declares_the_enriched_capability_list(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "audio"
        description = "The platform's voice surface."
        version = "0.1.0"

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.2

        [[capabilities]]
        name = "audio.stt"
        description = "Batch speech-to-text."
        version = "0.1.0"
        api = "/v1/audio/transcriptions"
        required = true

        [capabilities.ui]
        menu = [
            { label = "Transcribe", entry = "/stt" },
            { label = "Dictation", entry = "/dictation" },
        ]

        [[capabilities]]
        name = "audio.tts"
        description = "Batch text-to-speech."
        version = "0.1.0"
        api = "/v1/audio/speech"
        """,
    )
    svc = load_service_toml(path)
    assert len(svc.capabilities) == 2
    stt = svc.capabilities[0]
    assert stt.name == "audio.stt"
    assert stt.api == "/v1/audio/transcriptions"
    assert stt.required is True
    assert stt.ui == (
        {"label": "Transcribe", "entry": "/stt"},
        {"label": "Dictation", "entry": "/dictation"},
    )
    tts = svc.capabilities[1]
    assert tts.required is False  # optional when omitted
    assert tts.ui == ()


def test_service_toml_rejects_the_retired_families_key(tmp_path):
    """ADR-0031 §2: families are no longer declared — the key is a loud
    editing error, not silently ignored."""
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "svc"
        description = "d"
        version = "1.0.0"
        families = ["llm-inference"]
        capabilities = []

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1
        """,
    )
    with pytest.raises(ServiceDeclarationError, match="families"):
        load_service_toml(path)


def test_service_toml_rejects_unknown_top_level_keys(tmp_path):
    """A declaration is a closed shape — a typo (`desciption`) must fail at
    load, not silently load empty (the template's own contract: a malformed
    declaration fails at startup)."""
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "svc"
        desciption = "typo"
        version = "1.0.0"
        capabilities = []

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1
        """,
    )
    with pytest.raises(ServiceDeclarationError, match="unknown top-level key"):
        load_service_toml(path)


@pytest.mark.parametrize(
    "body,match",
    [
        # missing description
        (
            """
            name = "svc"
            version = "1.0.0"
            capabilities = []

            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            """,
            "description",
        ),
        # empty name
        (
            """
            name = ""
            description = "d"
            version = "1.0.0"
            capabilities = []

            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            """,
            "name",
        ),
        # unknown requirement key
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            capabilities = []

            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            vram-gb = 1.0
            """,
            "disk-gb and ram-gb only",
        ),
        # negative requirement
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            capabilities = []

            [requirements]
            disk-gb = -1
            ram-gb = 0.1
            """,
            "non-negative",
        ),
        # capability name not a lowercase dotted identifier
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [[capabilities]]
            name = "Canary.Echo"
            description = "d"
            version = "0.1.0"
            api = "/v1/echo"
            """,
            "lowercase dotted",
        ),
        # duplicate capability
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [[capabilities]]
            name = "a.b"
            description = "d"
            version = "0.1.0"
            api = "/v1/b"
            [[capabilities]]
            name = "a.b"
            description = "d"
            version = "0.1.0"
            api = "/v1/b"
            """,
            "duplicate",
        ),
        # api must be a path prefix
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [[capabilities]]
            name = "a.b"
            description = "d"
            version = "0.1.0"
            api = "v1/echo"
            """,
            "API path prefix",
        ),
        # required must be a bool
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [[capabilities]]
            name = "a.b"
            description = "d"
            version = "0.1.0"
            api = "/v1/b"
            required = "yes"
            """,
            "required",
        ),
        # ui menu entry missing
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [[capabilities]]
            name = "a.b"
            description = "d"
            version = "0.1.0"
            api = "/v1/b"
            [capabilities.ui]
            menu = [{ label = "Broken" }]
            """,
            "entry",
        ),
    ],
)
def test_service_toml_rejects_bad_declarations(tmp_path, body, match):
    path = write(tmp_path, "service.toml", body)
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)


def test_service_toml_missing_file_raises_declaration_error(tmp_path):
    with pytest.raises(ServiceDeclarationError, match="not found"):
        load_service_toml(tmp_path / "service.toml")


# ---------------------------------------------------------- implementation.toml


def valid_model_impl_toml() -> str:
    return """\
    capability = "llm.model"

    # Top-level keys precede any `[table]` header — in TOML everything after
    # a table header belongs to that table.
    source = "local-weights"
    license = "Apache-2.0"
    privacy-tier = "local"

    [identity]
    name = "qwen3-4b"
    version = "2026-05"
    description = "A 4B LLM."

    [links]
    release = "https://huggingface.co/Qwen/Qwen3-4B"

    [contents.model]
    type = "model"
    huggingface = "https://huggingface.co/Qwen/Qwen3-4B"
    artificial-analysis = "qwen-3-4b"

    [contents.model.facts]
    disk-gb = 2.5
    parameters-active = 4.0
    parameters-total = 4.0
    vram-at-load-gb = 3.2
    kv-cache-per-token = 0.00012
    quantization = "Q4_K_M"

    [requirements]
    disk-gb = 2.7
    ram-gb = 0.5
    vram-gb = 3.2

    [requirements.cpu]
    AVX2 = true

    [requirements.gpu]
    tensor-core = false

    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """


def test_model_implementation_declares_contents_facts_and_dependency(tmp_path):
    impl = load_implementation_toml(
        write(tmp_path, "implementation.toml", valid_model_impl_toml())
    )
    assert isinstance(impl, Implementation)
    assert impl.capability == "llm.model"
    assert (impl.name, impl.version, impl.description) == ("qwen3-4b", "2026-05", "A 4B LLM.")
    assert impl.source == "local-weights"
    assert impl.license == "Apache-2.0"
    assert impl.privacy_tier == "local"
    assert impl.links["release"].startswith("https://")

    # [contents] replaces kind — a named model part with per-type facts
    assert len(impl.contents) == 1
    part = impl.contents[0]
    assert isinstance(part, ContentPart)
    assert (part.name, part.type) == ("model", "model")
    assert part.huggingface == "https://huggingface.co/Qwen/Qwen3-4B"
    assert part.artificial_analysis == "qwen-3-4b"
    assert part.facts["disk-gb"] == 2.5
    assert part.facts["quantization"] == "Q4_K_M"

    # [requirements] — install AND run
    assert impl.requirements.disk_gb == 2.7
    assert impl.requirements.ram_gb == 0.5
    assert impl.requirements.vram_gb == 3.2
    assert impl.requirements.cpu_technologies == ("AVX2",)
    assert impl.requirements.gpu_technologies == ()  # tensor-core = false → not required

    # generic dependency: on a capability (any implementation satisfies)
    dep = impl.dependencies[0]
    assert isinstance(dep, Dependency)
    assert dep.capability == "llm.engine"
    assert dep.implementation is None
    assert dep.min_version == "0.5.0"
    assert dep.features == ("vision",)


def test_dependency_on_a_specific_implementation(tmp_path):
    body = valid_model_impl_toml().replace(
        """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
        """\
    [[dependencies]]
    implementation = "ollama"
    min-version = "0.12.0"
    """,
    )
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    dep = impl.dependencies[0]
    assert dep.capability is None
    assert dep.implementation == "ollama"
    assert dep.min_version == "0.12.0"


def _swap_contents(text: str, *, old: str, new: str) -> str:
    """Replace a `[contents]` block — fails loudly if the fixture drifted.

    `old`/`new` are given at the fixture's own indentation (the fixture
    text is indented; `write()` dedents it when the file is written).
    """
    assert old in text, "fixture drift: contents block not found"
    return text.replace(old, new)


def _drop_dependencies(text: str) -> str:
    dep_block = """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """
    assert dep_block in text, "fixture drift: dependencies block not found"
    return text.replace(dep_block, "")


def test_engine_implementation_declares_github_url(tmp_path):
    body = _swap_contents(
        valid_model_impl_toml(),
        old="""\
    [contents.model]
    type = "model"
    huggingface = "https://huggingface.co/Qwen/Qwen3-4B"
    artificial-analysis = "qwen-3-4b"

    [contents.model.facts]
    disk-gb = 2.5
    parameters-active = 4.0
    parameters-total = 4.0
    vram-at-load-gb = 3.2
    kv-cache-per-token = 0.00012
    quantization = "Q4_K_M\"""",
        new="""\
    [contents.ollama]
    type = "inference-engine"
    github = "https://github.com/ollama/ollama\"""",
    ).replace('capability = "llm.model"', 'capability = "llm.engine"')
    body = _drop_dependencies(body)
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    assert impl.contents[0].type == "inference-engine"
    assert impl.contents[0].github == "https://github.com/ollama/ollama"
    assert impl.dependencies == ()


def test_storage_space_part_proposes_a_quota(tmp_path):
    body = _swap_contents(
        valid_model_impl_toml(),
        old="""\
    [contents.model]
    type = "model"
    huggingface = "https://huggingface.co/Qwen/Qwen3-4B"
    artificial-analysis = "qwen-3-4b"

    [contents.model.facts]
    disk-gb = 2.5
    parameters-active = 4.0
    parameters-total = 4.0
    vram-at-load-gb = 3.2
    kv-cache-per-token = 0.00012
    quantization = "Q4_K_M\"""",
        new="""\
    [contents.corpus]
    type = "storage-space"
    default-quota-gb = 20.0""",
    ).replace('capability = "llm.model"', 'capability = "document.store"')
    body = _drop_dependencies(body)
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    part = impl.contents[0]
    assert part.type == "storage-space"
    assert part.facts["default-quota-gb"] == 20.0


def test_an_implementation_may_bundle_several_content_parts(tmp_path):
    body = valid_model_impl_toml().replace(
        """\
    [requirements]
    disk-gb = 2.7
    """,
        """\
    [contents.cache]
    type = "storage-space"
    default-quota-gb = 1.0

    [requirements]
    disk-gb = 2.7
    """,
    )
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    assert [p.type for p in impl.contents] == ["model", "storage-space"]


@pytest.mark.parametrize(
    "mutation,match",
    [
        # retired keys are loud errors, not silently ignored
        (
            lambda s: s.replace(
                'privacy-tier = "local"', 'privacy-tier = "local"\nkind = "model"'
            ),
            "kind.*superseded",
        ),
        (lambda s: s + "\n[ranks]\naccuracy = 1\n", "ranks.*removed"),
        # unknown top-level key (typo) fails loudly — closed shape
        (
            lambda s: s.replace('license = "Apache-2.0"', 'licens = "Apache-2.0"'),
            "unknown top-level key",
        ),
        # capability reference must follow the declared grammar
        (
            lambda s: s.replace('capability = "llm.model"', 'capability = "LLM.Model"'),
            "lowercase dotted",
        ),
        (
            lambda s: s.replace(
                """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
                """\
    [engine-dependency]
    capability = "llm.engine"
    min_version = "0.5.0"
    """,
            ),
            "engine-dependency.*superseded",
        ),
        # bad source / privacy / license
        (
            lambda s: s.replace('source = "local-weights"', 'source = "downloaded"'),
            "source",
        ),
        (lambda s: s.replace('license = "Apache-2.0"', 'license = ""'), "license"),
        (
            lambda s: s.replace('privacy-tier = "local"', 'privacy-tier = "private"'),
            "privacy-tier",
        ),
        # contents shape
        (
            lambda s: s.replace('    [contents.model]\n    type = "model"', '    [contents.model]\n    type = "widget"'),
            "type.*must be one of",
        ),
        (
            lambda s: s.replace('artificial-analysis = "qwen-3-4b"', "artificial-analysis = 42"),
            "artificial-analysis",
        ),
        (
            lambda s: s.replace(
                'huggingface = "https://huggingface.co/Qwen/Qwen3-4B"', 'huggingface = ""'
            ),
            "huggingface",
        ),
        # no quality claims in model facts
        (
            lambda s: s.replace(
                "[contents.model.facts]\n    disk-gb = 2.5",
                "[contents.model.facts]\n    elo-score = 1200\n    disk-gb = 2.5",
            ),
            "objective model fact",
        ),
        # requirements shape
        (
            lambda s: s.replace("[requirements]\n    disk-gb = 2.7", "[requirements]\n    disk-gb = -2.7"),
            "non-negative",
        ),
        (
            lambda s: s.replace("[requirements.cpu]\n    AVX2 = true", "[requirements.cpu]\n    AVX2 = 1"),
            "booleans",
        ),
        # dependency shape: exactly one of capability/implementation
        (
            lambda s: s.replace(
                """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
                """\
    [[dependencies]]
    capability = "llm.engine"
    implementation = "ollama"
    """,
            ),
            "exactly one",
        ),
    ],
)
def test_implementation_toml_rejects_bad_declarations(tmp_path, mutation, match):
    body = mutation(valid_model_impl_toml())
    with pytest.raises(ImplementationDeclarationError, match=match):
        load_implementation_toml(write(tmp_path, "implementation.toml", body))


def test_implementation_toml_missing_file_raises(tmp_path):
    with pytest.raises(ImplementationDeclarationError, match="not found"):
        load_implementation_toml(tmp_path / "implementation.toml")


# ------------------------------------------- read-time computation (ADR-0031 §5)


def make_impl(
    name: str,
    *,
    source: str = "local-weights",
    disk: float = 2.0,
    slug: str | None = None,
    cpu_tech: tuple[str, ...] = (),
    gpu_tech: tuple[str, ...] = (),
) -> Implementation:
    """A parsed `Implementation` (what `load_implementation_toml` returns)."""
    return Implementation(
        capability="llm.model",
        name=name,
        version="1",
        description=name,
        source=source,
        license="Apache-2.0",
        privacy_tier="local",
        links={},
        contents=(
            ContentPart(
                name="model",
                type="model",
                huggingface="https://huggingface.co/x" if slug else None,
                artificial_analysis=slug,
            ),
        ),
        requirements=Requirements(
            disk_gb=disk,
            ram_gb=0.5,
            cpu_technologies=cpu_tech,
            gpu_technologies=gpu_tech,
        ),
        dependencies=(),
    )


HARDWARE = {
    "disk_free_gb": 10.0,
    "technologies": {"AVX2": True, "AVX512": False},
}


def test_supported_gates_on_technologies_and_disk_fit():
    impls = [
        make_impl("fitting", cpu_tech=("AVX2",), disk=2.0),
        make_impl("missing-tech", cpu_tech=("AVX512",), disk=1.0),
        make_impl("too-big", disk=10.5),
    ]
    assert [i.name for i in compute_supported(impls, HARDWARE)] == ["fitting"]


def test_gpu_technologies_are_hard_gates_too():
    impls = [
        make_impl("needs-cuda", gpu_tech=("cuda-sm90",)),
        make_impl("no-gpu-needed"),
    ]
    assert [i.name for i in compute_supported(impls, HARDWARE)] == ["no-gpu-needed"]


def test_unknown_hardware_fails_the_hard_gate_never_silently_passes():
    """ADR-0005 §4: quantity fit is the hard gate — a machine with unknown
    quantities supports only cloud implementations."""
    impls = [make_impl("local m"), make_impl("c", source="cloud:nous/glm")]
    assert compute_supported(impls, {}) == [impls[1]]
    assert compute_supported(impls, {"disk_free_gb": None, "technologies": {}}) == [impls[1]]
    assert compute_supported(impls, {"disk_free_gb": "10", "technologies": {}}) == [impls[1]]


def test_cloud_implementations_do_not_consume_this_machine():
    impls = [make_impl("cloud one", source="cloud:nous/glm", disk=999.0)]
    # disk_free 10 GB — a cloud ref never consumes this machine's disk
    assert [i.name for i in compute_supported(impls, HARDWARE)] == ["cloud one"]


def test_supported_and_ordering_chain_off_the_parsed_declaration():
    """The read-time path is loader → compute → order (no dict bridge)."""
    impls = [make_impl("m1", disk=2.0, slug="m1"), make_impl("m2", disk=9.0, slug="m2")]
    supported = compute_supported(impls, HARDWARE)
    ordered = order_supported(supported, "size", metrics={})
    assert [i.name for i in ordered] == ["m1", "m2"]


def test_ordering_by_dynamic_metrics_with_unknown_last():
    """ADR-0031 §5: the goal orders by externally-supplied dynamic metrics;
    unknown values (offline, unfound on AA, no slug) order last."""
    impls = [
        make_impl("best", slug="best"),
        make_impl("mid", slug="mid"),
        make_impl("no-slug"),
        make_impl("unfound", slug="unfound"),
    ]
    metrics = {
        "best": {"performance": 1400, "speed": 120, "cost": 5.0},
        "mid": {"performance": 1200, "speed": 90, "cost": 1.0},
        # "unfound" absent — unknown
    }
    assert [i.name for i in order_supported(impls, "performance", metrics)] == [
        "best", "mid", "no-slug", "unfound",
    ]
    assert [i.name for i in order_supported(impls, "speed", metrics)] == [
        "best", "mid", "no-slug", "unfound",
    ]
    assert [i.name for i in order_supported(impls, "cost", metrics)] == [
        "mid", "best", "no-slug", "unfound",
    ]


def test_performance_per_dollar_replaces_balanced():
    """performance ÷ cost; unknown on either side → last."""
    impls = [
        make_impl("premium", slug="premium"),
        make_impl("value", slug="value"),
        make_impl("unknown-cost", slug="uc"),
    ]
    metrics = {
        "premium": {"performance": 1400, "cost": 5.0},   # 280 / $
        "value": {"performance": 1200, "cost": 1.0},     # 1200 / $
        "uc": {"performance": 1300},                      # cost unknown
    }
    assert [i.name for i in order_supported(impls, "performance-per-dollar", metrics)] == [
        "value", "premium", "unknown-cost",
    ]


def test_size_orders_by_the_declared_disk_not_dynamic_metrics():
    impls = [
        make_impl("big", disk=9.0, slug="big"),
        make_impl("small", disk=1.0, slug="small"),
    ]
    # dynamic metrics irrelevant for size
    assert [i.name for i in order_supported(impls, "size", metrics={})] == ["small", "big"]


def test_no_goal_no_hidden_ranking():
    impls = [make_impl("b", disk=9.0), make_impl("a", disk=2.0)]
    assert [i.name for i in order_supported(impls, None, metrics={})] == ["b", "a"]


def test_unknown_goal_is_rejected():
    with pytest.raises(ValueError, match="model-selection goal"):
        validate_goal("balanced")


def test_offline_fallback_all_unknown_orders_by_name_last_bucket():
    """Offline → all values unknown → the ranking is the unknown bucket,
    name-tie-broken (deterministic, honest)."""
    impls = [make_impl("b", slug="b"), make_impl("a", slug="a")]
    ordered = order_supported(impls, "performance", metrics={})
    assert [i.name for i in ordered] == ["a", "b"]


def test_declarations_carry_no_quality_claims_or_stored_flags():
    text = valid_model_impl_toml().lower()
    for banned in ("[ranks]", "benchmark-score", "supported =", "recommended =", "elo-score"):
        assert banned not in text