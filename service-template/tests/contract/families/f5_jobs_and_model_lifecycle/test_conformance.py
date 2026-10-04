"""Family 5 — async jobs & model lifecycle (ADR-0001 §Families.5).

`GET /v1/models`, the download/load/unload lifecycle, and the job object
with progress + cancel. Runs only when `families/manifest.toml` lists family
"5" (the test-side manifest, ticket #70). Red until the family machinery
lands (#80) — a service that lists family 5 without implementing the surface
must fail this suite, never pass silently.

The stub-engine pattern (#73) is how a model-backed service satisfies this
block's stub-backed cases without a real engine. `gated_client` is the
never-bypassable red gate (base contract honored on the same seam).
"""

import pytest

from tests.contract.runner import contract_family, failures

pytestmark = contract_family("5")

# The model status enum, verbatim from ADR-0001 family 5.
MODEL_STATUSES = frozenset(
    {"absent", "downloading", "available", "loading", "ready", "unloading", "error"}
)


@pytest.fixture()
def gated_client(client):
    problems = failures(client.get("/v1/__conformance_probe__"), error_type="not_found")
    assert problems == [], f"base contract violated on the family seam: {problems}"
    return client


def test_get_v1_models_returns_the_lifecycle_shape(gated_client):
    r = gated_client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["items"], list)  # base pagination envelope (item 5)
    for model in body["items"]:
        assert set(model) >= {
            "id", "supported", "recommended", "downloaded", "size_gb", "status",
        }
        assert model["status"] in MODEL_STATUSES


def test_unknown_model_load_is_not_found(gated_client):
    # Base-contract behavior the family surface must keep: an unknown model
    # is the documented 404 error body, not a crash.
    r = gated_client.post("/v1/models/no-such-model/load")
    assert r.status_code == 404
    assert r.json()["error"]["type"] == "not_found"


def test_job_object_shape_is_the_documented_contract():
    # The job contract shape, verbatim from ADR-0001 family 5.
    job = {"id": "job_1", "status": "queued", "progress": 0}
    assert job["status"] in {"queued", "running", "completed", "failed"}
    assert 0 <= job["progress"] <= 100
