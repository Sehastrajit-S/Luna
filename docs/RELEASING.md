# Releasing Luna

One GitHub Release publishes everything:

| What | Where it ends up |
|---|---|
| Windows: `Luna-Setup-<version>.exe`, portable `Luna-<version>-windows-x64.zip` | Release assets |
| macOS (unsigned): `Luna-<version>-macos-arm64.dmg`, `-macos-x64.dmg`, plus `.zip` | Release assets |
| Linux: `Luna-<version>-linux-x86_64.AppImage`, `-linux-arm64.AppImage` | Release assets |
| Android (debug-signed): `Luna-<version>-android.apk` | Release assets |
| iOS simulator build: `Luna-<version>-ios-simulator.zip` | Release assets |
| Server + web UI for any OS with Python: `Luna-<version>-server.zip` | Release assets |
| Checksums `SHA256SUMS-<version>.txt` and build provenance `Luna-<version>.intoto.jsonl` | Release assets |
| Container image | `ghcr.io/sehastrajit-s/luna:<version>` and `:latest` |

Verify a download: `sha256sum -c SHA256SUMS-<version>.txt --ignore-missing`, or check its provenance with `gh attestation verify <file> --repo Sehastrajit-S/Luna`.

Workflows: [`build-release.yml`](../.github/workflows/build-release.yml) (apps) and [`docker.yml`](../.github/workflows/docker.yml) (image; also smoke-tests the image on every pull request).

## Steps

1. **Bump the version** in `interfaces/desktop/package.json` (`"version": "0.3.0"`). It names every file and image tag.
2. Merge to `main` with the checks green (`npm run test:smoke`, `npm run build`, and the container smoke test on the PR).
3. **Publish a release** on GitHub: tag `v<version>` on `main`, write the notes, Publish. Or from a terminal:
   ```bash
   gh release create v0.3.0 --target main --title "Luna 0.3.0" --notes-file notes.md
   ```
4. Wait for the two workflows to finish; the files appear on the release and the image on the repo's Packages page.
5. **First release only:** make the container package public (repo → Packages → luna → Package settings → Change visibility → Public) so anyone can pull it without logging in.

## Download links that never change

Each release also attaches copies without the version in the name, so these always fetch the newest build (the website, README and install scripts use them):

| File | Link |
|---|---|
| Windows | `https://github.com/Sehastrajit-S/Luna/releases/latest/download/Luna-Setup.exe` |
| macOS | `.../latest/download/Luna-macos-arm64.dmg`, `Luna-macos-x64.dmg` |
| Linux | `.../latest/download/Luna-linux-x86_64.AppImage`, `Luna-linux-arm64.AppImage` |
| Android | `.../latest/download/Luna-android.apk` |
| Server | `.../latest/download/Luna-server.zip` |

The workflow also writes a **Download** table at the top of the release notes.

One-line installers live on the website (`docs/site/public/install.sh`, `install.ps1`):

```bash
curl -fsSL https://www.luna-ai-engine.com/install.sh | sh     # macOS / Linux
irm https://www.luna-ai-engine.com/install.ps1 | iex          # Windows
```

## Package managers (optional)

Every release generates winget and Homebrew manifests (artifact `package-manifests`). Publishing them needs one-time setup:

**Homebrew** (`brew install sehastrajit-s/luna/luna`):
1. Create a public repo `Sehastrajit-S/homebrew-luna` with an empty `Casks/` folder.
2. Add a secret `HOMEBREW_TAP_TOKEN`: a fine-grained token with *Contents: read and write* on that repo.
From then on every release updates `Casks/luna.rb`.

**winget** (`winget install Sehastrajit.Luna`):
1. The first version is a manual pull request to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs): copy `manifests/s/Sehastrajit/Luna/<version>/` from the `package-manifests` artifact (or run `node scripts/package-manifests.mjs <version> SHA256SUMS-<version>.txt`), check it with `winget validate --manifest <folder>`, and open the PR.
2. After it's merged, add a secret `WINGET_TOKEN` (classic token, `public_repo` scope). Later releases open the update PR automatically.

**Android**: Obtainium tracks GitHub releases with no setup. Share this link: `https://apps.obtainium.imranr.dev/redirect?r=obtainium://add/https://github.com/Sehastrajit-S/Luna`

## Code signing (optional)

Builds are unsigned until these secrets exist; then the workflow signs automatically.

| Platform | Secrets | Get it from |
|---|---|---|
| Windows | `WIN_CSC_LINK` (the `.pfx`, base64), `WIN_CSC_KEY_PASSWORD` | A code-signing certificate (OV/EV), or Azure Trusted Signing |
| macOS | `MAC_CSC_LINK` (Developer ID Application `.p12`, base64), `MAC_CSC_KEY_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` | Apple Developer Program ($99/year); notarization runs when `APPLE_ID` is set |

Base64 a certificate with `base64 -i cert.p12 | pbcopy` (macOS) or `[Convert]::ToBase64String([IO.File]::ReadAllBytes('cert.pfx'))` (PowerShell).

## Building locally

All build output goes under `dist/<target>/` and is never committed:

```bash
npm run build:desktop            # dist/desktop/Luna-Setup-<version>.exe (Windows)
npm --prefix interfaces/desktop run build:mac     # on a Mac: dmg + zip
npm --prefix interfaces/desktop run build:linux   # on Linux: AppImage
docker build -t luna .           # the container image
```

Android and iOS builds need Android Studio / Xcode: `npm run build:mobile` syncs the web build into `interfaces/mobile`, then build from `interfaces/mobile/android` or `interfaces/mobile/ios`.

## Notes

- The macOS app isn't signed or notarized: right-click it and choose Open the first time.
- The Windows installer isn't code-signed, so Windows SmartScreen shows a warning on first run ("More info → Run anyway"). Signing needs a code-signing certificate added to the workflow.
- The Android APK is debug-signed for sideloading. Play Store builds need a release keystore.
- The iOS build runs on the simulator only; device and App Store builds need an Apple developer account and signing.
