"""Slice 4 — base contract item 5: pagination (ADR-0001 §Base contract.5).

Cursor-based only: `?limit` (default 50, max 200) + `?cursor`; responses
`{"items": [...], "next_cursor": "<opaque>"}`. No page numbers, no offset;
cursors never parsed by clients (opaque).
"""

import base64
import json

from starlette.routing import Route

from contract.base import create_service_app
from tests.support.test_server import InProcessService

THINGS = [{"id": i, "name": f"thing-{i}"} for i in range(250)]


async def list_things(request):
    # A capability endpoint using the vendored pagination helpers.
    from contract.base.pagination import paginate

    return paginate(request, THINGS, lambda t: str(t["id"]))


def make_service():
    return InProcessService(
        api_keys=["sk-correct"],
        extra_routes=[Route("/v1/things", list_things, methods=["GET"])],
    )


def test_pagination_default_limit_and_envelope():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/v1/things")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "next_cursor"}
    assert len(body["items"]) == 50  # default limit
    assert body["items"][0]["id"] == 0
    assert body["next_cursor"]  # more pages remain
    svc.close()


def test_pagination_limit_bounds():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/v1/things", params={"limit": 10})
        assert len(r.json()["items"]) == 10
        # max 200 — over is clipped, not an error (limit is a bound, not a request)
        r = c.get("/v1/things", params={"limit": 500})
        assert len(r.json()["items"]) == 200
    svc.close()


def test_pagination_cursor_walks_all_items_and_terminates():
    svc = make_service()
    seen = []
    with svc.authorized() as c:
        r = c.get("/v1/things", params={"limit": 100})
        seen.extend(r.json()["items"])
        while cursor := r.json()["next_cursor"]:
            r = c.get("/v1/things", params={"limit": 100, "cursor": cursor})
            seen.extend(r.json()["items"])
    assert [t["id"] for t in seen] == list(range(250))  # stable order, no gaps
    assert r.json()["next_cursor"] == ""  # last page: empty cursor
    svc.close()


def test_pagination_cursors_are_opaque():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/v1/things")
        cursor = r.json()["next_cursor"]
    # A cursor is an opaque token: it must not be a bare page number/offset,
    # and decoding it as such must not work. (Clients never parse cursors —
    # this is a template-level guarantee, so the token is at least not
    # trivially offset-shaped.)
    assert cursor != "1" and not cursor.isdigit()
    try:
        decoded = json.loads(base64.urlsafe_b64decode(cursor))
    except Exception:
        decoded = None
    assert decoded is None or not isinstance(decoded, int)
    svc.close()


def test_pagination_invalid_limit_is_invalid_request():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/v1/things", params={"limit": "not-a-number"})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    svc.close()


def test_pagination_tampered_cursor_is_invalid_request():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/v1/things", params={"cursor": "garbage!!"})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    svc.close()


def test_create_service_app_mounts_extra_routes_under_v1():
    # Sanity for the factory's /v1 mounting, independent of pagination.
    app = create_service_app(service_name="x", version="1", api_keys=["k"], extra_routes=[])
    assert any(getattr(r, "path", "") == "/v1" for r in app.routes)
