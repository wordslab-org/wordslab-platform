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


# --- Slice 2: /mcp — the agent surface (stateless JSON-RPC 2.0, ADR-0001
# --- item 9, ADR-0002 §3: tools auto-generated from the OpenAPI doc).

JSON_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def rpc(c, method, *, id=None, params=None):
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if id is not None:
        payload["id"] = id
    if params is not None:
        payload["params"] = params
    return c.post("/mcp", json=payload, headers=JSON_HEADERS)


def test_mcp_requires_the_bearer_key():
    svc = make_service()
    with svc.client as c:
        r = rpc(c, "initialize", id=1, params={"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}})
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "authentication_failed"


def test_mcp_initialize_returns_the_service_identity():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "initialize", id=1, params={"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["protocolVersion"].startswith("2025-")
    assert result["serverInfo"]["name"] == "template-service"
    assert result["serverInfo"]["version"]
    assert "tools" in result["capabilities"]


def test_mcp_tools_match_the_openapi_operations_zero_drift():
    svc = make_service()
    with svc.authorized() as c:
        doc = c.get("/openapi.json").json()
        tools = rpc(c, "tools/list", id=2).json()["result"]["tools"]
    expected = {
        op["operationId"]
        for item in doc["paths"].values()
        for op in item.values()
        if op.get("operationId")
    }
    assert {t["name"] for t in tools} == expected  # zero drift, by construction
    echo_tool = next(t for t in tools if t["name"] == "echo")
    assert echo_tool["inputSchema"]["type"] == "object"
    assert echo_tool["description"]


def test_mcp_tools_call_echo_returns_the_body():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "tools/call", id=3, params={"name": "echo", "arguments": {"text": "hi"}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == {"text": "hi"}


def test_mcp_tools_call_ping_returns_pong():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "tools/call", id=4, params={"name": "echo.ping", "arguments": {}})
    assert r.status_code == 200
    assert r.json()["result"]["structuredContent"] == {"pong": True}


def test_mcp_tools_call_unknown_tool_is_an_error_result_not_a_crash():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "tools/call", id=5, params={"name": "nope", "arguments": {}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True
    assert "nope" in result["content"][0]["text"]


def test_mcp_initialized_notification_is_accepted():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "notifications/initialized")
    assert r.status_code == 202
