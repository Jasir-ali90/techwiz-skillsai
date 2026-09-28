"""Cut the web brand assets out of the master logo image.

    .venv/Scripts/python.exe -m scripts.build_brand_assets

Reads docs/brand/skillsprint-logo-source.webp (the logo on a flat near-white
background) and writes:

  frontend/src/assets/brand/logo.png        mark + wordmark, for light surfaces
  frontend/src/assets/brand/logo-dark.png   same, navy recoloured for dark surfaces
  docs/brand/mark.png                       the S-and-arrow mark on its own (the favicon source)
  frontend/public/favicon.ico, favicon-32.png, apple-touch-icon.png, icon-192.png, icon-512.png
  docs/brand/logo-full.png, logo-full-dark.png   with the tagline, for docs and slides

Needs numpy, scipy and Pillow (all present in the API virtualenv).
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "brand" / "skillsprint-logo-source.webp"
ASSETS = ROOT / "frontend" / "src" / "assets" / "brand"
PUBLIC = ROOT / "frontend" / "public"
DOCS = ROOT / "docs" / "brand"

BG = 254.0  # the source background, #fefefe
SOFT_EDGE = 60.0  # colour distance over which a pixel ramps from clear to opaque
DARK_INK = np.array([238, 242, 248], dtype=float)  # stands in for navy on dark surfaces


def load_layers():
    rgb = np.asarray(Image.open(SRC).convert("RGB")).astype(float)
    dist = np.abs(rgb - BG).max(axis=2)
    alpha = np.clip((dist - 4) / SOFT_EDGE, 0, 1)
    # Un-mix the anti-aliased edges from the white background.
    safe = np.where(alpha > 0, alpha, 1)[..., None]
    colour = np.clip((rgb - (1 - alpha[..., None]) * BG) / safe, 0, 255)

    labels, _ = ndimage.label(dist > 20, structure=np.ones((3, 3)))
    # Give every faint halo pixel the label of the nearest solid shape.
    _, (iy, ix) = ndimage.distance_transform_edt(labels == 0, return_indices=True)
    nearest = labels[iy, ix]
    return colour, alpha, labels, nearest


def pick_parts(labels):
    boxes = ndimage.find_objects(labels)
    sizes = ndimage.sum(np.ones_like(labels), labels, index=range(1, len(boxes) + 1))
    mark = int(np.argmax(sizes)) + 1
    tagline = {i for i, (ys, _) in enumerate(boxes, 1) if ys.start >= 600}
    everything = set(range(1, len(boxes) + 1))
    return {"mark": {mark}, "logo": everything - tagline, "full": everything}


def render(colour, alpha, nearest, part, dark=False, pad=6):
    a = np.where(np.isin(nearest, list(part)), alpha, 0)
    c = colour.copy()
    if dark:
        # Navy has a low blue channel; the brand blues sit near 250.
        t = np.clip((190 - c[..., 2]) / 60, 0, 1)[..., None]
        c = c * (1 - t) + DARK_INK * t
    ys, xs = np.where(a > 0)
    y0, y1 = max(ys.min() - pad, 0), ys.max() + pad + 1
    x0, x1 = max(xs.min() - pad, 0), xs.max() + pad + 1
    rgba = np.dstack([c, a * 255])[y0:y1, x0:x1].round().astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def resize(im, width=None, height=None):
    w, h = im.size
    if width:
        size = (width, round(h * width / w))
    else:
        size = (round(w * height / h), height)
    # Resample premultiplied so edges do not pick up a white fringe.
    return im.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")


def tile(mark, size, fill=0.8, radius=0.22, rounded=True):
    """The mark centred on a white tile, so it reads on light and dark tab bars."""
    big = size * 4  # draw the corners large, then shrink, for a smooth edge
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    shape = ImageDraw.Draw(canvas)
    if rounded:
        shape.rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * radius), fill=(255, 255, 255, 255))
    else:
        shape.rectangle((0, 0, big, big), fill=(255, 255, 255, 255))
    canvas = resize(canvas, width=size)
    side = size * fill
    m = resize(mark, width=round(side)) if mark.width >= mark.height else resize(mark, height=round(side))
    canvas.alpha_composite(m, ((size - m.width) // 2, (size - m.height) // 2))
    return canvas


def main():
    colour, alpha, labels, nearest = load_layers()
    parts = pick_parts(labels)
    ASSETS.mkdir(parents=True, exist_ok=True)

    logo = render(colour, alpha, nearest, parts["logo"])
    resize(logo, width=960).save(ASSETS / "logo.png", optimize=True)
    resize(render(colour, alpha, nearest, parts["logo"], dark=True), width=960).save(ASSETS / "logo-dark.png", optimize=True)

    mark = render(colour, alpha, nearest, parts["mark"], pad=2)
    resize(mark, height=256).save(DOCS / "mark.png", optimize=True)

    full = render(colour, alpha, nearest, parts["full"], pad=12)
    full.save(DOCS / "logo-full.png", optimize=True)
    render(colour, alpha, nearest, parts["full"], dark=True, pad=12).save(DOCS / "logo-full-dark.png", optimize=True)

    icons = [tile(mark, s, fill=0.86 if s <= 32 else 0.8) for s in (16, 24, 32, 48, 64)]
    icons[-1].save(PUBLIC / "favicon.ico", sizes=[(i.width, i.height) for i in icons], append_images=icons[:-1])
    icons[2].save(PUBLIC / "favicon-32.png", optimize=True)
    tile(mark, 192).save(PUBLIC / "icon-192.png", optimize=True)
    tile(mark, 512).save(PUBLIC / "icon-512.png", optimize=True)
    # iOS rounds the corners itself, so this one is a plain square.
    tile(mark, 180, fill=0.72, rounded=False).convert("RGB").save(PUBLIC / "apple-touch-icon.png", optimize=True)

    print("mark", mark.size, "logo", logo.size, "full", full.size)


if __name__ == "__main__":
    main()
