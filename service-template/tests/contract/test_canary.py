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

from pathlib import Path

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
    # The service identity flows from the declaration, not from literals:
    # the copy-to-start ritual renames it (ticket #71).
    from contract.declaration import load_service_toml

    declaration = load_service_toml(
        Path(__file__).resolve().parents[2] / "service.toml"
    )
    assert doc["info"]["title"] == declaration.name
    assert doc["info"]["version"] == declaration.version


def test_openapi_doc_carries_the_canary_operations():
    svc = make_service()
    with svc.authorized() as c:
        doc = c.get("/openapi.json").json()
    paths = doc["paths"]
    assert set(paths) == {"/v1/echo", "/v1/echo/extract", "/v1/echo/ping"}
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


def rpc(c, method, *, req_id=None, params=None):
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if req_id is not None:
        payload["id"] = req_id
    if params is not None:
        payload["params"] = params
    return c.post("/mcp", json=payload, headers=JSON_HEADERS)


def test_mcp_requires_the_bearer_key():
    svc = make_service()
    with svc.client as c:
        r = rpc(c, "initialize", req_id=1, params={"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}})
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "authentication_failed"


def test_mcp_initialize_returns_the_service_identity():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "initialize", req_id=1, params={"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["protocolVersion"].startswith("2025-")
    from contract.declaration import load_service_toml

    declaration = load_service_toml(
        Path(__file__).resolve().parents[2] / "service.toml"
    )
    assert result["serverInfo"]["name"] == declaration.name
    assert result["serverInfo"]["version"] == declaration.version
    assert "tools" in result["capabilities"]


def test_mcp_tools_match_the_openapi_operations_zero_drift():
    svc = make_service()
    with svc.authorized() as c:
        doc = c.get("/openapi.json").json()
        tools = rpc(c, "tools/list", req_id=2).json()["result"]["tools"]
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
        r = rpc(c, "tools/call", req_id=3, params={"name": "echo", "arguments": {"text": "hi"}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == {"text": "hi"}


def test_mcp_tools_call_ping_returns_pong():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "tools/call", req_id=4, params={"name": "echo.ping", "arguments": {}})
    assert r.status_code == 200
    assert r.json()["result"]["structuredContent"] == {"pong": True}


def test_mcp_tools_call_unknown_tool_is_an_error_result_not_a_crash():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "tools/call", req_id=5, params={"name": "nope", "arguments": {}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True
    assert "nope" in result["content"][0]["text"]


def test_mcp_initialized_notification_is_accepted():
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "notifications/initialized")
    assert r.status_code == 202


# --- Slice 3: /echo — the human surface (FastHTML + vendored Alpine, no CDN).

def test_echo_page_is_served():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/echo")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Echo" in r.text


def test_echo_page_drives_the_deterministic_surface_and_vendors_assets():
    svc = make_service()
    with svc.authorized() as c:
        html = c.get("/echo").text
    assert "/v1/echo" in html  # the page calls the same API, no duplicate logic
    assert "/static/alpine.min.js" in html
    assert "/static/pico.min.css" in html
    assert "x-data" in html  # Alpine interactivity (Surreal never loaded)
    assert "surreal" not in html.lower()
    assert "htmx" not in html.lower()
    lowered = html.lower()
    assert "cdn." not in lowered and "://unpkg" not in lowered and "://jsdelivr" not in lowered


def test_the_echo_page_carries_the_visible_private_secret_toggle_defaulting_to_may_use():
    """Every user input surface carries the consent flag with the default
    may-use state and a VERY visible 'private/secret — do not use' toggle
    (ADR-0026 §1, ticket #72 AC1) — and the page drives the same API with it
    (no duplicate logic). The toggle is styled prominent in the vendored CSS
    (a bare unstyled checkbox is not 'very visible'; review finding)."""
    svc = make_service()
    with svc.authorized() as c:
        html = c.get("/echo").text
        css = c.get("/static/service.css").text
    lowered = html.lower()
    assert "private/secret" in lowered  # the ADR's toggle wording, visible
    assert "do not use" in lowered
    assert "may use" in lowered  # the default state is explained, not assumed
    assert "private: false" in html  # the toggle STARTS in the may-use state
    assert "may_use" in html and "private_secret" in html  # it sends the real states
    assert ".consent-toggle" in css and ".consent-hint" in css  # styled, not bare
    assert "font-weight: 600" in css  # emphasized — the visibility bar


def test_vendored_static_assets_are_served():
    svc = make_service()
    with svc.authorized() as c:
        alpine = c.get("/static/alpine.min.js")
        pico = c.get("/static/pico.min.css")
        css = c.get("/static/service.css")
    assert alpine.status_code == 200 and len(alpine.content) > 10_000
    assert "alpine" in alpine.text[:2000].lower() or alpine.text.startswith("((")
    assert pico.status_code == 200 and len(pico.content) > 10_000
    assert css.status_code == 200 and ".echo-result" in css.text


# --- Review findings (slice 5): contract-strictness on the canary surface.

def test_malformed_json_body_is_invalid_request_not_internal_error():
    """Client garbage is a client error: 400 `invalid_request`, never a 500
    `internal_error` (ADR-0001 item 4 — the fixed taxonomy; a real capability
    copied from this one must not learn to 500 on bad input)."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post(
            "/v1/echo",
            content=b"{not json",
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_tools_call_args_for_a_bodyless_operation_are_rejected_loudly():
    """Arguments the operation cannot consume are an error result, not
    silently dropped — a silent drop would promise behavior it doesn't
    deliver (review finding; query-param dispatch lands with the first real
    GET-with-params capability)."""
    svc = make_service()
    with svc.authorized() as c:
        r = rpc(c, "tools/call", req_id=9, params={"name": "echo.ping", "arguments": {"x": 1}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True
    assert "x" in result["content"][0]["text"]
