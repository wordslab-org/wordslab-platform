"""The per-control verification substrate — stub collaborators (ticket #276).

The shared scaffolding the seven per-control verification lanes (#277–#283)
consume so the verification environment is built ONCE, not per control (spec
#66's Testing Decisions: collaborator hardware/OS/LAN are stubbed **at their
contract surfaces**, and controls are asserted as behavioral contracts, never
re-tested as rendering). This module ships the **stub-collaborator set**; the
posture registry — where each lane records its control's runtime stance — is
its sibling module (`tests/support/posture_registry.py`).

Three environment stubs, each the repo's single stub-factory
(`StubCollaborator`, wired via `InProcessService(extra_routes=...)`), each at
the collaborator's CONTRACT seam — never a mock of internals, never a second
mocking framework:

- `StubAgentHarness` — the agent harness's native accept/refuse surface
  (ADR-0017 §6: the harness is the execution authority; the platform does NOT
  intercept it). A test flips the verdict, so a control can be asserted to
  hold *whether the harness approves or refuses* — the backstops fire
  regardless. Vocabulary (the #275 ruling): never bare "harness" — this is
  the **stub agent-harness**; the thing it models is the AI agent harness.
- `StubSharedMount` — the host-filesystem surface: the explicitly-shared
  directory crosses, an unshared host path does not (the seam #277 exercises
  for ADR-0017 §2's default-deny mount stance).
- `StubLan` — the LAN surface: an in-scope destination is reached, an
  out-of-scope LAN wander is refused (the seam #278 exercises for §5's
  scoped-network backstop).

The stub owning-capability surfaces #275 shipped (`HOME_STUBS` in
`security_controls_check.py`) are **reused, never re-created**:
`build_stub_collaborators()` is that set extended with the three environment
stubs.

**The substrate verifies NO control.** The assertions here are the stubs'
own contract — the shape a lane will assert of the real control. A test that
asserts the isolation/network-policy/secrets/door/guardrail/TLS/authenticity
*stance* holds has crossed into a lane (#277–#283's fence), and the
coherence sweep over recorded stances is #284's.

Test-side only: production code never imports this module. Deterministic and
offline: no network, no clock, no randomness.
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from contract.base.errors import invalid_request
from tests.support.security_controls_check import HOME_STUBS, build_home_stubs
from tests.support.stubs import StubCollaborator

__all__ = [
    "AGENT_HARNESS_VERDICTS",
    "ENVIRONMENT_STUB_PATHS",
    "StubAgentHarness",
    "StubLan",
    "StubSharedMount",
    "build_environment_stubs",
    "build_stub_collaborators",
]

#: The agent harness's native verdicts (ADR-0017 §6): the harness decides
#: "may this tool run" — accept or refuse, in its own opaque format. The
#: substrate models that surface; it never overrides it.
AGENT_HARNESS_VERDICTS = ("accept", "refuse")

#: The environment stubs' paths, keyed the way the lanes name them — the
#: stable seam names the seven verification tickets cite. ONE source: the
#: classes' default `path=` reads from here, so a seam name can never drift
#: from the class that serves it.
ENVIRONMENT_STUB_PATHS: dict[str, str] = {
    "agent-harness": "/v1/agent-harness/accept-refuse",
    "host-filesystem": "/v1/host-filesystem/mount-check",
    "lan": "/v1/lan/reach-check",
}


class _RecordingStub(StubCollaborator):
    """Shared request-recording for the environment stubs: parse the JSON
    body, record the request (the `StubCollaborator` discipline), and answer
    through the subclass's `_answer` — the recording shape lives once, the
    contract answer per surface stays per class."""

    async def _serve(self, request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            payload = None
        self.requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
                "payload": payload,
            }
        )
        if not isinstance(payload, dict):
            # a malformed request is answered as malformed, never silently
            # folded into a deny — a lane must not misread its own typo as
            # the backstop firing (the base contract's 400, base item 4)
            raise invalid_request("Expected a JSON object request body.")
        return JSONResponse(self._answer(payload))

    def _answer(self, payload: object) -> dict:
        raise NotImplementedError  # each surface answers at its own contract


class StubAgentHarness(_RecordingStub):
    """The agent harness's native accept/refuse surface (ADR-0017 §6), as a
    contract seam: a tool-call request in, a verdict out, over the one HTTP
    seam. A test flips the verdict (`set_verdict`) so a lane can assert its
    control holds *even when the harness approves the call* — the platform's
    security lives in the backstops around the harness, which fire under
    either verdict.

        stub_agent_harness = StubAgentHarness()
        svc = InProcessService(extra_routes=[stub_agent_harness.route])
        # POST {"tool": ...} -> {"tool": ..., "verdict": "accept"|"refuse"}
    """

    def __init__(
        self,
        *,
        path: str = ENVIRONMENT_STUB_PATHS["agent-harness"],
        verdict: str = "accept",
    ) -> None:
        super().__init__(
            path=path,
            methods=("POST",),
            body={"verdict": _validated_verdict(verdict), "surface": "stub-agent-harness"},
        )
        self._verdict = verdict

    @property
    def verdict(self) -> str:
        """The verdict the surface currently answers with."""
        return self._verdict

    def set_verdict(self, verdict: str) -> None:
        """Flip the native verdict — the accept/refuse state a lane drives.
        A value outside the native vocabulary is a loud rejection."""
        self._verdict = _validated_verdict(verdict)
        self.body = {"verdict": self._verdict, "surface": "stub-agent-harness"}

    def _answer(self, payload: object) -> dict:
        tool = payload.get("tool") if isinstance(payload, dict) else None
        return {"tool": tool, "verdict": self._verdict}


class StubSharedMount(_RecordingStub):
    """The host-filesystem surface (ADR-0017 §2's shape): a path crossing is
    answered at the seam — the explicitly-shared directory crosses, anything
    else (the host's Documents/Desktop and friends) is denied with its
    reason. #277 asserts the real mount stance holds in this shape; the
    default-deny *mechanics* stay installer territory (#63).

        mount = StubSharedMount(shared=("/shared/workspace",))
        # POST {"path": ...} -> {"crossing": "allowed"|"denied", "reason": ...}
    """

    def __init__(
        self,
        *,
        path: str = ENVIRONMENT_STUB_PATHS["host-filesystem"],
        shared: tuple[str, ...] = ("/shared/workspace",),
    ) -> None:
        super().__init__(path=path, methods=("POST",), body={"surface": "stub-shared-mount"})
        self.shared = tuple(shared)

    def _answer(self, payload: object) -> dict:
        target = payload.get("path") if isinstance(payload, dict) else None
        if target is not None and any(
            target == root or target.startswith(root.rstrip("/") + "/")
            for root in self.shared
        ):
            answer: dict[str, Any] = {
                "crossing": "allowed",
                "reason": "explicitly shared (ADR-0017 §2: sharing is explicit only)",
            }
        else:
            answer = {
                "crossing": "denied",
                "reason": f"{target!r} is not explicitly shared — the host "
                "filesystem is unreachable by default (ADR-0017 §2)",
            }
        return answer


class StubLan(_RecordingStub):
    """The LAN surface (ADR-0017 §5's shape): a reach request is answered at
    the seam — an in-scope destination is reached, an out-of-scope LAN wander
    is refused with its reason. #278 asserts the real container network
    policy holds in this shape; the policy's mechanics stay Chat+Agents'
    (#48).

        lan = StubLan(in_scope=("pypi.org", "github.com"))
        # POST {"address": ...} -> {"access": "allowed"|"denied", "reason": ...}
    """

    def __init__(
        self,
        *,
        path: str = ENVIRONMENT_STUB_PATHS["lan"],
        in_scope: tuple[str, ...] = ("pypi.org", "github.com"),
    ) -> None:
        super().__init__(path=path, methods=("POST",), body={"surface": "stub-lan"})
        self.in_scope = tuple(in_scope)

    def _answer(self, payload: object) -> dict:
        address = payload.get("address") if isinstance(payload, dict) else None
        if address in self.in_scope:
            answer: dict[str, Any] = {
                "access": "allowed",
                "reason": "in scoped need (ADR-0017 §5: default-allow-but-scoped-to-need)",
            }
        else:
            answer = {
                "access": "denied",
                "reason": f"{address!r} is an out-of-scope destination — no "
                "unrestricted host or LAN access (ADR-0017 §5)",
            }
        return answer


def _validated_verdict(verdict: str) -> str:
    if verdict not in AGENT_HARNESS_VERDICTS:
        raise ValueError(
            f"{verdict!r} is not a native agent-harness verdict — the agent "
            f"harness decides accept or refuse (ADR-0017 §6): "
            f"{AGENT_HARNESS_VERDICTS}"
        )
    return verdict


def build_environment_stubs() -> dict[str, StubCollaborator]:
    """The three environment stubs, keyed by seam name — deterministic and
    offline, each a `StubCollaborator` served over the one HTTP seam."""
    return {
        "agent-harness": StubAgentHarness(),
        "host-filesystem": StubSharedMount(),
        "lan": StubLan(),
    }


def build_stub_collaborators() -> dict[str, StubCollaborator]:
    """The full collaborator set the lanes consume: #275's stub
    owning-capability surfaces (`HOME_STUBS`, reused via `build_home_stubs`
    — extended, never forked) plus the three environment stubs."""
    return {**build_home_stubs(), **build_environment_stubs()}
