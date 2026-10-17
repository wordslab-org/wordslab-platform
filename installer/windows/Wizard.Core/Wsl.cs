using System.Text;

namespace Wordslab.Wizard.Core;

/// <summary>Everything crossing from the Windows host into the WSL distro goes through
/// <c>wsl.exe</c>; Windows paths become distro paths only via <c>wslpath -u</c> — never guessed.
/// Probes always run the real interpreter: <c>wsl -- python3 --version</c>, not
/// <c>wsl --version</c> (which would only prove WSL exists).</summary>
public static class Wsl
{
    public const string Exe = "wsl.exe";

    // wsl.exe (and wslpath) write UTF-16LE — decoding as the system default corrupts the output.
    private static readonly Encoding WslConsoleEncoding = Encoding.Unicode;

    public static Command PythonProbe() =>
        new(Exe, new[] { "--", "python3", "--version" }, "Checking for Python in the distro", WslConsoleEncoding);

    public static Command PathTranslate(string windowsPath) =>
        new(Exe, new[] { "wslpath", "-u", windowsPath }, "Translating a Windows path for the distro", WslConsoleEncoding);

    public static Command RunBash(string distroPath) =>
        new(Exe, new[] { "--", "bash", distroPath }, $"Running {System.IO.Path.GetFileName(distroPath)} inside the distro", WslConsoleEncoding);

    public static Command RunPython(string distroPath, IReadOnlyList<string>? args = null) =>
        new(Exe, new[] { "--", "python3", distroPath }.Concat(args ?? []).ToArray(), // Concat, not Union: argv duplicates are significant
            $"Running {System.IO.Path.GetFileName(distroPath)} in the distro Python", WslConsoleEncoding);
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
        return exit == 0 && firstLine is not null ? firstLine.Trim() : null;
    }
}
