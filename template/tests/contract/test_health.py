"""Slice 1 — base contract item 6: `GET /health` (ADR-0001 §Base contract.6).

Shape: `{"status", "service", "version", "resources", "models"?}`. HTTP 200
for alive/progressing states, 503 for cannot-serve states. Independent
source of truth: the ADR's literal status enum and payload keys.
"""

from tests.support.test_server import InProcessService


def test_health_returns_contract_payload_shape():
    svc = InProcessService(service_name="template-service", version="0.1.0")
    with svc.client as c:
        r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"status", "service", "version", "resources"}
    assert body["status"] == "ready"
    assert body["service"] == "template-service"
    assert body["version"] == "0.1.0"
    assert body["resources"] == {}


def test_health_cannot_serve_states_return_503():
    # From the ADR's status enum: full / stopping / down cannot serve.
    for status in ("full", "stopping", "down"):
        svc = InProcessService(health_status=status)
        with svc.client as c:
            r = c.get("/health")
        assert r.status_code == 503, status
        assert r.json()["status"] == status
        svc.close()


def test_health_is_reachable_without_auth():
    # The dashboard/monitoring surface reads /health (ADR-0001 item 6).
    svc = InProcessService()
    with svc.client as c:
        r = c.get("/health")
    assert r.status_code == 200
