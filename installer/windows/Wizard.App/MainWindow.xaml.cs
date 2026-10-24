using System.Collections.ObjectModel;
using Microsoft.UI.Xaml;
using Wordslab.Wizard.Core;
using Wordslab.Wizard.Core.Scripts;

namespace Wordslab.Wizard.App;

/// <summary>The whole Windows experience of ticket #87: one window, the numbered journey with
/// live streaming progress (Wizard.Core reports rendered straight onto the step cards), and the
/// web handoff. The code-behind only wires events to Wizard.Core — every decision lives there.</summary>
public sealed partial class MainWindow : Window
{
    private const string DashboardUrl = "https://wordslab.local/";

    private readonly NumberedScript[] _journey =
    {
        new Script01NetworkReachability(), new Script02WslDistroDisks(), new Script03UvPythonInDistro(),
        new Script04DataVolumes(), new Script05FirstPlatformCore(), new Script06FrontDoor(),
    };

    public ObservableCollection<StepVm> Steps { get; } = new();
    public ObservableCollection<DriveVm> Disks { get; } = new();
    private string _installDir = "";
    private string _parametersFile = "";
    private string _handoffUrl = DashboardUrl;
    private readonly ICommandExecutor _executor = new ProcessCommandExecutor();
    private readonly JourneyRunner _runner;
    private bool _running;

    public MainWindow(bool webViewPreview)
    {
        InitializeComponent();
        // The Wordslab lab-flask mark (from wordslab-notebooks, cropped + transparent):
        // title bar + taskbar. WinUI 3 has no Window.Icon/BitmapIcon (UWP-ism) — the desktop
        // window icon goes through AppWindow.SetIcon with a real file path (asset is copied
        // to the output). An icon failure is cosmetic, never fatal to the install.
        try
        {
            // Window.AppWindow: Windows App SDK 1.4+. The multi-size .ico is what SetIcon
            // renders most reliably in the title bar and taskbar; PNG as fallback.
            string stem = Path.Combine(AppContext.BaseDirectory, "Assets", "wordslab-mark");
            AppWindow.SetIcon(File.Exists(stem + ".ico") ? stem + ".ico" : stem + ".png");
        }
        catch (Exception ex) { System.Diagnostics.Debug.WriteLine($"icon: {ex}"); }
        // The original complaint: the window must be wide enough to keep all six step
        // cards visible — the layout is left (intro + locations) / right (live steps).
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1420, 940));
        _runner = new JourneyRunner(_executor);

        foreach (var script in _journey)
            Steps.Add(new StepVm(script.Number, script.Title));

        var skipped = new List<string>();
        foreach (var d in DriveInfo.GetDrives())
        {
            string drive = d.Name.TrimEnd('\\'); // "C:"
            if (d.DriveType is DriveType.CDRom or DriveType.Unknown) continue;
            if (d.DriveType != DriveType.Fixed)
            {
                skipped.Add($"{drive} ({d.DriveType.ToString().ToLower()} drive)");
                continue;
            }
            long freeGb;
            try { freeGb = d.AvailableFreeSpace / (1024 * 1024 * 1024); }
            catch (Exception) { freeGb = -1; } // fixed but momentarily locked — still list it
            Disks.Add(new DriveVm { Drive = drive, FreeGb = freeGb, Folder = drive + "\\wordslab" });
        }
        DiskList.ItemsSource = Disks;
        if (skipped.Count > 0) // transparency over silence: say what was left out and why
        {
            SkipsLine.Text = "Not listed: " + string.Join(", ", skipped) +
                " — Wordslab's Linux disks live on physical internal drives.";
            SkipsLine.Visibility = Visibility.Visible;
        }
        // v1: paths are fixed — <drive>:\wordslab everywhere (one less decision for a
        // first-time user). The window only informs: program exe + the exact Linux disk folders.
        string systemRoot = Path.GetPathRoot(Environment.SystemDirectory) ?? "C:\\";
        _installDir = systemRoot.TrimEnd('\\') + "\\wordslab";
        ProgramLine.Text = $"Program:  {_installDir}\\wordslab.exe";

        if (webViewPreview)
            _ = ShowWebHandoffAsync("Webview preview — the dashboard will live here");
    }

    private async void StartInstall_Click(object sender, RoutedEventArgs e)
    {
        if (_running) return;

        // No free-text fields in v1: the paths shown on screen ARE the paths used.
        string? installerDir = PayloadLocator.FindInstallerDir(AppContext.BaseDirectory);
        if (installerDir is null)
        {
            StatusLine.Text = "Something is missing: the Wordslab installer files were not found next to this window, so nothing was installed. Copy the whole installer folder (not just this file), then try again.";
            return;
        }

        var parameters = Parameters.ForWindows(
            _installDir,
            Disks.Where(d => d.Enabled).Select(d => (d.Drive, d.Folder)));
        string parametersFile = Path.Combine(AppContext.BaseDirectory, "wordslab-install-parameters.json");
        Parameters.Write(parameters, parametersFile);
        _parametersFile = parametersFile;

        var ctx = new InstallContext
        {
            InstallerDir = installerDir,
            Parameters = parameters,
            ParametersFile = parametersFile,
            WslPaths = new WslPathTranslator(_executor),
        };

        _running = true;
        StartButton.IsEnabled = false;
        StatusLine.Text = "Starting the six steps below. Nothing is installed silently — each one runs live, and starting again is always safe.";

        IReadOnlyList<StepResult> results;
        try
        {
            results = await _runner.RunAsync(_journey, ctx, report =>
                DispatcherQueue.TryEnqueue(() => ApplyReport(report)));
        }
        catch (Exception ex)
        {
            StatusLine.Text = $"FAILED — {ex.Message}. Nothing further is installed.";
            _running = false;
            StartButton.IsEnabled = true;
            return;
        }

        bool complete = results.Count == _journey.Length && results.All(r => r.Success);
        if (complete && !await _runner.PythonAvailableInDistroAsync())
        {
            StatusLine.Text = "Almost there — the Wordslab engine (Python) is not ready inside the Linux virtual machine yet. Press Start install again to continue; starting over is safe.";
            _running = false;
            StartButton.IsEnabled = true;
            return;
        }

        if (complete)
        {
            // The front-door step wrote its answered address next to the parameters file (#88
            // ruling: hand off to the VM's own address until #92/#94 land mDNS naming + CA trust).
            // From here the handoff stays an address, never a process switch (ADR-0014 §3 phase 3).
            _handoffUrl = FrontDoorAddress.ReadFor(_parametersFile, DashboardUrl);
            await ShowWebHandoffAsync("Wordslab is set up — the rest happens in your dashboard");
        }
        else
        {
            // One UAC prompt, zero console windows: switching Windows' built-in Linux on for the
            // first time is the single moment this wizard ever needs Windows admin. When step 2
            // failed and we are not elevated, the wizard restarts ITSELF with the approval asked
            // from Windows directly (ADR-0014: no console, no "run me as admin" instructions).
            bool wslStepFailed = results.Any(r => r.Script.Number == 2 && !r.Success);
            if (wslStepFailed && !IsElevated())
            {
                StatusLine.Text = "Windows' built-in Linux needs Windows admin approval the first time it is switched on — Wordslab asks Windows once, right now.";
                if (TryRelaunchElevated())
                {
                    Close(); // the elevated wizard takes over; same window, same six steps
                    return;
                }
                StatusLine.Text = "The Windows approval was declined. Press Start install again to be asked once, or start Wordslab once with right-click → Run as administrator.";
                _running = false;
                StartButton.IsEnabled = true;
                return;
            }
            StatusLine.Text = "The install stopped at the step marked in red. Open \"output\" on that card to see what went wrong, then press Start install again — starting over is safe.";
            _running = false;
            StartButton.IsEnabled = true;
        }
    }

    private static bool IsElevated()
    {
        using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
        return new System.Security.Principal.WindowsPrincipal(identity)
            .IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
    }

    private static bool TryRelaunchElevated()
    {
        try
        {
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = Environment.ProcessPath!,
                UseShellExecute = true,
                Verb = "runas", // the one UAC prompt Windows itself shows
            });
            return true;
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return false; // the approval was declined — say so plainly
        }
    }

    private void ApplyReport(Report report)
    {
        var vm = Steps.First(s => s.Number == report.Step);
        switch (report.Kind)
        {
            case ReportKind.Info:
                vm.IsRunning = true;
                vm.StatusText = "running…";
                break;
            case ReportKind.Start:
                vm.StatusText = report.Text;
                vm.AppendLog(report.Text);
                break;
            case ReportKind.Stdout or ReportKind.Stderr:
                vm.AppendLog(report.Kind == ReportKind.Stderr ? $"! {report.Text}" : report.Text);
                break;
            case ReportKind.Success:
                // "done" says nothing — show the step's own final report line instead.
                vm.MarkSuccess();
                break;
            case ReportKind.Failure:
                vm.IsRunning = false;
                vm.IsFailed = true;
                vm.StatusText = report.Text;
                vm.AppendLog(report.Text);
                break;
        }
    }

    // "··· more" / "··· show less": the log tail toggles in place (DataTemplate DataContext).
    private void LogTail_Tapped(object sender, Microsoft.UI.Xaml.Input.TappedRoutedEventArgs e)
    {
        if (sender is FrameworkElement { DataContext: StepVm vm }) vm.ToggleLog();
    }

    private async Task ShowWebHandoffAsync(string title)
    {
        JourneyPanel.Visibility = Visibility.Collapsed;
        WebPanel.Visibility = Visibility.Visible;
        WebTitle.Text = title;
        WebUrl.Text = _handoffUrl;
        try
        {
            // WinAppSDK's bundled WebView2 projection has no named 'userDataFolder' CreateAsync
            // overload; the documented knob is the WEBVIEW2_USER_DATA_FOLDER environment variable.
            Environment.SetEnvironmentVariable(
                "WEBVIEW2_USER_DATA_FOLDER",
                Path.Combine(Path.GetTempPath(), "wordslab-installer-webview"));
            await Web.EnsureCoreWebView2Async();
            Web.CoreWebView2.Navigate(_handoffUrl);
        }
        catch (Exception ex)
        {
            // No WebView2 runtime / no desktop session: the handoff is an address — say so plainly.
            WebUrl.Text = $"{_handoffUrl}  (the embedded browser is unavailable: {ex.GetType().Name} — use “Open in a web browser”)";
        }
    }

    private void OpenInBrowser_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
            {
                FileName = _handoffUrl,
                UseShellExecute = true,
            });
        }
        catch (Exception ex)
        {
            WebUrl.Text = $"{_handoffUrl}  (could not open the browser: {ex.Message} — copy the address)";
        }
    }
}
