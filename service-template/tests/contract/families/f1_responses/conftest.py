"""Family 1's conformance seam — the vendored module over a stub engine.

The family block drives the REAL family module (`contract/families/
family_1_responses/`) over the in-process test server: parse → engine seam →
normalized body, and the same pipeline streamed as SSE. Only the ENGINE is a
stub (`StubEngine`, or a scripted `ScenarioEngine` for shapes the canned stub
cannot produce) — the contract machinery under test is the shipped one, and
mounting it here is exactly how a model-backed capability mounts it.

`gated_client` is the shared never-bypassable red gate (base contract honored
on the same seam). It is built locally rather than taken from the suite's
`tests/contract/conftest.py` because that fixture's app mounts only the
template's own capabilities — the family surface is wired by this block.

Worth stating plainly: this block proves the vendored family machinery still
satisfies ADR-0001 §Families.1. A service's own suite proves the service
*chose* to mount it; that is the capability's test, not the contract's.
"""

from __future__ import annotations

import pytest

from contract.families.family_1_responses import responses_routes
from tests.contract.runner import failures
from tests.support.stubs import StubEngine
from tests.support.test_server import InProcessService


class ScenarioEngine:
    """An engine with a scripted reply — for the shapes the canned stub does
    not produce (a refusal, a citation, a function call, a malformed reply).
    Records every call in the stub-factory's shape (`{"operation", "request"}`),
    so an assertion written against `StubEngine.calls` reads the same here."""

    def __init__(self, reply):
        self.reply = reply
        self.calls: list[dict] = []

    def responses(self, request: dict) -> dict:
        self.calls.append({"operation": "responses", "request": request})
        return self.reply


@pytest.fixture()
def make_gated_client():
    """Build an in-process service with the family-1 surface mounted on `engine`,
    then apply the base-contract red gate before any test body runs."""
    services: list[InProcessService] = []

    def _make(engine, **route_kwargs):
        svc = InProcessService(extra_routes=[*responses_routes(engine, **route_kwargs)])
        services.append(svc)
        client = svc.authorized()
        problems = failures(client.get("/v1/__conformance_probe__"), error_type="not_found")
        assert problems == [], f"base contract violated on the family seam: {problems}"
        return client

    yield _make
    for svc in services:
        svc.close()


@pytest.fixture()
def gated_client(make_gated_client):
    return make_gated_client(StubEngine())
