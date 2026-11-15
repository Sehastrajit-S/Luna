<#
.SYNOPSIS
  Renders CLI help/output as a styled terminal image.

.PARAMETER Command
  The luna command to capture. Default: "--help"

.EXAMPLE
  .\capture_cli.ps1
  .\capture_cli.ps1 -Command "skills list"
#>
param(
    [string]$Command = "--help"
)

$ErrorActionPreference = "Stop"
$root   = (Resolve-Path "$PSScriptRoot\..\..")
$outDir = Join-Path $root "docs-site\public\screenshots"
$out    = Join-Path $outDir "cli-output.png"
$py     = Join-Path $PSScriptRoot "render_cli.py"

Write-Host "Running: luna $Command" -ForegroundColor Cyan

$raw = $null
try {
    $raw = & luna $Command 2>&1 | Out-String
} catch {
    # luna not in PATH - use placeholder text
}

if (-not $raw) {
    $raw = @"
Luna -- local AI assistant

Usage:
  luna [command] [flags]

Commands:
  chat        Start an interactive chat session
  run         Run a one-shot prompt
  skills      Manage installed skills
  voice       Control voice mode
  config      Edit Luna configuration
  status      Show backend status

Flags:
  -h, --help      Show this help
  -v, --version   Print version
"@
}

Write-Host "Rendering terminal image..." -ForegroundColor Cyan
$raw | python $py $out $Command

Write-Host "`nSaved: $out" -ForegroundColor Green
