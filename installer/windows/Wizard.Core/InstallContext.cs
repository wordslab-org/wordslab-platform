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

/// <summary>The fixed v1 path layout the UI promises and every step consumes (ADR-0014 §5, #88):
/// the program folder, one Wordslab Linux disk per enabled drive — a WSL-managed ext4.vhdx inside
/// the drive's Wordslab folder — and the shared cache for imported rootfs images. One place to
/// compute each path, so class and script bodies never re-derive them.</summary>
public static class InstallDirs
{
    public static string ProgramFolderOrThrow(IReadOnlyDictionary<string, string> parameters)
    {
        if (!parameters.TryGetValue("install_dir", out string? dir) || string.IsNullOrWhiteSpace(dir))
            throw new InvalidOperationException(
                "the parameters file has no install_dir - the wizard writes it before the journey starts");
        return dir.TrimEnd('\\');
    }

    /// <summary>Enabled drives (the wizard writes one volume_&lt;DRIVE&gt; key per enabled drive;
    /// disabled drives get no key at all), sorted by drive letter.</summary>
    public static IEnumerable<(string drive, string folder)> EnabledVolumes(
        IReadOnlyDictionary<string, string> parameters) =>
        parameters
            .Where(kv => kv.Key.StartsWith("volume_") && kv.Key.Length == "volume_X".Length)
            .Select(kv => (drive: kv.Key["volume_".Length..] + ":", folder: kv.Value))
            .OrderBy(v => v.drive, StringComparer.OrdinalIgnoreCase)
            .ToArray();

    public static string VolumeDistroName(string drive) =>
        "wordslab-" + drive.TrimEnd(':', '\\').ToLowerInvariant();

    /// <summary>The disk's folder on its own drive: <c>&lt;drive&gt;:\wordslab\wordslab-&lt;letter&gt;\</c>
    /// (the UI card promises exactly this — a folder, the WSL-managed ext4.vhdx lives inside it).</summary>
    public static string VolumeDistroFolder(string volumeFolder, string drive) =>
        Path.Combine(volumeFolder.TrimEnd('\\'), VolumeDistroName(drive));
}

/// <summary>The front-door address file step 6's probe writes next to the parameters file.
/// #88 ruling: the wizard hands off to the VM's own address until #92/#94 land mDNS naming and
/// CA trust — the handoff stays an address, never a process switch (ADR-0014 §3 phase 3).</summary>
public static class FrontDoorAddress
{
    public const string UrlFileName = "wordslab-front-door.url";

    public static string ReadFor(string parametersFile, string fallback)
    {
        string path = Path.Combine(Path.GetDirectoryName(parametersFile) ?? ".", UrlFileName);
        if (File.Exists(path))
        {
            string url = File.ReadAllText(path).Trim();
            if (url.StartsWith("https://")) return url;
        }
        return fallback;
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
            : "Please type a full folder path for the Wordslab program, like C:\\wordslab.";

    /// <summary>A volume folder must sit on the drive it names.</summary>
    public static string? ValidateVolumeFolder(string folder, string drive) =>
        folder.Length >= 3 && folder[0] == drive[0] && folder[1] == ':' && (folder[2] == '\\' || folder[2] == '/')
            ? null
            : $"The Wordslab folder for drive {drive} must be on that drive, like {drive}\\wordslab.";

    public static void Write(IReadOnlyDictionary<string, string> answers, string path) =>
        File.WriteAllText(path, JsonSerializer.Serialize(answers, new JsonSerializerOptions { WriteIndented = true }));

    public static IReadOnlyDictionary<string, string> Read(string path) =>
        JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(path))
        ?? throw new InvalidOperationException($"parameters file '{path}' is not a JSON object");
}
