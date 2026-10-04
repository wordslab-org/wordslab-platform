"""Declaration-surface tests (ticket #74; ADR-0002 §5, ADR-0018 §8,
**ADR-0031 — declaration model v2/v3**).

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
#
# Layout: own properties first, then per-capability documentation sections
# [<service-name>.<capability-name>].


def test_template_service_toml_loads_with_the_v3_shape(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "template-service"
        description = "The service template — copy-to-start skeleton."
        version = "0.1.0"

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


def test_service_toml_declares_full_capability_documentation(tmp_path):
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

        [audio.stt]
        description = "Batch speech-to-text."
        version = "0.1.0"
        api = "/v1/audio/transcriptions"
        api-functions = "POST /v1/audio/transcriptions — transcribes an upload; GET /v1/audio/transcriptions/{id} — fetches one job."
        versions-history = "0.1.0 — initial batch transcription."
        required = true

        [audio.stt.ui]
        description = "A transcription page with drag-and-drop upload."
        versions-history = "0.1.0 — initial page."
        menu = [
            { label = "Transcribe", entry = "/stt" },
            { label = "Dictation", entry = "/dictation" },
        ]

        [audio.tts]
        description = "Batch text-to-speech."
        version = "0.1.0"
        api = "/v1/audio/speech"
        api-functions = "POST /v1/audio/speech — synthesizes speech from text."
        versions-history = "0.1.0 — initial synthesis."

        [audio.tts.ui]
        description = "No dedicated page — invoked from the dictation flow."
        versions-history = "0.1.0 — initial."
        """,
    )
    svc = load_service_toml(path)
    assert len(svc.capabilities) == 2
    stt = svc.capabilities[0]
    assert stt.name == "stt"
    assert stt.api == "/v1/audio/transcriptions"
    assert stt.api_functions.startswith("POST /v1/audio/transcriptions")
    assert stt.versions_history == "0.1.0 — initial batch transcription."
    assert stt.required is True
    assert [(m.label, m.entry) for m in stt.ui_menu] == [
        ("Transcribe", "/stt"),
        ("Dictation", "/dictation"),
    ]
    assert stt.ui_description == "A transcription page with drag-and-drop upload."
    assert stt.ui_versions_history == "0.1.0 — initial page."
    tts = svc.capabilities[1]
    assert tts.required is False  # optional when omitted
    assert tts.ui_menu == ()
    assert tts.ui_description  # UI documentation still required
    assert tts.ui_versions_history


def test_service_toml_rejects_the_retired_families_key(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "svc"
        description = "d"
        version = "1.0.0"
        families = ["llm-inference"]

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1
        """,
    )
    with pytest.raises(ServiceDeclarationError, match="families"):
        load_service_toml(path)


def test_service_toml_rejects_the_retired_capabilities_list(tmp_path):
    """v1's `capabilities` list is superseded by the documentation sections —
    loud, not silently ignored."""
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "svc"
        description = "d"
        version = "1.0.0"
        capabilities = []

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1
        """,
    )
    with pytest.raises(ServiceDeclarationError, match="superseded"):
        load_service_toml(path)


def test_service_toml_rejects_unknown_top_level_keys(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "svc"
        desciption = "typo"
        version = "1.0.0"

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1
        """,
    )
    with pytest.raises(ServiceDeclarationError, match="unknown top-level key"):
        load_service_toml(path)


def test_capability_section_must_be_prefixed_by_the_service_name(tmp_path):
    path = write(
        tmp_path,
        "service.toml",
        """\
        name = "svc"
        description = "d"
        version = "1.0.0"

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1

        [other.cap]
        description = "d"
        version = "0.1.0"
        api = "/v1/cap"
        api-functions = "d"
        versions-history = "d"

        [other.cap.ui]
        description = "d"
        versions-history = "d"
        """,
    )
    with pytest.raises(ServiceDeclarationError, match="the service's own name is the prefix"):
        load_service_toml(path)


@pytest.mark.parametrize(
    "body,match",
    [
        # missing description
        (
            """
            name = "svc"
            version = "1.0.0"
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
            [requirements]
            disk-gb = -1
            ram-gb = 0.1
            """,
            "non-negative",
        ),
    ],
)
def test_service_toml_rejects_bad_own_properties(tmp_path, body, match):
    path = write(tmp_path, "service.toml", body)
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)


def _capability_body(section: str, entry: str) -> str:
    return f"""
        name = "svc"
        description = "d"
        version = "1.0.0"

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.1

        [{section}]
        description = "d"
        version = "0.1.0"
        api = "/v1/a"
        api-functions = "d"
        versions-history = "d"
        {entry}

        [{section}.ui]
        description = "d"
        versions-history = "d"
        """


@pytest.mark.parametrize(
    "body,match",
    [
        # capability name not a lowercase dotted identifier
        (_capability_body("svc.Canary", ""), "lowercase dotted"),
        # capability-level dependencies: loud, not silently dropped
        (
            _capability_body("svc.a", 'dependencies = [{ capability = "svc.b" }]'),
            "implementations declare their dependencies",
        ),
        # unknown key in a capability section
        (_capability_body("svc.a", "rank = 1"), "unknown key"),
        # api must be an entry-point path
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [svc.a]
            description = "d"
            version = "0.1.0"
            api = "v1/echo"
            api-functions = "d"
            versions-history = "d"
            [svc.a.ui]
            description = "d"
            versions-history = "d"
            """,
            "api description",
        ),
        # required must be a bool
        (_capability_body("svc.a", 'required = "yes"'), "required"),
        # ui menu entry missing
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [svc.a]
            description = "d"
            version = "0.1.0"
            api = "/v1/a"
            api-functions = "d"
            versions-history = "d"
            [svc.a.ui]
            description = "d"
            versions-history = "d"
            menu = [{ label = "Broken" }]
            """,
            "entry",
        ),
        # api-functions and versions-history are required documentation
        (
            """
            name = "svc"
            description = "d"
            version = "1.0.0"
            [requirements]
            disk-gb = 0.1
            ram-gb = 0.1
            [svc.a]
            description = "d"
            version = "0.1.0"
            api = "/v1/a"
            [svc.a.ui]
            description = "d"
            versions-history = "d"
            """,
            "api-functions",
        ),
    ],
)
def test_capability_sections_reject_bad_declarations(tmp_path, body, match):
    path = write(tmp_path, "service.toml", body)
    with pytest.raises(ServiceDeclarationError, match=match):
        load_service_toml(path)


def test_service_toml_missing_file_raises_declaration_error(tmp_path):
    with pytest.raises(ServiceDeclarationError, match="not found"):
        load_service_toml(tmp_path / "service.toml")


# ---------------------------------------------------------- implementation.toml
#
# Layout: own properties first, then per-part documentation sections
# [<capability>.<content-part-type>.<content-part-name>] — each type may
# appear several times.


def valid_impl_toml() -> str:
    return """\
    capability = "llm.model"
    license = "Apache-2.0"

    [identity]
    name = "qwen3-4b"
    version = "2026-05"
    description = "A 4B LLM served locally."

    # the implementation's OWN code requirements
    [requirements]
    disk-gb = 0.2
    ram-gb = 0.3

    # a local-model part — the source (weights URL) lives HERE now
    [llm.model.local-model.qwen3-4b]
    description = "The Qwen3 4B weights, quantized Q4_K_M."
    version = "2026-05"
    huggingface = "https://huggingface.co/Qwen/Qwen3-4B"
    artificial-analysis = "qwen-3-4b"

    [llm.model.local-model.qwen3-4b.facts]
    disk-gb = 2.5
    parameters-active = 4.0
    parameters-total = 4.0
    vram-at-load-gb = 3.2
    kv-cache-per-token = 0.00012
    quantization = "Q4_K_M"

    [llm.model.local-model.qwen3-4b.requirements]
    disk-gb = 2.5
    ram-gb = 0.2
    vram-gb = 3.2

    [llm.model.local-model.qwen3-4b.requirements.cpu]
    AVX2 = true

    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """


LOCAL_MODEL_BLOCK = """\
    [llm.model.local-model.qwen3-4b]
    description = "The Qwen3 4B weights, quantized Q4_K_M."
    version = "2026-05"
    huggingface = "https://huggingface.co/Qwen/Qwen3-4B"
    artificial-analysis = "qwen-3-4b"

    [llm.model.local-model.qwen3-4b.facts]
    disk-gb = 2.5
    parameters-active = 4.0
    parameters-total = 4.0
    vram-at-load-gb = 3.2
    kv-cache-per-token = 0.00012
    quantization = "Q4_K_M"

    [llm.model.local-model.qwen3-4b.requirements]
    disk-gb = 2.5
    ram-gb = 0.2
    vram-gb = 3.2

    [llm.model.local-model.qwen3-4b.requirements.cpu]
    AVX2 = true
"""


CLOUD_MODEL_BLOCK = """\
    [llm.model.cloud-model.gpt-5-nano]
    description = "OpenAI's smallest reasoning model, via the cloud gateway."
    version = "2026-08"
    provider = "openai"
    model = "gpt-5-nano"
    artificial-analysis = "gpt-5-nano"
    privacy-tier = "cloud"

    [llm.model.cloud-model.gpt-5-nano.facts]
    parameters-active = 8.0
    parameters-total = 12.0
    quantization = "unknown"
    """


def _swap_local_model(text: str, new: str) -> str:
    """Replace the local-model part block — fails loudly on fixture drift."""
    assert LOCAL_MODEL_BLOCK in text, "fixture drift: local-model block not found"
    return text.replace(LOCAL_MODEL_BLOCK, new)


def test_implementation_own_properties_and_a_local_model_part(tmp_path):
    impl = load_implementation_toml(
        write(tmp_path, "implementation.toml", valid_impl_toml())
    )
    assert isinstance(impl, Implementation)
    assert impl.capability == "llm.model"
    assert (impl.name, impl.version, impl.description) == (
        "qwen3-4b",
        "2026-05",
        "A 4B LLM served locally.",
    )
    assert impl.license == "Apache-2.0"
    assert impl.own_requirements.disk_gb == 0.2
    assert impl.own_requirements.ram_gb == 0.3

    # the part: source/URLs/facts on the part, not the implementation
    assert len(impl.contents) == 1
    part = impl.contents[0]
    assert isinstance(part, ContentPart)
    assert (part.name, part.type) == ("qwen3-4b", "local-model")
    assert part.huggingface == "https://huggingface.co/Qwen/Qwen3-4B"
    assert part.artificial_analysis == "qwen-3-4b"
    assert part.facts["disk-gb"] == 2.5
    assert part.facts["quantization"] == "Q4_K_M"
    assert part.requirements is not None
    assert part.requirements.vram_gb == 3.2
    assert part.requirements.cpu_technologies == ("AVX2",)

    # aggregation: own + parts (sum/union, ADR-0031 §3)
    assert impl.requirements.disk_gb == pytest.approx(0.2 + 2.5)
    assert impl.requirements.ram_gb == pytest.approx(0.3 + 0.2)
    assert impl.requirements.vram_gb == 3.2
    assert impl.requirements.cpu_technologies == ("AVX2",)

    # generic dependency
    dep = impl.dependencies[0]
    assert isinstance(dep, Dependency)
    assert dep.capability == "llm.engine"
    assert dep.implementation is None
    assert dep.min_version == "0.5.0"
    assert dep.features == ("vision",)


def test_dependency_on_a_specific_implementation(tmp_path):
    body = valid_impl_toml().replace(
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


def test_a_type_may_appear_several_times_and_parts_sum(tmp_path):
    """IMPORTANT (maintainer): each content-part type can appear multiple
    times — e.g. an implementation can use several models. Quantities sum
    across every local part; a storage-space part contributes its
    min-quota-gb (its disk requirement — the user's allocation may only
    exceed it)."""
    body = valid_impl_toml().replace(
        """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
        """\
    [llm.model.local-model.qwen3-0_6b]
    description = "A smaller sibling for low-memory machines."
    version = "2026-03"
    huggingface = "https://huggingface.co/Qwen/Qwen3-0.6B"
    artificial-analysis = "qwen-3-0-6b"

    [llm.model.local-model.qwen3-0_6b.facts]
    disk-gb = 0.5
    parameters-active = 0.6
    parameters-total = 0.6
    vram-at-load-gb = 0.6
    kv-cache-per-token = 0.00003
    quantization = "Q4_K_M"

    [llm.model.local-model.qwen3-0_6b.requirements]
    disk-gb = 0.6
    ram-gb = 0.1
    vram-gb = 0.6

    [llm.model.storage-space.cache]
    description = "Prompt/response cache storage."
    version = "0.1.0"
    min-quota-gb = 1.0
    default-quota-gb = 2.0

    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
    )
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    assert [p.type for p in impl.contents] == [
        "local-model",
        "local-model",
        "storage-space",
    ]
    small = impl.contents[1]
    assert small.huggingface == "https://huggingface.co/Qwen/Qwen3-0.6B"
    storage = impl.contents[2]
    assert storage.min_quota_gb == 1.0
    assert storage.default_quota_gb == 2.0
    assert storage.requirements.disk_gb == 1.0  # the minimum IS the part's disk requirement
    # sum across BOTH local-model parts + own + the storage minimum
    assert impl.requirements.disk_gb == pytest.approx(0.2 + 2.5 + 0.6 + 1.0)
    assert impl.requirements.ram_gb == pytest.approx(0.3 + 0.2 + 0.1)
    assert impl.requirements.vram_gb == pytest.approx(3.2 + 0.6)


def test_cloud_parts_carry_privacy_tier_and_no_requirements(tmp_path):
    body = _swap_local_model(valid_impl_toml(), CLOUD_MODEL_BLOCK)
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    part = impl.contents[0]
    assert (part.type, part.name) == ("cloud-model", "gpt-5-nano")
    assert part.provider == "openai"
    assert part.model == "gpt-5-nano"
    assert part.artificial_analysis == "gpt-5-nano"
    assert part.privacy_tier == "cloud"
    assert part.requirements is None  # cloud parts declare no requirements
    # aggregation ignores cloud parts; only the own code remains
    assert impl.requirements.disk_gb == 0.2
    # all-cloud-parts — derivable from the part types (no is_cloud field)
    assert all(p.type == "cloud-model" for p in impl.contents)


def test_a_cloud_service_part(tmp_path):
    body = _swap_local_model(
        valid_impl_toml(),
        """\
    [llm.model.cloud-service.openai-engine]
    description = "OpenAI's chat-completions endpoint via the cloud gateway."
    version = "2026-08"
    provider = "openai"
    service = "chat-completions"
    privacy-tier = "cloud_no_data"

    """ + LOCAL_MODEL_BLOCK,
    )
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    svc_part = impl.contents[0]
    assert (svc_part.type, svc_part.name) == ("cloud-service", "openai-engine")
    assert svc_part.service == "chat-completions"
    assert svc_part.privacy_tier == "cloud_no_data"
    assert svc_part.requirements is None
    # a local-model part is still present — the implementation is not cloud
    assert any(p.type == "local-model" for p in impl.contents)


def test_an_engine_part_declares_github_url(tmp_path):
    body = (
        valid_impl_toml()
        .replace('capability = "llm.model"', 'capability = "llm.engine"')
    )
    body = body.replace(
        LOCAL_MODEL_BLOCK,
        """\
    [llm.engine.inference-engine.ollama]
    description = "The Ollama inference engine."
    version = "0.12.0"
    github = "https://github.com/ollama/ollama"

    [llm.engine.inference-engine.ollama.requirements]
    disk-gb = 1.5
    ram-gb = 0.4
    """,
    ).replace(
        """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
        "",
    )
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    part = impl.contents[0]
    assert (part.type, part.name) == ("inference-engine", "ollama")
    assert part.github == "https://github.com/ollama/ollama"
    assert impl.dependencies == ()
    assert impl.requirements.disk_gb == pytest.approx(0.2 + 1.5)


def test_a_database_part(tmp_path):
    body = (
        valid_impl_toml()
        .replace('capability = "llm.model"', 'capability = "document.store"')
        .replace(
            LOCAL_MODEL_BLOCK,
            """\
    [document.store.database.sqlite-vec]
    description = "SQLite with the sqlite-vec extension for vectors."
    version = "0.1.6"
    github = "https://github.com/asg017/sqlite-vec"

    [document.store.database.sqlite-vec.requirements]
    disk-gb = 0.05
    ram-gb = 0.1
    """,
        )
        .replace(
            """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
            "",
        )
    )
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    part = impl.contents[0]
    assert (part.type, part.name) == ("database", "sqlite-vec")
    assert part.github == "https://github.com/asg017/sqlite-vec"


def test_an_open_source_app_part(tmp_path):
    body = (
        valid_impl_toml()
        .replace('capability = "llm.model"', 'capability = "chat.ui"')
        .replace(
            LOCAL_MODEL_BLOCK,
            """\
    [chat.ui.open-source-app.open-webui]
    description = "The vendored Open WebUI chat surface."
    version = "0.6.0"
    github = "https://github.com/open-webui/open-webui"

    [chat.ui.open-source-app.open-webui.requirements]
    disk-gb = 1.0
    ram-gb = 0.5
    """,
        )
        .replace(
            """\
    [[dependencies]]
    capability = "llm.engine"
    min-version = "0.5.0"
    features = ["vision"]
    """,
            "",
        )
    )
    impl = load_implementation_toml(write(tmp_path, "implementation.toml", body))
    part = impl.contents[0]
    assert (part.type, part.name) == ("open-source-app", "open-webui")
    assert part.github == "https://github.com/open-webui/open-webui"


def _prepend_own_property(text: str, line: str) -> str:
    """Insert a top-level key BEFORE the first `[table]` header — after it,
    TOML would swallow the key into the table (the ordering pitfall)."""
    i = text.index("\n    [")
    return text[:i] + "\n" + line + text[i:]


@pytest.mark.parametrize(
    "mutation,match",
    [
        # retired keys are loud errors, not silently ignored
        (lambda s: _prepend_own_property(s, 'kind = "model"'), "kind.*superseded"),
        (lambda s: _prepend_own_property(s, "[ranks]\naccuracy = 1\n"), "ranks.*removed"),
        (
            lambda s: _prepend_own_property(s, '[engine-dependency]\ncapability = "llm.engine"\n'),
            "engine-dependency.*superseded",
        ),
        # source moved to the parts
        (lambda s: _prepend_own_property(s, 'source = "local-weights"'), "moved under the model parts"),
        # privacy-tier moved to cloud parts
        (lambda s: _prepend_own_property(s, 'privacy-tier = "local"'), "moved to the cloud parts"),
        # stored supported/recommended are loud errors
        (lambda s: _prepend_own_property(s, "supported = true"), "supported.*never stored"),
        (lambda s: _prepend_own_property(s, "recommended = true"), "recommended.*never stored"),
        # the v2 [contents] shape is retired
        (
            lambda s: _prepend_own_property(s, '[contents.model]\ntype = "model"\n'),
            r"`\[contents\]` is superseded",
        ),
        # unknown top-level key (typo) fails loudly
        (
            lambda s: s.replace('license = "Apache-2.0"', 'licens = "Apache-2.0"'),
            "unknown top-level key",
        ),
        # capability reference must follow the declared grammar
        (
            lambda s: s.replace('capability = "llm.model"', 'capability = "LLM.Model"'),
            "lowercase dotted",
        ),
        # part section for a DIFFERENT capability — fails loudly (the shared
        # root `llm` walks into `other` and rejects the unknown type)
        (
            lambda s: _prepend_own_property(
                s, '[llm.other.local-model.x]\ndescription = "d"\nversion = "1"\n'
            ),
            "unknown content-part type",
        ),
        # no part sections at all
        (
            lambda s: s.replace(LOCAL_MODEL_BLOCK, ""),
            "no content-part documentation sections",
        ),
        # unknown part type
        (
            lambda s: s.replace(
                "[llm.model.local-model.qwen3-4b]", "[llm.model.widget.qwen3-4b]"
            ),
            "widget",
        ),
        # model part without the weights URL
        (
            lambda s: s.replace(
                'huggingface = "https://huggingface.co/Qwen/Qwen3-4B"', ""
            ),
            "huggingface.*required",
        ),
        # model part without the AA slug
        (
            lambda s: s.replace('artificial-analysis = "qwen-3-4b"', ""),
            "artificial-analysis.*required",
        ),
        # no quality claims in model facts
        (
            lambda s: s.replace(
                "[llm.model.local-model.qwen3-4b.facts]",
                "[llm.model.local-model.qwen3-4b.facts]\nelo-score = 1200",
            ),
            "objective model fact",
        ),
        # cloud parts declare no requirements
        (
            lambda s: _swap_local_model(
                s,
                """\
    [llm.model.cloud-model.gpt-5-nano]
    description = "d"
    version = "1"
    provider = "openai"
    model = "gpt-5-nano"
    artificial-analysis = "gpt-5-nano"
    privacy-tier = "cloud"

    [llm.model.cloud-model.gpt-5-nano.requirements]
    disk-gb = 1.0
    """,
            ),
            "cloud parts consume no machine",
        ),
        # cloud parts need a privacy tier
        (
            lambda s: _swap_local_model(
                s,
                """\
    [llm.model.cloud-service.openai-engine]
    description = "d"
    version = "1"
    provider = "openai"
    service = "chat-completions"
    """,
            ),
            "privacy-tier.*must be",
        ),
        # a local part may not declare cloud properties
        (
            lambda s: s.replace(
                'artificial-analysis = "qwen-3-4b"',
                'artificial-analysis = "qwen-3-4b"\n    privacy-tier = "local"',
            ),
            "unknown key",
        ),
        # requirements must be non-negative
        (
            lambda s: s.replace(
                "[llm.model.local-model.qwen3-4b.requirements]\n    disk-gb = 2.5",
                "[llm.model.local-model.qwen3-4b.requirements]\n    disk-gb = -2.5",
            ),
            "non-negative",
        ),
        # technologies must be booleans
        (
            lambda s: s.replace(
                "[llm.model.local-model.qwen3-4b.requirements.cpu]\n    AVX2 = true",
                "[llm.model.local-model.qwen3-4b.requirements.cpu]\n    AVX2 = 1",
            ),
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
        # missing identity
        (
            lambda s: s.replace(
                """\
    [identity]
    name = "qwen3-4b"
    version = "2026-05"
    description = "A 4B LLM served locally."

    # the implementation's OWN code requirements
    """,
                """\
    # the implementation's OWN code requirements
    """,
            ),
            "identity",
        ),
        # missing license
        (lambda s: s.replace('license = "Apache-2.0"', 'license = ""'), "license"),
    ],
)
def test_implementation_toml_rejects_bad_declarations(tmp_path, mutation, match):
    body = mutation(valid_impl_toml())
    with pytest.raises(ImplementationDeclarationError, match=match):
        load_implementation_toml(write(tmp_path, "implementation.toml", body))


def test_implementation_toml_missing_file_raises(tmp_path):
    with pytest.raises(ImplementationDeclarationError, match="not found"):
        load_implementation_toml(tmp_path / "implementation.toml")


def test_the_parsed_object_is_the_install_configuration_data(tmp_path):
    """ADR-0031 §3 (maintainer ruling): the implementation-specific install
    function receives a typed python object representing the full contents
    of the toml file — parsed parts included, no re-parsing."""
    impl = load_implementation_toml(
        write(tmp_path, "implementation.toml", valid_impl_toml())
    )
    assert isinstance(impl, Implementation)  # the typed object itself
    assert all(isinstance(p, ContentPart) for p in impl.contents)
    assert all(
        isinstance(r, Requirements) for r in (impl.requirements, impl.own_requirements)
    )
    # every part carries its documentation + its own requirements — the
    # per-part config the install function consumes
    part = impl.contents[0]
    assert part.description and part.version
    assert isinstance(part.requirements, Requirements)


# ------------------------------------------- read-time computation (ADR-0031 §5)


def make_impl(
    name: str,
    *,
    cloud: bool = False,
    disk: float = 2.0,
    ram: float = 0.5,
    vram: float = 0.0,
    slug: str | None = None,
    cpu_tech: tuple[str, ...] = (),
    gpu_tech: tuple[str, ...] = (),
    contents_override: tuple[ContentPart, ...] | None = None,
) -> Implementation:
    """A parsed `Implementation` (what `load_implementation_toml` returns)."""
    part = ContentPart(
        name="m",
        type="cloud-model" if cloud else "local-model",
        description="d",
        version="1",
        huggingface=None if cloud else "https://huggingface.co/x",
        artificial_analysis=slug,
        provider="openai" if cloud else None,
        model="gpt" if cloud else None,
        privacy_tier="cloud" if cloud else None,
    )
    reqs = Requirements(
        disk_gb=disk,
        ram_gb=ram,
        vram_gb=vram,
        cpu_technologies=cpu_tech,
        gpu_technologies=gpu_tech,
    )
    return Implementation(
        capability="llm.model",
        name=name,
        version="1",
        description=name,
        license="Apache-2.0",
        own_requirements=reqs,
        requirements=reqs,
        contents=contents_override if contents_override is not None else (part,),
        dependencies=(),
    )


HARDWARE = {
    "disk_free_gb": 10.0,
    "ram_free_gb": 8.0,
    "vram_free_gb": 8.0,
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


def test_ram_and_vram_fit_are_hard_gates_too():
    """ADR-0005 §4: memory fit when running alone at minimum parameters —
    the declared ram-gb/vram-gb actually gate (not dead weight)."""
    impls = [
        make_impl("fits", disk=1.0),
        make_impl("ram-heavy", disk=1.0, ram=9.0),    # 9.0 > 8.0 free
        make_impl("vram-heavy", disk=1.0, vram=16.0),  # 16.0 > 8.0 free
    ]
    assert [i.name for i in compute_supported(impls, HARDWARE)] == ["fits"]


def test_unknown_hardware_fails_the_hard_gate_never_silently_passes():
    """ADR-0005 §4: quantity fit is the hard gate — a machine with unknown
    quantities supports only cloud implementations."""
    impls = [make_impl("local m"), make_impl("c", cloud=True)]
    assert compute_supported(impls, {}) == [impls[1]]
    assert compute_supported(impls, {"disk_free_gb": None, "technologies": {}}) == [impls[1]]
    assert compute_supported(impls, {"disk_free_gb": "10", "technologies": {}}) == [impls[1]]


def test_cloud_implementations_do_not_consume_this_machine():
    impls = [make_impl("cloud one", cloud=True, disk=999.0)]
    # disk_free 10 GB — a cloud implementation never consumes this machine
    assert [i.name for i in compute_supported(impls, HARDWARE)] == ["cloud one"]


def test_supported_and_ordering_chain_off_the_parsed_declaration():
    """The read-time path is loader → compute → order (no dict bridge)."""
    impls = [
        make_impl("m1", disk=2.0, slug="m1"),
        make_impl("m2", disk=9.0, slug="m2"),
    ]
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
        "value": {"performance": 1200, "cost": 1.0},    # 1200 / $
        "uc": {"performance": 1300},                     # cost unknown
    }
    assert [
        i.name for i in order_supported(impls, "performance-per-dollar", metrics)
    ] == ["value", "premium", "unknown-cost"]


def test_size_orders_by_the_aggregate_declared_disk_not_dynamic_metrics():
    impls = [
        make_impl("big", disk=9.0, slug="big"),
        make_impl("small", disk=1.0, slug="small"),
    ]
    assert [i.name for i in order_supported(impls, "size", metrics={})] == [
        "small", "big",
    ]


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
    text = valid_impl_toml().lower()
    for banned in (
        "[ranks]",
        "benchmark-score",
        "supported =",
        "recommended =",
        "elo-score",
    ):
        assert banned not in text

# ------------------------------------------- spec-review round 2 (closed shapes)



def _impl_load(tmp_path, body: str) -> Implementation:
    return load_implementation_toml(write(tmp_path, "implementation.toml", body))


SERVICE_TOML_STT_UI = """\
        [audio.stt]
        description = "Batch speech-to-text."
        version = "0.1.0"
        api = "/v1/audio/transcriptions"
        api-functions = "POST /v1/audio/transcriptions — transcribes an upload."
        versions-history = "0.1.0 — initial."
        required = true

        [audio.stt.ui]
        description = "A transcription page."
        versions-history = "0.1.0 — initial page."
        menu = [
            { label = "Transcribe", entry = "/stt" },
        ]
        """


def _svc_load(tmp_path, body: str) -> Service:
    return load_service_toml(write(tmp_path, "service.toml", body))


def test_same_part_name_under_two_types_is_legal(tmp_path):
    """'each content-part type can appear multiple times' (maintainer, #74
    comment 5977934074) — a name reused under a DIFFERENT type is two
    distinct sections, not a duplicate."""
    body = valid_impl_toml() + (
        "\n    [llm.model.database.qwen3-4b]\n"
        '    description = "The KV cache database."\n'
        '    version = "1"\n'
        '    github = "https://github.com/x/y"\n'
    )
    impl = _impl_load(tmp_path, body)
    names = {(p.type, p.name) for p in impl.contents}
    assert ("local-model", "qwen3-4b") in names
    assert ("database", "qwen3-4b") in names


def test_identity_rejects_unknown_keys(tmp_path):
    body = valid_impl_toml().replace(
        "    [identity]\n", '    [identity]\n    surprise = "x"\n'
    )
    with pytest.raises(ImplementationDeclarationError, match=r"\[identity\].*unknown key"):
        _impl_load(tmp_path, body)


def test_identity_rejects_stored_flags(tmp_path):
    body = valid_impl_toml().replace(
        "    [identity]\n", "    [identity]\n    supported = true\n"
    )
    with pytest.raises(ImplementationDeclarationError, match="supported.*never stored"):
        _impl_load(tmp_path, body)


def test_dependency_entries_are_closed(tmp_path):
    body = valid_impl_toml().replace(
        '    capability = "llm.engine"\n',
        '    capability = "llm.engine"\n    version = "1.0"\n',
    )
    with pytest.raises(ImplementationDeclarationError, match="dependencies.*unknown key"):
        _impl_load(tmp_path, body)


def test_part_requirements_tables_are_closed(tmp_path):
    body = valid_impl_toml().replace(
        "    [llm.model.local-model.qwen3-4b.requirements]\n",
        "    [llm.model.local-model.qwen3-4b.requirements]\n    recommended = true\n",
    )
    with pytest.raises(ImplementationDeclarationError, match="recommended.*never stored"):
        _impl_load(tmp_path, body)


def test_part_github_must_be_a_github_url(tmp_path):
    body = valid_impl_toml() + (
        "\n    [llm.model.database.qwen3-4b]\n"
        '    description = "The KV cache database."\n'
        '    version = "1"\n'
        '    github = "not-a-url"\n'
    )
    with pytest.raises(ImplementationDeclarationError, match="github repository URL"):
        _impl_load(tmp_path, body)


def test_model_part_huggingface_must_be_a_huggingface_url(tmp_path):
    body = valid_impl_toml().replace(
        '    huggingface = "https://huggingface.co/Qwen/Qwen3-4B"',
        '    huggingface = "x"',
    )
    with pytest.raises(ImplementationDeclarationError, match=r"huggingface.*huggingface\.co"):
        _impl_load(tmp_path, body)


def test_multi_slug_ordering_uses_every_parts_data():
    """A bundled implementation's SECOND model's data must not be silently
    ignored — the ordering value aggregates every AA slug (mean), unknown
    last (ADR-0031 §5)."""
    def bundled(name, slugs):
        parts = tuple(
            ContentPart(
                name=f"m{i}", type="local-model", description="d", version="1",
                artificial_analysis=s,
            )
            for i, s in enumerate(slugs)
        )
        return make_impl(name, slug=None, contents_override=parts)

    a = bundled("a", ["a"])
    b = bundled("b", ["b1", "b2"])
    ordered = order_supported(
        [a, b], "performance",
        metrics={"a": {"performance": 100}, "b1": {"performance": 50}, "b2": {"performance": 150}},
    )
    # a's single 100 vs b's mean(50, 150) = 100 — tie, name-breaker
    assert [i.name for i in ordered] == ["a", "b"]
    # b1 alone would rank below a; the aggregate proves b2's data counted
    ordered2 = order_supported(
        [a, b], "performance",
        metrics={"a": {"performance": 100}, "b1": {"performance": 50}, "b2": {"performance": 200}},
    )
    assert [i.name for i in ordered2] == ["b", "a"]


def test_service_walk_rejects_scalar_under_the_service_root(tmp_path):
    """A scalar key living under the service-name root (a mistyped section
    header, e.g. `[audio] zz = 5`) fails loudly — TOML makes it a dotted
    key `audio.zz` beside the capability sections."""
    body = """\
        name = "audio"
        description = "The platform's voice surface."
        version = "0.1.0"
        audio.zz = 5

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.2

        """ + SERVICE_TOML_STT_UI
    with pytest.raises(ServiceDeclarationError, match="not a table"):
        _svc_load(tmp_path, body)


def test_service_walk_rejects_typoed_capability_section(tmp_path):
    """A section whose keys are ALL typo'd (no capability-section key
    matches) must fail loudly, not vanish as a phantom capability."""
    body = """\
        name = "audio"
        description = "The platform's voice surface."
        version = "0.1.0"

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.2

        """ + SERVICE_TOML_STT_UI + """\
        [audio.tts]
        descrption = "typo"
        """
    with pytest.raises(ServiceDeclarationError, match="no capability documentation keys"):
        _svc_load(tmp_path, body)


def test_menu_hooks_are_closed(tmp_path):
    body = """\
        name = "audio"
        description = "The platform's voice surface."
        version = "0.1.0"

        [requirements]
        disk-gb = 0.1
        ram-gb = 0.2

        """ + SERVICE_TOML_STT_UI.replace(
        '{ label = "Transcribe", entry = "/stt" }',
        '{ label = "Transcribe", entry = "/stt", extra = "junk" }',
    )
    with pytest.raises(ServiceDeclarationError, match="menu.*unknown key"):
        _svc_load(tmp_path, body)


def test_storage_space_minimum_is_required(tmp_path):
    body = valid_impl_toml() + (
        "\n    [llm.model.storage-space.cache]\n"
        '    description = "Cache storage."\n'
        '    version = "0.1.0"\n'
    )
    with pytest.raises(ImplementationDeclarationError, match="min-quota-gb.*is required"):
        _impl_load(tmp_path, body)


def test_storage_space_default_may_not_undercut_the_minimum(tmp_path):
    body = valid_impl_toml() + (
        "\n    [llm.model.storage-space.cache]\n"
        '    description = "Cache storage."\n'
        '    version = "0.1.0"\n'
        "    min-quota-gb = 2.0\n"
        "    default-quota-gb = 1.0\n"
    )
    with pytest.raises(ImplementationDeclarationError, match="may not undercut"):
        _impl_load(tmp_path, body)


def test_storage_space_minimum_counts_in_aggregate_disk(tmp_path):
    body = valid_impl_toml() + (
        "\n    [llm.model.storage-space.cache]\n"
        '    description = "Cache storage."\n'
        '    version = "0.1.0"\n'
        "    min-quota-gb = 3.0\n"
    )
    impl = _impl_load(tmp_path, body)
    storage = impl.contents[-1]
    assert storage.min_quota_gb == 3.0
    assert storage.default_quota_gb is None  # a proposal, optional
    # own 0.2 + local-model 2.5 + storage minimum 3.0
    assert impl.requirements.disk_gb == pytest.approx(0.2 + 2.5 + 3.0)
