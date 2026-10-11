"""The per-user export/restore template contract (ticket #269; ADR-0021
§3/§5/§7).

The seam is the HTTP contract surface of the full template app over real
HTTP (the one seam, spec #46 §Testing Decisions), driven by the in-process
test server. One contract item per section:

  - the export surface requires the user+role context — the whole-DB export
    (no context) is the shape ADR-0021 §3 forbids, so the route cannot
    express it (400, never a silent whole-DB 200);
  - the export unit is self-contained: the closed shape, the service
    identity, per-user isolation (an export for one user+role never holds
    another's records);
  - the true-incremental delta (`since`) yields exactly the records above
    that seq (ADR-0021 §5);
  - the restore surface applies a full, chains a delta (409 on a broken
    chain), verifies the unit's service identity (ADR-0021 §7), and rejects
    malformed units loudly (closed shape, base item 4);
  - full + delta replay reproduces the source state (ADR-0021 §3/§5/§7).

The compliance checker (`tests/support/export_restore_check.py`) and its
probes — the controlled stub service (AC 2), the whole-DB negative (AC 3),
the sweeper entry point asserted against the canary (AC 4) — are in
`test_export_restore_check.py`.
"""

from contract.base.export_restore import (
    DEFAULT_OWNER,
    DEFAULT_ROLE,
    KIND_DELTA,
    KIND_FULL,
    ROLES,
    UNIT_KEYS,
)

from tests.support.test_server import InProcessService


def make_service():
    return InProcessService(api_keys=["sk-correct"])


def _echo(c, text, *, owner=None, role=None, consent=None):
    body: dict = {"text": text}
    if owner is not None:
        body["owner"] = owner
    if role is not None:
        body["role"] = role
    if consent is not None:
        body["consent"] = consent
    return c.post("/v1/echo", json=body)


# --- The export surface requires the user+role context (ADR-0021 §3) ------


def test_an_export_without_the_user_role_context_is_rejected_not_served():
    """The whole-DB export — an extraction with no user+role context — is
    the shape ADR-0021 §3 forbids ("a database's builtin whole-DB backup
    would capture every user at once"). The route cannot express it: a
    missing context is 400 `invalid_request`, never a whole-DB 200."""
    svc = make_service()
    with svc.authorized() as c:
        _echo(c, "mine")
        r = c.get("/v1/export")
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    assert "per user+role" in r.json()["error"]["message"]


def test_an_export_with_an_unknown_role_is_rejected_loudly():
    """The role is a closed vocabulary — the three data spheres (ADR-0021
    §1); anything else is 400 naming the offending value."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/v1/export", params={"owner": "alice", "role": "wizard"})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    assert "wizard" in r.json()["error"]["message"]


def test_an_export_with_a_non_integer_since_is_rejected_loudly():
    svc = make_service()
    with svc.authorized() as c:
        r = c.get("/v1/export", params={"owner": "alice", "role": "user", "since": "yesterday"})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


# --- The export unit is self-contained + per-user isolated (ADR-0021 §3) --


def test_a_full_export_is_one_self_contained_unit_with_the_service_identity():
    """The unit carries the closed shape: the service identity it was
    exported from (ADR-0021 §7's verification metadata), the user+role
    context, kind `full` with `since = null`, and the records (ADR-0021
    §3)."""
    svc = make_service()
    with svc.authorized() as c:
        _echo(c, "alice-1", owner="alice", role="user")
        r = c.get("/v1/export", params={"owner": "alice", "role": "user"})
    assert r.status_code == 200
    unit = r.json()
    assert set(unit) == set(UNIT_KEYS)
    assert unit["kind"] == KIND_FULL
    assert unit["since"] is None
    assert unit["owner"] == "alice" and unit["role"] == "user"
    from pathlib import Path

    from contract.declaration import load_service_toml

    declaration = load_service_toml(Path(__file__).resolve().parents[2] / "service.toml")
    assert unit["service"] == declaration.name
    assert unit["version"] == declaration.version
    assert [i["text"] for i in unit["items"]] == ["alice-1"]


def test_an_export_for_one_user_role_never_contains_another_s_records():
    """Per-user isolation — the property a whole-DB backup defeats: the
    export for alice/user holds alice's user-sphere records ONLY; bob's and
    alice's builder-sphere records stay out (ADR-0021 §1/§3)."""
    svc = make_service()
    with svc.authorized() as c:
        _echo(c, "alice-user", owner="alice", role="user")
        _echo(c, "alice-builder", owner="alice", role="builder")
        _echo(c, "bob-user", owner="bob", role="user")
        alice = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        bob = c.get("/v1/export", params={"owner": "bob", "role": "user"}).json()
    assert [i["text"] for i in alice["items"]] == ["alice-user"]
    assert [i["text"] for i in bob["items"]] == ["bob-user"]
    for unit in (alice, bob):
        assert all(i["owner"] == unit["owner"] and i["role"] == unit["role"] for i in unit["items"])


def test_an_input_without_attribution_belongs_to_the_local_user_identity():
    """An ABSENT attribution is not unattributed data: it belongs to the
    machine's local user identity (the canary's default, ticket #269) — the
    export for that identity finds it."""
    svc = make_service()
    with svc.authorized() as c:
        _echo(c, "unattributed")
        unit = c.get(
            "/v1/export", params={"owner": DEFAULT_OWNER, "role": DEFAULT_ROLE}
        ).json()
    assert [i["text"] for i in unit["items"]] == ["unattributed"]


def test_an_input_with_an_unknown_declared_role_is_rejected_loudly():
    """The attribution rides every recorded input; a DECLARED role outside
    the closed vocabulary is 400, never a silently degraded record."""
    svc = make_service()
    with svc.authorized() as c:
        r = _echo(c, "hi", owner="alice", role="wizard")
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


# --- The true-incremental delta (ADR-0021 §5) ------------------------------


def test_the_delta_since_a_seq_holds_exactly_the_records_above_it():
    """`since` selects the true-incremental delta: records with seq > since
    only — the chain semantics the hourly backups ride (ADR-0021 §5)."""
    svc = make_service()
    with svc.authorized() as c:
        _echo(c, "a1", owner="alice", role="user")
        _echo(c, "a2", owner="alice", role="user")
        full = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        first_seq = full["items"][0]["seq"]
        delta = c.get(
            "/v1/export", params={"owner": "alice", "role": "user", "since": first_seq}
        ).json()
    assert delta["kind"] == KIND_DELTA
    assert delta["since"] == first_seq
    assert [i["text"] for i in delta["items"]] == ["a2"]
    # the delta holds EXACTLY the records above `since`: the full up to
    # first_seq plus this delta is the full record, no overlap (ADR-0021 §5
    # chain semantics — asserted in the replay test end to end).
    prefix = [i for i in full["items"] if i["seq"] <= first_seq]
    assert prefix + delta["items"] == full["items"]


# --- The restore surface (ADR-0021 §3/§5/§7) -------------------------------


def test_a_full_restore_replaces_the_user_role_s_records():
    """Restore of a full unit: the user+role's records become the unit's —
    per user+role granularity, other identities untouched (ADR-0021 §7)."""
    svc = make_service()
    with svc.authorized() as c:
        _echo(c, "current", owner="alice", role="user")
        _echo(c, "keep-me", owner="bob", role="user")
        unit = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        unit["items"] = [{"seq": 99, "owner": "alice", "role": "user", "text": "from-backup", "consent": "may_use"}]
        unit["through"] = 99
        r = c.post("/v1/restore", json=unit)
        assert r.status_code == 200
        assert r.json() == {"restored": True, "owner": "alice", "role": "user", "kind": "full", "items": 1}
        alice = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        bob = c.get("/v1/export", params={"owner": "bob", "role": "user"}).json()
    assert [i["text"] for i in alice["items"]] == ["from-backup"]
    assert [i["text"] for i in bob["items"]] == ["keep-me"]


def test_a_delta_that_does_not_chain_is_a_conflict_never_silently_applied():
    """The incremental chain is enforced: a delta claiming to chain from a
    seq the service does not hold is 409 `conflict` with the reason — a
    silently applied broken chain would corrupt the restore (ADR-0021 §5)."""
    svc = make_service()
    with svc.authorized() as c:
        _echo(c, "a1", owner="alice", role="user")
        unit = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        unit["kind"] = KIND_DELTA
        unit["since"] = 10**9
        unit["through"] = 10**9 + 1
        unit["items"] = [{"seq": 10**9 + 1, "owner": "alice", "role": "user", "text": "bogus", "consent": "may_use"}]
        r = c.post("/v1/restore", json=unit)
    assert r.status_code == 409
    assert r.json()["error"]["type"] == "conflict"
    assert "chains from" in r.json()["error"]["message"]


def test_a_restore_unit_from_another_service_is_refused_with_the_reason():
    """Each backup carries service metadata so the restore verifies the
    target accepts it (ADR-0021 §7): a unit exported from a different
    service is 409 naming both identities — the portability rule ("the same
    services") enforced at the surface."""
    svc = make_service()
    with svc.authorized() as c:
        unit = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        unit["service"] = "some-other-service"
        r = c.post("/v1/restore", json=unit)
    assert r.status_code == 409
    assert r.json()["error"]["type"] == "conflict"
    assert "some-other-service" in r.json()["error"]["message"]


def test_a_restore_unit_with_an_unknown_key_is_rejected_loudly():
    """The unit shape is CLOSED: an unknown key is 400 naming it (the
    closed-shape scan runs before presence checks; base item 4)."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/restore", json={"items": [], "backup_blob": "opaque"})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    assert "backup_blob" in r.json()["error"]["message"]


def test_a_restore_unit_missing_a_key_is_rejected_loudly():
    """The unit is self-contained: a missing key is 400 naming what is
    missing — a partial unit is never applied."""
    svc = make_service()
    with svc.authorized() as c:
        r = c.post("/v1/restore", json={"owner": "alice", "role": "user", "kind": "full", "items": []})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"
    assert "service" in r.json()["error"]["message"]


def test_a_full_unit_with_a_non_null_since_is_rejected_loudly():
    """The kind/`since` pair is one rule: a full chains from nothing — a
    full unit carrying a `since` is a shape error, not a silent delta."""
    svc = make_service()
    with svc.authorized() as c:
        unit = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        unit["since"] = 5
        r = c.post("/v1/restore", json=unit)
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request"


def test_a_malformed_restore_body_is_invalid_request_not_internal_error():
    """Client garbage is a client error (base item 4): non-JSON, a
    non-object body — 400, never a 500."""
    svc = make_service()
    with svc.authorized() as c:
        r1 = c.post("/v1/restore", content=b"{not json", headers={"Content-Type": "application/json"})
        r2 = c.post("/v1/restore", json=[1, 2, 3])
    assert r1.status_code == 400 and r1.json()["error"]["type"] == "invalid_request"
    assert r2.status_code == 400 and r2.json()["error"]["type"] == "invalid_request"


# --- Full + delta replay (ADR-0021 §3/§5/§7) -------------------------------


def test_full_plus_delta_replay_reproduces_the_live_state():
    """The contract's load-bearing replay: export a full, record more,
    export the delta, restore the chain onto a fresh service — the target's
    state equals the source's exactly (the self-contained-unit + chain
    promise, ADR-0021 §3/§5)."""
    source = make_service()
    with source.authorized() as c:
        _echo(c, "r1", owner="alice", role="user")
        _echo(c, "r2", owner="alice", role="user")
        full = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
        _echo(c, "r3", owner="alice", role="user")
        delta = c.get(
            "/v1/export", params={"owner": "alice", "role": "user", "since": full["through"]}
        ).json()
        live = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
    target = make_service()
    with target.authorized() as c:
        assert c.post("/v1/restore", json=full).status_code == 200
        assert c.post("/v1/restore", json=delta).status_code == 200
        replayed = c.get("/v1/export", params={"owner": "alice", "role": "user"}).json()
    assert replayed["items"] == live["items"]


# --- The surface is documented on the deterministic + agent surfaces ------


def test_the_openapi_document_describes_the_export_and_restore_operations():
    """The export/restore pair rides the deterministic surface's
    self-description: owner+role REQUIRED on the export, the closed unit
    shape on the restore, the 409 chain/identity codes."""
    svc = make_service()
    with svc.authorized() as c:
        doc = c.get("/openapi.json").json()
    export = doc["paths"]["/v1/export"]["get"]
    assert export["operationId"] == "export"
    required = [p["name"] for p in export["parameters"] if p.get("required")]
    assert required == ["owner", "role"]
    role_param = next(p for p in export["parameters"] if p["name"] == "role")
    assert role_param["schema"]["enum"] == list(ROLES)
    restore = doc["paths"]["/v1/restore"]["post"]
    assert restore["operationId"] == "restore"
    assert "409" in restore["responses"]
    schema = restore["requestBody"]["content"]["application/json"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(UNIT_KEYS)


def test_the_mcp_surface_carries_the_export_and_restore_tools_zero_drift():
    """The agent surface inherits the operations from the OpenAPI document
    (ADR-0002 §3 zero drift) — the core's `backup` orchestration (ADR-0021
    §8) drives the same shape an agent would."""
    svc = make_service()
    with svc.authorized() as c:
        tools = c.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        ).json()["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"export", "restore"} <= names


def test_the_export_and_restore_endpoints_are_bearer_gated():
    svc = make_service()
    with svc.client as c:
        r1 = c.get("/v1/export", params={"owner": "alice", "role": "user"})
        r2 = c.post("/v1/restore", json={})
    assert r1.status_code == 401 and r2.status_code == 401
