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
Expect: Passed: 29, Failed: 0.

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
   C:\wordslab\wordslab.exe" line, then one checkbox row per fixed drive showing the exact
   Linux-disk **folder** it will create (`<drive>:\wordslab\wordslab-<drive>\` — WSL manages
   that folder's contents, its ext4.vhdx lives inside; #88 ruling, no loose VHDX). Untick a
   drive → it must be absent from the written parameters JSON
   (`wordslab-install-parameters.json` next to the exe).
3. Six numbered cards are visible from the start (right column), each with a number badge and
   its title — no status text before the install starts.
4. Press **Start install**: cards activate one by one — progress ring spins, the status sentence
   updates ("Checking the internet connection"…), and the last 3 output lines stream live on
   the card (a longer log ends with "··· more"; tapping it shows everything, "··· show less" folds back);
   since #88 the streamed lines are the real step reports ("github.com: reachable (HTTP 200)",
   "Creating the Wordslab virtual machine — the download takes a few minutes the first time."…).
5. If Windows' built-in Linux is not switched on yet (fresh machine): step 2 shows its sentence,
   and when the feature switch needs Windows admin the wizard asks Windows **once** (one UAC
   dialog — no console window) and restarts itself elevated; the same window and six steps come
   back. Declining the dialog must leave a plain sentence naming both ways forward.
6. On a machine with WSL already on (yours): steps 1–5 turn green, each showing the step's own
   final report line. Step 6 is **expected red until #62 (core) and #92 (cert + name) land** — its
   card shows the plain sentence ("The Wordslab home page did not answer yet…"), never a fake green.
   Screenshot 5/6 as you get them.

## S4 — the WebView2 handoff alone

```
dotnet run --project Wizard.App -- --webview-preview
```
Expect: the same window showing the dashboard area rendering `https://wordslab.local/`
(a TLS error page is FINE and expected — the front door does not exist yet) and an
"Open in your browser instead" button that opens your default browser. Screenshot the window.

## S5 — the #88 machinery on the real machine (state checks in PowerShell)

After a full **Start install** run (S3), check the machine state it claims — every check is a
plain command, nothing hidden:

```
wsl -l -v                    # wordslab, plus wordslab-<letter> per enabled drive — nothing else required
wsl --manage wordslab --show 2>$null  # (older wsl: get the location from the import line) shows the folder under C:\wordslab\virtual-machines\wordslab
dir D:\wordslab\wordslab-d   # contains ext4.vhdx (WSL-managed) — the folder the card promised
wsl -d wordslab -- ls /mnt/wordslab          # one folder per enabled drive, bind-mounted by step 4
wsl -d wordslab -- uv --version              # engine slot: uv in /usr/local/bin
wsl -d wordslab -- sh -c "ls /opt/wordslab/python"   # uv-managed Python landing place
dir $env:LOCALAPPDATA\..* -Filter wordslab-front-door.url  # or next to the exe: the handoff address file step 6 writes (only when a home page answered)
```

Then the **idempotency promise** (ADR-0014 §7, #88 exit criterion): press **Start install**
again. Expect steps 1–5 green again with "already there - keeping it" / "already installed -
keeping it" / "already switched on" lines — no downloads re-fetched, no machine recreated, no
data disk touched.

And the **re-runnable promise**: from WSL, run a shared script by hand with the same file the
UI wrote:
`wsl -d wordslab -- bash /mnt/c/.../installer/scripts/distro/04-data-volumes.sh --parameters <the parameters.json>`
→ same output, exit 0, mounts unchanged.

## S6 — what must NOT happen

- No console window at any point of S3/S4 (the UI is pure WinUI 3 — XAML, Mica, rounded cards);
  no WinForms/WPF window (check window styles / task manager).
- Nothing installed silently: every command has a visible numbered status and streamed output lines.
- No `wsl --mount`, no loose VHDX, no diskpart anywhere (#88 ruling) — `wsl -l -v` after install
  shows the named distros, and each one's folder on its chosen drive holds its ext4.vhdx.
- The TUI is never shown on Windows — it exists only for the Linux journey.

## S7 — standalone publish (no .NET installed)

```powershell
dotnet publish Wizard.App -c Release -r win-x64 --self-contained
```

Expected: a publish folder whose `Wizard.App.exe` launches the same journey on any Windows
10/11 x64 with **no .NET and no Windows App Runtime installed**. (Final exe name, payload
copy and icon metadata are #94's packaging job.)

Send screenshots of S3 (journey cards, ideally one mid-run streaming output) and S4
(webview handoff).
