using System.Runtime.InteropServices;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Wordslab.Wizard;

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
/// Over SSH / without a local browser the caller never constructs this host and prints the URL
/// instead (ADR-0014 §3: "the handoff is an address, not a process switch").
/// </summary>
public sealed class WebView2Host : IWebUiHost, IDisposable
{
    private Thread? _uiThread;

    public void Show(string url)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException(
                "The embedded webview is a Windows-host surface; remote installs print the dashboard URL instead (ADR-0014 §3).");

        // WinUI 3 needs an STA thread with its own message pump; the console wizard stays alive.
        _uiThread = new Thread(() => Application.Start(_ => new InstallApp(url)))
        {
            IsBackground = true,
            Name = "wordslab-webview-ui",
        };
        _uiThread.SetApartmentState(ApartmentState.STA);
        _uiThread.Start();
    }

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

    public void Dispose()
    {
        // The UI thread is a background thread; closing its window ends the pump.
        _uiThread = null;
    }
}

/// <summary>The WinUI 3 application for the installer's web phase — pure C#, no XAML markup.</summary>
sealed class InstallApp : Application
{
    private readonly string _url;
    private Window? _window;

    public InstallApp(string url) => _url = url;

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

        _ = NavigateAsync(view);
        _window.Activate();
    }

    private async Task NavigateAsync(WebView2 view)
    {
        await view.EnsureCoreWebView2Async();
        view.CoreWebView2.Navigate(_url);
    }
}
