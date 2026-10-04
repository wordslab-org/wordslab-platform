"""Family 1 — LLM & agents inference (ADR-0001 §Families.1).

The OpenAI Responses API by reference at `POST /v1/responses`. This block
runs only when `families/manifest.toml` lists family "1" (the test-side
manifest, ticket #70). It is the family conformance seam: red until the
family machinery lands (#76) — a service that lists family 1 without
implementing the surface must fail this suite, never pass silently.

Conformance asserts contract shapes at the seam, not engine internals
(spec #46 §Testing Decisions). `gated_client` refuses to let any test pass
while the base contract is violated on the same seam (the never-bypassable
red gate).
"""

import pytest

from tests.contract.runner import contract_family, failures

pytestmark = contract_family("1")

# A minimal Responses-API request by reference (ADR-0001 family 1: follow
# upstream OpenAI shapes, pinned to a reference date).
STUB_REQUEST = {"model": "stub-model", "input": "ping"}


@pytest.fixture()
def gated_client(client):
    # The never-bypassable red gate: the block cannot start while the base
    # contract is violated on its own seam — probed with the documented 404
    # error body (base item 4) through the authorized client.
    problems = failures(client.get("/v1/__conformance_probe__"), error_type="not_found")
    assert problems == [], f"base contract violated on the family seam: {problems}"
    return client


def test_post_v1_responses_returns_the_responses_body(gated_client):
    r = gated_client.post("/v1/responses", json=STUB_REQUEST)
    assert r.status_code == 200
    body = r.json()
    assert body["id"].startswith("resp_")
    assert body["object"] == "response"
    assert isinstance(body["output"], list)
    assert r.headers["X-Request-Id"]  # base item 4 — every response


def test_post_v1_responses_reports_usage(gated_client):
    # Base item 8 — usage on resource-consuming operations; the unit is
    # family-defined (family 1: tokens).
    r = gated_client.post("/v1/responses", json=STUB_REQUEST)
    assert "usage" in r.json()
