"""Slice 3 — base contract item 4: errors (ADR-0001 §Base contract.4).

Body shape `{"error": {"type", "message", "resource"?}, "request_id"}` and
`X-Request-Id` on every response. The 11-code taxonomy is exercised through
real errors raised over the seam.
"""

import pytest

from contract.base import ApiError
from tests.support.test_server import InProcessService

# The 11 codes, verbatim from ADR-0001 item 4: (status, type, resource?)
TAXONOMY = [
    (400, "invalid_request", None),
    (401, "authentication_failed", None),
    (403, "permission_denied", None),
    (404, "not_found", None),
    (409, "conflict", None),
    (413, "request_too_large", None),
    (429, "resource_exhausted", "vram"),
    (500, "internal_error", None),
    (503, "busy", None),
    (503, "unavailable", None),
    (504, "timeout", None),
]


def route_raising(error: ApiError):
    async def endpoint(request):
        raise error

    return endpoint


def service_with(error: ApiError) -> InProcessService:
    from starlette.routing import Route

    return InProcessService(
        api_keys=["sk-correct"],
        extra_routes=[Route("/v1/boom", route_raising(error), methods=["GET"])],
    )


@pytest.mark.parametrize(("status", "type_", "resource"), TAXONOMY)
def test_error_taxonomy_body_shape_over_real_http(status, type_, resource):
    svc = service_with(ApiError(type_, "boom", resource=resource))
    with svc.authorized() as c:
        r = c.get("/v1/boom")
    assert r.status_code == status
    body = r.json()
    assert set(body) == {"error", "request_id"}
    assert body["error"]["type"] == type_
    assert body["error"]["message"] == "boom"
    if resource is None:
        assert "resource" not in body["error"]
    else:
        assert body["error"]["resource"] == resource
    assert r.headers["X-Request-Id"] == body["request_id"]
    svc.close()


def test_resource_exhausted_requires_a_resource_name():
    with pytest.raises(ValueError):
        ApiError("resource_exhausted", "no resource given")


def test_unknown_error_type_is_rejected():
    with pytest.raises(ValueError):
        ApiError("not_a_code", "nope")


def test_every_response_carries_x_request_id():
    svc = InProcessService(api_keys=["sk-correct"])
    with svc.authorized() as c:
        ids = {c.get(path).headers["X-Request-Id"] for path in ("/health", "/v1/missing")}
    assert len(ids) == 2  # present on every response, and distinct per request
