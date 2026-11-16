# Install Luna on Windows.
#
#   irm https://www.luna-ai-engine.com/install.ps1 | iex
#
# Downloads the latest installer and runs it. To run the server in Docker instead:
#   & ([scriptblock]::Create((irm https://www.luna-ai-engine.com/install.ps1))) -Docker

param([switch]$Docker)

$ErrorActionPreference = 'Stop'
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

$url = "https://github.com/$Repo/releases/latest/download/Luna-Setup.exe"
$installer = Join-Path $env:TEMP 'Luna-Setup.exe'
Say 'Downloading the latest Luna installer'
$ProgressPreference = 'SilentlyContinue'  # Invoke-WebRequest is far slower with the progress bar
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing

$signature = Get-AuthenticodeSignature $installer
if ($signature.Status -ne 'Valid') {
  Write-Host '    The installer is not code-signed yet; Windows may ask you to confirm.' -ForegroundColor DarkGray
}

Say 'Running the installer'
Start-Process -FilePath $installer -Wait
Remove-Item $installer -ErrorAction SilentlyContinue
Say 'Done. Luna sets up everything else on first launch.'
