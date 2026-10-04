"""The consent-flag template contract (ticket #72; ADR-0026 §1/§2).

The seam is the HTTP contract surface of the full template app over real
HTTP (the one seam, spec #46 §Testing Decisions), driven by the in-process
test server. One contract item per slice:

  1. The canary's input (POST /v1/echo) carries the consent flag: the two
     ADR-0026 §1 states, the default "may use", unknown states rejected
     loudly; the flag documented in the OpenAPI fragment (the MCP surface
     inherits it — zero drift by construction).
  2. The extraction surface honors the never-bypassable private/secret
     exclusion (ADR-0026 §2 pass 1 — filter = the consent gate).
  3. The human surface carries the same flag: the visible
     "private/secret — do not use" toggle, defaulting to may-use.
  4. The scaffold carries a consent-flagged stub interaction + an
     exclusion-honored assertion helper (spec #68 story 9).
"""

from tests.support.test_server import InProcessService

MAY_USE = "may_use"
PRIVATE_SECRET = "private_secret"


def make_service():
    return InProcessService(api_keys=["sk-correct"])


# --- Slice 1: the input carries the consent flag (API surface) ---------------


def test_echo_accepts_a_consent_flagged_input_and_echoes_unchanged():
    """Every user input carries the consent flag (ADR-0026 §1): the client
    marks the interaction's state and the echoed body comes back unchanged
    (the flag rides WITH the input, it does not alter the echo)."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/echo", json={"text": "hi", "consent": PRIVATE_SECRET})
    assert r.status_code == 200
    assert r.json() == {"text": "hi", "consent": PRIVATE_SECRET}


def test_echo_rejects_an_unknown_consent_state_as_invalid_request():
    """A consent value outside the two ADR-0026 §1 states is a client error
    (400 `invalid_request`, base item 4) — consent never silently normalizes
    an unknown mark into an eligible state."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/echo", json={"text": "hi", "consent": "sure-why-not"})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_the_openapi_document_carries_the_consent_flag_with_the_default():
    """The flag is part of the deterministic surface's self-description: the
    two states + the `may_use` default (ADR-0026 §1). The MCP surface
    inherits this schema — zero drift by construction."""
    svc = make_service()
    with svc.authorized() as c:
        doc = c.get("/openapi.json").json()
    schema = doc["paths"]["/v1/echo"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    consent = schema["properties"]["consent"]
    assert consent["enum"] == [MAY_USE, PRIVATE_SECRET]
    assert consent["default"] == MAY_USE


# --- Slice 2: the extraction surface honors the never-bypassable exclusion
# --- (ADR-0026 §2 pass 1 — filter = the consent gate).


def test_extract_returns_only_may_use_interactions_and_counts_exclusions():
    """The gate is eligibility (ADR-0026 §2): a private/secret interaction is
    NEVER in the extraction's output, whatever else was recorded; only
    'may use for improvement' interactions pass. The exclusion is reported,
    not hidden (no magic)."""
    svc = make_service()
    with svc.authorized() as c:
        c.post("/v1/echo", json={"text": "usable", "consent": MAY_USE})
        c.post("/v1/echo", json={"text": "a private thought", "consent": PRIVATE_SECRET})
        c.post("/v1/echo", json={"text": "defaulted"})  # no flag → the may-use default
        r = c.get("/v1/echo/extract")
    assert r.status_code == 200
    body = r.json()
    assert [i["text"] for i in body["interactions"]] == ["usable", "defaulted"]
    assert [i["consent"] for i in body["interactions"]] == [MAY_USE, MAY_USE]
    assert body["excluded"] == {"private_secret": 1}


def test_an_input_without_the_flag_is_recorded_under_the_may_use_default():
    """Per-interaction consent defaults to 'may use for improvement'
    (ADR-0026 §1) — the resolved default state is visible in the recorded
    interaction, not silently assumed."""
    svc = make_service()
    with svc.authorized() as c:
        c.post("/v1/echo", json={"text": "defaulted"})
        r = c.get("/v1/echo/extract")
    assert r.json()["interactions"] == [{"text": "defaulted", "consent": MAY_USE}]


def test_extract_is_a_bearer_gated_contract_endpoint():
    svc = make_service()
    with svc.client as c:
        r = c.get("/v1/echo/extract")
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "authentication_failed"


def test_the_consent_gate_excludes_an_unset_interaction_fail_closed():
    """The gate's fail-closed rule (ADR-0026 §2: better to fail to improve a
    fix than to expose a secret): an interaction WITHOUT a consent state is
    excluded — an extraction surface that loses the flag must not gain
    eligibility."""
    from contract.base.consent import consent_gate

    eligible, excluded = consent_gate(
        [
            {"text": "ok", "consent": MAY_USE},
            {"text": "flag lost", "consent": None},
            {"text": "marked", "consent": PRIVATE_SECRET},
        ]
    )
    assert [i["text"] for i in eligible] == ["ok"]
    assert excluded == {"unset": 1, "private_secret": 1}


# --- Slice 5: the agent surface carries the flag — zero drift by
# --- construction (the MCP tools are auto-generated from the OpenAPI doc).

JSON_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def _rpc(c, method, *, req_id, params=None):
    payload: dict = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        payload["params"] = params
    return c.post("/mcp", json=payload, headers=JSON_HEADERS)


def test_the_mcp_echo_tool_carries_the_consent_flag_zero_drift():
    """The consent flag rides every user input surface — the agent surface
    included: the echo tool's inputSchema inherits the enum + default from
    the OpenAPI document (ADR-0002 §3 zero drift, ADR-0026 §1)."""
    svc = make_service()
    with svc.authorized() as c:
        tools = _rpc(c, "tools/list", req_id=6).json()["result"]["tools"]
    echo_tool = next(t for t in tools if t["name"] == "echo")
    consent = echo_tool["inputSchema"]["properties"]["consent"]
    assert consent["enum"] == [MAY_USE, PRIVATE_SECRET]
    assert consent["default"] == MAY_USE
