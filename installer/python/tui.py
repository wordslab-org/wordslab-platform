"""The phase-2 installer TUI (ADR-0014 §3 phase 2).

Renders the install wizard on top of the installer API: numbered scripts stay visible/runnable
beneath (transparency, no magic), progress is interpreted from streamed logs, and every decision
is surfaced. The final act is the web handoff: an address, not a process switch — the TUI prints
the reachable dashboard URL (remote/SSH) or hands the URL to the installer's embedded webview
(Windows host, via the wizard process that launched this TUI).

The numbered bootstrap scripts themselves are ticket #88's home; this owns the journey shell.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from installer_api import (
    ProgressInterpreter,
    ScriptStep,
    run_all,
)

# The bootstrap script slots the wizard drives (content lands in #88; the numbering is the contract).
BOOTSTRAP_STEPS: tuple[ScriptStep, ...] = (
    ScriptStep(1, "Check network reachability (github, pypi)", ("echo", "reachability check: placeholder until #88")),
    ScriptStep(2, "Install WSL + the Wordslab distro + virtual disks", ("echo", "wsl bootstrap: placeholder until #88")),
    ScriptStep(3, "Install uv + Python", ("echo", "uv bootstrap: placeholder until #88")),
    ScriptStep(4, "Provision data volumes on the chosen disks", ("echo", "data volumes: placeholder until #88")),
    ScriptStep(5, "Install the first platform core", ("echo", "core install: placeholder until #88")),
    ScriptStep(6, "Bring up the front door (wordslab.local)", ("echo", "front door: placeholder until #88")),
)

# Interpreted progress lines (ADR-0014 §3: "interpret the logs, render progress as lines are found").
PROGRESS_RULES: tuple[tuple[str, str], ...] = (
    ("Downloading", "downloading..."),
    ("Installing", "installing..."),
    ("Verifying", "verifying..."),
    ("Done", "done"),
)


def load_parameters(path: Path) -> dict[str, str]:
    """Reads the parameters file written by the phase-1 native wizard."""
    return json.loads(path.read_text())


def web_handoff(dashboard_url: str, mirror) -> str:
    """The journey's final act: hand off to the web UI as an address (ADR-0014 §3 phase 3).

    Returns the instruction line the TUI shows; the Windows installer additionally renders the
    URL in its embedded webview and opens the browser itself (the WebView2Host on the native side).
    """
    mirror(f"The platform core and dashboard are up: {dashboard_url}")
    return f"Open {dashboard_url} in your browser to continue the install (services, capabilities, activities)."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wordslab Platform installer TUI (phase 2)")
    parser.add_argument("--parameters", type=Path, required=True,
                        help="JSON parameters file collected by the phase-1 wizard")
    parser.add_argument("--dashboard-url", default="https://wordslab.local/",
                        help="Front-door address for the web handoff")
    args = parser.parse_args(argv)

    params = load_parameters(args.parameters)
    print("Wordslab Platform installer — phase 2 (Python TUI).")
    print("Collected parameters:")
    for key, value in params.items():
        print(f"  {key} = {value}")
    print("Every step below is a numbered script; you can re-run any of them yourself.")
    print()

    results = run_all(BOOTSTRAP_STEPS, print, ProgressInterpreter(PROGRESS_RULES))
    if len(results) != len(BOOTSTRAP_STEPS) or not all(r.success for r in results):
        print("The journey stopped on a failed script. Fix the cause and re-run — re-running is safe "
              "(Update path, ADR-0014 §7).")
        return 1

    print()
    print(web_handoff(args.dashboard_url, print))
    return 0


if __name__ == "__main__":
    sys.exit(main())
