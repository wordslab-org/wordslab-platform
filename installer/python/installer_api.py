"""The small, solid installer API (ADR-0014 §3 phase 2).

Wraps every command-line install step: run, stream stdout/stderr line by line, interpret the
logs into progress lines, and surface every decision. Nothing is installed silently: every
command, its output, and its exit code are visible to the TUI (and the numbered scripts stay
runnable beneath it — transparency, no magic).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

Mirror = Callable[[str], None]


@dataclass(frozen=True)
class ScriptStep:
    """One numbered bootstrap script (their content is #88; this owns the running + mirroring)."""

    number: int
    title: str
    command: Sequence[str]


@dataclass(frozen=True)
class StepResult:
    step: ScriptStep
    exit_code: int
    stdout_lines: tuple[str, ...]
    stderr_lines: tuple[str, ...]

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class ProgressInterpreter:
    """Turns streamed output lines into progress lines the TUI renders.

    A rule is (needle, progress_text): the first time a line contains the needle, the progress
    text is emitted. Unknown lines are mirrored raw — never dropped.
    """

    rules: tuple[tuple[str, str], ...] = ()
    _seen: set[str] = field(default_factory=set, repr=False)

    def interpret(self, line: str) -> str | None:
        for needle, progress in self.rules:
            if needle in line and needle not in self._seen:
                self._seen.add(needle)
                return progress
        return None


def run_step(
    step: ScriptStep,
    mirror: Mirror,
    interpreter: ProgressInterpreter | None = None,
    *,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> StepResult:
    """Runs one numbered script, mirroring every stdout/stderr line as it arrives."""
    label = f"[{step.number:02d}]"
    mirror(f"{label} {step.title}")
    proc = popen(
        list(step.command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None and proc.stderr is not None
    stdout: list[str] = []
    stderr: list[str] = []
    # Read both pipes line by line; stderr lines are mirrored loudly.
    for stream, sink, prefix in ((proc.stdout, stdout, ""), (proc.stderr, stderr, "! ")):
        for raw in stream:
            line = raw.rstrip("\n")
            sink.append(line)
            mirror(f"{label} {prefix}{line}")
            if interpreter is not None:
                progress = interpreter.interpret(line)
                if progress is not None:
                    mirror(f"{label} -> {progress}")
    proc.wait()
    if proc.returncode != 0:
        mirror(
            f"{label} FAILED (exit {proc.returncode}) — the journey stops here; "
            "nothing further is installed."
        )
    return StepResult(step, proc.returncode, tuple(stdout), tuple(stderr))


def run_all(
    steps: Iterable[ScriptStep],
    mirror: Mirror,
    interpreter: ProgressInterpreter | None = None,
    **kwargs,
) -> list[StepResult]:
    """Runs the numbered scripts in order; stops at the first failure (loudly)."""
    results: list[StepResult] = []
    for step in steps:
        result = run_step(step, mirror, interpreter, **kwargs)
        results.append(result)
        if not result.success:
            break
    return results
