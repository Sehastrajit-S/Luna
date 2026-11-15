#!/usr/bin/env python3
"""
Render CLI output as a styled terminal PNG.
Usage: python render_cli.py <output_path> <command_label> < input_text
"""
import asyncio, sys, re
from pathlib import Path

BG, FG, DIM, GREEN, PURPLE = "#0d0d14", "#e2e8f0", "#64748b", "#4ade80", "#a78bfa"

_default_out = Path(__file__).resolve().parents[2] / "docs-site" / "public" / "screenshots" / "cli-output.png"
out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_out
cmd_label = sys.argv[2] if len(sys.argv) > 2 else "--help"

text = sys.stdin.buffer.read().decode('utf-8-sig')

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def colorise(line):
    l = esc(line)
    if re.match(r'^[A-Z][A-Za-z ]+:$', l.strip()):
        return f'<span style="color:{PURPLE};font-weight:700">{l}</span>'
    l = re.sub(r'(?<![=\w])(--?[\w][\w-]*)', f'<span style="color:{GREEN}">\\1</span>', l)
    l = re.sub(
        r'^(\s{{2,}})(\w[\w-]+)(\s{{2,}})',
        lambda m: m.group(1) + f'<span style="color:{PURPLE}">{m.group(2)}</span>' + m.group(3),
        l
    )
    return l

lines_html = "".join(
    f'<div class="line">{colorise(l)}</div>'
    for l in text.splitlines()
)

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
* {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ background:{BG}; font:13px/1.55 "Cascadia Code","Fira Code",monospace;
        color:{FG}; padding:24px 30px; min-width:620px; }}
.bar {{ display:flex;align-items:center;gap:7px;margin-bottom:18px; }}
.dot {{ width:12px;height:12px;border-radius:50%; }}
.prompt {{ color:{DIM};font-size:11px;margin-bottom:10px; }}
.line {{ white-space:pre; }}
</style></head>
<body>
<div class="bar">
  <div class="dot" style="background:#ff5f57"></div>
  <div class="dot" style="background:#febc2e"></div>
  <div class="dot" style="background:#28c840"></div>
</div>
<div class="prompt">~ $ luna {esc(cmd_label)}</div>
{lines_html}
</body></html>"""

async def run():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        kwargs = dict(channel="chrome") if Path(chrome).exists() else {}
        b   = await pw.chromium.launch(**kwargs)
        ctx = await b.new_context(
            viewport={"width": 660, "height": 800},
            color_scheme="dark",
        )
        pg = await ctx.new_page()
        await pg.set_content(html)
        await pg.wait_for_timeout(200)
        body_h = await pg.evaluate("document.body.scrollHeight")
        await ctx.close()

        ctx2 = await b.new_context(
            viewport={"width": 660, "height": body_h + 48},
            color_scheme="dark",
        )
        pg2 = await ctx2.new_page()
        await pg2.set_content(html)
        await pg2.wait_for_timeout(200)
        await pg2.screenshot(path=str(out_path))
        await b.close()

    print(f"  ok  {out_path.name}")

asyncio.run(run())
