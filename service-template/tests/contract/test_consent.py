"""The consent-flag template contract (ticket #72; ADR-0026 §1/§2).

The seam is the HTTP contract surface of the full template app over real
HTTP (the one seam, spec #46 §Testing Decisions), driven by the in-process
test server. One contract item per section:

  - the input carries the consent flag: the two ADR-0026 §1 states, the
    default "may use", unknown marks rejected loudly (an explicit JSON
    null included — never silently normalized); the flag is documented in
    the OpenAPI fragment and inherited by the MCP surface (zero drift).
  - the extraction surface honors the never-bypassable private/secret
    exclusion (ADR-0026 §2 pass 1 — filter = the consent gate), through
    the base contract's item-5 pagination envelope.

The human-surface toggle lives in `test_canary.py`; the scaffold's consent
stub + exclusion-assertion helper live in `test_stubs.py`.
"""

from contract.base.consent import DEFAULT_CONSENT, MAY_USE, PRIVATE_SECRET

from tests.support.test_server import InProcessService


def make_service():
    return InProcessService(api_keys=["sk-correct"])


# --- The input carries the consent flag (API surface) ------------------------


def test_echo_accepts_a_consent_flagged_input_and_echoes_unchanged():
    """Every user input carries the consent flag (ADR-0026 §1): the client
    marks the interaction's state and the echoed body comes back unchanged
    (the flag rides WITH the input, it does not alter the echo)."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/echo", json={"text": "hi", "consent": PRIVATE_SECRET})
    assert r.status_code == 200
    assert r.json() == {"text": "hi", "consent": PRIVATE_SECRET}


def test_an_input_without_the_flag_defaults_to_may_use():
    """Per-interaction consent defaults to "may use for improvement"
    (ADR-0026 §1) — an ABSENT flag takes the default; the resolved state is
    visible in the recorded interaction (no silent assumption)."""
    svc = make_service()
    with svc.authorized() as c:
        c.post("/v1/echo", json={"text": "defaulted"})
        r = c.get("/v1/echo/extract")
    assert r.status_code == 200
    assert r.json()["items"] == [
        {"seq": 1, "text": "defaulted", "consent": DEFAULT_CONSENT}
    ]


def test_echo_rejects_an_unknown_consent_state_as_invalid_request():
    """A consent value outside the two ADR-0026 §1 states is a client error
    (400 `invalid_request`, base item 4) — consent never silently normalizes
    an unknown mark into an eligible state."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/echo", json={"text": "hi", "consent": "sure-why-not"})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_an_explicit_consent_null_is_rejected_not_normalized():
    """An explicit JSON `null` is a DECLARED mark, not an absent one — it is
    rejected loudly (400 `invalid_request`), never normalized into the
    eligible default (fail-closed, ADR-0026 §2; review finding)."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/echo", json={"text": "hi", "consent": None})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_an_input_without_a_text_string_is_rejected_loudly():
    """The canary's interaction record is `{seq, text, consent}` — an input
    without a string `text` has no interaction content to record, so it is
    a client error (400 `invalid_request`), not a silently degraded record
    (review finding)."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/echo", json={"foo": 1})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_the_openapi_document_carries_the_consent_flag_with_the_default():
    """The flag is part of the deterministic surface's self-description: the
    two states + the `may_use` default (ADR-0026 §1), the `text` field the
    interaction record needs. The MCP surface inherits this schema — zero
    drift by construction."""
    svc = make_service()
    with svc.authorized() as c:
        doc = c.get("/openapi.json").json()
    schema = doc["paths"]["/v1/echo"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert schema["required"] == ["text"]
    assert schema["properties"]["text"]["type"] == "string"
    consent = schema["properties"]["consent"]
    assert consent["enum"] == [MAY_USE, PRIVATE_SECRET]
    assert consent["default"] == MAY_USE


# --- The agent surface carries the flag — zero drift by construction (the
# --- MCP tools are auto-generated from the OpenAPI doc).

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


# --- The extraction surface honors the never-bypassable exclusion
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
    assert [i["text"] for i in body["items"]] == ["usable", "defaulted"]
    assert [i["consent"] for i in body["items"]] == [MAY_USE, MAY_USE]
    assert body["excluded"] == {"private_secret": 1}


def test_extract_is_a_bearer_gated_contract_endpoint():
    svc = make_service()
    with svc.client as c:
        r = c.get("/v1/echo/extract")
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "authentication_failed"


def test_extract_follows_the_item_5_pagination_envelope():
    """The extraction returns a LIST of interactions, so it carries the base
    contract's item-5 envelope — `?limit`/`?cursor`, `{"items",
    "next_cursor"}` — with the exclusion report riding every page (the gate
    is eligibility over the whole record; pagination slices the eligible
    list). Review finding: an unpaginated 128-item store exceeds the
    default limit of 50."""
    svc = make_service()
    with svc.authorized() as c:
        for n in range(55):
            c.post("/v1/echo", json={"text": f"note {n}", "consent": MAY_USE})
        c.post("/v1/echo", json={"text": "a private thought", "consent": PRIVATE_SECRET})
        first = c.get("/v1/echo/extract")
        assert first.status_code == 200
        body = first.json()
        assert set(body) == {"items", "next_cursor", "excluded"}
        assert len(body["items"]) == 50  # the item-5 default limit
        assert body["next_cursor"]  # an opaque cursor, not a page number
        assert body["excluded"] == {"private_secret": 1}
        second = c.get("/v1/echo/extract", params={"cursor": body["next_cursor"]})
        assert second.status_code == 200
        body2 = second.json()
        assert [i["text"] for i in body2["items"]] == [f"note {n}" for n in range(50, 55)]
        assert body2["next_cursor"] == ""  # the last page
        assert body2["excluded"] == {"private_secret": 1}
        # the private/secret interaction passed NO page
        assert not any(
            i["text"] == "a private thought" for i in body["items"] + body2["items"]
        )


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


def test_input_consent_applies_the_default_only_for_an_absent_flag():
    """The ADR-0026 §1 default rule lives ONCE (review round 2): an absent
    flag → the may-use default; a declared mark — a state, an unknown value,
    or an explicit null — → resolve_consent (ValueError → the caller's 400
    invalid_request)."""
    import pytest

    from contract.base.consent import input_consent

    assert input_consent({"text": "x"}) == MAY_USE
    assert input_consent({"text": "x", "consent": PRIVATE_SECRET}) == PRIVATE_SECRET
    assert input_consent({"text": "x", "consent": MAY_USE}) == MAY_USE
    with pytest.raises(ValueError):
        input_consent({"consent": None})
    with pytest.raises(ValueError):
        input_consent({"consent": "sure-why-not"})
