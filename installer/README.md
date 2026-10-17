# Installer & bootstrap entry points (ticket #87)

The native entry points and the phased guided journey (ADR-0014 §2/§3/§7). This is **not** a
base-contract service: no API, no DB, no keys (ADR-0003 §1 — the bootstrap layer lives below the
service contract).

## Layout

- `windows/` — the Windows side (.NET 10 solution):
  - `Wizard/` — the thin phase-1 console wizard: parameter collection, the numbered-script runner
    that mirrors output line by line, and the phase-handoff decision (native → Python TUI once
    the distro's Python exists → web handoff as an address). Python probes/launches go through
    `wsl.exe -- python3 …`, with Windows paths translated via `wslpath -u`.
  - `Wizard.Abstractions/` — the shared seams (`IWebUiHost`) so the wizard and the web host do
    not depend on each other.
  - `Wizard.WebUi/` — the embedded web-UI host: **WinUI 3 (Windows App SDK) + WebView2**, pure C#
    (no WinForms, no WPF, no XAML markup), unpackaged (`WindowsPackageType=None`). Builds on Linux
    via `EnableWindowsTargeting`; runs on the Windows host. The web phase keeps the installer
    process alive until the window closes (`WaitUntilClosed`).
  - `Wizard.Tests/` — xunit contract tests over the stub-process seam.
- `linux/install.sh` — the `curl … | bash` entry point: the same numbered journey, same handoff.
- `python/` — the phase-2 installer API + TUI (uv project): `installer_api.py` (run/stream/
  interpret), `tui.py` (the wizard shell + the web handoff), `tests/` (pytest over the same
  stub-command seam).

## The phased journey (ADR-0014 §3)

1. **Native** (`.exe` wizard / `install.sh`): collects install parameters (defaults shown, invalid
   answers re-asked), runs the numbered bootstrap scripts while mirroring their stdout/stderr,
   stops loudly at the first failure — nothing installed silently.
2. **Python TUI** once Python exists: `tui.py` takes over with the same numbered scripts visible
   and runnable beneath, progress interpreted from streamed logs.
3. **Web**: the handoff is **an address, not a process switch**. On Windows the installer renders
   the URL in its embedded WebView2 window and opens the dashboard in the browser itself; over
   SSH/remote the TUI prints the dashboard URL to open elsewhere.

The numbered-runner contract — `[NN]` labels, `! ` stderr prefix, `FAILED (exit N) — the journey
stops here; nothing further is installed.` — is deliberately implemented three times (C#, Python,
bash) because each entry point must run standalone before any other exists. The contract tests in
each language pin the same strings; keep them in step.

## Scope fence

The **content** of the numbered bootstrap scripts (WSL + distro + virtual disks, uv/Python,
network reachability, data volumes, first core, front door) is ticket **#88**'s home. #87 owns the
entry points, the wizard shell, the runner + mirroring contract, the phase handoffs, and the
webview host. The scripts here are visible numbered placeholders that say so.

## Test seams (no HTTP surface — the installer is not a service)

- C#: `dotnet test` in `windows/` — the wizard's script-runner + parameter-collection + handoff
  contract against a fake process table.
- Python: `uv sync && uv run pytest` in `python/` — the installer API (streaming, interpretation,
  stop-on-failure) and the TUI main flow against stub commands.
- Windows UI: verified by Laurent on the Windows host against written scenarios (screenshots as
  needed); the WebView2 host compiles in CI (`EnableWindowsTargeting`) and its console-side
  contract (show URL → open browser) is covered by the C# tests through the `IWebUiHost` seam.

## Build notes

- `dotnet` 10 SDK; on Linux set `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` if libicu is absent.
- `Wizard.WebUi` sets `EnableCoreMrtTooling=false`: the WindowsAppSDK MrtCore/PRI MSBuild tasks
  ship only with the Visual Studio toolset; the project has no PRI resources, so Linux CI builds
  stay green.
