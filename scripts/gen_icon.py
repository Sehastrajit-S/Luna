"""
Generates the Luna app icon — a purple glowing sphere.
Outputs: electron/assets/icon.png (512), icon.ico (multi-size), tray.png (16)
Run from the repo root: python scripts/gen_icon.py
"""
import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw, ImageFilter

OUT = Path("electron/assets")
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 512

def make_sphere(size: int, radius_scale: float = 0.34) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size / 2
    r = size * radius_scale

    # Pixel-by-pixel sphere with purple gradient + rim light
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > r:
                continue

            t = dist / r                         # 0 = center, 1 = edge
            nx, ny = dx / r, dy / r
            nz = math.sqrt(max(0.0, 1.0 - nx*nx - ny*ny))

            # Key light (top-left)
            light = nx * -0.4 + ny * -0.6 + nz * 0.7
            light = max(0.0, light) ** 0.7

            # Purple core colour
            base_r, base_g, base_b = 120, 60, 230

            # Rim / edge glow (violet-blue)
            rim = (1.0 - nz) ** 3.5
            rim_r, rim_g, rim_b = 180, 100, 255

            cr = int(min(255, base_r * light + rim_r * rim * 0.6 + 30 * light))
            cg = int(min(255, base_g * light + rim_g * rim * 0.6 + 20 * light))
            cb = int(min(255, base_b * light + rim_b * rim * 0.8 + 60 * light))

            # Specular highlight (top-left)
            spec_x, spec_y, spec_z = -0.5, -0.5, 0.7
            spec = nx*spec_x + ny*spec_y + nz*spec_z
            spec = max(0.0, spec) ** 18
            cr = int(min(255, cr + 255 * spec * 0.7))
            cg = int(min(255, cg + 255 * spec * 0.7))
            cb = int(min(255, cb + 255 * spec * 0.5))

            # Soft edge fade
            alpha = int(255 * min(1.0, (1.0 - t) * 8) if t > 0.875 else 255)
            pixels[x, y] = (cr, cg, cb, alpha)

    # Outer glow
    glow = img.filter(ImageFilter.GaussianBlur(size // 14))
    combined = Image.alpha_composite(glow, img)
    return combined


def rotated_ellipse_layer(
    size: int,
    bbox: tuple[float, float, float, float],
    angle: float,
    color: tuple[int, int, int, int],
    width: int,
    blur: int = 0,
    arc: tuple[int, int] | None = None,
) -> Image.Image:
    scale = 3
    big = size * scale
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    scaled_bbox = tuple(int(v * scale) for v in bbox)
    scaled_width = max(1, width * scale)

    if arc:
        draw.arc(scaled_bbox, start=arc[0], end=arc[1], fill=color, width=scaled_width)
    else:
        draw.ellipse(scaled_bbox, outline=color, width=scaled_width)

    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur * scale))

    layer = layer.rotate(angle, resample=Image.Resampling.BICUBIC, center=(big / 2, big / 2))
    return layer.resize((size, size), Image.Resampling.LANCZOS)


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size / 2
    stroke = max(1, round(size * 0.08))

    outer = (
        cx - size * 0.48,
        cy - size * 0.18,
        cx + size * 0.48,
        cy + size * 0.18,
    )
    inner = (
        cx - size * 0.32,
        cy - size * 0.115,
        cx + size * 0.32,
        cy + size * 0.115,
    )

    for bbox, angle, alpha, glow_width in (
        (outer, -24, 95, stroke * 3),
        (inner, 38, 80, max(1, stroke * 2)),
    ):
        img = Image.alpha_composite(
            img,
            rotated_ellipse_layer(
                size,
                bbox,
                angle,
                (168, 120, 255, alpha),
                glow_width,
                blur=max(1, round(size * 0.01)),
            ),
        )

    img = Image.alpha_composite(
        img,
        rotated_ellipse_layer(size, outer, -24, (139, 92, 246, 145), stroke),
    )
    img = Image.alpha_composite(
        img,
        rotated_ellipse_layer(size, inner, 38, (196, 181, 253, 115), max(1, round(stroke * 0.7))),
    )
    img = Image.alpha_composite(img, make_sphere(size, radius_scale=0.1425))
    img = Image.alpha_composite(
        img,
        rotated_ellipse_layer(size, outer, -24, (216, 196, 255, 230), max(1, round(stroke * 0.75)), arc=(16, 164)),
    )
    img = Image.alpha_composite(
        img,
        rotated_ellipse_layer(size, inner, 38, (167, 139, 250, 190), max(1, round(stroke * 0.55)), arc=(198, 338)),
    )
    return img


print("Generating Luna icon...")
icon_512 = make_icon(SIZE)
icon_512.save(OUT / "icon.png")
print("  icon.png (512x512) done")

# ICO with multiple sizes
sizes = [256, 128, 64, 48, 32, 16]
ico_images = [make_icon(s) for s in sizes]
ico_images[0].save(
    OUT / "icon.ico",
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=ico_images[1:],
)
print("  icon.ico (multi-size) done")

# Tray icon (16x16)
tray = make_icon(16)
tray.save(OUT / "tray.png")
print("  tray.png (16x16) done")

print("Icons written to electron/assets/")
