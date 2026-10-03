"""Declaration-surface tests (ticket #74; ADR-0002 §5, ADR-0018 §8, ADR-0027).

The declaration surface is **data** — tests assert the parsed shape and the
validation contract (a bad declaration fails a load with a precise error,
never a syntax crash at request time), plus the ADR-0005 read-time rule
that `supported`/`recommended` are computed and never stored.
"""

from __future__ import annotations

import textwrap

import pytest

from contract.declaration import (
    DECLARED_FAMILIES,
    Implementation,
    ImplementationDeclarationError,
    ResourceProfile,
    Service,
    ServiceDeclarationError,
    compute_recommended,
    compute_supported,
    load_implementation_toml,
    load_service_toml,
    validate_goal,
)


def write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(content))
    return path


# ---------------------------------------------------------------- service.toml


def test_template_service_toml_loads_with_the_declared_shape(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "template-service"
        version = "0.1.0"
        description = "The service template — copy-to-start skeleton."

        families = []

        capabilities = []

        [ui]
        nav = []
        """,
    )
    svc = load_service_toml(path)
    assert isinstance(svc, Service)
    assert svc.name == "template-service"
    assert svc.version == "0.1.0"
    assert svc.description == "The service template — copy-to-start skeleton."
    assert svc.families == ()
    assert svc.capabilities == ()
    assert svc.nav == ()


def test_service_toml_declares_families_capabilities_and_nav(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "template-service"
        version = "0.1.0"
        description = "d"

        # ADR-0001's nine family names
        families = ["llm-inference", "jobs-model-lifecycle"]

        capabilities = ["canary.echo"]

        [ui]
        nav = [
            { label = "Canary", target = "canary" },
            { label = "Docs", target = "docs.how-to-use" },
        ]
        """,
    )
    svc = load_service_toml(path)
    assert svc.families == ("llm-inference", "jobs-model-lifecycle")
    assert svc.capabilities == ("canary.echo",)
    assert svc.nav == (
        {"label": "Canary", "target": "canary"},
        {"label": "Docs", "target": "docs.how-to-use"},
    )


def test_nine_family_names_are_the_adr_0001_set():
    assert DECLARED_FAMILIES == (
        "llm-inference",
        "model-inference",
        "tool-services",
        "realtime",
        "jobs-model-lifecycle",
        "batch",
        "uploads",
        "webhooks",
        "authoring-management",
    )


@pytest.mark.parametrize(
    "body",
    [
        # unknown family name
        """
        name = "svc"
        version = "1.0.0"
        description = "d"
        families = ["llms"]
        capabilities = []
        [ui]
        nav = []
        """,
        # duplicate family
        """
        name = "svc"
        version = "1.0.0"
        description = "d"
        families = ["batch", "batch"]
        capabilities = []
        [ui]
        nav = []
        """,
        # missing description
        """
        name = "svc"
        version = "1.0.0"
        families = []
        capabilities = []
        [ui]
        nav = []
        """,
        # empty name
        """
        name = ""
        version = "1.0.0"
        description = "d"
        families = []
        capabilities = []
        [ui]
        nav = []
        """,
        # nav entry missing target
        """
        name = "svc"
        version = "1.0.0"
        description = "d"
        families = []
        capabilities = []
        [ui]
        nav = [{ label = "Broken" }]
        """,
        # capability name not a lowercase dotted identifier
        """
        name = "svc"
        version = "1.0.0"
        description = "d"
        families = []
        capabilities = ["Canary.Echo"]
        [ui]
        nav = []
        """,
    ],
)
def test_service_toml_rejects_bad_declarations(tmp_path, body):
    path = write(tmp_path, "service.toml", body)
    with pytest.raises(ServiceDeclarationError):
        load_service_toml(path)


def test_service_toml_missing_file_raises_declaration_error(tmp_path):
    with pytest.raises(ServiceDeclarationError, match="not found"):
        load_service_toml(tmp_path / "service.toml")


# ---------------------------------------------------------- implementation.toml


def valid_model_impl_toml() -> str:
    return """\
    kind = "model"
    capability = "llm.model"

    # identity, source, license are top-level keys — they precede any `[table]`
    # header, because in TOML everything after a table header belongs to it.
    source = "local-weights"
    license = "Apache-2.0"
    privacy-tier = "local"

    [identity]
    name = "qwen3-4b"
    version = "2026-05"
    description = "A 4B LLM."

    [links]
    release = "https://example.com/release"
    repo = "https://example.com/repo"
    license = "https://example.com/license"
    evaluations = "https://example.com/eval"

    [sizes]
    download_gb = 2.5
    disk_gb = 2.7

    [resource-profile]
    disk_gb = 2.7
    [resource-profile.technologies]
    AVX2 = true
    [resource-profile.variables.context_length]
    min = 512
    max = 32768
    [resource-profile.variables.batch]
    min = 1
    max = 8
    [resource-profile.formula]
    ram_gb = "weights_gb + context_length * kv_per_token_gb"

    [max-capacity]
    context_length = 32768
    batch = 8

    [ranks]
    accuracy = 2
    speed = 3

    [modalities]
    input = ["text"]
    output = ["text"]

    [engine-dependency]
    capability = "llm.engine"
    min_version = "0.5.0"
    features = ["vision"]
    """


def test_model_implementation_toml_declares_every_adr_0027_field(tmp_path):
    path = write(tmp_path, "implementation.toml", valid_model_impl_toml())
    impl = load_implementation_toml(path)
    assert isinstance(impl, Implementation)
    assert (impl.kind, impl.capability) == ("model", "llm.model")
    assert (impl.name, impl.version, impl.description) == (
        "qwen3-4b",
        "2026-05",
        "A 4B LLM.",
    )
    assert impl.source == "local-weights"
    assert impl.license == "Apache-2.0"
    assert impl.links["release"].startswith("https://")
    assert impl.sizes == {"download_gb": 2.5, "disk_gb": 2.7}
    assert impl.resource_profile.disk_gb == 2.7
    assert impl.resource_profile.technologies == {"AVX2": True}
    assert impl.resource_profile.variables["context_length"] == {"min": 512, "max": 32768}
    assert impl.resource_profile.formula == {
        "ram_gb": "weights_gb + context_length * kv_per_token_gb"
    }
    assert impl.max_capacity == {"context_length": 32768, "batch": 8}
    assert impl.ranks == {"accuracy": 2, "speed": 3}
    assert impl.modalities == {"input": ["text"], "output": ["text"]}
    assert impl.privacy_tier == "local"
    assert impl.engine_dependency is not None
    assert impl.engine_dependency.capability == "llm.engine"
    assert impl.engine_dependency.min_version == "0.5.0"
    assert impl.engine_dependency.features == ("vision",)


def test_cloud_model_declares_the_gateway_engine(tmp_path):
    path = write(
        tmp_path,
        "implementation.toml",
        valid_model_impl_toml().replace(
            'source = "local-weights"', 'source = "cloud:nous-portal/glm"'
        ).replace('capability = "llm.engine"', 'capability = "cloud-gateway.engine"'),
    )
    impl = load_implementation_toml(path)
    assert impl.source == "cloud:nous-portal/glm"
    assert impl.engine_dependency.capability == "cloud-gateway.engine"


def test_engine_implementation_has_no_engine_dependency(tmp_path):
    path = write(
        tmp_path,
        "implementation.toml",
        valid_model_impl_toml()
        .replace('kind = "model"', 'kind = "engine"')
        .replace('capability = "llm.model"', 'capability = "llm.engine"')
        .replace(
            """
    [engine-dependency]
    capability = "llm.engine"
    min_version = "0.5.0"
    features = ["vision"]
    """,
            "\n",
        ),
    )
    impl = load_implementation_toml(path)
    assert impl.engine_dependency is None


def test_model_without_engine_dependency_is_rejected(tmp_path):
    body = valid_model_impl_toml().replace(
        """
    [engine-dependency]
    capability = "llm.engine"
    min_version = "0.5.0"
    features = ["vision"]
    """,
        "",
    )
    with pytest.raises(ImplementationDeclarationError, match="engine-dependency"):
        load_implementation_toml(write(tmp_path, "implementation.toml", body))


def test_local_model_cannot_depend_on_the_cloud_gateway(tmp_path):
    body = valid_model_impl_toml().replace(
        'capability = "llm.engine"', 'capability = "cloud-gateway.engine"'
    )
    with pytest.raises(ImplementationDeclarationError, match="cloud-gateway"):
        load_implementation_toml(write(tmp_path, "implementation.toml", body))


def test_non_model_kind_cannot_declare_an_engine_dependency(tmp_path):
    body = valid_model_impl_toml().replace('kind = "model"', 'kind = "engine"')
    with pytest.raises(ImplementationDeclarationError, match="model implementations only"):
        load_implementation_toml(write(tmp_path, "implementation.toml", body))


def test_no_supported_or_recommended_keys_are_stored(tmp_path):
    """The read-time rule (ADR-0002 §5): the declaration carries only factual
    metadata — `supported`/`recommended` live in nothing on disk."""
    text = valid_model_impl_toml()
    assert "supported" not in text
    assert "recommended" not in text


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda s: s.replace('kind = "model"', 'kind = "widget"'), "kind"),
        (
            lambda s: s.replace('source = "local-weights"', 'source = "downloaded"'),
            "source",
        ),
        (lambda s: s.replace('license = "Apache-2.0"', 'license = ""'), "license"),
        (
            lambda s: s.replace("privacy-tier = \"local\"", "privacy-tier = \"private\""),
            "privacy-tier",
        ),
        (
            lambda s: s.replace("[ranks]\n    accuracy = 2\n    speed = 3", "[ranks]\n    cost = 1"),
            "rank",
        ),
        (
            lambda s: s.replace("[sizes]\n    download_gb = 2.5", "[sizes]\n    download_gb = -1"),
            "download_gb",
        ),
        (
            lambda s: s.replace(
                "[resource-profile.variables.batch]\n    min = 1\n    max = 8",
                "[resource-profile.variables.batch]\n    min = 1",
            ),
            "min.*max",
        ),
        (
            lambda s: s.replace(
                '[resource-profile.formula]\n    ram_gb = ', "[resource-profile.formula]\n    watts = "
            ),
            "ram_gb",
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


# ------------------------------------------------- read-time computation (ADR-0005)


def make_impl(
    name: str,
    *,
    source: str = "local-weights",
    disk: float = 2.0,
    ranks: dict | None = None,
    tech: dict | None = None,
) -> Implementation:
    """A parsed `Implementation` (what `load_implementation_toml` returns)."""
    return Implementation(
        kind="model" if not source.startswith("cloud:") else "model",
        capability="llm.model",
        name=name,
        version="1",
        description=name,
        source=source,
        license="Apache-2.0",
        links={},
        sizes={"download_gb": disk, "disk_gb": disk},
        resource_profile=ResourceProfile(disk_gb=disk, technologies=tech or {}),
        max_capacity={},
        ranks=ranks or {},
        modalities={},
        privacy_tier="local",
        engine_dependency=None,
    )


HARDWARE = {
    "disk_free_gb": 10.0,
    "technologies": {"AVX2": True, "AVX512": False},
}


def test_supported_gates_on_technologies_and_disk_fit():
    impls = [
        make_impl("fitting", tech={"AVX2": True}, disk=2.0),
        make_impl("missing-tech", tech={"AVX512": True}, disk=1.0),
        make_impl("too-big", disk=10.5),
    ]
    assert [i.name for i in compute_supported(impls, HARDWARE)] == ["fitting"]


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


def test_supported_and_recommended_chain_off_the_parsed_declaration():
    """The read-time path is loader → compute (no dict bridge): parsed
    declarations feed the hardware gate directly."""
    impls = [make_impl("m1", disk=2.0), make_impl("m2", disk=9.0)]
    supported = compute_supported(impls, HARDWARE)
    rec = compute_recommended(supported, "size")
    assert rec is not None and rec.name == "m1"


def test_recommended_is_computed_per_goal_at_read_time():
    impls = [
        make_impl("large-accurate", ranks={"accuracy": 1, "speed": 4}, disk=9.0),
        make_impl("small-fast", ranks={"accuracy": 4, "speed": 1}, disk=2.0),
        make_impl("middle", ranks={"accuracy": 2, "speed": 2}, disk=4.0),
    ]
    supported = compute_supported(impls, HARDWARE)
    assert compute_recommended(supported, "accuracy").name == "large-accurate"
    assert compute_recommended(supported, "speed").name == "small-fast"
    assert compute_recommended(supported, "size").name == "small-fast"
    # balanced: mean of the ranks → `middle` (2.0) beats large-accurate (2.5)
    # and small-fast (2.5); disk is only the tie-breaker.
    assert compute_recommended(supported, "balanced").name == "middle"


def test_no_goal_no_recommendation():
    assert compute_recommended([make_impl("m")], None) is None


def test_unknown_goal_is_rejected():
    with pytest.raises(ValueError, match="model-selection goal"):
        validate_goal("cheapest")


def test_recommendation_never_reads_stored_flags():
    """The computation inputs are the declared facts (ranks/disk) — there are
    no stored flags on the dataclass at all (a `recommended` field would not
    even exist to read)."""
    rec = compute_recommended([make_impl("m", ranks={"accuracy": 1})], "accuracy")
    assert rec is not None and rec.name == "m"
    assert not hasattr(rec, "recommended")
    assert not hasattr(rec, "supported")
