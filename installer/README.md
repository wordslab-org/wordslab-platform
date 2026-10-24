# Installer & bootstrap entry points (ticket #87)

The entry points and the phased guided journey (ADR-0014 §2/§3/§7). This is **not** a
base-contract service: no API, no DB, no keys (ADR-0003 §1 — the bootstrap layer lives below the
service contract).

**UI rule (maintainer decision):** Windows users see one beautiful, simple WinUI 3 journey from
start to web handoff — never a console, never a TUI. Linux users see the terminal scripts, then
the Python TUI, then the web UI. The XAML WinUI app is the mandated modern stack (WinForms and
WPF remain banned).

## Layout

- `windows/` — the Windows side (.NET 10):
  - `Wizard.Core/` — the wizard's brain, cross-platform and fully unit-tested on any OS:
    - `CommandExecution.cs` — the small command-execution library: `Command` (program + args +
      the human status sentence), streamed `ReportLine`s, an `ICommandExecutor` seam with a
      real streaming process executor (both pipes drained concurrently).
    - `NumberedScript.cs` — the numbered bootstrap scripts **as readable classes**; distro
      script classes run the shared numbered shell files (`DistroShellScript`) or Python files
      (`DistroPythonScript`, the #88 shape); paths cross into the distro only via `wslpath -u`; all `wsl.exe` output is decoded as UTF-16LE (its console encoding).
    - `Scripts/WindowsJourney.cs` — scripts 1–3 (everything WSL-specific up to the first step
      shared with Linux) as C# classes, plus the shared steps 4–6.
    - `JourneyRunner.cs` — runs the numbered scripts in order, streaming every status/output
      line out as reports for the UI, stop-on-first-failure loudly.
  - `Wizard.App/` — the WinUI 3 UI (XAML markup, Mica backdrop): install-locations card (the
    Windows program folder + one Linux disk per chosen drive, each switchable off — ADR-0014 §5),
    six numbered
    step cards with **live streaming progress** (progress ring, current status sentence,
    expandable output log), then a full-window WebView2 handoff. Unpackaged
    (`WindowsPackageType=None`). **Builds on Windows only** — XAML markup compilation
    (`XamlCompiler.exe`) is Windows tooling; all logic it renders lives in `Wizard.Core`.
    It writes `wordslab-install-parameters.json` with `install_dir` plus `volume_<DRIVE>` keys
    (one per enabled drive — the drive's wordslab folder; disabled drives get
    no key). v1 paths are FIXED (`<drive>:\wordslab`; the UI informs, it does not ask — one less
    decision for a first-timer), and the card shows the exact Linux-disk folder each install step
    will create (`<drive>:\wordslab\wordslab-<drive>\` — a folder WSL manages: its ext4.vhdx
    lives inside it, created by `wsl --import`, never a loose VHDX needing admin to attach — the
    #88 ruling). #88's scripts consume this contract; a data volume per disk, named after the disk.
  - `Wizard.Tests/` — xunit contract tests over the command-executor seam (no UI needed).
- `linux/install.sh` — the `curl … | bash` entry point: the same numbered journey (terminal
  output), artifact-gated handoff (never command-line gated); `linux/test_install_smoke.sh`
  is its smoke contract.
- `scripts/` — the numbered shared scripts as real files (`linux/` prefix steps, shared
  `distro/` steps 4–6) so every shared step is re-runnable by hand. Since #88 the `distro/`
  steps 4–6 carry their real machinery, and every one documents its contract (in / out / exit
  codes / re-run behaviour) in its file header; they all take `--parameters <file>` — the very
  JSON the wizard or TUI wrote (the shared parameters contract). Linux steps 1–3 keep visible
  placeholders until the payload download lands (#94 packaging). The Windows-only steps 1–3
  have no script files: they are C# classes in `Wizard.Core/Scripts/`, and their command plans
  are pinned as argv in `Wizard.Tests`.
- `python/` — the phase-2 installer API + TUI (uv project), the **Linux** phase-2 UI:
  `installer_api.py` (run/stream/interpret), `tui.py` (Linux journey shell + web handoff),
  `tests/` (pytest over the same stub-command seam).

## The phased journey (ADR-0014 §3)

| Phase | Windows | Linux |
|---|---|---|
| 1 native | WinUI window: parameter card, scripts 1–3 as C# classes with live progress | `install.sh` numbered terminal steps 1–3 |
| 2 shared steps | the same WinUI window wraps the shared distro shell scripts (streamed into the cards) — later the #88 Python steps via `DistroPythonScript` | Python TUI (`tui.py`) continues the numbered journey |
| 3 web | the window becomes a WebView2 rendering the dashboard address (+ "Open in your browser") | the TUI prints the dashboard URL to open elsewhere |

The handoff into phase 3 is **an address, not a process switch**, on every platform.

The numbered-runner contract — `[NN]` labels (bash/Python), `! ` stderr prefix, `FAILED (exit N)
— the journey stops here; nothing further is installed.` — is deliberately implemented three
times (C#, Python, bash) because each entry point must run standalone before any other exists.
The C# and Python contract tests pin the same strings and `linux/test_install_smoke.sh` checks
the bash copy end to end; keep them in step. The numbering is shared: Linux native steps 1–3
mirror `install.sh`, steps 4–6 are the same distro script files on both platforms
(`tui.py::journey_steps` ↔ `Wizard.Core/Scripts/`).

## The #88 machinery (the bootstrap's real content on Windows)

Design rulings, recorded on #88 (Laurent, 2026-10-24) — they shape every step:

- **No admin except turning Windows' built-in Linux on itself.** The app machine and every data
  disk are created with `wsl --import` (the proven wordslab-notebooks mechanism): WSL places and
  manages a dynamic `ext4.vhdx` inside a plain folder on the chosen drive, auto-attached at every
  future start — no diskpart, no loose VHDX, no `wsl --mount` (which needs admin AND detaches at
  each reboot). The single elevation moment (first-time feature switch) asks Windows once via the
  wizard relaunching ITSELF elevated (`runas`, one UAC dialog, zero console windows).
- **One named distro: `wordslab`.** Every distro-facing C# command carries `-d wordslab` (a live
  Windows run proved the default distro can lack bash entirely — `/bin/sh: bash: not found`).
  One constant, `Wsl.Distro`, every factory honors it; pinned by `every_wsl_command_targets_the_named_wordslab_distro`.
- **The disk model:** one minimal WSL instance per enabled drive (`wordslab-<letter>`, imported
  from a pinned Alpine minirootfs URL), folder `<drive>:\wordslab\wordslab-<letter>\`; each
  instance publishes `/volume` into `/mnt/wsl/wordslab-<letter>` (shared across distros), and
  the shared `04-data-volumes.sh` bind-mounts those into the app machine at `/mnt/wordslab/<letter>`.
- **Engine landing place:** uv in `/usr/local/bin`, uv-managed CPython 3.12 under
  `/opt/wordslab/python` — ticket #62's core plugs into the same slot (`05-first-core.sh` is the
  line that installs it once #62 ships).
- **Handoff stays an address:** step 6's probe proves the home page answers and writes
  `wordslab-front-door.url` next to the parameters file; the window navigates to that. The
  `wordslab.local` name + one TLS cert land with #92 — until then step 6 fails with a plain
  sentence rather than pretending (nothing installed silently).

## Scope fence

The **content** of the numbered bootstrap scripts (WSL + distro + virtual disks, uv/Python,
network reachability, data volumes, first core, front door) is ticket **#88**'s home — it fills
the placeholder commands inside the C# script classes and the placeholder content inside the
script FILES. #87 owns the entry points, the UI, the command-execution library, the numbered
script classes/shapes, the runner + streaming contract, and the web handoff. ADR-0014 §3 also
asks for per-step inline guidance ("essential when SSH'd into a VM"): with placeholder steps
there is nothing to guide yet — it lands with the real steps in #88.

## Test seams (no HTTP surface — the installer is not a service)

- C#: `dotnet test Wizard.Tests` in `windows/` (any OS) — script-class command plans (incl.
  `wsl -- python3` probe regression and `wslpath` translation), journey ordering/stop-on-failure,
  real streaming executor (incl. flooded-pipe deadlock regression), parameters round-trip.
- Python: `uv sync && uv run pytest` in `python/` — the installer API (streaming,
  interpretation, stop-on-failure) and the TUI main flow against stub commands.
- Bash: `bash installer/linux/test_install_smoke.sh` — the Linux entry end to end (labels,
  `[NN] !` stderr, handoff, loud gaps); `bash installer/linux/test_distro_scripts_smoke.sh` —
  the shared distro scripts' documented contract (usage exits, no-op re-runs, stubbed engine).
- Windows UI: verified by Laurent on the Windows host against `TEST-SCENARIOS-windows.md`;
  the repeatable full-journey harness (`e2e/reset.ps1` + `e2e/check.ps1` + `e2e/loop.ps1`,
  scenario doc `TEST-E2E-windows.md`) reverts the machine between cycles — the WSL feature
  itself is deliberately never removed.

## Standalone build (no .NET needed on the target machine)

```powershell
dotnet publish Wizard.App -c Release -r win-x64 --self-contained
```

Produces `Wizard.App\bin\Release\net10.0-windows10.0.26100.0\win-x64\publish\` —
copy the **whole folder** anywhere; `Wizard.App.exe` runs on any Windows 10/11 x64 with
nothing installed: the .NET runtime is bundled, and `WindowsAppSDKSelfContained=true` in
the csproj bundles the Windows App SDK native runtime too (no "Windows App Runtime"
dependency). WebView2 needs no extra install — the runtime ships with Edge on Windows 10/11.
Real packaging (#94): final exe name, `installer/` payload copied next to the exe (the
wizard locates the payload by walking up from the exe for `installer/python/tui.py`),
icon metadata.

## Build notes

- `dotnet` 10 SDK; on Linux set `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` if libicu is absent.
- On Linux build/test only `Wizard.Core` + `Wizard.Tests` (`Wizard.App` needs Windows XAML
  tooling). On Windows `dotnet build` at `windows/` builds all three.
