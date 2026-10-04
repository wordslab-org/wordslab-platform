"""The stub-factory's own conformance (ticket #70 acceptance: "the
stub-factory produces the documented stub shapes for base contract
fixtures") — every stub exercised over the real HTTP seam (the one seam,
spec #46 §Testing Decisions), never against internals.

The stub shapes are documented in `tests/support/stubs.py`; the independent
source of truth for the *contract* shapes is ADR-0001 (cited per assertion).
"""

import pytest

from tests.support.stubs import (
    StubCollaborator,
    stub_api_key,
    stub_401_violations,
    stub_health_payload,
    stub_health_violations,
)
from tests.support.test_server import InProcessService


# --- stub Bearer key (base item 2) ------------------------------------------


def test_stub_api_keys_are_unique_per_call():
    first, second = stub_api_key(), stub_api_key()
    assert first != second
    assert first.startswith("sk-stub-")


def test_stub_api_key_authenticates_only_itself_over_the_seam():
    key = stub_api_key()
    svc = InProcessService(api_keys=[key])
    with svc.client as c:
        # auth passed → the failure is the missing route's 404, not 401
        passed = c.get("/v1/things", headers={"Authorization": f"Bearer {key}"})
        rejected = c.get("/v1/things", headers={"Authorization": "Bearer sk-other"})
    assert passed.status_code == 404
    assert rejected.status_code == 401
    svc.close()


# --- expected 401 body (base items 2 + 4) ------------------------------------


def test_the_expected_401_matcher_accepts_the_documented_body():
    svc = InProcessService()
    with svc.client as c:
        r = c.get("/v1/things")  # no key
    assert r.status_code == 401
    assert stub_401_violations(r) == []
    svc.close()


def test_the_expected_401_matcher_rejects_a_non_401_response():
    svc = InProcessService()
    with svc.client as c:
        health = c.get("/health")  # 200 — not a 401
    assert stub_401_violations(health) != []
    svc.close()


def test_the_expected_401_matcher_rejects_a_drifted_error_body():
    # A 401 whose body carries the wrong taxonomy type is a violation.
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def wrong_401(request):
        return JSONResponse(
            {"error": {"type": "not_found", "message": "drifted"}, "request_id": "x"},
            status_code=401,
        )

    svc = InProcessService(
        api_keys=["sk-correct"], extra_routes=[Route("/v1/wrong-401", wrong_401, methods=["GET"])]
    )
    with svc.authorized() as c:
        r = c.get("/v1/wrong-401")
    assert r.status_code == 401
    problems = stub_401_violations(r)
    assert any("authentication_failed" in p for p in problems), problems
    svc.close()


# --- stub /health payload (base item 6) --------------------------------------


def test_the_stub_health_payload_matches_the_documented_shape_over_the_seam():
    payload = stub_health_payload(status="ready", service="template-service", version="0.1.0")
    assert set(payload) == {"status", "service", "version", "resources"}
    assert set(payload["resources"]) == {"cpu", "ram", "disk"}  # no GPU — gpu/vram omitted
    svc = InProcessService(
        service_name="template-service", version="0.1.0", resources=payload["resources"]
    )
    with svc.client as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert stub_health_violations(r, payload) == []
    svc.close()


def test_the_stub_health_matcher_flags_a_drifted_payload():
    svc = InProcessService()  # the template default: empty resources
    with svc.client as c:
        r = c.get("/health")
    assert stub_health_violations(r, stub_health_payload()) != []
    svc.close()


def test_the_stub_health_matcher_flags_a_wrong_status_code():
    # `full` cannot serve → 503; an expected `ready` payload mismatches.
    svc = InProcessService(health_status="full")
    with svc.client as c:
        r = c.get("/health")
    assert r.status_code == 503
    assert stub_health_violations(r, stub_health_payload(status="ready")) != []
    svc.close()


def test_the_stub_health_payload_rejects_an_unknown_status():
    with pytest.raises(ValueError):
        stub_health_payload(status="warp-drive")


# --- stub collaborator endpoint ----------------------------------------------


def _service_with(collab: StubCollaborator) -> InProcessService:
    return InProcessService(api_keys=["sk-correct"], extra_routes=[collab.route])


def test_the_stub_collaborator_serves_and_records_over_the_seam():
    collab = StubCollaborator()
    svc = _service_with(collab)
    with svc.authorized() as c:
        got = c.get("/v1/collaborator", params={"q": "hi"})
        posted = c.post("/v1/collaborator", json={"x": 1})
    assert got.status_code == 200
    assert got.json() == collab.body
    assert posted.status_code == 200
    assert [e["method"] for e in collab.requests] == ["GET", "POST"]
    assert collab.requests[0]["query"] == {"q": "hi"}
    assert collab.requests[1]["payload"] == {"x": 1}
    svc.close()


def test_the_stub_collaborator_is_deterministic():
    collab = StubCollaborator(body={"answer": 42})
    svc = _service_with(collab)
    with svc.authorized() as c:
        first = c.get("/v1/collaborator").json()
        second = c.get("/v1/collaborator").json()
    assert first == second == {"answer": 42}
    svc.close()


def test_the_stub_collaborator_respects_its_declared_methods():
    # A method mismatch is 400 invalid_request — every (status, type) pair is
    # inside the fixed taxonomy (base item 4) — and the stub is not reached.
    collab = StubCollaborator(methods=("GET",))
    svc = _service_with(collab)
    with svc.authorized() as c:
        r = c.post("/v1/collaborator", json={})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    assert not collab.requests
    svc.close()


def test_the_stub_collaborator_requires_a_full_v1_path():
    with pytest.raises(ValueError):
        StubCollaborator(path="/collaborator")
