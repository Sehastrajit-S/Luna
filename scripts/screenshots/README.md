# Screenshot capture scripts

These scripts are **git-ignored** — only the resulting images in `assets/screenshots/` are committed.

## Setup (once)

```
pip install -r requirements.txt
playwright install chromium
```

## Capture UI widgets

The frontend must be running first:
```
cd frontend && npm run dev
```

Then:
```
python capture_ui.py          # all four shots
python capture_ui.py orb      # voice orb startup splash
python capture_ui.py hud      # dashboard HUD panels (app must be open)
python capture_ui.py wave     # 3D wave-loader animation
python capture_ui.py chat     # chat exchange bubbles
```

## Capture CLI output

```powershell
.\capture_cli.ps1                       # luna --help
.\capture_cli.ps1 -Command "skills list"
```

`luna` must be on PATH, otherwise a placeholder is used.

## Output

All images land in `../../docs-site/public/screenshots/` and can be committed.
Vercel serves them at `/screenshots/<file>.png` on the docs site.
