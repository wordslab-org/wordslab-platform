"""The phase-2 installer TUI (ADR-0014 §3 phase 2).

Renders the install wizard on top of the installer API: numbered scripts stay visible/runnable
beneath (transparency, no magic), progress is interpreted from streamed logs, and every decision
is surfaced. The final act is the web handoff: an address, not a process switch — the TUI prints
the dashboard URL to open elsewhere (remote/SSH). On Windows there is no TUI at all: the WinUI
installer app runs the same numbered journey natively (Wizard.Core script classes) and renders
the web handoff itself — Linux users see these terminal + TUI phases.

The numbered bootstrap scripts live as real files under `installer/scripts/` so the re-run
promise is literal: the user can execute any numbered script by hand. The steps already run by
the native phase (1–3) are re-shown as completed context, never silently skipped and never
re-executed here. The scripts' real content is ticket #88's home; #87 owns the numbering, the
journey shell, and the runner contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from installer_api import (
    Mirror,
    ProgressInterpreter,
    ScriptStep,
    run_all,
)

# Steps run wherever the TUI runs (inside the WSL distro on Windows, natively on Linux);
# script paths resolve relative to this file, so a /mnt/c checkout or an extracted payload work.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

# Steps 1–3 belong to the native (install.sh) phase of the Linux journey. The TUI re-shows them
# as completed context; numbering and titles match install.sh exactly — the numbering is the
# contract, shared with the Windows WinUI journey's steps 4–6 (ADR-0003: WSL is Windows-only,
# and the Windows journey's steps 1–3 are C# script classes, never scripts here).
NATIVE_STEPS: tuple[tuple[int, str], ...] = (
    (1, "Download the Wordslab installer payload"),
    (2, "Check network reachability (github, pypi)"),
    (3, "Install uv + Python"),
)

# Steps 4–6 run wherever the TUI runs, as the same numbered files for every journey.
DISTRO_STEPS: tuple[tuple[int, str, str], ...] = (
    (4, "Provision data volumes on the chosen disks", "04-data-volumes.sh"),
    (5, "Install the first platform core", "05-first-core.sh"),
    (6, "Bring up the front door (wordslab.local)", "06-front-door.sh"),
)


def journey_steps() -> tuple[ScriptStep, ...]:
    """The full numbered Linux journey: native steps re-shown as completed context, distro
    steps executed as their script FILES (re-runnable by hand — no magic)."""
    native = tuple(
        ScriptStep(n, title, ("echo", f"{title} — already completed by the native phase; "
                                     "re-run its script yourself any time (placeholder until #88)"))
        for n, title in NATIVE_STEPS
    )
    distro = tuple(
        ScriptStep(n, title, ("bash", str(SCRIPTS_DIR / "distro" / script)))
        for n, title, script in DISTRO_STEPS
    )
    return native + distro


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


def web_handoff(dashboard_url: str, mirror: Mirror) -> str:
    """The journey's final act: hand off to the web UI as an address (ADR-0014 §3 phase 3).

    Returns the instruction line the TUI shows; the Windows installer additionally renders the
    URL in its embedded webview and opens the browser itself (the WebView2Host on the native side).
    """
    mirror(f"The install now continues in the dashboard at: {dashboard_url}")
    return f"Open {dashboard_url} in your browser to continue the install (services, capabilities, activities)."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wordslab Platform installer TUI (phase 2)")
    parser.add_argument("--parameters", type=Path, required=True,
                        help="JSON parameters file collected by the phase-1 wizard")
    parser.add_argument("--dashboard-url", default="https://wordslab.local/",
                        help="Front-door address for the web handoff")
    args = parser.parse_args(argv)

    steps = journey_steps()
    params = load_parameters(args.parameters)
    print("Wordslab Platform installer — phase 2 (Python TUI).")
    print("Collected parameters:")
    for key, value in params.items():
        print(f"  {key} = {value}")
    print("Every step below is a numbered script; you can re-run any of them yourself.")
    print()

    results = run_all(steps, print, ProgressInterpreter(PROGRESS_RULES))
    if len(results) != len(steps) or not all(r.success for r in results):
        print("The journey stopped on a failed script. Fix the cause and re-run — re-running is safe "
              "(Update path, ADR-0014 §7).")
        return 1

    print()
    print(web_handoff(args.dashboard_url, print))
    return 0


if __name__ == "__main__":
    sys.exit(main())
