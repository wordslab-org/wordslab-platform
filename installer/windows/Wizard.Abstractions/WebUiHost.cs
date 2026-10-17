namespace Wordslab.Wizard.Abstractions;

/// <summary>The embedded web-UI host seam (ADR-0014 §2: the installer "renders the web-UI phase in an
/// embedded webview; on completion opens the dashboard in the browser itself"). Implemented by the
/// WinUI 3 + WebView2 host (Wizard.WebUi) on the Windows build.</summary>
public interface IWebUiHost
{
    void Show(string url);
    void OpenInBrowser(string url);
}
