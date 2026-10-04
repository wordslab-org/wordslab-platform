"""The conformance suite's selection + red-gate machinery (ticket #70; spec
#46 §Testing Decisions — "the conformance runner … always runs base, and
runs a family's tests only when declared").

Imported by `tests/contract/conftest.py`:

- `declared_families()` reads `families/manifest.toml` — explicit data next
  to the tests, no probing, no magic (the maintainer ruling on #70: families
  are not declared anywhere, ADR-0031 §2). An unknown family number, a
  listed family with no block on disk, or a malformed manifest fails the
  suite loudly — a declared family must never be silently skipped.
- `contract_family(number)` marks a family conformance block; the conftest
  deselects marked items whose family the manifest does not list. Base tests
  carry no mark — they always run.
- `failures(response, error_type=None)` collects observed base-contract
  violations on one response; a family block's `gated_client` fixture turns
  a non-empty list into a red gate, so no family test can pass while the
  base contract is violated on the same seam.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

FAMILIES_DIR = Path(__file__).resolve().parent / "families"
MANIFEST = FAMILIES_DIR / "manifest.toml"

# The ADR-0001 family numbers — the manifest's only legal entries.
KNOWN_FAMILIES = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9"})


def declared_families() -> list[str]:
    """The family numbers the manifest lists, validated loudly."""
    data = tomllib.loads(MANIFEST.read_text())
    declared = data.get("families", [])
    if not isinstance(declared, list) or not all(isinstance(f, str) for f in declared):
        raise pytest.UsageError(
            "families/manifest.toml: `families` must be a list of ADR-0001 "
            'family-number strings ("1".."9") — e.g. families = ["1", "5"].'
        )
    unknown = [f for f in declared if f not in KNOWN_FAMILIES]
    if unknown:
        raise pytest.UsageError(
            f"families/manifest.toml lists unknown family/families {unknown!r} — "
            "not among ADR-0001's nine family numbers "
            f"{sorted(KNOWN_FAMILIES)!r}. The suite refuses to silently skip them."
        )
    on_disk = {d.name.split("_", 1)[0][1:] for d in FAMILIES_DIR.iterdir() if d.is_dir()}
    missing = [f for f in declared if f not in on_disk]
    if missing:
        raise pytest.UsageError(
            f"families/manifest.toml lists family/families {missing!r} but no "
            f"families/f<N>_<slug>/ block exists for them — a declared family "
            "must never be silently skipped. Restore the block or fix the manifest."
        )
    return list(declared)


def contract_family(number: str):
    """Mark a family conformance block: `pytestmark = contract_family("1")`."""
    return pytest.mark.contract_family(number)


def failures(response, error_type: str | None = None) -> list[str]:
    """Observed violations of the base contract on one response.

    Checks what the base contract fixes for every response: the
    `X-Request-Id` header (item 4), the JSON-object body (item 1), the error
    body shape `{"error": {"type", "message", "resource"?}, "request_id"}`
    with `request_id` matching the header when an error body is present, and
    — with `error_type` — that the error body carries that taxonomy type.

    A family block's `gated_client` fixture collects these and goes red when
    the list is non-empty (the never-bypassable red gate); it asserts on
    specifics separately.
    """
    problems: list[str] = []
    if response.headers.get("X-Request-Id") is None:
        problems.append("X-Request-Id header missing (base item 4)")
    try:
        body = response.json()
    except ValueError:
        problems.append("response body is not JSON (base item 1)")
        return problems
    if not isinstance(body, dict):
        problems.append("response body is not a JSON object (base item 1)")
        return problems
    if "error" in body:
        error = body["error"]
        if not (isinstance(error, dict) and error.get("type") and error.get("message")):
            problems.append(
                'error body is not {"type", "message", "resource"?} (base item 4)'
            )
        elif error_type is not None and error.get("type") != error_type:
            problems.append(f"error type {error.get('type')!r} != {error_type!r} (base item 4)")
    elif error_type is not None:
        problems.append(f"response carries no error body; expected {error_type!r} (base item 4)")
    request_id = body.get("request_id")
    if request_id is not None and request_id != response.headers.get("X-Request-Id"):
        problems.append("request_id does not match the X-Request-Id header (base item 4)")
    return problems
