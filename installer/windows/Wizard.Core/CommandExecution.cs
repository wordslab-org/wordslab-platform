using System.Text;

namespace Wordslab.Wizard.Core;

/// <summary>One command line the wizard runs. <paramref name="Status"/> is the human sentence
/// shown in the UI while the command runs — the commands report what they do as they stream.
/// <paramref name="OutputEncoding"/> is set for processes whose console encoding is not the
/// system default — notably <c>wsl.exe</c>/<c>wslpath</c>, which emit UTF-16LE.</summary>
public sealed record Command(string Program, IReadOnlyList<string> Args, string Status, Encoding? OutputEncoding = null)
{
    public override string ToString() => $"{Program} {string.Join(' ', Args)}";
}

// Info/Start drive the live status line; Stdout/Stderr feed the expandable log; Success/Failure
// are TYPED so the UI's card state machine never parses prose (prose stays display-only payload).
public enum ReportKind { Info, Start, Stdout, Stderr, Success, Failure }

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

/// <summary>
/// Picks the PowerShell host: PowerShell 7 (pwsh) when installed, otherwise Windows PowerShell.
/// The installer must work on a stock machine that has no pwsh at all.
/// </summary>
public static class PowerShellHost
{
    public static string Resolve()
    {
        string[] candidates = OperatingSystem.IsWindows()
            ? new[] { "pwsh.exe", "powershell.exe" }
            : new[] { "pwsh" };
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string candidate in candidates)
        {
            foreach (string dir in path.Split(Path.PathSeparator))
            {
                if (string.IsNullOrWhiteSpace(dir)) continue;
                try
                {
                    string full = Path.Combine(dir.Trim(), candidate);
                    if (File.Exists(full)) return full;
                }
                catch (Exception) { }
            }
        }
        // Nothing on PATH: Windows always has powershell.exe via App Paths.
        return OperatingSystem.IsWindows() ? "powershell.exe" : "pwsh";
    }
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
            // null for system-default tools; set for UTF-16LE emitters like wsl.exe/wslpath
            StandardOutputEncoding = command.OutputEncoding,
            StandardErrorEncoding = command.OutputEncoding,
        };
        foreach (var a in command.Args) p.StartInfo.ArgumentList.Add(a);
        try
        {
            p.Start();
        }
        catch (System.ComponentModel.Win32Exception ex)
        {
            // Non-technical wording: a missing program is the common cause.
            report(new ReportLine(ReportKind.Stderr,
                $"! Could not start the program '{command.Program}' — it may not be installed. ({ex.Message})"));
            return -1;
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
