using Microsoft.UI.Xaml;

namespace Wordslab.Wizard.App;

public partial class App : Application
{
    public App() => InitializeComponent();

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        // Dev/verification aid: jump straight to the embedded webview (renders the front-door
        // address even before the core exists) so the WebView2 handoff can be exercised alone.
        bool preview = Environment.GetCommandLineArgs().Contains("--webview-preview");
        var window = new MainWindow(preview);
        window.Activate();
    }
}
