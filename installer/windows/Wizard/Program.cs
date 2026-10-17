using Wordslab.Wizard;

// Wordslab Platform — phase-1 native wizard (ADR-0014 §3 phase 1).
// Thin by design: it collects the initial parameters, runs the numbered bootstrap scripts while
// mirroring their output, then hands off to the Python TUI once Python exists. The bootstrap
// scripts themselves are ticket #88's home; here they are the numbered script FILES the wizard
// drives (installer/scripts/windows/) — real files so any step stays re-runnable by hand.

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
    previewHost.WaitUntilClosed();
    if (previewHost.StartFailure is not null)
        Console.WriteLine($"Webview could not start in this session ({previewHost.StartFailure.GetType().Name}).");
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

// Only parameters with teeth in THIS ticket (ADR-0014 §5 data locations). The join decision
// belongs to the join flow (#90), where it does something.
var specs = new List<ParameterSpec>
{
    new("data_disk", "Which disk should hold the Wordslab data volumes? (type a drive path, e.g. D:\\)",
        DriveInfo.GetDrives().FirstOrDefault(d => d.DriveType == DriveType.Fixed && d.Name != "C:\\")?.Name,
        ParameterCollector.ValidateDiskPath),
};

var answers = collector.Collect(specs);
ParameterCollector.WriteParameters(answers, parametersFile);
Console.WriteLine($"Parameters saved to {parametersFile} — the later phases read the same file.");
Console.WriteLine();

// The wizard ships inside the checkout/payload; walk up from the binary to the root that holds
// the installer layout (installer/ in a checkout, the payload root itself when installed).
static string? FindInstallerDir()
{
    for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
    {
        if (File.Exists(Path.Combine(dir.FullName, "installer", "python", "tui.py")))
            return Path.Combine(dir.FullName, "installer");
        if (File.Exists(Path.Combine(dir.FullName, "python", "tui.py")))
            return dir.FullName;
        if (dir.Parent is null) break;
    }
    return null;
}

string? installerDir = FindInstallerDir();
if (installerDir is null)
{
    Console.WriteLine("FAILED — the installer payload (python/tui.py + scripts/) was not found next to this wizard. Nothing further is installed.");
    return 1;
}
string scriptsWindows = Path.Combine(installerDir, "scripts", "windows");

// Step 3 runs inside the distro; translate its script path up front. Without WSL the path
// cannot resolve — the step then fails loudly through wsl.exe's own error output, after
// steps 1–2 have run, instead of silently skipping anything.
string step3Script = Path.Combine(scriptsWindows, "03-uv-python.sh");
string step3Path = handoff.ToDistroPath("wsl.exe", step3Script) ?? step3Script;

// The numbered bootstrap scripts (their content is #88; the wizard owns the running + mirroring).
var steps = new List<ScriptStep>
{
    new(1, "Check network reachability (github, pypi)", "pwsh",
        new[] { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", Path.Combine(scriptsWindows, "01-reachability.ps1") }),
    new(2, "Install WSL + the Wordslab distro + virtual disks", "pwsh",
        new[] { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", Path.Combine(scriptsWindows, "02-wsl-distro-disks.ps1") }),
    new(3, "Install uv + Python inside the distro", "wsl.exe",
        new[] { "--", "bash", step3Path }),
};

var results = runner.RunAll(steps);
if (results.Count != steps.Count || !results.All(r => r.Success))
{
    Console.WriteLine("The journey stopped on a failed script. Fix the cause and re-run the installer — re-running is safe (Update path, ADR-0014 §7).");
    return 1;
}

// The distro's Python only exists once the uv/Python bootstrap (step 3, #88) has run.
if (!handoff.PythonAvailableInWsl())
{
    Console.WriteLine("Python is not available in the distro yet — the bootstrap scripts above must complete first.");
    return 1;
}

string tuiScript = Path.Combine(installerDir, "python", "tui.py");
int tuiExit = handoff.HandOffToPythonTuiInWsl(tuiScript, parametersFile, journey: "windows");
if (tuiExit != 0)
    return tuiExit;

#if WINDOWS
// Phase 3 (Windows host): the TUI finished the bootstrap and printed the dashboard address —
// render the web UI phase in the installer's embedded WebView2 window, then open the browser
// (ADR-0014 §2). In a headless/SSH session the webview or browser cannot start: fall back to
// printing the address — the handoff is an address, not a process switch, either way.
const string dashboardUrl = "https://wordslab.local/";
var webHost = new Wordslab.Wizard.WebUi.WebView2Host();
try
{
    handoff.HandOffToWeb(dashboardUrl, webHost);
}
catch (Exception ex)
{
    Console.WriteLine($"Embedded webview/browser unavailable in this session ({ex.GetType().Name}).");
}
webHost.WaitUntilClosed(); // the web phase lasts exactly as long as its window
if (webHost.StartFailure is not null)
    Console.WriteLine($"The install continues at {dashboardUrl} — open it in your browser (no desktop session for the webview).");
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
