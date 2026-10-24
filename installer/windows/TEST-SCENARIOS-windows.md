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
Expect a single modern WinUI window (Mica backdrop, rounded cards) — **no console window, no
TUI**:
1. Title "Welcome to Wordslab Platform" ("lab" in small caps where the font supports it) +
   two intro paragraphs: what Wordslab is (soul-faithful) and what this installer will do.
2. An install-locations card: a prefilled program-folder text box, then one row per fixed drive
   (checkbox ticked + "<drive> — N GB free" + a prefilled folder). Untick one drive → it must be
   absent from the written parameters JSON. Type a folder on the wrong drive → red
   "The Wordslab folder for drive D: must be on that drive…" (multiple problems join on one line).
3. Six numbered cards are visible from the start, each with a number badge and its title.
4. Press **Start install**: cards activate one by one — progress ring spins, the status sentence
   updates ("Checking the internet connection"…), and the "output" expander appears with
   the streamed placeholder lines ("placeholder until #88").
5. Without a WSL distro installed: steps 2–6 show the loud `FAILED (exit …)` line in their card
   and the bottom line says the journey stopped and re-running is safe. Screenshot this.
6. With WSL + a distro containing Python 3: all six cards turn done, then the window becomes the
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
- Nothing installed silently: every command has a visible numbered status and streamed output.
- The TUI is never shown on Windows — it exists only for the Linux journey.

Send screenshots of S3 (journey cards, ideally one mid-run with the expander open) and S4
(webview handoff).
