using Wordslab.Wizard.Abstractions;

namespace Wordslab.Wizard;

/// <summary>
/// Decides when the wizard hands off: native -> Python TUI once Python (via uv) exists, and the
/// journey's final act resolves to the web handoff — "an address, not a process switch"
/// (ADR-0014 §3 phase 3). The handoff is surfaced to the user, never silent.
///
/// On Windows the Python the bootstrap installs lives INSIDE the WSL distro: every Python probe
/// and launch goes through `wsl.exe -- python3 …`, and Windows paths are translated with
/// `wslpath -u` so the distro can read them.
/// </summary>
public sealed class PhaseHandoff
{
    private readonly IProcessRunner _process;
    private readonly Action<string> _mirror;

    public PhaseHandoff(IProcessRunner process, Action<string> mirror)
    {
        _process = process;
        _mirror = mirror;
    }

    /// <summary>True when a Python interpreter runs inside the distro (the uv-installed one from the
    /// bootstrap). Probes `wsl.exe -- python3 --version` — NOT `wsl.exe --version`, which would
    /// only prove WSL exists.</summary>
    public bool PythonAvailableInWsl(string wslCommand = "wsl.exe") =>
        _process.Run(wslCommand, new[] { "--", "python3", "--version" }, null, null) == 0;

    /// <summary>Launches the Python TUI (phase 2) inside the distro with the collected parameters
    /// file. Both Windows paths are translated via `wslpath -u` first; a failed translation stops
    /// the journey loudly. Returns the TUI's exit code.</summary>
    public int HandOffToPythonTuiInWsl(string tuiScriptWindowsPath, string parametersWindowsPath, string wslCommand = "wsl.exe")
    {
        string? tuiPath = ToDistroPath(wslCommand, tuiScriptWindowsPath);
        string? paramsPath = ToDistroPath(wslCommand, parametersWindowsPath);
        if (tuiPath is null || paramsPath is null)
        {
            _mirror($"FAILED — could not translate a Windows path for the distro (wslpath): " +
                    $"'{tuiScriptWindowsPath}' / '{parametersWindowsPath}'. The journey stops here; nothing further is installed.");
            return 1;
        }
        _mirror("Python is available in the distro — handing the journey to the Python installer TUI.");
        return _process.Run(wslCommand, new[] { "--", "python3", tuiPath, "--parameters", paramsPath },
            line => _mirror(line), line => _mirror($"! {line}"));
    }

    /// <summary>Translates a Windows path to its WSL (distro) form via `wslpath -u`.</summary>
    public string? ToDistroPath(string wslCommand, string windowsPath)
    {
        string? line = null;
        int exit = _process.Run(wslCommand, new[] { "wslpath", "-u", windowsPath },
            l => line ??= l, null);
        return exit == 0 && line is not null ? line.Trim() : null;
    }

    /// <summary>
    /// The web handoff (phase 3): the Windows installer renders the web UI phase in its embedded
    /// WebView2 host, then opens the dashboard in the browser. The caller reaches this only after
    /// the bootstrap's front-door step reported the address (reachability itself is the front
    /// door's concern, #88). Over SSH / without a local browser the caller prints the URL instead
    /// (ADR-0014 §3: "the handoff is an address, not a process switch").
    /// </summary>
    public void HandOffToWeb(string dashboardUrl, IWebUiHost webHost)
    {
        _mirror($"The install now continues in the dashboard at: {dashboardUrl}");
        webHost.Show(dashboardUrl);
        webHost.OpenInBrowser(dashboardUrl);
        _mirror($"Dashboard opened at {dashboardUrl} — the rest of the install continues there.");
    }
}
