"""The verification substrate's stub-collaborator tests (ticket #276 AC 1/2/5).

The substrate stands up the environment the per-control verification lanes
(#277–#283) exercise their controls against — a **stub agent-harness** (the
agent harness's native accept/refuse surface, ADR-0017 §6), a **stub shared
mount** and a **stub LAN** (the host-OS / LAN surfaces the isolation and
network-policy lanes wander) — reusing the placement checker's stub
owning-capability surfaces (#275's `HOME_STUBS`), never re-creating them.

Every stub sits at the collaborator's CONTRACT surface — a route served over
the one HTTP seam via `InProcessService(extra_routes=...)` — never a mock of
internals, never a second mocking framework (#66's Testing Decisions). The
substrate verifies NO control: the backstop assertions here are the stubs'
own contract (the shape a lane will assert of the real control), not the
isolation or network-policy stance itself — that is #277/#278's fence.

Vocabulary: never bare "harness" — the artifact is the **stub agent-harness**
(the agent harness it models is ADR-0017 §6's).
"""

from __future__ import annotations

import pytest

from tests.support.security_controls_check import HOME_STUBS, build_home_stubs
from tests.support.stubs import StubCollaborator
from tests.support.test_server import InProcessService
from tests.support.verification_substrate import (
    StubAgentHarness,
    StubLan,
    StubSharedMount,
    build_environment_stubs,
    build_stub_collaborators,
)

# ------------------------------------------------- the stub agent-harness


def test_the_stub_agent_harness_answers_its_native_accept_refuse_surface():
    """#276 AC 1: the stub agent-harness exposes the agent harness's native
    accept/refuse contract surface — a tool-call request in, a verdict out —
    asserted over the one HTTP seam."""
    harness = StubAgentHarness(verdict="accept")
    svc = InProcessService(api_keys=["sk-correct"], extra_routes=[harness.route])
    try:
        with svc.authorized() as client:
            response = client.post(harness.path, json={"tool": "shell"})
            assert response.status_code == 200
            assert response.json() == {"tool": "shell", "verdict": "accept"}
            assert harness.requests[-1]["payload"] == {"tool": "shell"}
    finally:
        svc.close()


def test_the_verdict_is_flippable_and_the_flip_shows_at_the_contract_surface():
    """The verdict a test can flip: the SAME surface answers `refuse` after
    the flip — the accept/refuse state is the surface's contract, not test
    scaffolding read from a private attribute."""
    harness = StubAgentHarness(verdict="accept")
    svc = InProcessService(api_keys=["sk-correct"], extra_routes=[harness.route])
    try:
        with svc.authorized() as client:
            first = client.post(harness.path, json={"tool": "shell"})
            harness.set_verdict("refuse")
            second = client.post(harness.path, json={"tool": "shell"})
    finally:
        svc.close()
    assert first.json()["verdict"] == "accept"
    assert second.json()["verdict"] == "refuse"


def test_the_agent_harness_verdict_vocabulary_is_closed():
    """The native verdict is accept or refuse — anything else is a loud
    rejection naming the offending value."""
    harness = StubAgentHarness()
    with pytest.raises(ValueError, match="not a native agent-harness verdict"):
        harness.set_verdict("maybe")


# ------------------------------------------ the stub host-OS / LAN surfaces


def test_the_stub_shared_mount_allows_only_explicitly_shared_paths():
    """#276 AC 2: a test exercises a shared-mount crossing against the seam —
    the explicitly-shared directory crosses, an unshared host path does not
    (the shape #277 asserts of the real mount stance)."""
    mount = StubSharedMount(shared=("/shared/workspace",))
    svc = InProcessService(api_keys=["sk-correct"], extra_routes=[mount.route])
    try:
        with svc.authorized() as client:
            shared = client.post(
                mount.path, json={"path": "/shared/workspace/notes.md"}
            )
            host = client.post(
                mount.path, json={"path": "/Users/anyone/Documents/secret.txt"}
            )
    finally:
        svc.close()
    assert shared.json()["crossing"] == "allowed"
    assert host.json()["crossing"] == "denied"
    assert "not explicitly shared" in host.json()["reason"]


def test_the_stub_lan_denies_an_out_of_scope_lan_wander():
    """#276 AC 2: an out-of-scope LAN access is exercised against the seam —
    a wander to another LAN machine is refused at the surface, an in-scope
    destination is reached (the shape #278 asserts of the real policy)."""
    lan = StubLan(in_scope=("pypi.org", "github.com"))
    svc = InProcessService(api_keys=["sk-correct"], extra_routes=[lan.route])
    try:
        with svc.authorized() as client:
            wander = client.post(lan.path, json={"address": "192.168.1.7"})
            scoped = client.post(lan.path, json={"address": "pypi.org"})
    finally:
        svc.close()
    assert wander.json()["access"] == "denied"
    assert "out-of-scope" in wander.json()["reason"]
    assert scoped.json()["access"] == "allowed"


# ------------------------- the substrate's own behavioral contract (AC 1)


def test_the_stub_backstops_deny_whether_the_agent_harness_approves_or_refuses():
    """#276 AC 1's behavioral contract: a control can be asserted to hold
    whether the agent harness approves or refuses the call — the stub
    backstops deny the mount crossing and the LAN wander under BOTH verdicts.

    This is the scaffolding's contract (ADR-0017 §6's shape: the platform
    never intercepts the agent harness; the backstops fire regardless), not
    the isolation or network-policy stance — those lanes (#277/#278) assert
    the real controls hold in this shape."""
    harness = StubAgentHarness()
    mount = StubSharedMount(shared=("/shared/workspace",))
    lan = StubLan(in_scope=("pypi.org",))
    svc = InProcessService(
        api_keys=["sk-correct"],
        extra_routes=[harness.route, mount.route, lan.route],
    )
    try:
        with svc.authorized() as client:
            for verdict in ("accept", "refuse"):
                harness.set_verdict(verdict)
                call = client.post(harness.path, json={"tool": "shell"})
                assert call.json()["verdict"] == verdict
                crossing = client.post(
                    mount.path, json={"path": "/Users/anyone/Documents/x"}
                )
                wander = client.post(lan.path, json={"address": "10.0.0.9"})
                assert crossing.json()["crossing"] == "denied", verdict
                assert wander.json()["access"] == "denied", verdict
    finally:
        svc.close()


# --------------------------- contract-surface discipline + determinism (AC 5)


def test_every_stub_is_a_stub_collaborator_served_over_the_one_http_seam():
    """#276 AC 5: collaborator hardware/OS/LAN are stubbed ONLY at contract
    surfaces — every stub is the repo's single stub-factory
    (`StubCollaborator`), wired via `extra_routes`, answering over its
    `/v1/...` path with the base contract holding on every response."""
    from tests.contract.runner import failures

    stubs = build_environment_stubs()
    assert set(stubs) == {"agent-harness", "host-filesystem", "lan"}
    assert all(isinstance(stub, StubCollaborator) for stub in stubs.values())
    svc = InProcessService(
        api_keys=["sk-correct"], extra_routes=[s.route for s in stubs.values()]
    )
    try:
        with svc.authorized() as client:
            probe = {
                "agent-harness": {"tool": "shell"},
                "host-filesystem": {"path": "/shared/workspace/a"},
                "lan": {"address": "pypi.org"},
            }
            for name, stub in stubs.items():
                response = client.post(stub.path, json=probe[name])
                assert response.status_code == 200, name
                assert failures(response) == [], name
                assert stub.requests[-1]["path"] == stub.path
    finally:
        svc.close()


def test_the_substrate_reuses_the_placement_checkers_home_stubs_never_reforks_them():
    """The full collaborator set is #275's stub owning-capability surfaces
    PLUS the environment stubs — `HOME_STUBS` is extended, never re-created
    (#276's scope fence against the placement checker)."""
    collaborators = build_stub_collaborators()
    home_stubs = build_home_stubs()
    assert set(collaborators) == set(HOME_STUBS) | {
        "agent-harness",
        "host-filesystem",
        "lan",
    }
    for home, stub in home_stubs.items():
        assert collaborators[home].path == stub.path
        assert collaborators[home].body == stub.body


def test_the_substrate_is_deterministic_and_offline():
    """Two builds answer identically — no network, no clock, no randomness
    (#66's Testing Decisions)."""
    first, second = build_environment_stubs(), build_environment_stubs()
    assert [s.path for s in first.values()] == [s.path for s in second.values()]
    harness = StubAgentHarness()
    assert harness.body == StubAgentHarness().body
