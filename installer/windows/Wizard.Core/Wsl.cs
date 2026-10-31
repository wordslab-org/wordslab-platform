using System.Text;

namespace Wordslab.Wizard.Core;

/// <summary>Everything crossing from the Windows host into the WSL distro goes through
/// <c>wsl.exe</c>; Windows paths become distro paths only via <c>wslpath -u</c> — never guessed.
/// Probes always run the real interpreter: <c>wsl -- python3 --version</c>, not
/// <c>wsl --version</c> (which would only prove WSL exists).</summary>
public static class Wsl
{
    public const string Exe = "wsl.exe";

    /// <summary>The ONE distro running the platform (the app VM). Explicit name = folder name =
    /// thing it is (#88 follow-up): `wordslab-platform-vm`. Every VM-facing command targets it by
    /// name — the live Windows run proved the machine's DEFAULT distro can lack even bash
    /// ("/bin/sh: bash: not found", exit 127), so the default is never good enough. The data disks
    /// are separate distros named `wordslab-platform-disk<letter>` (InstallDirs.VolumeDistroName).</summary>
    public const string VmDistro = "wordslab-platform-vm";

    // ONE output contract for every wsl command: UTF-8. wsl.exe's own messages are UTF-16LE by
    // default, so the executor sets WSL_UTF8=1 for wsl.exe (ProcessCommandExecutor) — that makes
    // them UTF-8, the same encoding as the Linux child's relayed output. Decoding the child's
    // UTF-8 as UTF-16LE is exactly the "lines of Chinese characters" step-3 bug (2026-10-31).
    private static readonly Encoding WslOutputEncoding = Encoding.UTF8;

    private static string[] Targeted(params string[] rest) =>
        new[] { "-d", VmDistro }.Concat(rest).ToArray(); // Concat, not Union: argv duplicates are significant

    public static Command PythonProbe() =>
        new(Exe, Targeted("--", "python3", "--version"), "Checking for Python in the Wordslab virtual machine", WslOutputEncoding);

    public static Command PathTranslate(string windowsPath) =>
        new(Exe, Targeted("wslpath", "-u", windowsPath), "Translating a Windows path for the Wordslab virtual machine", WslOutputEncoding);

    public static Command RunBash(string distroPath, IReadOnlyList<string>? args = null) =>
        new(Exe, Targeted("--", "bash", distroPath).Concat(args ?? []).ToArray(), // Concat, not Union: argv duplicates are significant
            $"Running {System.IO.Path.GetFileName(distroPath)} inside the Wordslab virtual machine", WslOutputEncoding);

    public static Command RunPython(string distroPath, IReadOnlyList<string>? args = null) =>
        new(Exe, Targeted("--", "python3", distroPath).Concat(args ?? []).ToArray(), // Concat, not Union: argv duplicates are significant
            $"Running {System.IO.Path.GetFileName(distroPath)} in the Wordslab virtual machine's Python", WslOutputEncoding);

}

/// <summary>Runs <c>wslpath -u</c> through the executor seam so even path translation is visible
/// in the streamed journey and testable with the fake.</summary>
public sealed class WslPathTranslator(ICommandExecutor executor)
{
    /// <summary>C:\a\b -> /mnt/c/a/b — WSL's default automount convention, COMPUTED rather than
    /// asked. The Ubuntu OCI rootfs we import ships no <c>wslpath</c> binary (live bug: step 3
    /// ran with the raw Windows path and died on "C:Userslaure...", exit 127), so the tool must
    /// not depend on that helper for its own payload. Null when the path is not drive-rooted
    /// (UNC, relative) — those still go through wslpath, and callers fail loudly if it cannot
    /// answer.</summary>
    public static string? MapDrivePath(string windowsPath)
    {
        string p = windowsPath.Trim();
        if (p.Length < 3 || !char.IsLetter(p[0]) || p[1] != ':' || (p[2] != '\\' && p[2] != '/'))
            return null;
        string rest = p[2..].Replace('\\', '/').Trim('/');
        return "/mnt/" + char.ToLowerInvariant(p[0]) + (rest.Length > 0 ? "/" + rest : "");
    }

    public async Task<string?> ToDistroPathAsync(string windowsPath, Action<ReportLine>? report = null)
    {
        string? mapped = MapDrivePath(windowsPath);
        if (mapped is not null) return mapped;   // deterministic: no subprocess, no dependency

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
