using System.Runtime.InteropServices;
using Microsoft.UI.Xaml;

namespace Wordslab.Wizard.App;

public partial class App : Application
{
    public App()
    {
        InitializeComponent();
        // Without an explicit AppUserModelID an unpackaged WinUI 3 app groups under the
        // generic host in the taskbar and its window icon is ignored there.
        try { SetCurrentProcessExplicitAppUserModelID("org.wordslab.installer"); } catch { }
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern int SetCurrentProcessExplicitAppUserModelID(string appID);

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        // Dev/verification aid: jump straight to the embedded webview (renders the front-door
        // address even before the core exists) so the WebView2 handoff can be exercised alone.
        bool preview = Environment.GetCommandLineArgs().Contains("--webview-preview");
        var window = new MainWindow(preview);
        window.Activate();
    }
}
