using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Wordslab.Wizard.Abstractions;

namespace Wordslab.Wizard.WebUi;

/// <summary>
/// The installer's embedded web-UI host (ADR-0014 §2: the installer "renders the web-UI phase in an
/// embedded webview; on completion opens the dashboard in the browser itself").
///
/// Modern Windows UI stack: WinUI 3 (Windows App SDK) hosting the WebView2 control — no WinForms,
/// no WPF. Built in pure C# (no XAML markup): the window and the WebView2 element are constructed
/// in code, so the project also compiles on Linux (EnableWindowsTargeting) and runs on the Windows
/// host. Built now, ahead of the dashboard: <see cref="Show"/> opens the WebView2 window at the
/// given URL; when the core + dashboard exist (stage 2) the same window renders the install web UI.
///
/// Lifetime: the web phase keeps the installer process alive exactly as long as its window is on
/// screen — the caller blocks in <see cref="WaitUntilClosed"/> until the window is closed. In a
/// headless/SSH session the pump cannot start: <see cref="StartFailure"/> records it and the
/// caller prints the URL instead (ADR-0014 §3: "the handoff is an address, not a process switch").
/// </summary>
public sealed class WebView2Host : IWebUiHost
{
    private readonly ManualResetEventSlim _windowClosed = new(false);
    private Thread? _uiThread;

    /// <summary>Set when the WinUI 3 message pump could not start (headless / SSH session): the
    /// caller falls back to printing the address instead of rendering a window.</summary>
    public Exception? StartFailure { get; private set; }

    public void Show(string url)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException(
                "The embedded webview is a Windows-host surface; remote installs print the dashboard URL instead (ADR-0014 §3).");

        // WinUI 3 needs an STA thread with its own message pump; the console wizard stays alive
        // and joins this thread via WaitUntilClosed(). A headless/SSH session cannot start the
        // pump — record it and unblock the caller rather than crash the journey's last step.
        _uiThread = new Thread(() =>
        {
            try
            {
                Application.Start(_ => new InstallApp(url, OnWindowClosed));
            }
            catch (Exception ex)
            {
                StartFailure = ex;
                _windowClosed.Set();
            }
        })
        {
            IsBackground = true,
            Name = "wordslab-webview-ui",
        };
        _uiThread.SetApartmentState(ApartmentState.STA);
        _uiThread.Start();
    }

    /// <summary>Blocks until the webview window is closed, so the installer does not exit while the
    /// user is still reading it.</summary>
    public void WaitUntilClosed() => _windowClosed.Wait();

    private void OnWindowClosed() => _windowClosed.Set();

    public void OpenInBrowser(string url)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("Opening the browser is a Windows-host surface.");
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
        {
            FileName = url,
            UseShellExecute = true,
        });
    }
}

/// <summary>The WinUI 3 application for the installer's web phase — pure C#, no XAML markup.</summary>
sealed class InstallApp : Application
{
    private readonly string _url;
    private readonly Action _onWindowClosed;
    private Window? _window;

    public InstallApp(string url, Action onWindowClosed)
    {
        _url = url;
        _onWindowClosed = onWindowClosed;
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        _window = new Window { Title = "Wordslab Platform — install" };

        var view = new WebView2
        {
            HorizontalAlignment = HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Stretch,
        };
        var root = new Grid();
        root.Children.Add(view);
        _window.Content = root;
        _window.Closed += (_, _) => _onWindowClosed();

        _ = NavigateAsync(view);
        _window.Activate();
    }

    private async Task NavigateAsync(WebView2 view)
    {
        await view.EnsureCoreWebView2Async();
        view.CoreWebView2.Navigate(_url);
    }
}
