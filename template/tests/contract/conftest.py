"""Smoke tests: the in-process helper boots the template service and the base
contract is observable over real HTTP (ticket #69 acceptance — the seam, not
internals; spec #46 §Testing Decisions).

The full family-parameterized conformance suite is ticket #70; these smoke
tests are the minimal proof that the machinery is testable by the helper from
day one.
"""

import sys
from pathlib import Path

import pytest

# The template's placeholder package directory is `<service>` — not importable
# by name. The copy-to-start ritual renames it (template/CONTRIBUTING.md);
# for the template's own tests, put its parent on sys.path so `contract` is a
# plain package.
TEMPLATE_SRC = Path(__file__).resolve().parents[2] / "src" / "<service>"
sys.path.insert(0, str(TEMPLATE_SRC))

from tests.support.test_server import InProcessService, stub_api_key  # noqa: E402


@pytest.fixture()
def service():
    svc = InProcessService()
    yield svc
    svc.close()


@pytest.fixture()
def client(service):
    return service.authorized()
