"""The canary capability — the template's proof capability (ticket #71).

Acceptance seam (spec #46 §Testing Decisions — ONE seam): the HTTP/OpenAPI
contract surface of the full template app over real HTTP, driven by the
in-process test server. The canary is wired to the three callable surfaces:
`/openapi.json` (deterministic), `/mcp` (agent), `/echo` (human, FastHTML +
Alpine).

Slices, one per red→green cycle:
  1. /openapi.json — the deterministic surface, assembled from the canary's
     OpenAPI fragment.
  2. /mcp — the agent surface, tools auto-generated from the OpenAPI doc.
  3. /echo — the human surface.
"""

from tests.support.test_server import InProcessService


def make_service():
    return InProcessService(api_keys=["sk-correct"])


def test_openapi_doc_is_served_at_openapi_json():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/openapi.json")
    assert r.status_code == 200
    doc = r.json()
    assert doc["openapi"].startswith("3.1")
    assert doc["info"]["title"] == "template-service"
    assert doc["info"]["version"]


def test_openapi_doc_carries_the_canary_operations():
    svc = make_service()
    with svc.authorized() as c:
        doc = c.get("/openapi.json").json()
    paths = doc["paths"]
    assert set(paths) == {"/v1/echo", "/v1/echo/ping"}
    post = paths["/v1/echo"]["post"]
    get = paths["/v1/echo/ping"]["get"]
    assert post["operationId"] == "echo"
    assert get["operationId"] == "echo.ping"
    assert post["requestBody"]["content"]["application/json"]["schema"]["type"] == "object"


def test_openapi_doc_requires_the_bearer_key():
    svc = make_service()
    with svc.client as c:
        r = c.get("/openapi.json")
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "authentication_failed"
