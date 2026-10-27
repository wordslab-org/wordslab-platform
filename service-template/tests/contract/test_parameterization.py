"""The conformance-of-the-conformance: the suite's own guarantees, proven on
a fresh copy of `service-template/` — exactly what the copy-to-start ritual
produces (CONTRIBUTING.md step 1).

Ticket #70 acceptance:
- the suite is parameterized by the **test-side manifest**
  (`tests/contract/families/manifest.toml` — the maintainer ruling on #70:
  families are NOT declared in `service.toml`, ADR-0031 §2; the service's
  own tests declare which family blocks they exercise, as explicit data next
  to the tests, no probing, no magic);
- base always runs; a family block runs only when the manifest lists it;
- deleting an unlisted family's modules cannot break the suite; a listed
  family with no block, or an unknown/malformed manifest entry, fails the
  suite loudly.

Every case runs the vendored suite as a subprocess against a fresh copy —
one seam, offline, deterministic.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).resolve().parents[2]
FAMILIES_DIR = TEMPLATE_ROOT / "tests" / "contract" / "families"

# The base block — the files the suite ALWAYS runs. The fresh-copy subprocess
# is scoped to these (plus `families/` for the selection probes): the
# template-self meta files (this one, `test_declaration_files.py`) assert on
# the template AT THE REPO ROOT and are meaningless inside a copy — they are
# not part of a copied service's always-run suite.
BASE_FILES = [
    "tests/contract/test_auth.py",
    "tests/contract/test_errors.py",
    "tests/contract/test_health.py",
    "tests/contract/test_idempotency.py",
    "tests/contract/test_pagination.py",
    "tests/contract/test_stubs.py",
]


@pytest.fixture()
def copied_template(tmp_path):
    """A copy of `service-template/` as the copy-to-start ritual produces it."""
    dst = tmp_path / "service"
    shutil.copytree(
        TEMPLATE_ROOT,
        dst,
        ignore=shutil.ignore_patterns(".venv", ".pytest_cache", "__pycache__"),
    )
    return dst


def manifest(copied: Path) -> list[str]:
    data = tomllib.loads((copied / "tests/contract/families/manifest.toml").read_text())
    return data.get("families", [])


def write_manifest(copied: Path, families: list[str] | str) -> None:
    if isinstance(families, str):  # a deliberately malformed manifest
        body = f"families = {families!r}\n"
    else:
        items = ", ".join(f'"{f}"' for f in families)
        body = f"families = [{items}]\n"
    (copied / "tests/contract/families/manifest.toml").write_text(body)


def block_dirs(copied: Path) -> list[str]:
    return sorted(d.name for d in (copied / "tests/contract/families").iterdir() if d.is_dir())


def run_suite(copied: Path, *args: str) -> subprocess.CompletedProcess:
    # The same interpreter this suite runs under (the template venv), so the
    # subprocess needs no network and no extra installation. The args always
    # name files/dirs explicitly — never this meta module — so a copied
    # suite's run cannot re-run the meta-tests' own subprocesses.
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", *args],
        cwd=copied,
        capture_output=True,
        text=True,
        timeout=300,
    )


def run_base(copied: Path) -> subprocess.CompletedProcess:
    return run_suite(copied, *BASE_FILES)


def collect_families(copied: Path) -> subprocess.CompletedProcess:
    return run_suite(copied, "--collect-only", "tests/contract/families")


# pytest's exit codes a collect-only probe may legitimately return: 0 (nodes
# collected) or 5 ("no tests collected" — the probe's every node deselected,
# which IS the empty-manifest behavior under test).
COLLECTION_EXIT_CODES = {0, 5}

# The manifest this tree ships with. Two guarantees below are TEMPLATE facts
# about the manifest as it ships EMPTY; a service copy that declares the
# families it implements (CONTRIBUTING.md step 5) is no longer the template, so
# they skip there rather than failing the copy's suite.
SHIPPED_MANIFEST = manifest(TEMPLATE_ROOT)

requires_empty_shipped_manifest = pytest.mark.skipif(
    SHIPPED_MANIFEST != [],
    reason="running inside a copy that declares families — the empty shipped manifest is a template fact",
)


@requires_empty_shipped_manifest
def test_the_manifest_ships_as_explicit_test_side_data(copied_template):
    # Explicit data next to the tests (maintainer ruling on #70) — the
    # template declares no family yet, but the reference blocks exist.
    assert manifest(copied_template) == []
    assert len(block_dirs(copied_template)) >= 2  # two blocks prove selection


def test_base_suite_passes_out_of_the_box_on_a_fresh_copy(copied_template):
    result = run_base(copied_template)
    assert result.returncode == 0, result.stdout + result.stderr


@requires_empty_shipped_manifest
def test_no_family_tests_collected_when_the_manifest_is_empty(copied_template):
    collected = collect_families(copied_template)
    assert collected.returncode in COLLECTION_EXIT_CODES, collected.stdout + collected.stderr
    for block in block_dirs(copied_template):
        assert f"families/{block}" not in collected.stdout


def test_a_listed_block_runs_and_is_red_until_the_machinery_lands(copied_template):
    # The selection MECHANISM: a listed block is collected AND executed. Proved
    # with a synthetic block rather than a real family's red-on-purpose state —
    # which families still lack machinery changes with every stage-0 ticket
    # (#76 shipped family 1; #77–#84 follow), so anchoring on a real block
    # would mean rewriting this guard each time.
    probe = copied_template / "tests" / "contract" / "families" / "f9_red_probe"
    probe.mkdir()
    (probe / "__init__.py").write_text("")
    (probe / "test_conformance.py").write_text(
        "import pytest\n"
        "from tests.contract.runner import contract_family\n"
        '\npytestmark = contract_family("9")\n'
        "\n"
        "\n"
        "def test_deliberately_red():\n"
        "    assert False, 'the red probe ran'\n"
    )
    write_manifest(copied_template, ["9"])
    collected = collect_families(copied_template)
    assert "families/f9_red_probe" in collected.stdout
    failed = run_suite(copied_template, "tests/contract/families/f9_red_probe")
    assert failed.returncode != 0
    assert "the red probe ran" in failed.stdout  # assertion-red, not a collection crash


# Family blocks whose machinery this template actually ships. Each family
# ticket (#76–#84) adds its own number here in the same commit that lands the
# module — that is what keeps "listed family + shipped machinery = GREEN"
# honest instead of aspirational.
SHIPPED_FAMILIES: set[str] = {"1"}


@pytest.mark.parametrize("family", sorted(SHIPPED_FAMILIES))
def test_a_listed_block_with_shipped_machinery_is_green(copied_template, family):
    block = next(b for b in block_dirs(copied_template) if b.startswith(f"f{family}_"))
    write_manifest(copied_template, [family])
    result = run_suite(copied_template, f"tests/contract/families/{block}")
    assert result.returncode == 0, result.stdout + result.stderr


def test_an_unlisted_block_does_not_run(copied_template):
    blocks = block_dirs(copied_template)
    write_manifest(copied_template, [blocks[0].split("_", 1)[0][1:]])
    collected = collect_families(copied_template)
    assert f"families/{blocks[0]}" in collected.stdout
    assert f"families/{blocks[1]}" not in collected.stdout


def test_deleting_an_unlisted_block_does_not_break_the_suite(copied_template):
    # CONTRIBUTING.md step 5: keep only the family blocks you exercise.
    victim = block_dirs(copied_template)[1]  # unlisted — the manifest is empty
    shutil.rmtree(copied_template / "tests/contract/families" / victim)
    assert run_base(copied_template).returncode == 0
    assert collect_families(copied_template).returncode in COLLECTION_EXIT_CODES


def test_a_listed_block_with_no_directory_fails_the_suite_loudly(copied_template):
    # A declared family must never be silently skipped.
    victim = block_dirs(copied_template)[0]
    write_manifest(copied_template, [victim.split("_", 1)[0][1:]])
    shutil.rmtree(copied_template / "tests/contract/families" / victim)
    result = run_base(copied_template)
    assert result.returncode != 0
    assert "silently skipped" in result.stdout + result.stderr


def test_an_unknown_family_number_fails_the_suite_loudly(copied_template):
    write_manifest(copied_template, ["banana"])
    result = run_base(copied_template)
    assert result.returncode != 0
    assert "banana" in result.stdout + result.stderr


def test_a_malformed_manifest_fails_the_suite_loudly(copied_template):
    write_manifest(copied_template, "1")  # a string, not a list of strings
    result = run_base(copied_template)
    assert result.returncode != 0
    assert "list of ADR-0001" in result.stdout + result.stderr


def test_a_missing_manifest_fails_the_suite_loudly(copied_template):
    # The suite refuses to run without its parameterization data — a guided
    # UsageError, not a traceback.
    (copied_template / "tests/contract/families/manifest.toml").unlink()
    result = run_base(copied_template)
    assert result.returncode != 0
    assert "refuses to run" in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
