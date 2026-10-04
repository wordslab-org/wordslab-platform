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


@pytest.fixture()
def make_service():
    """Builds `InProcessService` variants and closes every one in teardown —
    a failing assert never leaks a service."""
    made = []

    def _make(**kwargs) -> InProcessService:
        svc = InProcessService(**kwargs)
        made.append(svc)
        return svc

    yield _make
    for svc in made:
        svc.close()


# --- stub Bearer key (base item 2) ------------------------------------------


def test_stub_api_keys_are_unique_per_call():
    first, second = stub_api_key(), stub_api_key()
    assert first != second
    assert first.startswith("sk-stub-")


def test_stub_api_key_authenticates_only_itself_over_the_seam(make_service):
    key = stub_api_key()
    svc = make_service(api_keys=[key])
    with svc.client as c:
        # auth passed → the failure is the missing route's 404, not 401
        passed = c.get("/v1/things", headers={"Authorization": f"Bearer {key}"})
        rejected = c.get("/v1/things", headers={"Authorization": "Bearer sk-other"})
    assert passed.status_code == 404
    assert rejected.status_code == 401


# --- expected 401 body (base items 2 + 4) ------------------------------------


def test_the_expected_401_matcher_accepts_the_documented_body(make_service):
    svc = make_service()
    with svc.client as c:
        r = c.get("/v1/things")  # no key
    assert r.status_code == 401
    assert stub_401_violations(r) == []


def test_the_expected_401_matcher_rejects_a_non_401_response(make_service):
    svc = make_service()
    with svc.client as c:
        health = c.get("/health")  # 200 — not a 401
    assert stub_401_violations(health) != []


def test_the_expected_401_matcher_rejects_a_drifted_error_body(make_service):
    # A 401 whose body carries the wrong taxonomy type is a violation.
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def wrong_401(request):
        return JSONResponse(
            {"error": {"type": "not_found", "message": "drifted"}, "request_id": "x"},
            status_code=401,
        )

    svc = make_service(
        api_keys=["sk-correct"],
        extra_routes=[Route("/v1/wrong-401", wrong_401, methods=["GET"])],
    )
    with svc.authorized() as c:
        r = c.get("/v1/wrong-401")
    assert r.status_code == 401
    problems = stub_401_violations(r)
    assert any("authentication_failed" in p for p in problems), problems


def test_the_expected_401_matcher_flags_a_body_without_request_id(make_service):
    # An error body without request_id is a violation (base item 4), not a
    # skip — the drift-detection gap the matchers must never have.
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def bare_401(request):
        return JSONResponse(
            {"error": {"type": "authentication_failed", "message": "no request id"}},
            status_code=401,
        )

    svc = make_service(
        api_keys=["sk-correct"],
        extra_routes=[Route("/v1/bare-401", bare_401, methods=["GET"])],
    )
    with svc.authorized() as c:
        r = c.get("/v1/bare-401")
    problems = stub_401_violations(r)
    assert any("no request_id" in p for p in problems), problems


# --- stub /health payload (base item 6) --------------------------------------


def test_the_stub_health_payload_matches_the_documented_shape_over_the_seam(make_service):
    payload = stub_health_payload(status="ready", service="template-service", version="0.1.0")
    assert set(payload) == {"status", "service", "version", "resources"}
    assert set(payload["resources"]) == {"cpu", "ram", "disk"}  # no GPU — gpu/vram omitted
    svc = make_service(
        service_name="template-service", version="0.1.0", resources=payload["resources"]
    )
    with svc.client as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert stub_health_violations(r, payload) == []


def test_the_stub_health_matcher_flags_a_drifted_payload(make_service):
    svc = make_service()  # the template default: empty resources
    with svc.client as c:
        r = c.get("/health")
    assert stub_health_violations(r, stub_health_payload()) != []


def test_the_stub_health_matcher_flags_a_wrong_status_code(make_service):
    # `full` cannot serve → 503; an expected `ready` payload mismatches.
    svc = make_service(health_status="full")
    with svc.client as c:
        r = c.get("/health")
    assert r.status_code == 503
    assert stub_health_violations(r, stub_health_payload(status="ready")) != []


def test_the_stub_health_payload_rejects_an_unknown_status():
    with pytest.raises(ValueError):
        stub_health_payload(status="warp-drive")


# --- stub collaborator endpoint ----------------------------------------------


def test_the_stub_collaborator_serves_and_records_over_the_seam(make_service):
    collab = StubCollaborator()
    svc = make_service(api_keys=["sk-correct"], extra_routes=[collab.route])
    with svc.authorized() as c:
        got = c.get("/v1/collaborator", params={"q": "hi"})
        posted = c.post("/v1/collaborator", json={"x": 1})
    assert got.status_code == 200
    assert got.json() == collab.body
    assert posted.status_code == 200
    assert [e["method"] for e in collab.requests] == ["GET", "POST"]
    assert collab.requests[0]["query"] == {"q": "hi"}
    assert collab.requests[1]["payload"] == {"x": 1}


def test_the_stub_collaborator_is_deterministic(make_service):
    collab = StubCollaborator(body={"answer": 42})
    svc = make_service(api_keys=["sk-correct"], extra_routes=[collab.route])
    with svc.authorized() as c:
        first = c.get("/v1/collaborator").json()
        second = c.get("/v1/collaborator").json()
    assert first == second == {"answer": 42}


def test_the_stub_collaborator_respects_its_declared_methods(make_service):
    # A method mismatch is 400 invalid_request — every (status, type) pair is
    # inside the fixed taxonomy (base item 4) — and the stub is not reached.
    collab = StubCollaborator(methods=("GET",))
    svc = make_service(api_keys=["sk-correct"], extra_routes=[collab.route])
    with svc.authorized() as c:
        r = c.post("/v1/collaborator", json={})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    assert not collab.requests


def test_the_stub_collaborator_requires_a_full_v1_path():
    with pytest.raises(ValueError):
        StubCollaborator(path="/collaborator")
