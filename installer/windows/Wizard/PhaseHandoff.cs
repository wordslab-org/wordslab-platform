namespace Wordslab.Wizard;

/// <summary>The three UIs of the one guided journey, in sequence (ADR-0014 §3).</summary>
public enum Phase { Native, PythonTui, Web }

/// <summary>
/// Decides when the wizard hands off: native -> Python TUI once Python (via uv) exists, and the
/// journey's final act resolves to the web handoff — "an address, not a process switch"
/// (ADR-0014 §3 phase 3). The handoff is surfaced to the user, never silent.
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

    /// <summary>True when a Python interpreter is reachable (the uv-installed one from the bootstrap).</summary>
    public bool PythonAvailable(string pythonCommand = "python3") =>
        _process.Run(pythonCommand, new[] { "--version" }, null, null) == 0;

    /// <summary>Launches the Python TUI (phase 2) with the collected parameters file. Returns its exit code.</summary>
    public int HandOffToPythonTui(string pythonCommand, string tuiScript, string parametersFile)
    {
        _mirror("Python is available — handing the journey to the Python installer TUI.");
        return _process.Run(pythonCommand, new[] { tuiScript, "--parameters", parametersFile },
            line => _mirror(line), line => _mirror($"! {line}"));
    }

    /// <summary>
    /// The web handoff (phase 3): once the core + dashboard are reachable, the Windows installer
    /// renders the web UI phase in its embedded WebView2 host, then opens the dashboard in the
    /// browser. Over SSH / without a local browser the caller prints the URL instead
    /// (ADR-0014 §3: "the handoff is an address, not a process switch").
    /// </summary>
    public void HandOffToWeb(string dashboardUrl, IWebUiHost webHost)
    {
        _mirror($"The platform core and dashboard are up: {dashboardUrl}");
        webHost.Show(dashboardUrl);
        webHost.OpenInBrowser(dashboardUrl);
        _mirror($"Dashboard opened at {dashboardUrl} — the rest of the install continues in the dashboard.");
    }
}
