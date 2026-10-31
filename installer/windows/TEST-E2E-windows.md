# Windows end-to-end test — the whole journey, as many times as you want (#88 harness)

Everything below runs from `installer\windows\`. You need the .NET 10 SDK
(`winget install Microsoft.DotNet.SDK.10`) and the built wizard (`dotnet build`).

The loop harness lives in `e2e\`:

| script | what it does |
|---|---|
| `e2e\reset.ps1` | Deletes **only folders carrying the installer's ownership marker** (`.wordslab-installer`, written by the steps that created them) and the files/ distros a run wrote. An unmarked folder is reported, never touched — `C:\wordslab-platform\virtual-machines` is also used by **wordslab-notebooks**, so no parent folder is ever deleted (a parent goes only when empty). Distros are unregistered only when their WSL registry `BasePath` is one of those marked folders; orphans are listed, and `-RemoveOrphans` unregisters them on explicit request. **Never removes Windows' built-in Linux** — the feature stays on between cycles, by design. `-DryRun` previews every deletion, `-KeepDownloads` keeps the cached rootfs tarballs. |
| `e2e\check.ps1` | Asserts the machine state the six steps promise: distros registered, folders exactly where the UI card showed them (`ext4.vhdx` inside), cached downloads, each `wsl.conf` **in effect** (not just written), engine slot filled, disk mounts inside the app VM, step-6 honesty. Exit 0 = every promise holds. `-AfterRestart` skips the bind-mount checks (re-binding at every launch is #94's launcher job). |
| `e2e\loop.ps1` | One cycle = reset → launch the wizard → check. `-Runs N` (default 3), `-KeepDownloads`, `-Exe <path>` to test a published setup.exe instead of `dotnet run`. Prints a per-cycle PASS/FAIL summary and exits non-zero if any cycle broke a promise. |

```
powershell -ExecutionPolicy Bypass -File e2e\loop.ps1 -Runs 5 -KeepDownloads     # the everyday iteration
powershell -ExecutionPolicy Bypass -File e2e\reset.ps1 -DryRun                   # see exactly what would be deleted
```

`-ExecutionPolicy Bypass` is per-run (nothing changes on the machine): a default Windows
policy of `Restricted` refuses any `.ps1`. If you prefer it once per shell:
`Set-ExecutionPolicy -Scope Process Bypass` then drop the flag from every command.

## Reset safety contract (read once)

`reset.ps1` may delete a folder ONLY when it contains `.wordslab-installer`. That marker is
written by the step that creates the folder (`<install_dir>\virtual-machines\wordslab-platform`,
`<drive>:\wordslab-platform\wordslab-platform-<letter>`). Consequences you can rely on:

- The two products live in **separate roots**: ours is `<install_dir>` (default `C:\wordslab-platform`),
  wordslab-notebooks' is `C:\wordslab` (its VMs sit in `C:\wordslab\virtual-machines`). Even against a
  future product sharing a parent, only the marked child is removed; the parent only if it ends up empty.
- Any folder you or another project created has no marker → reported as KEPT, never deleted.
- Distros: unregistered only when the WSL registry shows a `BasePath` inside a marked folder.
  `wordslab-notebooks*`, `docker-desktop`, `Ubuntu-24.04` never match the name pattern at all.
- Leftovers from a broken install (registered distro whose folder is gone) are listed, not
  removed: `powershell -ExecutionPolicy Bypass -File e2e\reset.ps1 -RemoveOrphans` is the
  explicit way to clean them — an orphaned registration is the last trace of data.

## What "everything" covers

### E1 — first install from the clean state
Fresh reset, `dotnet run --project Wizard.App`, press **Start install**. Expect:
- Step 1 green: `github.com: reachable (HTTP 200)` + `pypi.org: …` + "Internet connection OK".
- Step 2: if WSL is already on (your machine): the guard line
  ("Windows' built-in Linux is already switched on - nothing to do."), then
  "Creating the Wordslab virtual machine — the
  download takes a few minutes the first time." (watch the disk folder appear:
  `C:\wordslab-platform\virtual-machines\wordslab-platform\`). If the feature is off: see E6.
- Step 3: version lines end with "Wordslab engine ready - uv 0.x and Python 3.12.x …".
- Step 4: one "Creating the Wordslab Linux disk on drive C:" per ticked drive + the shared
  script's `Wordslab Linux disk c mounted at /mnt/wordslab-platform/c` lines.
- Step 5: "engine slot present … core install slot ready".
- **Step 6 RED with the plain sentence** ("The Wordslab home page did not answer yet…") —
  this is the honest, expected state until #62 (page) and #92 (cert + name) land. A green
  step 6 with no real page behind it would be the actual bug.
- Bottom line: "The install stopped at the step marked in red…" — **expected** (step 6).
Then: `powershell -ExecutionPolicy Bypass -File e2e\check.ps1` → expect **0 failed**, except the step-6 PASS line
that says "no front-door address file — the honest state".

### E2 — idempotency WITHOUT reset (press Start install a second time)
Same wizard window state, press Start install again. Expect every step to say its guard
sentence — "already switched on", "already installed - keeping it", "already there - keeping
it" — and nothing re-download (compare: `C:\wordslab-platform\cache` file timestamps unchanged). Data
on the disks must survive: make a file first —
`wsl -d wordslab-platform -- sh -c "mkdir -p /mnt/wordslab-platform/c/e2e && echo keep > /mnt/wordslab-platform/c/e2e/probe.txt"` —
re-run, then `wsl -d wordslab-platform -- cat /mnt/wordslab-platform/c/e2e/probe.txt` still says `keep`.
Then `check.ps1` again → 0 failed.

### E3 — reset → reinstall loops
`powershell -ExecutionPolicy Bypass -File e2e\loop.ps1 -Runs 3` (or with `-KeepDownloads` once you've done one
download cycle). Expect: reset prints exactly the wordslab-named deletions (no other distro
named), then the wizard installs from scratch again, check passes, 3× OK in the summary.

### E4 — reboot between install and check
After a green E1, reboot the machine, then `powershell -ExecutionPolicy Bypass -File e2e\check.ps1 -AfterRestart`.
Expect 0 failed: distros, folders, engine, configs all survive the reboot (they are
WSL-registered, not session state). The bind mounts are NOT asserted here — re-publishing
them at every launch is #94's launcher; re-running Start install re-applies them (step 4's
publish line is idempotent).

### E5 — drives off/on
Untick D: in the card, run: step 4 creates C: only; an existing `wordslab-platform-d` instance (from
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
- `wsl --mount`, diskpart, or a loose `.vhdx` outside a `wordslab-platform-<letter>` folder
  (`reset.ps1 -DryRun` naming only `wordslab*` distros is part of this proof).
- Reset ever unregistering a distro it doesn't own, or touching the WSL feature.
- A step succeeding by lying (step 6 green with no page answering).

## Reporting back
For each cycle that misbehaves: the card's red line + its "··· more" log, the
`check.ps1` FAIL lines, and the `loop.ps1` summary line. Screenshots for E1 (all six cards
mid-stream) and E6 (the UAC dialog) are the two worth keeping.
