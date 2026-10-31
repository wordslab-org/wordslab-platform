#Requires -Version 5.1
<#
publish.ps1 - build a self-contained Windows installer folder you can carry to another machine.

    powershell -ExecutionPolicy Bypass -File publish.ps1              # folder in artifacts\
    powershell -ExecutionPolicy Bypass -File publish.ps1 -Zip         # folder + .zip
    powershell -ExecutionPolicy Bypass -File publish.ps1 -OutDir D:\tmp -Zip

Result (the wizard walks up from its exe looking for installer\python\tui.py, so the payload MUST
travel next to it - that is why this script copies the payload instead of only the exe):

    wordslab-installer\           Wizard.App.exe + runtime + Assets
      installer\python\           the phase-2 TUI and installer API
      installer\scripts\          the numbered distro/linux/windows scripts (LF endings)
      installer\windows\e2e\      reset.ps1 / check.ps1 / loop.ps1
      installer\windows\TEST-E2E-windows.md

Nothing is signed: a copy downloaded from the internet shows SmartScreen's "Windows protected
your PC" - "More info" then "Run anyway". Signing, the final exe name and version metadata are
ticket #94's job; this is the test-delivery path.
#>
[CmdletBinding()]
param(
    [string]$OutDir = (Join-Path $PSScriptRoot '..\..\artifacts'),
    [switch]$Zip
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path     # installer\windows -> repo root
$stage = Join-Path $OutDir 'wordslab-installer'

Write-Host "publish: repo    $repo"
Write-Host "publish: staging $stage"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force $stage | Out-Null

# 1) The app itself: self-contained (no .NET, no Windows App Runtime on the target machine).
& dotnet publish (Join-Path $PSScriptRoot 'Wizard.App\Wizard.App.csproj') `
    -c Release -r win-x64 --self-contained -o $stage
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed (exit $LASTEXITCODE)" }

# 2) The payload: exactly the parts the journey reads at run time.
$payload = Join-Path $stage 'installer'
New-Item -ItemType Directory -Force $payload | Out-Null
foreach ($part in 'python', 'scripts') {
    Copy-Item -Recurse -Force (Join-Path $repo "installer\$part") (Join-Path $payload $part)
}
New-Item -ItemType Directory -Force (Join-Path $payload 'windows') | Out-Null
Copy-Item -Recurse -Force (Join-Path $repo 'installer\windows\e2e') (Join-Path $payload 'windows\e2e')
Copy-Item -Force (Join-Path $repo 'installer\windows\TEST-E2E-windows.md') (Join-Path $payload 'windows')
Copy-Item -Force (Join-Path $repo 'installer\README.md') $payload

# Proof the wizard will find it: the walk-up check the exe performs at Start install.
if (-not (Test-Path (Join-Path $payload 'python\tui.py'))) { throw "payload incomplete: python\tui.py missing" }
if (-not (Test-Path (Join-Path $payload 'scripts\distro\04-data-volumes.sh'))) { throw "payload incomplete: distro scripts missing" }

$size = [math]::Round(((Get-ChildItem $stage -Recurse | Measure-Object Length -Sum).Sum / 1MB), 0)
Write-Host "publish: folder ready ($size MB)"

if ($Zip) {
    $zip = Join-Path $OutDir 'wordslab-installer-win-x64.zip'
    if (Test-Path $zip) { Remove-Item -Force $zip }
    Compress-Archive -Path $stage -DestinationPath $zip
    $zsize = [math]::Round(((Get-Item $zip).Length / 1MB), 0)
    Write-Host "publish: $zip ($zsize MB)"
}
