"""Compose the README gallery images from the committed example sets.

Each image has three rows: the legacy reference PNG, the redrawn Light export and the
redrawn Dark export, all 32 px and enlarged 4x with nearest-neighbour so pixels stay honest.

    python examples/build_readme_gallery.py
"""
from __future__ import annotations

import io
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "docs" / "media"
SCALE = 4
CELL = 32 * SCALE + 24
LIGHT_BG, DARK_BG = (255, 255, 255), (30, 34, 40)

# (example dir, output name, [(reference id, exported id), ...])
BASE = [(i, i) for i in ("pump", "valve", "alarm-list", "network", "trend-chart", "device-connect")]
BADGED = [(e, e) for e in ("pump-add", "valve-remove", "alarm-list-clear", "network-add", "device-connected")]
GALLERY = [
    ("scada-demo", "outline", BASE),
    ("scada-filled", "filled", BASE),
    ("scada-duotone", "duotone", BASE),
    ("scada-outline-bold", "outline-bold", BASE),
    ("scada-badged", "badged", BADGED),
    ("scada-badge-accent", "badge-accent", BADGED),
]


def load(path: Path) -> Image.Image:
    if path.suffix == ".svg":  # SVG references are rasterised at 32 px like the exports
        png = subprocess.run(["resvg", "-w", "32", "-h", "32", str(path), "-c"], check=True, capture_output=True).stdout
        return Image.open(io.BytesIO(png))
    return Image.open(path)


def tile(path: Path, bg: tuple[int, int, int]) -> Image.Image:
    icon = load(path).convert("RGBA").resize((32 * SCALE,) * 2, Image.NEAREST)
    tile = Image.new("RGBA", (CELL, CELL), bg + (255,))
    tile.alpha_composite(icon, ((CELL - icon.width) // 2, (CELL - icon.height) // 2))
    return tile


def reference(example: str, icon_id: str) -> Path:
    folder = ROOT / example / "references"
    return next(p for p in (folder / f"{icon_id}.png", folder / f"{icon_id}.svg") if p.exists())


def build(example: str, name: str, pairs: list[tuple[str, str]]) -> Path:
    exports = ROOT / example / "icon-work" / example / "exports" / "desktop"
    rows = [
        (lambda r, e: reference(example, r), LIGHT_BG),
        (lambda r, e: exports / "light" / "normal" / "32" / f"{e}.png", LIGHT_BG),
        (lambda r, e: exports / "dark" / "normal" / "32" / f"{e}.png", DARK_BG),
    ]
    sheet = Image.new("RGBA", (CELL * len(pairs), CELL * len(rows)), LIGHT_BG + (255,))
    for y, (locate, bg) in enumerate(rows):
        for x, (ref, exported) in enumerate(pairs):
            sheet.paste(tile(locate(ref, exported), bg), (x * CELL, y * CELL))
    draw = ImageDraw.Draw(sheet)
    for y, label in enumerate(("legacy reference", "redrawn, Light", "redrawn, Dark")):
        fill = (110, 110, 110) if y < 2 else (170, 175, 185)
        draw.text((6, y * CELL + 4), label, fill=fill)
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"example-{name}.png"
    sheet.convert("RGB").save(target, optimize=True)
    return target


if __name__ == "__main__":
    for example, name, pairs in GALLERY:
        print(build(example, name, pairs))
