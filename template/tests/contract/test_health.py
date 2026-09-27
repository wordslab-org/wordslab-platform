"""Slices 1 & 6 — base contract item 6: `GET /health` (ADR-0001
§Base contract.6).

Shape: `{"status", "service", "version", "resources", "models"?}`. HTTP 200
for alive/progressing states, 503 for cannot-serve states; the `resources`
payload shape comes from `resources()`. Independent source of truth: the
ADR's literal status enum and payload keys.
"""

from contract.base.health import resources
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


def test_resources_helper_builds_the_item_6_shape_without_gpu():
    r = resources(cpu_percent=12.5, ram_gb=(4.0, 16.0), disk_gb=(30.0, 500.0))
    assert set(r) == {"cpu", "ram", "disk"}
    assert r["cpu"] == 12.5
    assert r["ram"] == {"used": 4.0, "total": 16.0}
    assert r["disk"] == {"used": 30.0, "total": 500.0}
    assert "gpu" not in r and "vram" not in r  # omitted when no GPU


def test_resources_helper_includes_gpu_and_vram_when_present():
    r = resources(
        cpu_percent=12.5,
        ram_gb=(4.0, 16.0),
        disk_gb=(30.0, 500.0),
        gpu_percent=88.0,
        vram_gb=(3.5, 8.0),
    )
    assert r["gpu"] == 88.0
    assert r["vram"] == {"used": 3.5, "total": 8.0}


def test_health_reports_service_supplied_resources():
    res = resources(cpu_percent=1.0, ram_gb=(1.0, 8.0), disk_gb=(2.0, 64.0))
    svc = InProcessService(resources=res)
    with svc.client as c:
        body = c.get("/health").json()
    assert body["resources"] == res


def test_wrong_method_returns_400_invalid_request_not_405():
    # 405 is not one of the 11 codes: every (status, type) pair must be
    # inside the fixed taxonomy, so a method mismatch is 400 invalid_request.
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def only_get(request):
        return JSONResponse({"ok": True})

    svc = InProcessService(
        api_keys=["sk-correct"],
        extra_routes=[Route("/v1/only-get", only_get, methods=["GET"])],
    )
    with svc.authorized() as c:
        r = c.post("/v1/only-get")
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["type"] == "invalid_request"
    assert body["request_id"]
    assert r.headers["X-Request-Id"] == body["request_id"]
