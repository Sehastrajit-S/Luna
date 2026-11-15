#!/usr/bin/env python3
"""
Luna UI screenshot capture.

Prerequisites:
  pip install -r requirements.txt
  playwright install chromium        # or uses system Chrome automatically

The frontend must be running first:
  cd frontend && npm run dev

Usage:
  python capture_ui.py              # all shots
  python capture_ui.py orb          # just the voice orb
  python capture_ui.py hud          # dashboard HUD panels
  python capture_ui.py wave         # 3D wave loader
  python capture_ui.py chat         # chat exchange
"""

import asyncio, sys, base64
from pathlib import Path
from playwright.async_api import async_playwright, Page

OUT  = Path(__file__).resolve().parents[2] / "docs-site" / "public" / "screenshots"
URL  = "http://localhost:5173"

# Use system Chrome if Playwright's bundled Chromium wasn't installed
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# App colors so mock HTML matches
BG      = "#09090f"
SURFACE = "#0f0f17"
PURPLE  = "#a78bfa"
DIM     = "#64748b"
TEXT    = "#e2e8f0"


# ── helpers ───────────────────────────────────────────────────────────────────

async def new_page(pw, width=1200, height=800):
    chrome = Path(CHROME)
    kwargs = dict(channel="chrome") if chrome.exists() else {}
    browser = await pw.chromium.launch(**kwargs)
    ctx     = await browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme="dark",
    )
    return browser, ctx, await ctx.new_page()

async def save(page: Page, name: str, clip: dict | None = None):
    path = OUT / name
    kwargs = dict(path=str(path))
    if clip:
        kwargs["clip"] = clip
    await page.screenshot(**kwargs)
    print(f"  ok  {name}")


# ── 1. Voice Orb — startup splash widget ─────────────────────────────────────
# The app shows a 164 px orb + "LUNA" label for 1.7 s at launch.
# We capture only the centred area, stripping window chrome entirely.

async def shot_orb():
    async with async_playwright() as pw:
        browser, _, page = await new_page(pw)
        await page.goto(URL, wait_until="domcontentloaded")

        # Splash is fixed full-screen; grab it before it fades (1.7 s)
        splash = page.locator("div.fixed.inset-0.z-50")
        await splash.wait_for(state="visible", timeout=4000)

        box = await splash.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

        await save(page, "voice-orb.png", clip={
            "x": cx - 140, "y": cy - 160,
            "width": 280,  "height": 320,
        })
        await browser.close()


# ── 2. Dashboard HUD panels — stocks + weather crop ──────────────────────────
# Opens the Luna dashboard and screenshots only the top-two HUD cards.
# Full-screen overlay is dark and large; a 2-panel crop shows the aesthetic.

async def shot_hud():
    async with async_playwright() as pw:
        browser, _, page = await new_page(pw)
        await page.goto(URL, wait_until="networkidle")

        # Wait for splash to go away
        await page.wait_for_timeout(2000)

        # The dashboard toggle is in the TitleBar — aria-label or title "Luna"
        toggle = page.get_by_title("Luna").first
        if not await toggle.is_visible():
            toggle = page.locator("button[aria-label='Luna']").first
        await toggle.click()
        await page.wait_for_timeout(600)

        # The HUD panels are rendered inside the dashboard overlay.
        # Grab the first two panel containers (corner-bracket bordered divs).
        panels = page.locator("[style*='border: 1px solid']").filter(
            has_text=lambda t: True
        )
        count = await panels.count()
        if count < 2:
            print("  ! Could not locate HUD panels — is the dashboard open?")
            await browser.close()
            return

        # Bounding box of first two panels together
        b1 = await panels.nth(0).bounding_box()
        b2 = await panels.nth(1).bounding_box()
        left  = min(b1["x"],  b2["x"]) - 12
        top   = min(b1["y"],  b2["y"]) - 12
        right = max(b1["x"] + b1["width"],  b2["x"] + b2["width"])  + 12
        bot   = max(b1["y"] + b1["height"], b2["y"] + b2["height"]) + 12

        await save(page, "dashboard-hud.png", clip={
            "x": left, "y": top,
            "width": right - left, "height": bot - top,
        })
        await browser.close()


# ── 3. WaveLoader — 3D generation loading animation ──────────────────────────
# Rendered in a standalone HTML page that mounts just the canvas animation.
# Matches the exact algorithm from DynamicWidgetOverlay.tsx → WaveLoader.

WAVE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#000; display:flex; flex-direction:column;
         align-items:center; justify-content:center;
         width:400px; height:400px; }
  canvas { width:360px; height:320px; border-radius:4px; }
  p { color:#64748b; font:10px/1 monospace; letter-spacing:.22em;
      text-transform:uppercase; margin-top:14px; }
</style>
</head>
<body>
<canvas id="c"></canvas>
<p>generating 3d scene…</p>
<script>
const canvas = document.getElementById('c')
const ctx    = canvas.getContext('2d')
canvas.width  = 360; canvas.height = 320
const COLS = 30, ROWS = 24
let t = 0
const lerp = (a, b, f) => a + (b-a)*f
function draw() {
  requestAnimationFrame(draw); t += 0.018
  const W = canvas.width, H = canvas.height
  ctx.fillStyle = '#000'; ctx.fillRect(0,0,W,H)
  const cw = W/COLS, ch = H/ROWS
  for (let row=0; row<ROWS; row++) {
    for (let col=0; col<COLS; col++) {
      const x = (col+.5)*cw, y = (row+.5)*ch
      const wave =
        Math.sin(col*.42 + row*.22 + t*1.3)*.45 +
        Math.sin(col*.28 - row*.52 + t*.85)*.35 +
        Math.sin((col+row)*.31  + t*1.05)*.20
      const n = Math.max(0, Math.min(1, (wave+1)/2))
      let r,g,b
      if      (n < 0.35) { const f=n/.35;        r=lerp(4,90,f);   g=lerp(0,10,f);   b=lerp(12,180,f) }
      else if (n < 0.65) { const f=(n-.35)/.30;  r=lerp(90,139,f); g=lerp(10,92,f);  b=lerp(180,246,f) }
      else               { const f=(n-.65)/.35;  r=lerp(139,216,f);g=lerp(92,180,f); b=lerp(246,254,f) }
      const radius = 1.0 + n*2.8
      const alpha  = 0.25 + n*0.75
      ctx.beginPath()
      ctx.arc(x, y, radius, 0, Math.PI*2)
      ctx.fillStyle = `rgba(${r|0},${g|0},${b|0},${alpha.toFixed(2)})`
      ctx.fill()
    }
  }
}
draw()
</script>
</body>
</html>"""

async def shot_wave():
    async with async_playwright() as pw:
        browser, ctx, page = await new_page(pw, 400, 400)
        await page.set_content(WAVE_HTML)
        # Let the animation run for a moment to reach a rich frame
        await page.wait_for_timeout(1200)
        await save(page, "wave-loader.png")
        await browser.close()


# ── 4. Chat exchange — message bubbles only ───────────────────────────────────
# Renders a standalone HTML page with 2 message bubbles matching the app's
# MessageBubble styles: user message right-aligned, Luna response left-aligned
# with mood-gradient avatar. No sidebar, no titlebar.

CHAT_HTML = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:{BG}; font-family:Inter,system-ui,sans-serif;
          display:flex; align-items:center; justify-content:center;
          width:560px; height:320px; }}
  .msgs {{ width:100%; padding:24px 28px; display:flex; flex-direction:column; gap:18px; }}

  /* user bubble */
  .user {{ display:flex; justify-content:flex-end; }}
  .user-bubble {{
    background:linear-gradient(135deg,#7c3aed,#5b21b6);
    color:#f3f0ff; border-radius:18px 18px 4px 18px;
    padding:10px 16px; max-width:72%; font-size:13.5px; line-height:1.5;
    box-shadow:0 2px 8px rgba(139,92,246,.35);
  }}

  /* luna bubble */
  .luna {{ display:flex; align-items:flex-start; gap:10px; }}
  .avatar {{
    width:32px; height:32px; border-radius:50%; flex-shrink:0;
    background:linear-gradient(135deg,#a78bfa,#6d28d9);
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 0 10px rgba(139,92,246,.5);
    font-size:12px; font-weight:700; color:#fff; margin-top:2px;
  }}
  .luna-bubble {{
    background:{SURFACE}; color:{TEXT}; border:1px solid #1e1e2e;
    border-radius:4px 18px 18px 18px; padding:12px 16px;
    max-width:78%; font-size:13.5px; line-height:1.6;
  }}
  .luna-bubble .mood {{
    font-size:10px; color:{DIM}; letter-spacing:.06em;
    margin-bottom:6px; display:flex; align-items:center; gap:5px;
  }}
  .dot {{ width:6px; height:6px; border-radius:50%;
          background:linear-gradient(135deg,#a78bfa,#6d28d9); }}
</style>
</head>
<body>
<div class="msgs">
  <div class="user">
    <div class="user-bubble">What's the weather looking like today?</div>
  </div>
  <div class="luna">
    <div class="avatar">L</div>
    <div class="luna-bubble">
      <div class="mood"><div class="dot"></div> thoughtful</div>
      It's partly cloudy with a high of 19 °C — good jacket weather.
      The afternoon looks clear, so if you had any outdoor plans, after
      3 pm should be comfortable.
    </div>
  </div>
</div>
</body>
</html>"""

async def shot_chat():
    async with async_playwright() as pw:
        browser, ctx, page = await new_page(pw, 560, 320)
        await page.set_content(CHAT_HTML)
        await page.wait_for_timeout(200)
        await save(page, "chat-exchange.png")
        await browser.close()


# ── dispatch ──────────────────────────────────────────────────────────────────

SHOTS = {
    "orb":  shot_orb,
    "hud":  shot_hud,
    "wave": shot_wave,
    "chat": shot_chat,
}

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    targets = sys.argv[1:] or list(SHOTS)
    unknown = [t for t in targets if t not in SHOTS]
    if unknown:
        print(f"Unknown targets: {unknown}. Valid: {list(SHOTS)}")
        sys.exit(1)

    print(f"Saving to: {OUT}\n")
    for name in targets:
        print(f">> {name}")
        await SHOTS[name]()

    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(main())
