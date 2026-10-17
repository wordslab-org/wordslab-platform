namespace Wordslab.Wizard.Core;

public sealed record StepResult(NumberedScript Script, IReadOnlyList<int> ExitCodes)
{
    public bool Success => ExitCodes.Count > 0 && ExitCodes.All(c => c == 0);
}

/// <summary>Runs the numbered scripts in order, streaming every status and output line out as
/// <see cref="Report"/>s for the UI to render live, and stops at the first failure — loudly.
/// Same journey contract as the Python (Linux TUI) and bash (Linux entry) runners:
/// "[NN] title", the FAILED line, nothing installed silently.</summary>
public sealed class JourneyRunner(ICommandExecutor executor)
{
    public async Task<IReadOnlyList<StepResult>> RunAsync(
        IReadOnlyList<NumberedScript> scripts, InstallContext ctx,
        Action<Report> report, CancellationToken cancel = default)
    {
        var results = new List<StepResult>();
        foreach (var script in scripts)
        {
            report(new Report(script.Number, ReportKind.Info, script.Title));
            var exits = new List<int>();
            foreach (var command in await script.PlanAsync(ctx))
            {
                cancel.ThrowIfCancellationRequested();
                report(new Report(script.Number, ReportKind.Start, command.Status));
                int exit = await executor.RunAsync(
                    command, line => report(new Report(script.Number, line.Kind, line.Text)), cancel);
                exits.Add(exit);
                if (exit == 0)
                {
                    report(new Report(script.Number, ReportKind.Exit, "done"));
                }
                else
                {
                    report(new Report(script.Number, ReportKind.Exit,
                        $"FAILED (exit {exit}) — the journey stops here; nothing further is installed."));
                    results.Add(new StepResult(script, exits));
                    return results; // stop at the first failure; the UI shows what happened
                }
            }
            results.Add(new StepResult(script, exits));
        }
        return results;
    }

    /// <summary>The distro's Python only exists once step 3 has run; the probe runs the real
    /// interpreter inside the distro, never `wsl --version`.</summary>
    public async Task<bool> PythonAvailableInDistroAsync(CancellationToken cancel = default)
    {
        var quiet = new Action<ReportLine>(_ => { });
        return await executor.RunAsync(Wsl.PythonProbe(), quiet, cancel) == 0;
    }
}
