using System.Globalization;
using System.Text.Json;

namespace Wordslab.Wizard.Core;

/// <summary>Where the journey runs: the installer payload layout, the collected parameters and
/// the path translator the distro steps need. Everything a script class could need — passed
/// visibly, never reached for from thin air.</summary>
public sealed class InstallContext
{
    /// <summary>The installer root (the repo's `installer/` in a checkout, the payload root when installed).</summary>
    public required string InstallerDir { get; init; }
    public required IReadOnlyDictionary<string, string> Parameters { get; init; }
    public required string ParametersFile { get; init; }
    public required WslPathTranslator WslPaths { get; init; }

    public string DistroScript(string relativeName) =>
        Path.Combine(InstallerDir, "scripts", relativeName);
    public string PythonScript(string relativeName) =>
        Path.Combine(InstallerDir, "python", relativeName);
}

/// <summary>Finds the installer layout by walking up from the running binary: a checkout has
/// `installer/python/tui.py`; an extracted payload has `python/tui.py` at its root.</summary>
public static class PayloadLocator
{
    public static string? FindInstallerDir(string startDir)
    {
        for (var dir = new DirectoryInfo(startDir); dir is not null; dir = dir.Parent)
        {
            if (File.Exists(Path.Combine(dir.FullName, "installer", "python", "tui.py")))
                return Path.Combine(dir.FullName, "installer");
            if (File.Exists(Path.Combine(dir.FullName, "python", "tui.py")))
                return dir.FullName;
            if (dir.Parent is null) break;
        }
        return null;
    }
}

/// <summary>Install parameters (ADR-0014 §3): surfaced with defaults and validation in the UI,
/// written as JSON for the later phases (the distro TUI and scripts read the same file).</summary>
public static class Parameters
{
    /// <summary>Accepts a Windows drive root (D:\) or a POSIX absolute path. The bare root "/"
    /// is refused on purpose.</summary>
    public static string? ValidateDiskPath(string value)
    {
        bool windowsDrive = value.Length is 3 && char.IsLetter(value[0]) && value[1] == ':' && (value[2] == '\\' || value[2] == '/');
        bool posixRoot = value.Length > 1 && value[0] == '/';
        return windowsDrive || posixRoot ? null : "Please type a drive letter followed by a colon, like C:\\ or D:\\ (including the backslash).";
    }

    /// <summary>Windows install parameters: the program folder, plus one data volume per
    /// chosen drive — each volume is a folder on that drive holding its virtual Linux disk
    /// (VHDX), named after the drive (ADR-0014 §5). Disabled drives simply get no key.</summary>
    public static Dictionary<string, string> ForWindows(
        string installDir, IEnumerable<(string drive, string folder)> volumes)
    {
        var answers = new Dictionary<string, string> { ["install_dir"] = installDir };
        foreach (var (drive, folder) in volumes)
            answers["volume_" + drive.TrimEnd('\\', ':').ToUpperInvariant()] = folder;
        return answers;
    }

    /// <summary>A full Windows folder path (drive letter + colon + separator).</summary>
    public static string? ValidateInstallDir(string value) =>
        value.Length >= 3 && char.IsLetter(value[0]) && value[1] == ':' && (value[2] == '\\' || value[2] == '/')
            ? null
            : "Please type a full folder path for the Wordslab program, like C:\\Wordslab.";

    /// <summary>A volume folder must sit on the drive it names.</summary>
    public static string? ValidateVolumeFolder(string folder, string drive) =>
        folder.Length >= 3 && folder[0] == drive[0] && folder[1] == ':' && (folder[2] == '\\' || folder[2] == '/')
            ? null
            : $"The Wordslab folder for drive {drive} must be on that drive, like {drive}\\Wordslab.";

    public static void Write(IReadOnlyDictionary<string, string> answers, string path) =>
        File.WriteAllText(path, JsonSerializer.Serialize(answers, new JsonSerializerOptions { WriteIndented = true }));

    public static IReadOnlyDictionary<string, string> Read(string path) =>
        JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(path))
        ?? throw new InvalidOperationException($"parameters file '{path}' is not a JSON object");
}
