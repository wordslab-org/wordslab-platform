# Windows end-to-end test — the whole journey, as many times as you want (#88 harness)

Everything below runs from `installer\windows\`. You need the .NET 10 SDK
(`winget install Microsoft.DotNet.SDK.10`) and the built wizard (`dotnet build`).

The loop harness lives in `e2e\`:

| script | what it does |
|---|---|
| `e2e\reset.ps1` | Deletes **exactly** what the journey creates — the `wordslab` + `wordslab-<letter>` distros (pattern-guarded: **no other distro can be touched**), the `<drive>:\wordslab\wordslab-<letter>\` folders, `C:\wordslab\virtual-machines\`, `C:\wordslab\cache\`, the parameters/front-door files, the WebView2 profile. **Never removes Windows' built-in Linux** — the feature stays switched on between cycles, by design. `-DryRun` previews, `-KeepDownloads` keeps the cached rootfs tarballs (faster cycles, downloads once ever). |
| `e2e\check.ps1` | Asserts the machine state the six steps promise: distros registered, folders exactly where the UI card showed them (`ext4.vhdx` inside), cached downloads, each `wsl.conf` **in effect** (not just written), engine slot filled, disk mounts inside the app VM, step-6 honesty. Exit 0 = every promise holds. `-AfterRestart` skips the bind-mount checks (re-binding at every launch is #94's launcher job). |
| `e2e\loop.ps1` | One cycle = reset → launch the wizard → check. `-Runs N` (default 3), `-KeepDownloads`, `-Exe <path>` to test a published setup.exe instead of `dotnet run`. Prints a per-cycle PASS/FAIL summary and exits non-zero if any cycle broke a promise. |

```
powershell -File e2e\loop.ps1 -Runs 5 -KeepDownloads     # the everyday iteration
powershell -File e2e\reset.ps1 -DryRun                   # see exactly what would be deleted
```

## What "everything" covers

### E1 — first install from the clean state
Fresh reset, `dotnet run --project Wizard.App`, press **Start install**. Expect:
- Step 1 green: `github.com: reachable (HTTP 200)` + `pypi.org: …` + "Internet connection OK".
- Step 2: if WSL is already on (your machine): the guard line
  ("Windows' built-in Linux is already switched on - nothing to do."), then
  "Creating the Wordslab virtual machine — the
  download takes a few minutes the first time." (watch the disk folder appear:
  `C:\wordslab\virtual-machines\wordslab\`). If the feature is off: see E6.
- Step 3: version lines end with "Wordslab engine ready - uv 0.x and Python 3.12.x …".
- Step 4: one "Creating the Wordslab Linux disk on drive C:" per ticked drive + the shared
  script's `Wordslab Linux disk c mounted at /mnt/wordslab/c` lines.
- Step 5: "engine slot present … core install slot ready".
- **Step 6 RED with the plain sentence** ("The Wordslab home page did not answer yet…") —
  this is the honest, expected state until #62 (page) and #92 (cert + name) land. A green
  step 6 with no real page behind it would be the actual bug.
- Bottom line: "The install stopped at the step marked in red…" — **expected** (step 6).
Then: `powershell -File e2e\check.ps1` → expect **0 failed**, except the step-6 PASS line
that says "no front-door address file — the honest state".

### E2 — idempotency WITHOUT reset (press Start install a second time)
Same wizard window state, press Start install again. Expect every step to say its guard
sentence — "already switched on", "already installed - keeping it", "already there - keeping
it" — and nothing re-download (compare: `C:\wordslab\cache` file timestamps unchanged). Data
on the disks must survive: make a file first —
`wsl -d wordslab -- sh -c "mkdir -p /mnt/wordslab/c/e2e && echo keep > /mnt/wordslab/c/e2e/probe.txt"` —
re-run, then `wsl -d wordslab -- cat /mnt/wordslab/c/e2e/probe.txt` still says `keep`.
Then `check.ps1` again → 0 failed.

### E3 — reset → reinstall loops
`powershell -File e2e\loop.ps1 -Runs 3` (or with `-KeepDownloads` once you've done one
download cycle). Expect: reset prints exactly the wordslab-named deletions (no other distro
named), then the wizard installs from scratch again, check passes, 3× OK in the summary.

### E4 — reboot between install and check
After a green E1, reboot the machine, then `powershell -File e2e\check.ps1 -AfterRestart`.
Expect 0 failed: distros, folders, engine, configs all survive the reboot (they are
WSL-registered, not session state). The bind mounts are NOT asserted here — re-publishing
them at every launch is #94's launcher; re-running Start install re-applies them (step 4's
publish line is idempotent).

### E5 — drives off/on
Untick D: in the card, run: step 4 creates C: only; an existing `wordslab-d` instance (from
a previous run) is **kept, untouched** (the data-volume invariant — switching a drive off in
v1 never deletes data). Tick it back, re-run: "already there - keeping it".
To actually test fresh-per-drive, reset first.

### E6 — the one elevation moment
Only reachable on a machine where Windows' built-in Linux has never been switched on
(a fresh Windows VM — your daily machine has it). Expect: step 2's guard sentence, one UAC
dialog (never a console window), wizard restarts itself and continues; declining the dialog
leaves "The Windows approval was declined…" with both ways forward. If Windows then needs
one restart, the elevated run says so plainly and a later Start install completes.

### E7 — what must NEVER happen in any cycle
- Any console window (cmd/powershell/pwsh) opening during the journey.
- `wsl --mount`, diskpart, or a loose `.vhdx` outside a `wordslab-<letter>` folder
  (`reset.ps1 -DryRun` naming only `wordslab*` distros is part of this proof).
- Reset ever unregistering a distro it doesn't own, or touching the WSL feature.
- A step succeeding by lying (step 6 green with no page answering).

## Reporting back
For each cycle that misbehaves: the card's red line + its "··· more" log, the
`check.ps1` FAIL lines, and the `loop.ps1` summary line. Screenshots for E1 (all six cards
mid-stream) and E6 (the UAC dialog) are the two worth keeping.
