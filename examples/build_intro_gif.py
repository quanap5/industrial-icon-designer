#!/usr/bin/env python3
"""Build docs/media/intro.gif, the pixel-art intro shown at the top of README.md.

    python examples/build_intro_gif.py [--out docs/media/intro.gif]

Art direction follows the `pixel-arcade` grammar of the ak:motion-video style catalog: a fixed 16-colour
palette, whole-pixel positions, stepped (not eased) motion, a HUD with a score that ticks on the beat,
LEVEL cards, pixel-dissolve and iris transitions. The sprites are the project's own redrawn masters
(tests/fixtures/masters) rendered at 12 px and thresholded, so the GIF shows the real icon set.
The GIF is silent and deterministic: the same inputs give the same bytes.
"""
from __future__ import annotations

import argparse
import random
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "industrial-icon-designer" / "scripts"))
from common import recolor_svg, render_svg  # noqa: E402

ART_W, ART_H, SCALE, FPS_MS = 160, 90, 5, 80
CARD = 8  # frames of the LEVEL card at the start of each level
CACHE_DIR = Path(tempfile.gettempdir()) / "industrial-icon-designer-intro"

# Sweetie 16: the fixed palette (no gradients, no blends)
HEX = ["1a1c2c", "5d275d", "b13e53", "ef7d57", "ffcd75", "a7f070", "38b764", "257179",
       "29366f", "3b5dc9", "41a6f6", "73eff7", "f4f4f4", "94b0c2", "566c86", "333c57"]
RGB = [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in HEX]
BG, PURPLE, RED, ORANGE, YELLOW, LIME, GREEN, TEAL, NAVY, BLUE, SKY, CYAN, INK, MUTE, SLATE, DARK = RGB

PAL_IMG = Image.new("P", (1, 1))
PAL_IMG.putpalette([c for rgb in RGB for c in rgb] + [0] * (768 - 48))

# ----------------------------------------------------------------------------------------------- font
GLYPHS = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000", "/": "00001 00010 00010 00100 01000 01000 10000",
    ".": "00000 00000 00000 00000 00000 01100 01100", "-": "00000 00000 00000 11111 00000 00000 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000", "!": "00100 00100 00100 00100 00100 00000 00100",
    ":": "00000 01100 01100 00000 01100 01100 00000", ">": "10000 01000 00100 00010 00100 01000 10000",
}
FONT = {ch: [[c == "1" for c in row] for row in rows.split()] for ch, rows in GLYPHS.items()}
HEART = ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"]
CHECK = ["0000001", "0000011", "1000110", "1101100", "0111000", "0010000"]


def text_width(s: str, scale: int = 1) -> int:
    return len(s) * 6 * scale - scale


def text(img: Image.Image, x: int, y: int, s: str, color, scale: int = 1, shadow=None) -> None:
    d = ImageDraw.Draw(img)
    for pass_color, dx, dy in ([(shadow, scale, scale)] if shadow else []) + [(color, 0, 0)]:
        cx = x
        for ch in s:
            for ry, row in enumerate(FONT.get(ch, FONT[" "])):
                for rx, on in enumerate(row):
                    if on:
                        d.rectangle([cx + dx + rx * scale, y + dy + ry * scale,
                                     cx + dx + (rx + 1) * scale - 1, y + dy + (ry + 1) * scale - 1], fill=pass_color)
            cx += 6 * scale


def ctext(img, y, s, color, scale=1, shadow=None, dx=0) -> None:
    text(img, (ART_W - text_width(s, scale)) // 2 + dx, y, s, color, scale, shadow)


def sprite(img: Image.Image, x: int, y: int, rows: list[str], color) -> None:
    d = ImageDraw.Draw(img)
    for ry, row in enumerate(rows):
        for rx, c in enumerate(row):
            if c == "1":
                d.point((x + rx, y + ry), fill=color)


# --------------------------------------------------------------------------------------------- sprites
MASTERS = ["add", "alarm-list", "device-connect", "network", "open-folder", "pump", "save", "settings",
           "trend-chart", "valve"]


def icon_mask(name: str, size: int = 12) -> Image.Image:
    """A real master rendered at `size` px and thresholded to a 1-bit pixel sprite mask."""
    svg = (ROOT / "tests" / "fixtures" / "masters" / f"{name}.svg").read_text()
    out = CACHE_DIR / f"{name}-{size}.png"
    render_svg(recolor_svg(svg, "#ffffff").encode(), out, size)
    alpha = Image.open(out).convert("RGBA").getchannel("A")
    return alpha.point(lambda v: 255 if v >= 96 else 0)


def logo_sprite(size: int = 24) -> Image.Image:
    out = CACHE_DIR / f"logo-{size}.png"
    render_svg((ROOT / "logos" / "export" / "logo.svg").read_bytes(), out, size)
    flat = Image.new("RGBA", (size, size), RGB[0] + (255,))
    flat.alpha_composite(Image.open(out).convert("RGBA"))
    return flat.convert("RGB").quantize(palette=PAL_IMG, dither=Image.Dither.NONE).convert("RGB")


def dilate(mask: Image.Image) -> Image.Image:
    from PIL import ImageFilter
    return mask.filter(ImageFilter.MaxFilter(3))


def paste_mask(img: Image.Image, mask: Image.Image, x: int, y: int, color) -> None:
    img.paste(color, (x, y), mask)


def popped(mask: Image.Image, step: int) -> Image.Image | None:
    """Power-up pop in whole steps: nothing, 60 %, 125 %, 100 %."""
    factor = [0.0, 0.6, 1.25, 1.0][min(step, 3)]
    if factor == 0:
        return None
    n = max(2, round(mask.width * factor))
    return mask.resize((n, n), Image.NEAREST)


# ----------------------------------------------------------------------------------------------- frames
CACHE: dict = {}


def masks(kind: str):
    if kind not in CACHE:
        rnd = random.Random(11)
        if kind == "clean":
            CACHE[kind] = [icon_mask(n, 12) for n in MASTERS]
        else:  # mismatched weights, sizes and colours: the "before"
            sizes = [12, 14, 12, 11, 13, 12, 12, 14, 12, 13]
            colours = [RED, ORANGE, TEAL, GREEN, PURPLE, YELLOW, SKY, LIME, RED, ORANGE]
            out = []
            for i, n in enumerate(MASTERS):
                m = icon_mask(n, sizes[i])
                out.append((dilate(m) if i in (3, 6, 9) else m, colours[i], rnd.choice([-1, 0, 1]), rnd.choice([-1, 0, 1])))
            CACHE[kind] = out
    return CACHE[kind]


def base(frame: int, ground: bool = True) -> Image.Image:
    img = Image.new("RGB", (ART_W, ART_H), BG)
    d = ImageDraw.Draw(img)
    rnd = random.Random(5)
    for i in range(26):  # twinkling stars: each toggles on its own beat
        sx = rnd.choice([rnd.randrange(2, 9), rnd.randrange(ART_W - 9, ART_W - 2)])  # margins only: never behind text
        sy = rnd.randrange(12, 76)
        if (frame // 3 + i) % 4:
            d.point((sx, sy), fill=MUTE if i % 3 else SLATE)
    if ground:
        for gx in range(0, ART_W, 8):  # brick strip scrolling one art pixel every 3 frames
            off = (frame // 3) % 8
            d.rectangle([gx - off, ART_H - 8, gx - off + 6, ART_H - 1], fill=DARK)
            d.rectangle([gx - off + 7, ART_H - 8, gx - off + 7, ART_H - 1], fill=NAVY)
    return img


def hud(img: Image.Image, frame: int, level: int) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, ART_W - 1, 9], fill=BG)
    d.line([(0, 10), (ART_W - 1, 10)], fill=SLATE)
    text(img, 4, 2, f"SCORE {(frame // 6) * 100:06d}", INK)
    text(img, 92, 2, f"LV {level}", YELLOW)
    for i in range(3):
        sprite(img, 124 + i * 9, 2, HEART, RED)


def card(frame: int, local: int, level: int, title: str, color) -> Image.Image:
    img = base(frame, ground=False)
    d = ImageDraw.Draw(img)
    d.rectangle([20, 26, ART_W - 21, 64], outline=INK, width=2, fill=BG)
    ctext(img, 32, f"LEVEL {level}", color, 2, shadow=SLATE)
    ctext(img, 52, title, INK)
    return img


def scene_title(f: int, local: int) -> Image.Image:
    img = base(f)
    logo = logo_sprite(28)
    step = min(local // 2, 3)
    factor = [0, 0.6, 1.25, 1.0][step]
    if factor:
        n = max(4, round(28 * factor))
        sprite_img = logo.resize((n, n), Image.NEAREST)
        img.paste(sprite_img, ((ART_W - n) // 2, 6 + (28 - n) // 2))
    drop = [-30, -18, -8, -2, 0][min(max(local - 6, 0), 4)] if local >= 6 else -40
    shake = [2, -2, 1, 0][local - 10] if 10 <= local < 14 else 0
    if local >= 6:
        ctext(img, 39 + drop, "INDUSTRIAL", INK, 2, shadow=SLATE, dx=shake)
        ctext(img, 55 + drop, "ICON DESIGNER", YELLOW, 2, shadow=SLATE, dx=shake)
    if local >= 14 and (local // 3) % 2 == 0:
        ctext(img, 73, "PRESS START", INK)
    return img


def grid_pos(i: int) -> tuple[int, int]:
    return 31 + (i % 5) * 20, 32 + (i // 5) * 20


def scene_inventory(f: int, local: int) -> Image.Image:
    if local < CARD:
        return card(f, local, 1, "INVENTORY", RED)
    t = local - CARD
    img = base(f)
    ctext(img, 16, "OLD ICON SET", MUTE)
    for i, (mask, colour, jx, jy) in enumerate(masks("messy")):
        step = min(max(t - i, 0), 3)
        m = popped(mask, step)
        if m is not None:
            x, y = grid_pos(i)
            paste_mask(img, m, x + (14 - m.width) // 2 + jx, y + (14 - m.height) // 2 + jy, colour)
    if t >= 14 and (t // 3) % 2 == 0:
        ctext(img, 74, "10 ICONS  10 STYLES", RED)
    hud(img, f, 1)
    return img


def scene_redraw(f: int, local: int) -> Image.Image:
    if local < CARD:
        return card(f, local, 2, "REDRAW", GREEN)
    t = local - CARD
    img = base(f)
    ctext(img, 16, "ONE STYLE" if t >= 14 else "REDRAW", LIME if t >= 14 else MUTE)
    for i, ((mess, colour, jx, jy), clean) in enumerate(zip(masks("messy"), masks("clean"))):
        x, y = grid_pos(i)
        start = 2 + i
        if t < start:
            paste_mask(img, mess, x + (14 - mess.width) // 2 + jx, y + (14 - mess.height) // 2 + jy, colour)
        else:
            m = popped(clean, min(t - start + 1, 3))
            paste_mask(img, m, x + (14 - m.width) // 2, y + (14 - m.height) // 2, INK)
    if t >= 14:
        ctext(img, 72, "24 GRID  1.5 STROKE", MUTE)
        sprite(img, 27, 15, CHECK, GREEN)
    hud(img, f, 2)
    return img


def scene_export(f: int, local: int) -> Image.Image:
    if local < CARD:
        return card(f, local, 3, "EXPORT", SKY)
    t = local - CARD
    img = base(f)
    d = ImageDraw.Draw(img)
    pump = icon_mask("pump", 24)  # rendered at its own size, not stretched from 12 px
    for k, (label, bg, fg) in enumerate((("LIGHT", INK, DARK), ("DARK", DARK, INK))):
        x = 12 + k * 40
        d.rectangle([x, 22, x + 33, 55], fill=bg, outline=MUTE if k else SLATE, width=1)
        pm = popped(pump, min(max(t - 2 * k, 0), 3))
        if pm is not None:
            paste_mask(img, pm, x + (34 - pm.width) // 2, 25 + (30 - pm.height) // 2, fg)
        text(img, x + (34 - text_width(label)) // 2, 59, label, INK)
    png = min(160, max(0, t - 2) * 16)
    svg = 10 if t >= 8 else 0
    text(img, 98, 24, "PNG", SKY, 1)
    text(img, 98, 34, f"{png:03d}", INK, 2, shadow=SLATE)
    text(img, 98, 54, "SVG", LIME, 1)
    text(img, 98, 64, f"{svg:02d}", INK, 2, shadow=SLATE)
    blocks = min(20, png // 8)
    for b in range(20):
        d.rectangle([12 + b * 4, 74, 12 + b * 4 + 2, 80], fill=GREEN if b < blocks else DARK)
    hud(img, f, 3)
    return img


def scene_verify(f: int, local: int) -> Image.Image:
    if local < CARD:
        return card(f, local, 4, "VERIFY", YELLOW)
    t = local - CARD
    img = base(f)
    rows = [("183 TESTS PASS", GREEN, CHECK), ("HASH-BOUND APPROVAL", GREEN, CHECK),
            ("REAL APP TEST NOT YET", YELLOW, None)]
    for i, (label, colour, mark) in enumerate(rows):
        if t >= 2 + i * 4:
            y = 22 + i * 12
            if mark:
                sprite(img, 12, y, mark, colour)
            else:
                text(img, 14, y, "!", colour)
            text(img, 26, y, label, INK)
    if t >= 15 and (t // 2) % 2 == 0:
        ctext(img, 62, "ASSETS READY", LIME, 2, shadow=SLATE)
    hud(img, f, 4)
    return img


def scene_cta(f: int, local: int) -> Image.Image:
    img = base(f)
    logo = logo_sprite(24)
    img.paste(logo, ((ART_W - 24) // 2, 14))
    if local >= 4:
        ctext(img, 44, "CLAUDE CODE SKILL", YELLOW, 1)
    if local >= 8:
        ctext(img, 56, "/INDUSTRIAL-ICON-DESIGNER", INK, 1)
    if local >= 14:
        ctext(img, 70, "MIT", MUTE, 1)
        sprite(img, ART_W // 2 - 20, 69, HEART, RED)
        sprite(img, ART_W // 2 + 14, 69, HEART, RED)
    return img


SCENES = [("title", 20, scene_title), ("inventory", 32, scene_inventory), ("redraw", 32, scene_redraw),
          ("export", 32, scene_export), ("verify", 32, scene_verify), ("cta", 28, scene_cta)]
DISSOLVE = [3, 6, 12]  # pixel-dissolve block sizes (art px) closing a scene; reversed when opening the next


def mosaic(img: Image.Image, block: int) -> Image.Image:
    small = img.resize((max(1, ART_W // block), max(1, ART_H // block)), Image.NEAREST)
    return small.resize((ART_W, ART_H), Image.NEAREST)


def iris(img: Image.Image, step: int, closing: bool) -> Image.Image:
    """Level-clear iris: a circle closes on the logo in six steps (or opens again)."""
    radius = [88, 70, 52, 36, 20, 6][step if closing else 5 - step]
    mask = Image.new("L", (ART_W, ART_H), 0)
    ImageDraw.Draw(mask).ellipse([ART_W // 2 - radius, ART_H // 2 - radius, ART_W // 2 + radius, ART_H // 2 + radius],
                                 fill=255)
    out = Image.new("RGB", (ART_W, ART_H), BG)
    out.paste(img, (0, 0), mask)
    return out


def build_frames() -> list[Image.Image]:
    frames, g = [], 0
    for si, (name, length, fn) in enumerate(SCENES):
        for local in range(length):
            img = fn(g, local)
            if si < len(SCENES) - 1 and local >= length - 3:
                step = local - (length - 3)
                if SCENES[si + 1][0] == "cta":
                    img = iris(img, [1, 3, 5][step], closing=True)
                else:
                    img = mosaic(img, DISSOLVE[step])
            if si > 0 and local < 3:
                if name == "cta":
                    img = iris(img, [1, 3, 5][local], closing=False)
                else:
                    img = mosaic(img, DISSOLVE[2 - local])
            frames.append(img)
            g += 1
    return frames


def to_gif(frames: list[Image.Image], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    big = [f.resize((ART_W * SCALE, ART_H * SCALE), Image.NEAREST).quantize(palette=PAL_IMG, dither=Image.Dither.NONE)
           for f in frames]
    big[0].save(out, save_all=True, append_images=big[1:], duration=FPS_MS, loop=0, optimize=True, disposal=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "docs" / "media" / "intro.gif"))
    ap.add_argument("--contact-sheet", help="also write a PNG contact sheet of selected frames (for review)")
    args = ap.parse_args()
    frames = build_frames()
    to_gif(frames, Path(args.out))
    if args.contact_sheet:
        picks = list(range(0, len(frames), len(frames) // 16))[:16]
        sheet = Image.new("RGB", (ART_W * 4, ART_H * 4))
        for n, i in enumerate(picks):
            sheet.paste(frames[i], ((n % 4) * ART_W, (n // 4) * ART_H))
        sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(args.contact_sheet)
    size = Path(args.out).stat().st_size
    print(f"{len(frames)} frames, {len(frames) * FPS_MS / 1000:.1f} s, {size / 1024:.0f} KiB -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
