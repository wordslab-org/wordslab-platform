#Requires -Version 5.1
<#
loop.ps1 — run the whole Windows journey as many times as you want, each time from the
same clean starting state. One cycle =

    reset (delete the created distros + files; the WSL feature itself is KEPT)
    -> launch the wizard (you press Start install; close the window when done)
    -> check the machine state it promised (check.ps1)

  from installer\windows:
    powershell -File e2e\loop.ps1                      # 3 cycles
    powershell -File e2e\loop.ps1 -Runs 10             # 10 cycles
    powershell -File e2e\loop.ps1 -KeepDownloads       # reset keeps the cached rootfs tarballs
                                                       # (faster cycles; downloads only ever once)
    powershell -File e2e\loop.ps1 -Exe C:\path\WordslabSetup.exe   # test the published exe (#94) instead

Notes:
  · Step 6 is EXPECTED red until #62 (core) and #92 (cert + name) land — check.ps1 still
    passes on everything up to it; a cycle "fails" only on a real promise break.
  · To test the idempotency promise, use the wizard itself: press Start install a second
    time WITHOUT any reset ("keeping it" lines everywhere) — then run e2e\check.ps1.
#>
[CmdletBinding()]
param([int]$Runs = 3, [string]$Exe = "", [switch]$KeepDownloads)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path          # installer\windows\e2e
$windows = Split-Path -Parent $here                              # installer\windows

$results = @()
for ($n = 1; $n -le $Runs; $n++) {
    Write-Host ""
    Write-Host "================ cycle $n / $Runs ================"

    if ($KeepDownloads) { & (Join-Path $here 'reset.ps1') -KeepDownloads }
    else { & (Join-Path $here 'reset.ps1') }

    Write-Host "cycle $n : launching the wizard — press Start install, watch the six cards, then CLOSE the window"
    if ($Exe) {
        Start-Process -FilePath $Exe -Wait
    } else {
        Push-Location $windows
        & dotnet run --project Wizard.App
        Pop-Location
    }

    & (Join-Path $here 'check.ps1')
    if ($LASTEXITCODE -eq 0) { Write-Host "cycle $n : CHECK OK"; $results += "$n : OK" }
    else { Write-Host "cycle $n : CHECK FAILED (see FAIL lines above)"; $results += "$n : CHECK-FAIL" }
}

Write-Host ""
Write-Host "================ loop summary ================"
$results | ForEach-Object { Write-Host "  cycle $_" }
exit $(if (@($results | Where-Object { $_ -notmatch ': OK$' }).Count -eq 0) { 0 } else { 1 })
