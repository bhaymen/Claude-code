"""Render Byte's intro, outro, movement showreel, wardrobe sheet and SFX library.

Usage: PYTHONPATH=src python3 scripts/render_clips.py docs/character
"""

import io
import sys
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

from autopilot.audio import sfx
from autopilot.character import scenes
from autopilot.character.rig import render_svg, state_for


def wardrobe_sheet(out: Path) -> None:
    looks = [
        ("coffee + hoodie\n+ headphones", dict(prop="coffee", outfit="hoodie", hat="headphones"), "cozy"),
        ("cookie + sweater\n+ beanie", dict(prop="cookie", outfit="sweater", hat="beanie"), "happy"),
        ("laptop + green tee\n+ cap + glasses", dict(prop="laptop", outfit="tshirt_green", hat="cap", glasses=True), "confident"),
        ("sketchbook + tee\n+ party hat", dict(prop="sketchbook", outfit="tshirt", hat="party"), "excited"),
        ("acorn, no outfit", dict(prop="acorn", outfit="none"), "neutral"),
        ("Hello World tee", dict(outfit="tshirt", shirt_print="Hello World"), "wink"),
    ]
    cw = 420
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    sheet = Image.new("RGB", (cw * 3, 2 * (int(cw * 1.1) + 70)), (255, 246, 234))
    d = ImageDraw.Draw(sheet)
    for i, (label, kw, expr) in enumerate(looks):
        st = state_for(expr, "hold", background="scene", **kw)
        img = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=render_svg(st).encode(), output_width=cw)))
        x, y = (i % 3) * cw, (i // 3) * (int(cw * 1.1) + 70)
        sheet.paste(img, (x, y))
        d.multiline_text((x + cw / 2, y + int(cw * 1.1) + 8), label, fill=(74, 46, 32), font=font, anchor="ma", align="center")
    sheet.save(out)


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sfx.export_library(Path("assets/sfx"))
    wardrobe_sheet(out / "byte_wardrobe.png")
    for name, fn in (("byte_intro", scenes.intro), ("byte_outro", scenes.outro), ("byte_showreel", scenes.showreel)):
        duration, frame, events = fn()
        scenes.render_clip(out / f"{name}.mp4", duration, frame, events)
        print("rendered", name, f"{duration:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/character")
