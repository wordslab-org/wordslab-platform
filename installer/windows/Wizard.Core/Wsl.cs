using System.Text;

namespace Wordslab.Wizard.Core;

/// <summary>Everything crossing from the Windows host into the WSL distro goes through
/// <c>wsl.exe</c>; Windows paths become distro paths only via <c>wslpath -u</c> — never guessed.
/// Probes always run the real interpreter: <c>wsl -- python3 --version</c>, not
/// <c>wsl --version</c> (which would only prove WSL exists).</summary>
public static class Wsl
{
    public const string Exe = "wsl.exe";

    /// <summary>The named Wordslab distro the journey itself installs (#88). Every distro-facing
    /// command targets it — the live Windows run proved the machine's DEFAULT distro can lack even
    /// bash ("/bin/sh: bash: not found", exit 127), so the default is never good enough.</summary>
    public const string Distro = "wordslab";

    // wsl.exe (and wslpath) write UTF-16LE — decoding as the system default corrupts the output.
    private static readonly Encoding WslConsoleEncoding = Encoding.Unicode;

    private static string[] Targeted(params string[] rest) =>
        new[] { "-d", Distro }.Concat(rest).ToArray(); // Concat, not Union: argv duplicates are significant

    public static Command PythonProbe() =>
        new(Exe, Targeted("--", "python3", "--version"), "Checking for Python in the Wordslab virtual machine", WslConsoleEncoding);

    public static Command PathTranslate(string windowsPath) =>
        new(Exe, Targeted("wslpath", "-u", windowsPath), "Translating a Windows path for the Wordslab virtual machine", WslConsoleEncoding);

    public static Command RunBash(string distroPath, IReadOnlyList<string>? args = null) =>
        new(Exe, Targeted("--", "bash", distroPath).Concat(args ?? []).ToArray(), // Concat, not Union: argv duplicates are significant
            $"Running {System.IO.Path.GetFileName(distroPath)} inside the Wordslab virtual machine", WslConsoleEncoding);

    public static Command RunPython(string distroPath, IReadOnlyList<string>? args = null) =>
        new(Exe, Targeted("--", "python3", distroPath).Concat(args ?? []).ToArray(), // Concat, not Union: argv duplicates are significant
            $"Running {System.IO.Path.GetFileName(distroPath)} in the Wordslab virtual machine's Python", WslConsoleEncoding);

    /// <summary>An inline bash body inside the named distro (Windows-only steps have no script
    /// files — the C# class carries the readable body).</summary>
    public static Command RunBashInline(string bashBody, string? status = null) =>
        new(Exe, Targeted("--", "bash", "-c", bashBody), status ?? "Working inside the Wordslab virtual machine", WslConsoleEncoding);
}

/// <summary>Runs <c>wslpath -u</c> through the executor seam so even path translation is visible
/// in the streamed journey and testable with the fake.</summary>
public sealed class WslPathTranslator(ICommandExecutor executor)
{
    public async Task<string?> ToDistroPathAsync(string windowsPath, Action<ReportLine>? report = null)
    {
        string? firstLine = null;
        int exit = await executor.RunAsync(Wsl.PathTranslate(windowsPath), line =>
        {
            if (line.Kind == ReportKind.Stdout && firstLine is null) firstLine = line.Text;
            report?.Invoke(line);
        });
        // Distro-facing boundary: a path handed to WSL must never carry Windows backslashes,
        // whatever wslpath (or a test double) returned. Host-side checks tolerate '/' on Windows.
        return exit == 0 && firstLine is not null ? firstLine.Trim().Replace('\\', '/') : null;
    }
}
