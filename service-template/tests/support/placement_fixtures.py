"""Placement-map test fixtures, shared by the loader tests and the harness
tests (ticket #275).

The map documents are built from NAMED part constants, never chained
`.replace()` calls on a whole document — a no-op replace silently tests the
unmutated fixture (a lesson the template's loader tests already carry). Each
mutation swaps a whole block, so a rejection case can never quietly become a
happy path.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

__all__ = [
    "CONTROL_ONE",
    "CONTROL_TWO",
    "FRAME_ALPHA",
    "FRAME_BETA",
    "good_map",
    "map_document",
    "write_map",
]

FRAME_ALPHA = """\
[[frames]]
id = "alpha"
adr = "ADR-0017 §1.1 (compromised/malicious agent or harness)"
"""

FRAME_BETA = """\
[[frames]]
id = "beta"
adr = "ADR-0017 §1.2 (accidental data leakage)"
"""

CONTROL_ONE = """\
[[controls]]
id = "control-one"
adr = "ADR-0017 §2"
home = "core"
seam = "the keys/secrets capabilities"
backs = ["alpha"]
"""

CONTROL_TWO = """\
[[controls]]
id = "control-two"
adr = "ADR-0017 §7"
home = "connectors"
seam = "the audited door"
backs = ["beta"]
"""


def map_document(
    *,
    frames: str = FRAME_ALPHA + FRAME_BETA,
    controls: str = CONTROL_ONE + CONTROL_TWO,
) -> str:
    """A placement map document from whole named blocks."""
    return frames + "\n" + controls


def write_map(tmp_path, content: str | None = None) -> Path:
    """Write a map document to a `tmp_path` fixture and return its path."""
    content = map_document() if content is None else content
    path = tmp_path / "placement_map.toml"
    path.write_text(textwrap.dedent(content))
    return path


def good_map(tmp_path) -> Path:
    """A green map: two frames, each backed, one control per home."""
    return write_map(tmp_path, map_document())
