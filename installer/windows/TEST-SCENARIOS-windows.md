# Windows test scenarios — ticket #87 (for Laurent, native host)

Run these on the Windows machine. The repo clone must have the .NET 10 SDK
(`winget install Microsoft.DotNet.SDK.10`). All commands from `installer\windows\`.

## S1 — everything builds natively

```
Remove-Item -Recurse -Force Wizard.App\bin, Wizard.App\obj -ErrorAction SilentlyContinue
dotnet build
```
Expect: Build succeeded, 0 errors — including `Wizard.App` (XAML markup compiles on Windows).

## S2 — the C# contract tests pass natively

```
dotnet test Wizard.Tests
```
Expect: Passed: 18, Failed: 0.

## S3 — the WinUI journey (the whole Windows experience)

```
dotnet run --project Wizard.App
```
Expect a single modern WinUI window — white background, white cards with light borders, two
columns (left: intro + "Where Wordslab will live" card; right: all six step cards visible) —
**no console window, no TUI**:
1. Title "Welcome to Wordslab Platform" (brand is plain "Wordslab", lowercase lab) with the
   Wordslab lab-flask mark (wordmark included) in the title bar, taskbar and beside the heading,
   plus two intro paragraphs: what Wordslab is (soul-faithful) and what this installer will do.
2. The locations card is inform-only (v1 fixed paths, no text boxes): a "Program:
   C:\wordslab\wordslab.exe" line, then one checkbox row per fixed drive showing the exact VHDX
   path it will create (`<drive>:\wordslab\wordslab-<drive>.vhdx`). Untick a drive → it must be
   absent from the written parameters JSON (`wordslab-install-parameters.json` next to the exe).
3. Six numbered cards are visible from the start (right column), each with a number badge and
   its title — no status text before the install starts.
4. Press **Start install**: cards activate one by one — progress ring spins, the status sentence
   updates ("Checking the internet connection"…), and the last 3 output lines stream live on
   the card (a longer log ends with "··· more"; tapping it shows everything, "··· show less" folds back);
   the streamed placeholder lines ("placeholder until #88").
5. Without a WSL distro installed: steps 2–6 show the loud `FAILED (exit …)` line in their card
   and the bottom line says the journey stopped and re-running is safe. Screenshot this.
6. With WSL + a distro containing Python 3: all six cards turn green and each shows the step's own final report line as its result, then the window becomes the
   dashboard handoff. Screenshot whichever of 5/6 you get.

## S4 — the WebView2 handoff alone

```
dotnet run --project Wizard.App -- --webview-preview
```
Expect: the same window showing the dashboard area rendering `https://wordslab.local/`
(a TLS error page is FINE and expected — the front door does not exist yet) and an
"Open in your browser instead" button that opens your default browser. Screenshot the window.

## S5 — what must NOT happen

- No console window at any point of S3/S4 (the UI is pure WinUI 3 — XAML, Mica, rounded cards);
  no WinForms/WPF window (check window styles / task manager).
- Nothing installed silently: every command has a visible numbered status and streamed output lines.
- The TUI is never shown on Windows — it exists only for the Linux journey.

Send screenshots of S3 (journey cards, ideally one mid-run streaming output) and S4
(webview handoff).
