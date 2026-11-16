# Install Luna on Windows.
#
#   irm https://www.luna-ai-engine.com/install.ps1 | iex
#
# Downloads the latest installer and runs it. To run the server in Docker instead:
#   & ([scriptblock]::Create((irm https://www.luna-ai-engine.com/install.ps1))) -Docker

param([switch]$Docker)

$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 may default to TLS 1.0/1.1, which GitHub rejects
# ("The connection was closed unexpectedly"). Make sure TLS 1.2 is on.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Repo = 'Sehastrajit-S/Luna'
$Image = 'ghcr.io/sehastrajit-s/luna:latest'

function Say($text) { Write-Host "==> $text" -ForegroundColor Magenta }

if ($Docker) {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker isn't installed. Install Docker Desktop, or run this without -Docker for the app." }
  docker info *> $null
  if ($LASTEXITCODE -ne 0) { throw "Docker isn't running. Start Docker Desktop and try again." }
  Say "Pulling $Image"
  docker pull $Image
  docker container inspect luna *> $null
  if ($LASTEXITCODE -eq 0) {
    Say "Replacing the existing 'luna' container (your data stays in the luna_data volume)"
    docker rm -f luna | Out-Null
  }
  docker run -d --name luna --restart unless-stopped -p 127.0.0.1:8899:8899 -v luna_data:/app/data $Image | Out-Null
  Say 'Luna is running at http://localhost:8899'
  Start-Process 'http://localhost:8899'
  return
}

# Ask GitHub for the newest release's installer instead of guessing its file name.
Say 'Finding the latest Luna release'
try {
  $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'luna-installer' }
} catch {
  throw "Couldn't reach GitHub ($($_.Exception.Message)). Check your internet connection, or download Luna from https://www.luna-ai-engine.com/#download"
}
$asset = $release.assets | Where-Object { $_.name -match '^Luna-Setup(-[\d.]+)?\.exe$' } | Select-Object -First 1
if (-not $asset) { throw "Release $($release.tag_name) has no Windows installer. Download Luna from https://www.luna-ai-engine.com/#download" }

$installer = Join-Path $env:TEMP $asset.name
Say "Downloading $($asset.name) ($([math]::Round($asset.size / 1MB)) MB)"
$ProgressPreference = 'SilentlyContinue'  # Invoke-WebRequest is far slower with the progress bar
try {
  Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $installer -UseBasicParsing
} catch {
  throw "Download failed ($($_.Exception.Message)). Try again, or download it from $($release.html_url)"
}

$signature = Get-AuthenticodeSignature $installer
if ($signature.Status -ne 'Valid') {
  Write-Host '    The installer is not code-signed yet; Windows may ask you to confirm.' -ForegroundColor DarkGray
}

Say 'Running the installer'
Start-Process -FilePath $installer -Wait
Remove-Item $installer -ErrorAction SilentlyContinue
Say 'Done. Luna sets up everything else on first launch.'
