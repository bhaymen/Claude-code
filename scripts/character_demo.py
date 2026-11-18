"""Render a short silent test clip of Byte (9:16, 30 fps) to check the animation feel.

The mouth track is hand-made here; in the pipeline it comes from Rhubarb Lip Sync
run on the TTS audio. Usage:
    PYTHONPATH=src python3 scripts/character_demo.py docs/character/byte_demo.mp4
"""

from __future__ import annotations

import random
import subprocess
import sys

import cairosvg

from autopilot.character.animator import Cue, MouthKey, Timeline
from autopilot.character.rig import render_svg

W, H, FPS = 1080, 1920, 30
CHAR_W = 1000  # character render width in px
BG = "#F3EFE6"


def fake_talk(start: float, end: float, seed: int) -> list[MouthKey]:
    """Plausible speech-like mouth sequence (stand-in for Rhubarb output)."""
    rng = random.Random(seed)
    keys, t = [], start
    shapes = ["B", "C", "D", "E", "F", "B", "C", "G", "H", "A"]
    while t < end:
        keys.append(MouthKey(t, rng.choice(shapes)))
        t += rng.uniform(0.07, 0.16)
        if rng.random() < 0.12:  # word gap
            keys.append(MouthKey(t, "A"))
            t += 0.12
    keys.append(MouthKey(end, "X"))
    return keys


def main(out: str) -> None:
    duration = 9.0
    tl = Timeline(
        duration,
        cues=[
            Cue(0.0, "happy", "wave"),
            Cue(1.6, "neutral", "explain"),
            Cue(3.4, "thinking", "thinking"),
            Cue(4.8, "surprised", "point_up"),
            Cue(6.0, "excited", "excited"),
            Cue(7.4, "confident", "point_right"),
        ],
        mouth=fake_talk(0.2, 1.4, 1) + fake_talk(1.7, 3.2, 2) + fake_talk(5.0, 5.8, 3) + fake_talk(6.1, 8.6, 4),
        emphasis=[4.8, 6.0],
    )
    # paste the character onto a 9:16 canvas with the background
    x_off = (W - CHAR_W) // 2
    y_off = H - int(CHAR_W * 1.1) - 260
    ff = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", out,
        ],
        stdin=subprocess.PIPE,
    )
    from PIL import Image
    import io

    bg = Image.new("RGBA", (W, H), BG)
    n = int(duration * FPS)
    for i in range(n):
        st = tl.state_at(i / FPS)
        png = cairosvg.svg2png(bytestring=render_svg(st).encode(), output_width=CHAR_W)
        frame = bg.copy()
        char = Image.open(io.BytesIO(png)).convert("RGBA")
        frame.alpha_composite(char, (x_off, y_off))
        ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    ff.wait()
    print("wrote", out, n, "frames")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/character/byte_demo.mp4")
