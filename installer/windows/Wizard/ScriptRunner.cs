namespace Wordslab.Wizard;

/// <summary>One numbered bootstrap script in the guided journey (ADR-0014 §3 phase 1).</summary>
/// <param name="Number">The visible script number (transparency: numbered, runnable, no magic).</param>
/// <param name="Title">One-line human description shown before the script runs.</param>
/// <param name="Command">Executable to run.</param>
/// <param name="Args">Arguments for the executable.</param>
public sealed record ScriptStep(int Number, string Title, string Command, IReadOnlyList<string> Args);

/// <summary>Result of running one script step.</summary>
public sealed record StepResult(ScriptStep Step, int ExitCode, IReadOnlyList<string> StdoutLines, IReadOnlyList<string> StderrLines)
{
    public bool Success => ExitCode == 0;
}

/// <summary>Process abstraction so the wizard's contract is testable against stub commands.</summary>
public interface IProcessRunner
{
    /// <summary>Runs <paramref name="command"/> with <paramref name="args"/>, streaming each stdout and
    /// stderr line to the callbacks as it arrives, and returns the exit code.</summary>
    int Run(string command, IReadOnlyList<string> args, Action<string>? onStdout, Action<string>? onStderr);
}

/// <summary>
/// Runs the numbered bootstrap scripts in order and mirrors their text output (ADR-0014 §3 phase 1:
/// "runs the first native scripts and mirrors their text output until Python is installed").
/// A failing script stops the journey loudly — nothing is installed silently (ADR-0014 §7).
/// </summary>
public sealed class ScriptRunner
{
    private readonly IProcessRunner _process;
    private readonly Action<string> _mirror;

    public ScriptRunner(IProcessRunner process, Action<string> mirror)
    {
        _process = process;
        _mirror = mirror;
    }

    /// <summary>Runs every step in order. Returns the results collected so far; stops at the first
    /// non-zero exit code and reports it loudly on the mirror.</summary>
    public IReadOnlyList<StepResult> RunAll(IReadOnlyList<ScriptStep> steps)
    {
        var results = new List<StepResult>();
        foreach (var step in steps)
        {
            var result = RunOne(step);
            results.Add(result);
            if (!result.Success)
                break;
        }
        return results;
    }

    public StepResult RunOne(ScriptStep step)
    {
        _mirror($"[{step.Number:D2}] {step.Title}");
        var stdout = new List<string>();
        var stderr = new List<string>();
        int exit = _process.Run(
            step.Command,
            step.Args,
            line => { stdout.Add(line); _mirror($"[{step.Number:D2}] {line}"); },
            line => { stderr.Add(line); _mirror($"[{step.Number:D2}] ! {line}"); });
        if (exit != 0)
            _mirror($"[{step.Number:D2}] FAILED (exit {exit}) — the journey stops here; nothing further is installed.");
        return new StepResult(step, exit, stdout, stderr);
    }
}
