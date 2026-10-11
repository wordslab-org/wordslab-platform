using Wordslab.Wizard;

// Wordslab Platform — phase-1 native wizard (ADR-0014 §3 phase 1).
// Thin by design: it collects the initial parameters, runs the numbered bootstrap scripts while
// mirroring their output, then hands off to the Python TUI once Python exists. The bootstrap
// scripts themselves are ticket #88's home; here they are the numbered slots the wizard drives.

string parametersFile = Path.Combine(AppContext.BaseDirectory, "wordslab-install-parameters.json");

#if WINDOWS
// Dev/verification aid: open the embedded webview host directly (renders the front-door URL even
// before the core exists) so the WinUI 3 + WebView2 host can be exercised on the Windows host.
if (args.Contains("--webview-preview"))
{
    var previewHost = new Wordslab.Wizard.WebUi.WebView2Host();
    previewHost.Show("https://wordslab.local/");
    previewHost.OpenInBrowser("https://wordslab.local/");
    Console.WriteLine("Webview preview open at https://wordslab.local/ — close the window to exit.");
    Thread.Sleep(Timeout.Infinite);
    return 0;
}
#endif

var process = new ProcessRunner();
var runner = new ScriptRunner(process, Console.WriteLine);
var handoff = new PhaseHandoff(process, Console.WriteLine);

Console.WriteLine("Wordslab Platform installer — phase 1 (native).");
Console.WriteLine("Every step is shown as a numbered script; you can re-run any of them yourself.");
Console.WriteLine();

var collector = new ParameterCollector(spec => Console.ReadLine());

var specs = new List<ParameterSpec>
{
    new("data_disk", "Which disk should hold the Wordslab data volumes? (type a drive path, e.g. D:\\)",
        DriveInfo.GetDrives().FirstOrDefault(d => d.DriveType == DriveType.Fixed && d.Name != "C:\\")?.Name,
        ParameterCollector.ValidateDiskPath),
    new("join_lan", "Join an existing Wordslab platform on this network if one is found? (y/n)",
        "y", ParameterCollector.ValidateYesNo),
};

var answers = collector.Collect(specs);
ParameterCollector.WriteParameters(answers, parametersFile);
Console.WriteLine($"Parameters saved to {parametersFile} — the later phases read the same file.");
Console.WriteLine();

// The numbered bootstrap scripts (their content is #88; the wizard owns the running + mirroring).
var steps = new List<ScriptStep>
{
    new(1, "Check network reachability (github, pypi)", "pwsh",
        new[] { "-NoProfile", "-Command", "Write-Output 'reachability check: placeholder until #88'" }),
    new(2, "Install WSL + the Wordslab distro + virtual disks", "pwsh",
        new[] { "-NoProfile", "-Command", "Write-Output 'wsl bootstrap: placeholder until #88'" }),
    new(3, "Install uv + Python inside the distro", "wsl.exe",
        new[] { "--", "bash", "-c", "echo 'uv bootstrap: placeholder until #88'" }),
};

var results = runner.RunAll(steps);
if (results.Count != steps.Count || !results.All(r => r.Success))
{
    Console.WriteLine("The journey stopped on a failed script. Fix the cause and re-run the installer — re-running is safe (Update path, ADR-0014 §7).");
    return 1;
}

if (!handoff.PythonAvailable("wsl.exe"))
{
    Console.WriteLine("Python is not available yet — the bootstrap scripts above must complete first.");
    return 1;
}

int tuiExit = handoff.HandOffToPythonTui("wsl.exe", "installer/tui.py", parametersFile);
if (tuiExit != 0)
    return tuiExit;

#if WINDOWS
// Phase 3 (Windows host): the TUI finished the bootstrap and the core + dashboard are up —
// render the web UI phase in the installer's embedded WebView2 window, then open the browser
// (ADR-0014 §2). Over SSH the TUI printed the URL instead and this branch never runs.
const string dashboardUrl = "https://wordslab.local/";
handoff.HandOffToWeb(dashboardUrl, new Wordslab.Wizard.WebUi.WebView2Host());
#endif
return 0;

// Default process runner: streams stdout/stderr line by line.
sealed class ProcessRunner : IProcessRunner
{
    public int Run(string command, IReadOnlyList<string> args, Action<string>? onStdout, Action<string>? onStderr)
    {
        using var p = new System.Diagnostics.Process();
        p.StartInfo = new System.Diagnostics.ProcessStartInfo
        {
            FileName = command,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        foreach (var a in args) p.StartInfo.ArgumentList.Add(a);
        try
        {
            p.Start();
        }
        catch (Exception ex)
        {
            onStderr?.Invoke(ex.Message);
            return -1;
        }
        p.OutputDataReceived += (_, e) => { if (e.Data != null) onStdout?.Invoke(e.Data); };
        p.ErrorDataReceived += (_, e) => { if (e.Data != null) onStderr?.Invoke(e.Data); };
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
        p.WaitForExit();
        return p.ExitCode;
    }
}
