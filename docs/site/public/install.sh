#!/bin/sh
# Install Luna on macOS or Linux.
#
#   curl -fsSL https://www.luna-ai-engine.com/install.sh | sh
#
# With Docker running, it starts (or updates) the Luna server container.
# Otherwise it installs the desktop app. Force one with:
#   curl -fsSL https://www.luna-ai-engine.com/install.sh | sh -s -- --docker
#   curl -fsSL https://www.luna-ai-engine.com/install.sh | sh -s -- --app
set -eu

REPO="Sehastrajit-S/Luna"
IMAGE="ghcr.io/sehastrajit-s/luna:latest"

say() { printf '\033[1;35m==>\033[0m %s\n' "$1"; }
fail() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

MODE="auto"
for arg in "$@"; do
  case "$arg" in
    --docker) MODE="docker" ;;
    --app) MODE="app" ;;
    *) fail "unknown option: $arg (use --docker or --app)" ;;
  esac
done

docker_ready() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }

install_docker() {
  docker_ready || fail "Docker isn't running. Start Docker, or use --app for the desktop app."
  say "Pulling ${IMAGE}"
  docker pull "$IMAGE"
  if docker container inspect luna >/dev/null 2>&1; then
    say "Replacing the existing 'luna' container (your data stays in the luna_data volume)"
    docker rm -f luna >/dev/null
  fi
  docker run -d --name luna --restart unless-stopped \
    -p 127.0.0.1:8899:8899 -v luna_data:/app/data "$IMAGE" >/dev/null
  say "Luna is running at http://localhost:8899"
  echo "    Pick a model in Settings: a local Ollama model or a cloud API key."
  if command -v tailscale >/dev/null 2>&1; then
    echo "    Use it from your other devices:  tailscale serve --bg --https=8899 http://127.0.0.1:8899"
  fi
}

download() {
  if command -v curl >/dev/null 2>&1; then curl -fL --progress-bar -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then wget -q --show-progress -O "$2" "$1"
  else fail "curl or wget is required"; fi
}

# URL of the newest release's file whose name matches an extended regex.
# Asks the GitHub API rather than guessing the name, so it works with
# versioned (Luna-0.2.1-macos-arm64.dmg) and fixed (Luna-macos-arm64.dmg) names.
asset_url() {
  api="https://api.github.com/repos/${REPO}/releases/latest"
  if command -v curl >/dev/null 2>&1; then json="$(curl -fsSL -H 'User-Agent: luna-installer' "$api")" || json=""
  else json="$(wget -qO- --header='User-Agent: luna-installer' "$api")" || json=""; fi
  [ -n "$json" ] || fail "couldn't reach GitHub. Check your connection, or download from https://www.luna-ai-engine.com/#download"
  url="$(printf '%s\n' "$json" | grep -o '"browser_download_url": *"[^"]*"' | sed 's/.*"\(https[^"]*\)"$/\1/' | grep -E "/$1\$" | head -1)"
  [ -n "$url" ] || fail "the latest release has no file matching $1. Download from https://www.luna-ai-engine.com/#download"
  printf '%s' "$url"
}

install_app() {
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$os" in
    Darwin)
      case "$arch" in arm64) march="arm64" ;; *) march="x64" ;; esac
      url="$(asset_url "Luna-([0-9.]+-)?macos-${march}\.dmg")"
      file="${url##*/}"
      tmp="$(mktemp -d)"
      say "Downloading ${file}"
      download "$url" "${tmp}/${file}"
      say "Installing to /Applications"
      mount="$(hdiutil attach -nobrowse -quiet "${tmp}/${file}" | tail -1 | awk -F '\t' '{print $NF}')"
      rm -rf /Applications/Luna.app
      cp -R "${mount}/Luna.app" /Applications/
      hdiutil detach -quiet "$mount"
      rm -rf "$tmp"
      # Downloaded by this script rather than a browser, so macOS won't block the unsigned app.
      say "Installed. Opening Luna..."
      open /Applications/Luna.app
      ;;
    Linux)
      case "$arch" in
        x86_64|amd64) larch="x86_64" ;;
        aarch64|arm64) larch="arm64" ;;
        *) fail "no desktop build for ${arch}; use --docker" ;;
      esac
      dest="${HOME}/.local/bin"
      mkdir -p "$dest"
      url="$(asset_url "Luna-([0-9.]+-)?linux-${larch}\.AppImage")"
      say "Downloading ${url##*/}"
      download "$url" "${dest}/luna.AppImage"
      chmod +x "${dest}/luna.AppImage"
      apps="${HOME}/.local/share/applications"
      mkdir -p "$apps"
      cat > "${apps}/luna.desktop" <<DESKTOP
[Desktop Entry]
Name=Luna
Comment=Open-source, self-hosted AI assistant
Exec=${dest}/luna.AppImage
Terminal=false
Type=Application
Categories=Utility;
DESKTOP
      say "Installed to ${dest}/luna.AppImage (also in your app menu)"
      echo "    Run it with: ${dest}/luna.AppImage"
      echo "    If it won't start, install FUSE: sudo apt install libfuse2   (Ubuntu/Debian)"
      ;;
    *) fail "unsupported OS: ${os}. On Windows, run in PowerShell: irm https://www.luna-ai-engine.com/install.ps1 | iex" ;;
  esac
}

case "$MODE" in
  docker) install_docker ;;
  app) install_app ;;
  auto)
    if docker_ready; then
      say "Docker is running: installing the Luna server (use --app for the desktop app instead)"
      install_docker
    else
      install_app
    fi
    ;;
esac
