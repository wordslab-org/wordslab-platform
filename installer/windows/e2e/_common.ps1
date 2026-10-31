#Requires -Version 5.1
<#
_common.ps1 - shared by the e2e scripts. Dot-source it: ". (Join-Path $PSScriptRoot '_common.ps1')".

The e2e folder lives in two layouts, and the files the journey writes must be found in both:

  checkout   <repo>\installer\windows\e2e\      -> exe + parameters under Wizard.App\bin\...
  published  <folder>\installer\windows\e2e\    -> exe + parameters NEXT TO the exe, at <folder>\

Get-InstallerFile walks up from the e2e folder and returns the newest match for a file name.
#>

function Get-InstallerFile {
    param(
        [Parameter(Mandatory = $true)][string]$E2eDir,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $dir = Get-Item -LiteralPath $E2eDir
    for ($level = 0; $level -lt 5 -and $null -ne $dir; $level++) {
        $hits = @(Get-ChildItem -Path $dir.FullName -Recurse -Depth 4 -Filter $Name -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending)
        if ($hits.Count -gt 0) { return $hits[0].FullName }
        $dir = $dir.Parent
    }
    return $null
}
