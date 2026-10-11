"""Contract tests for the installer API and the phase-2 TUI shell.

Seam: the installer-API function surface (run/stream/interpret) driven against stub commands —
no HTTP surface exists for the installer (it is not a base-contract service, ADR-0003 §1).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from installer_api import ProgressInterpreter, ScriptStep, run_all, run_step
import tui


def _popen(command, **kwargs):  # noqa: ANN001 - mirror subprocess.Popen signature
    return subprocess.Popen(command, **kwargs)


def test_run_step_streams_and_mirrors_stdout_line_by_line():
    mirror: list[str] = []
    step = ScriptStep(1, "Greets", ("echo", "hello"))

    result = run_step(step, mirror.append, popen=_popen)

    assert result.success
    assert result.stdout_lines == ("hello",)
    assert "[01] Greets" in mirror
    assert "[01] hello" in mirror


def test_run_step_mirrors_stderr_loudly():
    mirror: list[str] = []
    step = ScriptStep(2, "Warns", ("sh", "-c", "echo oops >&2"))

    result = run_step(step, mirror.append, popen=_popen)

    assert result.success
    assert result.stderr_lines == ("oops",)
    assert "[02] ! oops" in mirror


def test_run_step_reports_failure_loudly():
    mirror: list[str] = []
    step = ScriptStep(3, "Fails", ("sh", "-c", "exit 7"))

    result = run_step(step, mirror.append, popen=_popen)

    assert result.exit_code == 7
    assert not result.success
    assert any("FAILED (exit 7)" in line for line in mirror)


def test_run_all_stops_at_first_failure():
    mirror: list[str] = []
    steps = (
        ScriptStep(1, "Fails", ("sh", "-c", "exit 3")),
        ScriptStep(2, "Never runs", ("echo", "should not appear")),
    )

    results = run_all(steps, mirror.append, popen=_popen)

    assert len(results) == 1
    assert "should not appear" not in "".join(mirror)


def test_progress_interpreter_emits_once_per_rule_and_keeps_unknown_lines():
    mirror: list[str] = []
    step = ScriptStep(1, "Streams", ("sh", "-c", "printf 'Downloading x\\nDownloading y\\nother\\n'"))

    run_step(step, mirror.append, ProgressInterpreter((("Downloading", "downloading..."),)), popen=_popen)

    assert mirror.count("[01] -> downloading...") == 1  # first match only
    assert "[01] Downloading y" in mirror  # unknown lines mirrored raw, never dropped
    assert "[01] other" in mirror


def test_interpreter_returns_none_for_unknown_lines():
    interp = ProgressInterpreter((("Verifying", "verifying..."),))
    assert interp.interpret("Verifying checksum") == "verifying..."
    assert interp.interpret("Verifying again") is None  # once per rule
    assert interp.interpret("unrelated") is None


def test_parameters_round_trip_from_the_phase1_wizard(tmp_path: Path):
    params_file = tmp_path / "wordslab-install-parameters.json"
    params_file.write_text(json.dumps({"data_disk": "D:\\", "join_lan": "y"}))

    params = tui.load_parameters(params_file)

    assert params == {"data_disk": "D:\\", "join_lan": "y"}


def test_web_handoff_is_an_address_not_a_process_switch():
    mirror: list[str] = []

    instruction = tui.web_handoff("https://wordslab.local/", mirror.append)

    assert "https://wordslab.local/" in instruction
    assert any("are up: https://wordslab.local/" in line for line in mirror)


def test_tui_main_runs_the_numbered_scripts_and_hands_off(tmp_path: Path, capsys):
    params_file = tmp_path / "params.json"
    params_file.write_text(json.dumps({"data_disk": "/data"}))

    rc = tui.main(["--parameters", str(params_file), "--dashboard-url", "https://wordslab.local/"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "[01]" in out and "[06]" in out  # all six numbered slots visible
    assert "data_disk = /data" in out
    assert "Open https://wordslab.local/" in out


def test_tui_main_stops_loudly_on_a_failing_script(tmp_path: Path, capsys, monkeypatch):
    params_file = tmp_path / "params.json"
    params_file.write_text(json.dumps({"data_disk": "/data"}))
    monkeypatch.setattr(
        tui, "BOOTSTRAP_STEPS",
        (ScriptStep(1, "Fails", ("sh", "-c", "exit 9")),) + tui.BOOTSTRAP_STEPS[1:],
    )

    rc = tui.main(["--parameters", str(params_file)])

    out = capsys.readouterr().out
    assert rc == 1
    assert "FAILED (exit 9)" in out
    assert "Open https://wordslab.local/" not in out  # no handoff after a failure
