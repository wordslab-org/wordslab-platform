#Requires -Version 5.1
<#
reset.ps1 — revert this machine to the state the Wordslab journey starts from.

Deletes exactly and only what the #88 journey creates:
  · the named distros:  wordslab  and  wordslab-<letter>  (pattern-guarded — see below)
  · <drive>:\wordslab\wordslab-<letter>\      (the Wordslab Linux disks, VHDX inside)
  · <install_dir>\virtual-machines\ and <install_dir>\cache\  (VM + downloaded rootfs tarballs)
  · the written files: wordslab-install-parameters.json, wordslab-front-door.url
  · the wizard's WebView2 data folder (%TEMP%\wordslab-installer-webview)

NEVER touches Windows' built-in Linux itself (#88 ruling, by design): the WSL feature stays
enabled across cycles, and no distro is unregistered whose name does not match
^wordslab(-[a-z])?$ — other distros (docker-desktop, Ubuntu you installed, …) are untouchable.

Dry preview:   powershell -File reset.ps1 -DryRun
Actual reset:  powershell -File reset.ps1
#>
[CmdletBinding()]
param([switch]$DryRun, [switch]$KeepDownloads)

$ErrorActionPreference = 'Stop'

function Step($m) { Write-Host "reset: $m" }
function Trash($path, $why) {
    if (Test-Path -LiteralPath $path) {
        if ($DryRun) { Write-Host "reset: WOULD delete $path  ($why)" }
        else { Remove-Item -Recurse -Force -LiteralPath $path; Write-Host "reset: deleted $path  ($why)" }
    } else { Write-Host "reset: nothing at $path" }
}

Write-Host "reset: starting (DryRun=$DryRun)"

# 1) The distro names: read them from what WSL itself registered — never assume.
$raw = & wsl --list --quiet 2>$null
$installed = ($raw | Out-String) -split "`0" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($LASTEXITCODE -ne 0 -or -not $installed) { Step "no WSL distros answer (WSL may be off - nothing to unregister)" }

# Safety pattern: ONLY our own names. docker-desktop, Store Ubuntu, anything else: untouchable.
$mine = @($installed | Where-Object { $_ -match '^wordslab(-[a-z])?$' })
Step "registered Wordslab distros: $(if ($mine) { $mine -join ', ' } else { 'none' })"
& wsl --shutdown 2>$null   # stop everything first: unregister needs no running instance
foreach ($name in $mine) {
    if ($DryRun) { Write-Host "reset: WOULD unregister $name (removes its WSL-managed ext4.vhdx)"; continue }
    & wsl --unregister $name 2>&1 | ForEach-Object { Write-Host "  wsl: $_" }
    if ($LASTEXITCODE -ne 0) { throw "unregistering $name failed (exit $LASTEXITCODE)" }
    Step "unregistered $name"
}

# 2) The folders the journey creates, per fixed drive (the v1 fixed layout — one formula:
#    every Wordslab disk folder is <drive>:\wordslab\wordslab-<letter>).
foreach ($d in (Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Free -ne $null })) {
    $root = "$($d.Name):\"
    if (-not (Test-Path -LiteralPath "${root}wordslab")) { continue }
    Get-ChildItem -LiteralPath "${root}wordslab" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^wordslab-[a-z]$' } |
        ForEach-Object { Trash $_.FullName "Wordslab Linux disk on $($d.Name):" }
}
Trash "C:\wordslab\virtual-machines" "the Wordslab virtual machine (WSL import folder)"
if ($KeepDownloads) { Step "keeping C:\wordslab\cache (rootfs tarballs) as asked — installs reuse them via Test-Path" }
else { Trash "C:\wordslab\cache" "downloaded rootfs tarballs" }

# 3) The written files: parameters + handoff address, next to the built wizard (search bin).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path   # installer\windows\e2e
$windows = Split-Path -Parent $here
foreach ($name in 'wordslab-install-parameters.json', 'wordslab-front-door.url') {
    $found = Get-ChildItem -Path (Join-Path $windows 'Wizard.App\bin') -Recurse -Filter $name -ErrorAction SilentlyContinue
    if ($found) { $found | ForEach-Object { Trash $_.FullName "wizard-written file" } }
    else { Write-Host "reset: nothing at Wizard.App\bin\**\$name" }
}
Trash (Join-Path $env:TEMP 'wordslab-installer-webview') "WebView2 profile"

# 4) Proof of the contract: what is left, shown — the machine state you can trust to re-run.
Write-Host "reset: --- machine state now ---"
& wsl --status 2>&1 | ForEach-Object { Write-Host "  wsl --status: $_" }
if ($LASTEXITCODE -eq 0) { Write-Host "  KEPT: Windows' built-in Linux stays switched on (never removed by this reset)" }
& wsl --list --quiet 2>$null | Out-String | ForEach-Object { Write-Host "  remaining distros: $($_.Trim() -replace "`0", ' ')" }
Write-Host "reset: done — the machine is at the journey's starting state again."
