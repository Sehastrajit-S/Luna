# Luna — build and auto-install
# Run from repo root: .\scripts\build_and_install.ps1

Set-Location $PSScriptRoot\..

Write-Host "[Luna] Building frontend..." -ForegroundColor Cyan
npm run build --workspace=frontend
if (-not $?) { Write-Host "[Luna] Frontend build failed" -ForegroundColor Red; exit 1 }

Write-Host "[Luna] Building installer..." -ForegroundColor Cyan
npm run build:win --workspace=electron
if (-not $?) { Write-Host "[Luna] Electron build failed" -ForegroundColor Red; exit 1 }

$installer = Get-ChildItem -Path "dist-electron" -Filter "Luna Setup*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) { Write-Host "[Luna] Installer not found in dist-electron/" -ForegroundColor Red; exit 1 }

Write-Host "[Luna] Running installer: $($installer.Name)" -ForegroundColor Green
Start-Process -FilePath $installer.FullName -Wait
