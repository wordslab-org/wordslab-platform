"""Contract tests for the installer API and the phase-2 TUI shell.

Seam: the installer-API function surface (run/stream/interpret) driven against stub commands —
no HTTP surface exists for the installer (it is not a base-contract service, ADR-0003 §1).
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from installer_api import ProgressInterpreter, ScriptStep, run_all, run_step
import tui


def test_run_step_streams_and_mirrors_stdout_line_by_line():
    mirror: list[str] = []
    step = ScriptStep(1, "Greets", ("echo", "hello"))

    result = run_step(step, mirror.append)

    assert result.success
    assert result.stdout_lines == ("hello",)
    assert "[01] Greets" in mirror
    assert "[01] hello" in mirror


def test_run_step_mirrors_stderr_loudly():
    mirror: list[str] = []
    step = ScriptStep(2, "Warns", ("sh", "-c", "echo oops >&2"))

    result = run_step(step, mirror.append)

    assert result.success
    assert result.stderr_lines == ("oops",)
    assert "[02] ! oops" in mirror


def test_run_step_reports_failure_loudly():
    mirror: list[str] = []
    step = ScriptStep(3, "Fails", ("sh", "-c", "exit 7"))

    result = run_step(step, mirror.append)

    assert result.exit_code == 7
    assert not result.success
    assert any("FAILED (exit 7)" in line for line in mirror)


def test_run_all_stops_at_first_failure():
    mirror: list[str] = []
    steps = (
        ScriptStep(1, "Fails", ("sh", "-c", "exit 3")),
        ScriptStep(2, "Never runs", ("echo", "should not appear")),
    )

    results = run_all(steps, mirror.append)

    assert len(results) == 1
    assert "should not appear" not in "".join(mirror)


def test_progress_interpreter_emits_once_per_rule_and_keeps_unknown_lines():
    mirror: list[str] = []
    step = ScriptStep(1, "Streams", ("sh", "-c", "printf 'Downloading x\\nDownloading y\\nother\\n'"))

    run_step(step, mirror.append, ProgressInterpreter((("Downloading", "downloading..."),)))

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


def test_the_linux_journey_matches_install_sh_and_uses_script_files():
    """Numbering is the shared contract: 1-3 mirror install.sh, WSL is absent (Linux journey,
    ADR-0003), and steps 4-6 run the numbered script FILES (re-runnable by hand)."""
    steps = tui.journey_steps()
    assert [s.number for s in steps] == [1, 2, 3, 4, 5, 6]
    assert not any("WSL" in s.title for s in steps)
    assert steps[0].title == "Download the Wordslab installer payload"  # matches install.sh step 01
    for s in steps[3:]:
        assert s.command[0] == "bash" and Path(s.command[1]).is_file()


def test_web_handoff_is_an_address_not_a_process_switch():
    mirror: list[str] = []

    instruction = tui.web_handoff("https://wordslab.local/", mirror.append)

    assert "https://wordslab.local/" in instruction
    assert any("continues in the dashboard at: https://wordslab.local/" in line for line in mirror)


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
    original = tui.journey_steps  # captured before patching, so the wrapper cannot recurse
    monkeypatch.setattr(
        tui, "journey_steps",
        lambda: (ScriptStep(1, "Fails", ("sh", "-c", "exit 9")),) + original()[1:],
    )

    rc = tui.main(["--parameters", str(params_file)])

    out = capsys.readouterr().out
    assert rc == 1
    assert "FAILED (exit 9)" in out
    assert "Open https://wordslab.local/" not in out  # no handoff after a failure


def test_run_step_does_not_deadlock_when_stderr_fills_its_pipe():
    """Regression: draining stdout to EOF *before* stderr deadlocks whenever the process writes
    more than one pipe buffer to stderr while stdout is still open."""
    mirror: list[str] = []
    procs: list[subprocess.Popen] = []

    def watch_popen(command, **kwargs):  # noqa: ANN001
        proc = subprocess.Popen(command, **kwargs)
        procs.append(proc)
        return proc

    step = ScriptStep(
        4, "Floods stderr", ("sh", "-c",
        'i=0; while [ $i -lt 4000 ]; do echo "err line $i paddingpaddingpadding" >&2; '
        "i=$((i+1)); done; echo last-stdout"))

    finished: list = []
    t = threading.Thread(
        target=lambda: finished.append(run_step(step, mirror.append, popen=watch_popen)),
        daemon=True)
    t.start()
    t.join(timeout=15)
    for proc in procs:
        if proc.poll() is None:
            proc.kill()

    assert finished, "run_step deadlocked draining the two pipes"
    assert finished[0].success
    assert finished[0].stdout_lines == ("last-stdout",)
    assert len(finished[0].stderr_lines) == 4000
