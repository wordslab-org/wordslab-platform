"""The stub-factory's own conformance (ticket #70 acceptance: "the
stub-factory produces the documented stub shapes for base contract
fixtures") — every stub exercised over the real HTTP seam (the one seam,
spec #46 §Testing Decisions), never against internals.

The stub shapes are documented in `tests/support/stubs.py`; the independent
source of truth for the *contract* shapes is ADR-0001 (cited per assertion).
"""

import pytest

from contract.base.consent import MAY_USE, PRIVATE_SECRET

from tests.contract.runner import failures
from tests.support.stubs import (
    COMPOSITION_PRIMITIVES,
    StubCollaborator,
    StubEngine,
    StubRegistry,
    stub_api_key,
    stub_401_violations,
    stub_health_payload,
    stub_health_violations,
)
from tests.support.test_server import InProcessService

# The family-5 model status enum, verbatim from ADR-0001 family 5 (the same
# enum the f5 conformance block pins).
MODEL_STATUSES = frozenset(
    {"absent", "downloading", "available", "loading", "ready", "unloading", "error"}
)


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


# --- consent-flagged stub interaction + the exclusion-assertion helper
# --- (spec #68 story 9, ticket #72: the ADR-0026 gate testable at every
# --- service's seam from the first service).


def test_the_consent_stub_interaction_carries_the_flag_with_the_default():
    from tests.support.stubs import stub_consent_interaction

    interaction = stub_consent_interaction()
    assert interaction["consent"] == MAY_USE  # the ADR-0026 §1 default
    assert "text" in interaction  # the interaction's content
    marked = stub_consent_interaction(text="a secret", consent=PRIVATE_SECRET)
    assert marked == {"text": "a secret", "consent": PRIVATE_SECRET}


def test_the_consent_gate_matcher_accepts_an_exclusion_honoring_extraction(make_service):
    from tests.support.stubs import (
        stub_consent_gate_violations,
        stub_consent_interaction,
    )

    svc = make_service()
    recorded = [
        stub_consent_interaction(text="usable"),
        stub_consent_interaction(text="a private thought", consent="private_secret"),
    ]
    with svc.authorized() as c:
        c.post("/v1/echo", json={"text": "usable", "consent": MAY_USE})
        c.post("/v1/echo", json={"text": "a private thought", "consent": PRIVATE_SECRET})
        r = c.get("/v1/echo/extract")
    assert stub_consent_gate_violations(r.json()["items"], recorded) == []


def test_the_consent_gate_matcher_flags_a_private_interaction_leaking_through(make_service):
    """A private/secret recorded interaction appearing verbatim in the
    extraction's output is a violation — the exclusion is never bypassed
    (ADR-0026 §2)."""
    from tests.support.stubs import stub_consent_gate_violations, stub_consent_interaction

    recorded = [
        stub_consent_interaction(text="usable"),
        stub_consent_interaction(text="a private thought", consent=PRIVATE_SECRET),
    ]
    svc = make_service()
    with svc.authorized() as c:
        c.post("/v1/echo", json={"text": "usable", "consent": MAY_USE})
        c.post("/v1/echo", json={"text": "a private thought", "consent": PRIVATE_SECRET})
        extracted = c.get("/v1/echo/extract").json()["items"]
        extracted.append(
            stub_consent_interaction(text="a private thought", consent=PRIVATE_SECRET)
        )
    violations = stub_consent_gate_violations(extracted, recorded)
    assert any("private/secret" in v for v in violations), violations


def test_the_consent_gate_matcher_flags_an_extracted_item_outside_the_may_use_state():
    """Every eligible interaction carries the `may_use` state — an extracted
    item with another (or a missing) state is a violation."""
    from tests.support.stubs import stub_consent_gate_violations

    violations = stub_consent_gate_violations(
        [{"text": "x", "consent": PRIVATE_SECRET}, {"text": "y"}], []
    )
    assert len(violations) == 2, violations


# --- stub engine (spec #68 story 3; the family-1/2/5 seam) -------------------
# The engine's deterministic canned output is asserted through a family-shaped
# HTTP surface wired to it via the factory's `extra_routes` (the same seam as
# every stage-0 ticket) — never against internals, and with NO family module
# added (the family modules are #76–#84's deliverables; this stub serves them).


def test_the_stub_engine_serves_the_family_1_responses_shape(make_service):
    engine = StubEngine()
    svc = make_service(api_keys=["sk-correct"], extra_routes=engine.routes())
    with svc.authorized() as c:
        r = c.post("/v1/responses", json={"model": "stub-model", "input": "ping"})
    assert r.status_code == 200
    body = r.json()
    # ADR-0001 family 1 — the Responses API by reference: `resp_` id, the
    # `response` object, a typed `output` list, `usage` in tokens.
    assert body["id"].startswith("resp_")
    assert body["object"] == "response"
    assert isinstance(body["output"], list)
    assert body["usage"]["total_tokens"] > 0  # base item 8
    assert failures(r) == []  # the base contract holds on the family seam


def test_the_stub_engine_is_deterministic_and_offline():
    # No randomness, no network: two fresh engines answer the same request
    # identically, and a different request answers differently — canned output
    # derived purely from the request (spec #68 Implementation Decisions).
    request = {"model": "stub-model", "input": "ping"}
    first = StubEngine().responses(dict(request))
    second = StubEngine().responses(dict(request))
    assert first == second
    assert first["id"] != StubEngine().responses({"input": "pong"})["id"]


def test_the_stub_engine_serves_the_family_5_model_catalog(make_service):
    engine = StubEngine()
    svc = make_service(api_keys=["sk-correct"], extra_routes=engine.routes())
    with svc.authorized() as c:
        r = c.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"items", "next_cursor"}  # base item 5 envelope
    assert body["items"], "the stub catalog is never empty"
    for model in body["items"]:
        # ADR-0001 family 5 — the model lifecycle record shape.
        assert set(model) >= {
            "id", "supported", "recommended", "downloaded", "size_gb", "status",
        }
        assert model["status"] in MODEL_STATUSES


def test_the_stub_engine_serves_the_family_2_embeddings_shape(make_service):
    engine = StubEngine()
    svc = make_service(api_keys=["sk-correct"], extra_routes=engine.routes())
    with svc.authorized() as c:
        r = c.post("/v1/embeddings", json={"model": "stub-model", "input": "ping"})
    assert r.status_code == 200
    body = r.json()
    # ADR-0001 family 2 — embeddings by reference: the `list` object, per-input
    # embedding records, `usage` in the reference API's native unit.
    assert body["object"] == "list"
    assert body["data"] and body["data"][0]["embedding"]
    assert "usage" in body


def test_the_stub_engine_rejects_a_malformed_body(make_service):
    # Malformed JSON is a CLIENT error (base item 4), never an unhandled 500.
    engine = StubEngine()
    svc = make_service(api_keys=["sk-correct"], extra_routes=engine.routes())
    with svc.authorized() as c:
        r = c.post(
            "/v1/responses",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


# --- stub-collaborator resolution (spec #68 story 4; ADR-0008 §7/§8) ---------
# The fake capability registry: composition references of any primitive kind
# (`call`/`model`/`agent`, ADR-0007 §3) resolve by stable name to a fake
# endpoint (a `StubCollaborator`), which records the dispatched request.


def test_the_stub_registry_resolves_a_call_reference_to_the_fake_endpoint(make_service):
    collab = StubCollaborator()
    registry = StubRegistry()
    registry.register("document.parse", collab.path)
    reference = registry.resolve("call", "document.parse")
    assert reference.endpoint == collab.path
    svc = make_service(api_keys=["sk-correct"], extra_routes=[collab.route])
    with svc.authorized() as c:
        r = c.post(reference.endpoint, json={"document": "bundle-1"})
    assert r.status_code == 200
    assert collab.requests[-1]["payload"] == {"document": "bundle-1"}


def test_the_stub_registry_resolves_call_model_and_agent_references():
    # ADR-0008 §7: one registry, one name→URL role — the three composition
    # primitive kinds all resolve a stable name to the same endpoint, each
    # reference recording the primitive that made it.
    registry = StubRegistry()
    registry.register("document.parse", "/v1/document/parse")
    for primitive in COMPOSITION_PRIMITIVES:
        reference = registry.resolve(primitive, "document.parse")
        assert (reference.primitive, reference.name, reference.endpoint) == (
            primitive,
            "document.parse",
            "/v1/document/parse",
        )


def test_the_stub_registry_refuses_an_unknown_reference():
    with pytest.raises(ValueError, match="does not resolve"):
        StubRegistry().resolve("call", "document.parse")


def test_the_stub_registry_refuses_an_unknown_composition_primitive():
    registry = StubRegistry()
    registry.register("document.parse", "/v1/document/parse")
    with pytest.raises(ValueError, match="composition primitive"):
        registry.resolve("subworkflow", "document.parse")


def test_the_stub_registry_rejects_a_stable_name_collision():
    # ADR-0008 §8: a second claimant can never shadow a reserved name.
    registry = StubRegistry()
    registry.register("document.parse", "/v1/document/parse")
    with pytest.raises(ValueError, match="already reserved"):
        registry.register("document.parse", "/v1/document/parse-2")


def test_the_stub_registry_rejects_a_malformed_stable_name():
    with pytest.raises(ValueError, match="stable name"):
        StubRegistry().register("document", "/v1/document")


def test_the_stub_registry_rejects_a_non_v1_endpoint():
    with pytest.raises(ValueError, match="under /v1"):
        StubRegistry().register("document.parse", "/document/parse")
