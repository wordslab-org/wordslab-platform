#Requires -Version 5.1
<#
reset.ps1 - revert this machine to the state the Wordslab journey starts from.

OWNERSHIP RULE (incident 2026-10-24, never again): this script deletes a folder ONLY when it
carries the installer's marker file (.wordslab-installer, written by the numbered steps when
they created that folder). A folder without the marker is NOT ours - it may belong to
wordslab-notebooks, to the user, or to anything else - and is reported, never touched. A
registered distro is unregistered ONLY when its WSL BasePath is one of those marked folders.
Parent folders (<install_dir>\virtual-machines, <drive>:\wordslab-platform) are never deleted as such:
at most a parent is removed when it is EMPTY after its own marked children went. C:\wordslab is
wordslab-notebooks' root and is never written or deleted here (incident 2026-10-24).

Never touched, by design: Windows' built-in Linux itself (the feature stays on across cycles),
other WSL distros (docker-desktop, Ubuntu, wordslab-notebooks*), and any unmarked folder.

  powershell -ExecutionPolicy Bypass -File reset.ps1 -DryRun           # preview, changes nothing
  powershell -ExecutionPolicy Bypass -File reset.ps1                   # the real reset
  powershell -ExecutionPolicy Bypass -File reset.ps1 -KeepDownloads    # keep cached tarballs
  powershell -ExecutionPolicy Bypass -File reset.ps1 -RemoveOrphans    # ALSO unregister
      # wordslab-platform-named distros whose backing folder is gone or unmarked (leftovers of a broken
      # install). Opt-in on purpose: an orphaned registration is the last trace of data.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$KeepDownloads,
    [switch]$RemoveOrphans,
    [string]$InstallDir = 'C:\wordslab-platform'
)

$ErrorActionPreference = 'Stop'
$MarkerName = '.wordslab-installer'
$Downloads = @('ubuntu-noble-oci-amd64-root.tar.gz', 'alpine-minirootfs.tar.gz')

function Step($m) { Write-Host "reset: $m" }
function HasMarker($folder) { Test-Path -LiteralPath (Join-Path $folder $MarkerName) }

# Delete one folder - only if it proves it is ours.
function RemoveOurs($folder, $why) {
    if (-not (Test-Path -LiteralPath $folder)) { return }
    if (-not (HasMarker $folder)) {
        Write-Host "reset: KEPT $folder  ($why) - no $MarkerName marker: not created by this installer"
        return
    }
    if ($DryRun) { Write-Host "reset: WOULD delete $folder  ($why)"; return }
    Remove-Item -Recurse -Force -LiteralPath $folder
    Write-Host "reset: deleted $folder  ($why)"
}

# A parent goes away only when it is empty - it may hold other people's things.
function RemoveIfEmpty($folder) {
    if (-not (Test-Path -LiteralPath $folder)) { return }
    if (@(Get-ChildItem -LiteralPath $folder -Force).Count -ne 0) { return }
    if ($DryRun) { Write-Host "reset: WOULD remove empty folder $folder"; return }
    Remove-Item -Force -LiteralPath $folder
    Write-Host "reset: removed empty folder $folder"
}

Write-Host "reset: starting (DryRun=$DryRun, InstallDir=$InstallDir)"

# 1) Registered Wordslab-named distros, with their real backing folders from the WSL registry.
$candidates = @()
try {
    $lxss = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
    if (Test-Path $lxss) {
        $candidates = @(Get-ChildItem $lxss | ForEach-Object {
            $name = $_.GetValue('DistributionName')
            $path = $_.GetValue('BasePath')
            if ($name -and $name -match '^wordslab-platform(-[a-z])?$') {
                [pscustomobject]@{ Name = $name; BasePath = ($path -replace '^\\\\\?\\', '').TrimEnd('\') }
            }
        })
    } else { Step "no WSL registry here - no distros to consider" }
} catch { Step "could not read the WSL registry ($($_.Exception.Message)) - no distro will be unregistered" }
if (-not $candidates) { Step "no wordslab-platform-named distros registered" }

try { & wsl --shutdown 2>$null } catch {}   # stop everything first; unregister needs no running instance

foreach ($d in $candidates) {
    $ours = $false
    if ($d.BasePath -and (Test-Path -LiteralPath $d.BasePath) -and (HasMarker $d.BasePath)) { $ours = $true }
    if (-not $ours -and -not $RemoveOrphans) {
        Write-Host "reset: KEPT distro '$($d.Name)' at '$($d.BasePath)' - backing folder is gone or unmarked; pass -RemoveOrphans to unregister it"
        continue
    }
    if ($DryRun) {
        Write-Host "reset: WOULD unregister $($d.Name) ($(if ($ours) { 'marked folder' } else { 'orphan, -RemoveOrphans' }))"
        continue
    }
    & wsl --unregister $d.Name 2>&1 | ForEach-Object { Write-Host "  wsl: $_" }
    if ($LASTEXITCODE -ne 0) { Write-Host "reset: unregistering $($d.Name) failed (exit $LASTEXITCODE) - continuing"; continue }
    Write-Host "reset: unregistered $($d.Name)"
}

# 2) Marked folders the journey created. Note the exact paths - never a shared parent:
#    <install_dir>\virtual-machines\wordslab-platform   (the app VM)
#    <drive>:\wordslab-platform\wordslab-platform-<letter> (the per-drive disks)
RemoveOurs (Join-Path (Join-Path $InstallDir 'virtual-machines') 'wordslab-platform') 'app VM import folder'
RemoveIfEmpty (Join-Path $InstallDir 'virtual-machines')       # only if nothing else lives there
foreach ($d in (Get-PSDrive -PSProvider FileSystem | Where-Object { $null -ne $_.Free })) {
    $root = "$($d.Name):\wordslab-platform"
    if (-not (Test-Path -LiteralPath $root)) { continue }
    Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^wordslab-platform-[a-z]$' } |
        ForEach-Object { RemoveOurs $_.FullName "Wordslab Linux disk on $($d.Name):" }
}

# 3) Downloaded tarballs: deleted as FILES by exact name (they are caches - re-downloadable),
#    never by deleting the folder that may hold someone else's downloads.
$cache = Join-Path $InstallDir 'cache'
if ($KeepDownloads) { Step "keeping $cache (downloads) as asked" }
elseif (Test-Path -LiteralPath $cache) {
    foreach ($f in $Downloads) {
        $path = Join-Path $cache $f
        if (Test-Path -LiteralPath $path) {
            if ($DryRun) { Write-Host "reset: WOULD delete $path  (downloaded rootfs)" }
            else { Remove-Item -Force -LiteralPath $path; Write-Host "reset: deleted $path  (downloaded rootfs)" }
        }
    }
}

# 4) The wizard-written files (names are ours), next to the built wizard.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$windows = Split-Path -Parent $here
foreach ($name in 'wordslab-install-parameters.json', 'wordslab-front-door.url') {
    Get-ChildItem -Path (Join-Path $windows 'Wizard.App\bin') -Recurse -Filter $name -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($DryRun) { Write-Host "reset: WOULD delete $($_.FullName)" }
            else { Remove-Item -Force -LiteralPath $_.FullName; Write-Host "reset: deleted $($_.FullName)" }
        }
}
$webview = Join-Path $env:TEMP 'wordslab-installer-webview'
if (Test-Path -LiteralPath $webview) {
    if ($DryRun) { Write-Host "reset: WOULD delete $webview  (WebView2 profile)" }
    else { Remove-Item -Recurse -Force -LiteralPath $webview; Write-Host "reset: deleted $webview  (WebView2 profile)" }
}

# 5) Proof of the contract: what remains, shown.
Write-Host "reset: --- machine state now ---"
try {
    & wsl --status 2>&1 | ForEach-Object { Write-Host "  wsl --status: $_" }
    & wsl --list --quiet 2>$null | Out-String | ForEach-Object { Write-Host "  remaining distros: $($_.Trim() -replace "`0", ' ')" }
} catch { Write-Host "  (wsl did not answer)" }
Write-Host "reset: done - only this installer's own marked folders and files were removed."
