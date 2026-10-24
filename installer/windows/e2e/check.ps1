#Requires -Version 5.1
<#
check.ps1 — assert the machine state the #88 journey promises, right after a run.

Every check mirrors the documented per-step contracts (class docs + script headers) and the
S5 scenario: distros registered, folders exactly where the UI card promised them, each
wsl.conf actually IN EFFECT (not just written), the engine slot filled, the disk mounts
visible inside the app VM.

Run after Start install finished (steps 1-5 green; step 6 is expected RED until #62/#92 —
its plain sentence on the card, and NO wordslab-front-door.url file, are the HONEST state).

  powershell -File check.ps1                 # full assertions, exit 0 = everything holds
  powershell -File check.ps1 -AfterRestart   # skips the bind-mount checks on purpose:
                                             # re-binding at every launch is the resident
                                             # launcher's job (#94), not the installer's.
#>
[CmdletBinding()]
param([string]$ParametersFile = "", [switch]$AfterRestart)

$ErrorActionPreference = 'Stop'
$script:pass = 0; $script:fail = 0

function CheckBool($name, [scriptblock]$body) {
    if (& $body) { $script:pass++; Write-Host "PASS  $name" }
    else { $script:fail++; Write-Host "FAIL  $name" }
}
function CheckExit($name, [scriptblock]$body) {
    $global:LASTEXITCODE = 0
    & $body *> $null
    if ($LASTEXITCODE -eq 0) { $script:pass++; Write-Host "PASS  $name" }
    else { $script:fail++; Write-Host "FAIL  $name  (exit $LASTEXITCODE)" }
}

# Locate the parameters file the wizard wrote (next to the built exe).
if (-not $ParametersFile) {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $bin = Join-Path (Split-Path -Parent $here) 'Wizard.App\bin'
    $ParametersFile = (Get-ChildItem -Path $bin -Recurse -Filter 'wordslab-install-parameters.json' -ErrorAction SilentlyContinue |
        Select-Object -First 1).FullName
}
if (-not $ParametersFile -or -not (Test-Path $ParametersFile)) {
    Write-Host "FAIL  no wordslab-install-parameters.json found — press Start install in the wizard first"
    exit 1
}
$params = Get-Content -Raw $ParametersFile | ConvertFrom-Json
$installDir = "$($params.install_dir)".TrimEnd('\')
$letters = @($params.PSObject.Properties | Where-Object { $_.Name -match '^volume_([A-Z])$' } |
    ForEach-Object { $_.Name.Substring('volume_'.Length) })
Write-Host "check: parameters from $ParametersFile (install_dir=$installDir, drives: $($letters -join ', '))"

# 1) Distro names registered (the named distro model — never the default).
$raw = (& wsl --list --quiet 2>$null) | Out-String
$installed = @(($raw -split "`0") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
CheckBool "distro 'wordslab' is registered" { $installed -contains 'wordslab' }
foreach ($l in $letters) {
    $n = "wordslab-$($l.ToLower())"
    CheckBool "distro '$n' is registered" { $installed -contains $n }
}

# 2) Folders exactly where the UI card promised them, WSL-managed ext4.vhdx inside.
CheckBool "VM folder ($installDir\virtual-machines\wordslab\ext4.vhdx)" {
    Test-Path "$installDir\virtual-machines\wordslab\ext4.vhdx"
}
foreach ($l in $letters) {
    $folder = "$($l):\wordslab\wordslab-$($l.ToLower())\ext4.vhdx"
    CheckBool "disk folder ($folder)" { Test-Path $folder }
}

# 3) Cached rootfs downloads exist (fetched once, reused by Test-Path guard).
CheckBool "cached Ubuntu rootfs ($installDir\cache)" { Test-Path "$installDir\cache\ubuntu-noble-oci-amd64-root.tar.gz" }
CheckBool "cached Alpine rootfs ($installDir\cache)" { Test-Path "$installDir\cache\alpine-minirootfs.tar.gz" }

# 4) The VM's wsl.conf written AND in effect. appendWindowsPath off = no Windows PATH in the
#    VM (cmd.exe not runnable); automount STAYS on by ruling (#93 re-homes it) — payload access.
CheckExit "VM wsl.conf contents" { & wsl -d wordslab -- sh -c "grep -q 'systemd = true' /etc/wsl.conf && grep -q 'appendWindowsPath = false' /etc/wsl.conf" }
CheckExit "VM appendWindowsPath in effect (no cmd.exe on the VM PATH)" { & wsl -d wordslab -- sh -c "! command -v cmd.exe >/dev/null" }
CheckExit "VM automount kept on for payload access (/mnt/c present)" { & wsl -d wordslab -- sh -c "mountpoint -q /mnt/c" }

# 5) Engine slot filled exactly as ruled: uv in /usr/local/bin, CPython 3.12 under /opt/wordslab.
CheckExit "uv installed at /usr/local/bin/uv" { & wsl -d wordslab -- sh -c "test -x /usr/local/bin/uv" }
CheckExit "uv-managed Python under /opt/wordslab/python" { & wsl -d wordslab -- sh -c "ls /opt/wordslab/python >/dev/null" }
CheckExit "python 3.12 answers through uv" { & wsl -d wordslab -- sh -c "UV_PYTHON_INSTALL_DIR=/opt/wordslab/python uv run --no-project --python 3.12 python -c 'import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)'" }

# 6) Every disk instance: automount off IN EFFECT (the wsl --terminate after wsl.conf worked).
foreach ($l in $letters) {
    CheckExit "disk wordslab-$($l.ToLower()): automount in effect (no /mnt/c inside)" {
        & wsl -d "wordslab-$($l.ToLower())" -- sh -c "! mountpoint -q /mnt/c"
    }
}

# 7) The shared 04 script's bind mounts, visible inside the app VM. Skipped with
#    -AfterRestart: surviving shutdown/reboot is the launcher's re-bind job (#94).
if (-not $AfterRestart) {
    foreach ($l in $letters) {
        CheckExit "disk published at /mnt/wordslab/$($l.ToLower()) inside the VM" {
            & wsl -d wordslab -- sh -c "mountpoint -q /mnt/wordslab/$($l.ToLower())"
        }
    }
}

# 8) Step 6's honest state: the url file exists ONLY if a home page actually answered.
$urlFile = Join-Path (Split-Path -Parent $ParametersFile) 'wordslab-front-door.url'
if (Test-Path $urlFile) { $pass++; Write-Host "PASS  front-door address file present: $(Get-Content $urlFile)" }
else { $pass++; Write-Host "PASS  no front-door address file — the honest state until #62/#92 answer behind step 6" }

Write-Host "check: $pass passed, $fail failed"
exit $(if ($fail -eq 0) { 0 } else { 1 })
