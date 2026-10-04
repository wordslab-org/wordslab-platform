"""The vendored conformance suite (ticket #70; spec #46 §Testing Decisions).

The base-contract block always runs (`test_auth/errors/health/idempotency/
pagination/stubs` — the machinery over real HTTP, ticket #69's slices plus
#70's stub-factory). Family conformance blocks live in `families/f<N>_<slug>/`
and run only when the **test-side manifest** (`families/manifest.toml`) lists
that family — the maintainer ruling on #70: families are NOT declared in
`service.toml` (ADR-0031 §2); the service's own tests declare which family
blocks they exercise, as explicit data next to the tests, no probing, no
magic. The selection machinery is `runner.py`.
"""

import sys
from pathlib import Path

import pytest

# The template's placeholder package directory is `<service>` — not importable
# by name. The copy-to-start ritual renames it (service-template/CONTRIBUTING.md);
# for the template's own tests, put its parent on sys.path so `contract` is a
# plain package.
TEMPLATE_SRC = Path(__file__).resolve().parents[2] / "src" / "<service>"
sys.path.insert(0, str(TEMPLATE_SRC))

from tests.support.test_server import InProcessService  # noqa: E402,F401

from .runner import declared_families  # noqa: E402

_declared = declared_families()


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "contract_family(number): a family conformance block; runs only when "
        "families/manifest.toml lists the family (ticket #70)",
    )


def pytest_collection_modifyitems(config, items) -> None:
    """Family conformance blocks are deselected unless the manifest lists
    them (spec #46 story 16 — via the test-side manifest). Base tests, which
    carry no mark, always run."""
    selected, deselected = [], []
    for item in items:
        mark = item.get_closest_marker("contract_family")
        if mark is None:
            selected.append(item)
            continue
        if not mark.args:
            raise pytest.UsageError(
                f"{item.nodeid}: contract_family requires the family number — "
                'use contract_family("1") … contract_family("9")'
            )
        if mark.args[0] in _declared:
            selected.append(item)
        else:
            deselected.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


# --- base-contract fixtures -------------------------------------------------

@pytest.fixture()
def service():
    svc = InProcessService()
    yield svc
    svc.close()


@pytest.fixture()
def client(service):
    return service.authorized()
