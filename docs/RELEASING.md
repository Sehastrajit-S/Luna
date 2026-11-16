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
