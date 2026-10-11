"""Consent-controls-map test fixtures, shared by the loader tests and the
compliance-checker tests (ticket #285).

The map documents are built from NAMED part constants, never chained
`.replace()` calls on a whole document — a no-op replace silently tests the
unmutated fixture (the lesson the security-controls fixtures already carry).
Each mutation swaps a whole block, so a rejection case can never quietly
become a happy path.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

__all__ = [
    "CONTROL_ANONYMIZE",
    "CONTROL_FLAG",
    "CONTROL_GATE",
    "SECTION_ONE",
    "SECTION_TWO",
    "good_map",
    "map_document",
    "write_map",
]

SECTION_ONE = """\
[[sections]]
id = "1"
adr = "ADR-0026 §1 (consent capture)"
"""

SECTION_TWO = """\
[[sections]]
id = "2"
adr = "ADR-0026 §2 (the two passes at the mediated boundary)"
"""

CONTROL_FLAG = """\
[[controls]]
id = "consent-flag"
adr = "ADR-0026 §1 (per-interaction consent, default may-use)"
home = "template"
seam = "the per-input consent flag on every user input surface"
"""

CONTROL_GATE = """\
[[controls]]
id = "private-secret-exclusion"
adr = "ADR-0026 §2 (pass 1 — the filter is the consent gate)"
home = "template"
seam = "the never-bypassable consent gate"
"""

CONTROL_ANONYMIZE = """\
[[controls]]
id = "core-anonymize-pass"
adr = "ADR-0026 §2 (pass 2 — data replacement at the core)"
home = "core"
seam = "the core's `datasets` capability before storing"
"""


def map_document(
    *,
    sections: str = SECTION_ONE + SECTION_TWO,
    controls: str = CONTROL_FLAG + CONTROL_GATE + CONTROL_ANONYMIZE,
) -> str:
    """A consent-controls map document from whole named blocks."""
    return sections + "\n" + controls


def write_map(tmp_path, content: str | None = None) -> Path:
    """Write a map document to a `tmp_path` fixture and return its path."""
    content = map_document() if content is None else content
    path = tmp_path / "consent_controls_map.toml"
    path.write_text(textwrap.dedent(content))
    return path


def good_map(tmp_path) -> Path:
    """A green map: two sections, each carrying controls, two homes used."""
    return write_map(tmp_path, map_document())
