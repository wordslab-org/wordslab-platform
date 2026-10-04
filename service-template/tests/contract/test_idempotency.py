"""Slice 5 — base contract item 7: idempotency (ADR-0001 §Base contract.7).

Optional `Idempotency-Key` header on mutating endpoints; the service dedupes
retries and returns the original result.
"""

from starlette.responses import JSONResponse
from starlette.routing import Route

from tests.support.test_server import InProcessService

CALLS = {"count": 0}


async def create_thing(request):
    CALLS["count"] += 1
    return JSONResponse({"id": 1, "name": "thing"}, status_code=201)


def make_service():
    CALLS["count"] = 0
    return InProcessService(
        api_keys=["sk-correct"],
        extra_routes=[Route("/v1/things", create_thing, methods=["POST"])],
    )


def test_idempotency_key_dedupes_retry_and_returns_original_result():
    svc = make_service()
    with svc.authorized() as c:
        headers = {"Idempotency-Key": "abc-123"}
        first = c.post("/v1/things", headers=headers)
        second = c.post("/v1/things", headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert CALLS["count"] == 1  # the endpoint ran once; the retry replayed it
    svc.close()


def test_without_idempotency_key_every_request_executes():
    svc = make_service()
    with svc.authorized() as c:
        c.post("/v1/things")
        c.post("/v1/things")
    assert CALLS["count"] == 2
    svc.close()


def test_idempotency_is_opt_in_and_scoped_per_key():
    svc = make_service()
    with svc.authorized() as c:
        c.post("/v1/things", headers={"Idempotency-Key": "k1"})
        c.post("/v1/things", headers={"Idempotency-Key": "k2"})
    assert CALLS["count"] == 2  # different keys are different operations
    svc.close()


def test_idempotent_replay_preserves_status_and_request_id():
    svc = make_service()
    with svc.authorized() as c:
        headers = {"Idempotency-Key": "abc-123"}
        first = c.post("/v1/things", headers=headers)
        second = c.post("/v1/things", headers=headers)
    assert second.status_code == first.status_code
    assert second.headers["X-Request-Id"] == first.headers["X-Request-Id"]
    svc.close()
