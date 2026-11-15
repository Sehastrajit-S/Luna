# Creates a Windows .lnk shortcut for Luna on the current user's Desktop.
# Run from repo root: .\scripts\create_shortcut.ps1

Set-Location $PSScriptRoot\..

$repoRoot = (Get-Location).Path
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Luna.lnk"
$iconPath = Join-Path $repoRoot "electron\assets\icon.ico"

$installedCandidates = @(
  (Join-Path $env:LOCALAPPDATA "Programs\Luna\Luna.exe"),
  (Join-Path $env:ProgramFiles "Luna\Luna.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "Luna\Luna.exe")
) | Where-Object { $_ -and (Test-Path $_) }

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)

if ($installedCandidates.Count -gt 0) {
  $shortcut.TargetPath = $installedCandidates[0]
  $shortcut.WorkingDirectory = Split-Path $installedCandidates[0]
} else {
  $shortcut.TargetPath = "$env:SystemRoot\System32\wscript.exe"
  $shortcut.Arguments = "`"$(Join-Path $repoRoot "scripts\start_luna_hidden.vbs")`""
  $shortcut.WorkingDirectory = $repoRoot
}

if (Test-Path $iconPath) {
  $shortcut.IconLocation = $iconPath
}

$shortcut.Description = "Open Luna"
$shortcut.Save()

Write-Host "[Luna] Shortcut created: $shortcutPath" -ForegroundColor Green
