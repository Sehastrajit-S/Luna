#!/usr/bin/env node
/**
 * Write package-manager manifests for a release from its SHA256SUMS file:
 *   dist/packaging/winget/manifests/s/Sehastrajit/Luna/<version>/*.yaml   (winget-pkgs layout)
 *   dist/packaging/homebrew/Casks/luna.rb                                  (Homebrew tap)
 *
 * Usage: node scripts/package-manifests.mjs <version> <path/to/SHA256SUMS-<version>.txt>
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const [version, sumsPath] = process.argv.slice(2)
if (!version || !sumsPath) {
  console.error('Usage: node scripts/package-manifests.mjs <version> <SHA256SUMS file>')
  process.exit(1)
}

const REPO = 'Sehastrajit-S/Luna'
const HOMEPAGE = 'https://www.luna-ai-engine.com'
const DESC = 'Open-source, self-hosted AI assistant. Run local LLMs with Ollama or any cloud model, with voice, memory and meeting notes.'
const release = `https://github.com/${REPO}/releases/download/v${version}`

const sums = Object.fromEntries(
  readFileSync(sumsPath, 'utf8').trim().split('\n').map(line => {
    const [hash, name] = line.trim().split(/\s+/)
    return [name.replace(/^\*/, ''), hash]
  }),
)
function sha(name) {
  if (!sums[name]) throw new Error(`${name} is not in ${sumsPath}`)
  return sums[name]
}

const root = resolve(import.meta.dirname, '..', 'dist', 'packaging')

// ── winget (manifest schema 1.6) ──────────────────────────────────────────────
const id = 'Sehastrajit.Luna'
const wingetDir = join(root, 'winget', 'manifests', 's', 'Sehastrajit', 'Luna', version)
mkdirSync(wingetDir, { recursive: true })
const header = kind => `# yaml-language-server: $schema=https://aka.ms/winget-manifest.${kind}.1.6.0.schema.json\n`

writeFileSync(join(wingetDir, `${id}.yaml`), `${header('version')}
PackageIdentifier: ${id}
PackageVersion: ${version}
DefaultLocale: en-US
ManifestType: version
ManifestVersion: 1.6.0
`)

writeFileSync(join(wingetDir, `${id}.installer.yaml`), `${header('installer')}
PackageIdentifier: ${id}
PackageVersion: ${version}
InstallerType: nullsoft
Scope: user
UpgradeBehavior: install
Installers:
  - Architecture: x64
    InstallerUrl: ${release}/Luna-Setup-${version}.exe
    InstallerSha256: ${sha(`Luna-Setup-${version}.exe`).toUpperCase()}
ManifestType: installer
ManifestVersion: 1.6.0
`)

writeFileSync(join(wingetDir, `${id}.locale.en-US.yaml`), `${header('defaultLocale')}
PackageIdentifier: ${id}
PackageVersion: ${version}
PackageLocale: en-US
Publisher: Sehastrajit
PublisherUrl: https://github.com/Sehastrajit-S
PackageName: Luna
PackageUrl: ${HOMEPAGE}
License: MIT
LicenseUrl: https://github.com/${REPO}/blob/main/LICENSE
ShortDescription: ${DESC}
Moniker: luna
Tags:
  - ai
  - ai-assistant
  - llm
  - ollama
  - self-hosted
  - voice-assistant
ReleaseNotesUrl: https://github.com/${REPO}/releases/tag/v${version}
ManifestType: defaultLocale
ManifestVersion: 1.6.0
`)

// ── Homebrew cask ─────────────────────────────────────────────────────────────
const caskDir = join(root, 'homebrew', 'Casks')
mkdirSync(caskDir, { recursive: true })
writeFileSync(join(caskDir, 'luna.rb'), `cask "luna" do
  arch arm: "arm64", intel: "x64"

  version "${version}"
  sha256 arm:   "${sha(`Luna-${version}-macos-arm64.dmg`)}",
         intel: "${sha(`Luna-${version}-macos-x64.dmg`)}"

  url "https://github.com/${REPO}/releases/download/v#{version}/Luna-#{version}-macos-#{arch}.dmg"
  name "Luna"
  desc "${DESC.split('.')[0]}"
  homepage "${HOMEPAGE}"

  livecheck do
    url :url
    strategy :github_latest
  end

  app "Luna.app"

  zap trash: [
    "~/Library/Application Support/Luna",
    "~/Library/Logs/Luna",
    "~/Library/Preferences/com.luna.desktop.plist",
  ]
end
`)

console.log(`Wrote winget and Homebrew manifests for ${version} to ${root}`)
