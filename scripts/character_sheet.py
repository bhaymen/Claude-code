"""Render Byte's character sheet: expressions, poses and lip-sync mouth shapes.

Usage: PYTHONPATH=src python3 scripts/character_sheet.py docs/character
"""

from __future__ import annotations

import io
import sys
from dataclasses import replace
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

from autopilot.character.rig import EXPRESSIONS, MOUTHS, POSES, State, render_svg, state_for

BG = (246, 244, 239)
INK = (40, 30, 25)


def _png(state: State, width: int) -> Image.Image:
    data = cairosvg.svg2png(bytestring=render_svg(state).encode(), output_width=width)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grid(items: list[tuple[str, State]], cols: int, cell_w: int, title: str, crop_head: bool = False) -> Image.Image:
    face_box = (0.20, 0.16, 0.80, 0.66)
    cell_h = int(cell_w * ((face_box[3] - face_box[1]) * 1.1 / (face_box[2] - face_box[0])) if crop_head else cell_w * 1.1)
    rows = (len(items) + cols - 1) // cols
    head_h = 90
    sheet = Image.new("RGB", (cols * cell_w, head_h + rows * (cell_h + 46)), BG)
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 24), title, fill=INK, font=_font(40))
    for i, (label, st) in enumerate(items):
        img = _png(st, cell_w if not crop_head else int(cell_w * 1.5))
        if crop_head:  # zoom on the face
            w, h = img.size
            box = (int(w * face_box[0]), int(h * face_box[1]), int(w * face_box[2]), int(h * face_box[3]))
            img = img.crop(box).resize((cell_w, cell_h))
        x = (i % cols) * cell_w
        y = head_h + (i // cols) * (cell_h + 46)
        sheet.paste(img, (x, y), img)
        tw = draw.textlength(label, font=_font(28))
        draw.text((x + (cell_w - tw) / 2, y + cell_h + 6), label, fill=INK, font=_font(28))
    return sheet


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    hero = _png(state_for("happy", "wave"), 900)
    canvas = Image.new("RGB", (900, 990), BG)
    canvas.paste(hero, (0, 0), hero)
    canvas.save(out / "byte_hero.png")

    exprs = [(name, state_for(name, "idle")) for name in EXPRESSIONS]
    grid(exprs, 4, 360, "Byte: expressions", crop_head=True).save(out / "byte_expressions.png")

    poses = [(name, state_for("happy" if name in ("wave", "excited") else "neutral", name)) for name in POSES]
    grid(poses, 5, 320, "Byte: poses").save(out / "byte_poses.png")

    labels = {
        "X": "X rest", "A": "A  m b p", "B": "B  k s t", "C": "C  eh ae", "D": "D  aa",
        "E": "E  ao er", "F": "F  oo w", "G": "G  f v", "H": "H  l",
    }
    mouths = [(labels[m], replace(State(), mouth=m)) for m in MOUTHS]
    grid(mouths, 5, 300, "Byte: lip-sync mouth shapes", crop_head=True).save(out / "byte_mouths.png")
    print("wrote", sorted(p.name for p in out.glob("byte_*.png")))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/character")
