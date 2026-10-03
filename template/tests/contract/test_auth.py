"""Slice 2 — base contract item 2: auth (ADR-0001 §Base contract.2).

401 `authentication_failed` when the Bearer key is absent/invalid; keys
validated by the service itself.
"""

from tests.support.test_server import InProcessService


def test_missing_bearer_key_is_401_authentication_failed():
    svc = InProcessService()
    with svc.client as c:
        r = c.get("/v1/things")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["type"] == "authentication_failed"
    assert body["error"]["message"]
    assert body["request_id"]


def test_invalid_bearer_key_is_401():
    svc = InProcessService(api_keys=["sk-correct"])
    with svc.client as c:
        r = c.get("/v1/things", headers={"Authorization": "Bearer sk-wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "authentication_failed"


def test_valid_bearer_key_passes_auth():
    svc = InProcessService(api_keys=["sk-correct"])
    with svc.authorized() as c:
        r = c.get("/v1/things")
    # The route doesn't exist — but the failure is 404, not 401.
    assert r.status_code == 404
    assert r.json()["error"]["type"] == "not_found"


def test_health_is_exempt_from_auth():
    svc = InProcessService()
    with svc.client as c:
        assert c.get("/health").status_code == 200
