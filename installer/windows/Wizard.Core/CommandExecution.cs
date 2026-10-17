namespace Wordslab.Wizard.Core;

/// <summary>One command line the wizard runs. <paramref name="Status"/> is the human sentence
/// shown in the UI while the command runs — the commands report what they do as they stream.</summary>
public sealed record Command(string Program, IReadOnlyList<string> Args, string Status)
{
    public override string ToString() => $"{Program} {string.Join(' ', Args)}";
}

public enum ReportKind { Info, Start, Stdout, Stderr, Exit }

/// <summary>A streamed status line. The UI renders these live: step header (Info), command
/// status (Start), output lines (Stdout/Stderr) and the outcome (Exit).</summary>
public sealed record ReportLine(ReportKind Kind, string Text);

/// <summary>Report line stamped with its numbered script — what the UI groups by.</summary>
public sealed record Report(int Step, ReportKind Kind, string Text);

/// <summary>The command-execution seam: the small library every numbered script runs through.
/// Tests use a fake; the app uses <see cref="ProcessCommandExecutor"/>.</summary>
public interface ICommandExecutor
{
    Task<int> RunAsync(Command command, Action<ReportLine> report, CancellationToken cancel = default);
}

/// <summary>Streams both pipes concurrently, line by line as they arrive (never stdout-to-EOF
/// first — that deadlocks when a command is chatty on stderr).</summary>
public sealed class ProcessCommandExecutor : ICommandExecutor
{
    public async Task<int> RunAsync(Command command, Action<ReportLine> report, CancellationToken cancel = default)
    {
        using var p = new System.Diagnostics.Process();
        p.StartInfo = new System.Diagnostics.ProcessStartInfo
        {
            FileName = command.Program,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        foreach (var a in command.Args) p.StartInfo.ArgumentList.Add(a);
        try
        {
            p.Start();
        }
        catch (Exception ex)
        {
            report(new ReportLine(ReportKind.Stderr, ex.Message));
            return -1;
        }

        var draining = new[]
        {
            DrainAsync(p.StandardOutput, ReportKind.Stdout, report),
            DrainAsync(p.StandardError, ReportKind.Stderr, report),
        };
        await Task.WhenAll(draining);
        await p.WaitForExitAsync(cancel);
        return p.ExitCode;
    }

    private async Task DrainAsync(System.IO.StreamReader stream, ReportKind kind, Action<ReportLine> report)
    {
        string? line;
        while ((line = await stream.ReadLineAsync()) is not null)
            report(new ReportLine(kind, line));
    }
}
