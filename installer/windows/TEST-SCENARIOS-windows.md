# Windows test scenarios — ticket #87 (for Laurent, native host)

Run these on the Windows machine (the Hermes gateway there). The repo clone must have the .NET 10
SDK (`winget install Microsoft.DotNet.SDK.10`). All commands from `installer\windows\`.

## S1 — the solution builds natively

```
dotnet build
```
Expect: Build succeeded, 0 errors (no `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT` needed on Windows).

## S2 — the C# contract tests pass natively

```
dotnet test
```
Expect: Passed: 14, Failed: 0.

## S3 — the phase-1 console wizard runs

```
dotnet run --project Wizard
```
Expect, in order:
1. Header "Wordslab Platform installer — phase 1 (native)." + the transparency line.
2. One parameter prompt with a visible default (`data_disk` defaults to the first non-C fixed
   drive). Type a bogus disk path → expect "not a valid drive path" and the prompt re-asked.
   Type `D:\` (or your data disk) → accepted.
3. "Parameters saved to ...wordslab-install-parameters.json".
4. Three numbered scripts `[01]..[03]`, each running a real script FILE under
   `installer\scripts\windows\` and printing its placeholder line (the files say
   "placeholder until #88" — you can re-run any of them by hand).
5. Handoff: the wizard probes `wsl -- python3 --version`.
   - No WSL distro / no python3 in it → "Python is not available in the distro yet — the bootstrap
     scripts above must complete first." (exit 1). Screenshot it.
   - With a WSL distro containing Python 3 → "Python is available in the distro — handing the
     journey to the Python installer TUI." then the phase-2 TUI output (`[01]..[06]` placeholders
     + the web-handoff address line), then — on a GUI session — the WebView2 window. Screenshot
     whichever you get.

## S4 — the embedded webview host (WinUI 3 + WebView2)

The webview window only opens after the TUI phase succeeds (phase 3). To exercise the host alone,
run from `installer\windows\`:

```
dotnet run --project Wizard -- --webview-preview
```

Expect: a window titled "Wordslab Platform — install" rendering `https://wordslab.local/`
(a TLS error page is FINE and expected — the front door does not exist yet; the point is the
WebView2 window renders and the installer process stays alive beside it). Closing the window
ends the app. Screenshot the window.

## S5 — what must NOT happen

- No WinForms/WPF window anywhere (task manager / window styles: the window is WinUI 3 — rounded,
  Mica-ish title bar).
- Nothing installed silently: every action is a numbered, mirrored line.

Send screenshots of S3 (wizard output) and S4 (webview window).
