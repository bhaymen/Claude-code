"""9:16 scene compositor plus Byte's intro, outro and a movement showreel.

A scene frame is one SVG (1080x1920): background, Byte (nested at any scale),
particles (sparkles, confetti, hearts), and sticker-style text. Frames are
rasterised with cairosvg and piped into FFmpeg together with a synthesized
sound-effects track.
"""

from __future__ import annotations

import io
import math
import random
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cairosvg
from PIL import Image

from ..audio import sfx
from . import wardrobe
from .animator import Action, Cue, Timeline
from .rig import State, character_group
from .style import PALETTE, VIEWBOX, f, star

W, H, FPS = 1080, 1920, 30
CHAR_SCALE = 0.95
CHAR_X = (W - VIEWBOX[0] * CHAR_SCALE) / 2
CHAR_Y = H - VIEWBOX[1] * CHAR_SCALE - 230
FONT = "DejaVu Sans, sans-serif"

GLYPHS = ("{ }", "</>", ";", "()", "[ ]", "#", "=>", "01")


def _ease_out_back(x: float) -> float:
    x = max(0.0, min(1.0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# -------------------------------------------------------------- layers -------
def background(t: float, seed: int = 1) -> str:
    rng = random.Random(seed)
    out = [
        f'<rect width="{W}" height="{H}" fill="{PALETTE["bg"]}"/>',
        f'<circle cx="{W / 2}" cy="{CHAR_Y + 560 * CHAR_SCALE}" r="500" fill="{PALETTE["bg_circle"]}"/>',
    ]
    for _ in range(14):  # faint floating code glyphs, slowly drifting up
        x, y0 = rng.uniform(40, W - 120), rng.uniform(0, H)
        speed, size = rng.uniform(15, 35), rng.uniform(40, 80)
        y = (y0 - speed * t) % (H + 100) - 50
        out.append(
            f'<text x="{f(x)}" y="{f(y)}" font-family="DejaVu Sans Mono, monospace" font-weight="bold" '
            f'font-size="{f(size)}" fill="#F3C9A0" opacity="0.55">{rng.choice(GLYPHS).replace("<", "&lt;").replace(">", "&gt;")}</text>'
        )
    out.append(f'<ellipse cx="{W / 2}" cy="{CHAR_Y + 1040 * CHAR_SCALE}" rx="380" ry="34" fill="#000000" opacity="0.06"/>')
    return "".join(out)


def character(s: State, extra: str = "") -> str:
    vw, vh = VIEWBOX
    return (
        f'<svg x="{f(CHAR_X)}" y="{f(CHAR_Y)}" width="{f(vw * CHAR_SCALE)}" height="{f(vh * CHAR_SCALE)}" '
        f'viewBox="0 0 {vw} {vh}" overflow="visible">{character_group(s)}{extra}</svg>'
    )


def to_scene(x: float, y: float) -> tuple[float, float]:
    """Character coordinates -> scene coordinates."""
    return CHAR_X + x * CHAR_SCALE, CHAR_Y + y * CHAR_SCALE


_FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _advance(text: str, size: float) -> list[float]:
    """Per-character advance widths for the bold sans font (falls back to an estimate)."""
    try:
        from PIL import ImageFont

        font = ImageFont.truetype(_FONT_FILE, int(size))
        return [font.getlength(ch) for ch in text]
    except OSError:
        return [size * 0.62] * len(text)


def _glyph(ch: str, size: float, fill: str, stroke: str) -> str:
    safe = ch.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    common = f'x="0" y="0" font-family="{FONT}" font-weight="bold" font-size="{size}" text-anchor="middle"'
    return (
        f'<text {common} fill="{stroke}" stroke="{stroke}" stroke-width="{size * 0.32:.1f}" stroke-linejoin="round">{safe}</text>'
        f"<text {common} fill=\"{fill}\">{safe}</text>"
    )


def sticker_text(
    text: str,
    x: float,
    y: float,
    size: float,
    progress: float = 1.0,
    fill: str = "#FFFFFF",
    stroke: str | None = None,
    stagger: float = 0.06,
    letter_dur: float = 0.35,
) -> str:
    """Sticker-style text whose letters pop in one after another (branded overshoot).

    ``progress`` is seconds since the text started appearing (>= total time = fully shown).
    """
    stroke = stroke or PALETTE["outline"]
    widths = _advance(text, size)
    total = sum(widths)
    max_w = W - 120  # keep clear of the frame edges (and the outline stroke)
    if total > max_w:  # auto-fit long titles
        size *= max_w / total
        widths = [w * max_w / total for w in widths]
        total = max_w
    cx = x - total / 2
    out = []
    for i, (ch, w) in enumerate(zip(text, widths)):
        k = _ease_out_back((progress - i * stagger) / letter_dur)
        gx = cx + w / 2
        cx += w
        if ch == " " or k <= 0.01:
            continue
        lift = (1 - min(1.0, k)) * size * 0.5
        out.append(f'<g transform="translate({f(gx)} {f(y + lift)}) scale({k:.3f})">{_glyph(ch, size, fill, stroke)}</g>')
    return "".join(out)


@dataclass
class Burst:
    """Particles that spring out of a point and fade."""

    t0: float
    x: float
    y: float
    kind: str = "sparkle"  # sparkle | confetti | heart
    n: int = 10
    seed: int = 0
    dur: float = 0.9
    parts: list = field(default_factory=list)

    def __post_init__(self) -> None:
        rng = random.Random(self.seed)
        colours = [PALETTE["yellow"], PALETTE["mint"], PALETTE["pink"], "#FFFFFF", PALETTE["red"]]
        for _ in range(self.n):
            a = rng.uniform(0, 2 * math.pi)
            sp = rng.uniform(220, 520)
            self.parts.append((math.cos(a) * sp, math.sin(a) * sp - 200, rng.choice(colours), rng.uniform(0.6, 1.2), rng.uniform(0, 360)))

    def svg(self, t: float) -> str:
        p = (t - self.t0) / self.dur
        if not 0 <= p <= 1:
            return ""
        el = t - self.t0
        out = []
        for vx, vy, col, sz, rot in self.parts:
            x = self.x + vx * el
            y = self.y + vy * el + 600 * el * el * (1.0 if self.kind == "confetti" else 0.4)
            op = 1 - p**2
            if self.kind == "sparkle":
                out.append(f'<g opacity="{op:.2f}">{star(x, y, 26 * sz * (1 - 0.4 * p), col)}</g>')
            elif self.kind == "heart":
                s = 1.6 * sz
                out.append(
                    f'<path transform="translate({f(x)} {f(y)}) scale({s:.2f})" d="M 0 6 c -10 -14 -32 -4 -20 12 l 20 18 l 20 -18 c 12 -16 -10 -26 -20 -12 Z" '
                    f'fill="{PALETTE["pink"]}" stroke="{PALETTE["outline"]}" stroke-width="4" opacity="{op:.2f}"/>'
                )
            else:
                out.append(
                    f'<rect x="{f(x - 9)}" y="{f(y - 5)}" width="18" height="10" rx="3" fill="{col}" '
                    f'transform="rotate({f(rot + 600 * el)} {f(x)} {f(y)})" opacity="{op:.2f}"/>'
                )
        return "".join(out)


# -------------------------------------------------------------- render -------
def render_clip(
    out: str | Path,
    duration: float,
    frame_svg: Callable[[float], str],
    sound_events: list[tuple[float, str, float]] | None = None,
) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "sfx.wav"
        sfx.write_wav(wav, sfx.mix(sound_events or [], duration))
        ff = subprocess.Popen(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                "-i", str(wav),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", str(out),
            ],
            stdin=subprocess.PIPE,
        )
        for i in range(int(duration * FPS)):
            t = i / FPS
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{frame_svg(t)}</svg>'
            png = cairosvg.svg2png(bytestring=svg.encode())
            ff.stdin.write(Image.open(io.BytesIO(png)).convert("RGB").tobytes())
        ff.stdin.close()
        ff.wait()
    return out


def still(out: str | Path, t: float, frame_svg: Callable[[float], str]) -> Path:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{frame_svg(t)}</svg>'
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out))
    return Path(out)


# --------------------------------------------------------------- clips -------
TITLE = "BYTE-SIZED TECH"


def intro(look: State | None = None, title: str = TITLE):
    """~1.6 s: Byte pops up from below, lands with a squash, sparkles, waves; title pops in."""
    duration = 1.6
    base = look or State(outfit="tshirt", hat=None)
    tl = Timeline(
        duration,
        cues=[Cue(0.0, "excited", "paws"), Cue(0.55, "happy", "paws")],
        actions=[Action(0.0, "pop_in", 0.6), Action(0.6, "wave", 1.0)],
        base=base,
    )
    hx, hy = to_scene(465, 300)
    bursts = [Burst(0.45, hx, hy, "sparkle", 12, seed=1), Burst(0.5, W / 2, 330, "confetti", 26, seed=2, dur=1.1)]

    def frame(t: float) -> str:
        return (
            background(t)
            + character(tl.state_at(t))
            + "".join(b.svg(t) for b in bursts)
            + sticker_text(title, W / 2, 330, 104, t - 0.5, fill=PALETTE["yellow"], stagger=0.045)
        )

    events = [(0.0, "whoosh", 0.8), (0.42, "pop", 1.0), (0.45, "jingle", 0.9), (0.5, "sparkle", 0.6), (0.62, "squeak", 0.5)]
    return duration, frame, events


def outro(look: State | None = None, line1: str = "Follow for more!", line2: str = "new byte every day"):
    """~3 s: wave + text, an acorn drops into Byte's paws (boing!), happy hop with hearts, wink."""
    duration = 3.0
    base = look or State(outfit="tshirt")
    tl = Timeline(
        duration,
        cues=[
            Cue(0.0, "happy", "paws"),
            Cue(1.35, "surprised", "hold", prop="acorn"),
            Cue(1.75, "happy"),
            Cue(2.4, "wink"),
        ],
        actions=[Action(0.0, "wave", 1.1), Action(1.85, "hop", 0.55), Action(2.4, "nod", 0.5)],
        base=base,
    )
    hx, hy = to_scene(465, 330)

    def falling_acorn(t: float, s: State) -> str:
        if not 0.95 <= t < 1.35:
            return ""
        p = (t - 0.95) / 0.4
        y = -250 + (720 + s.bob + 250) * p * p
        under, _ = wardrobe.prop("acorn", 465, y)
        return f'<g transform="rotate({f(200 * (1 - p))} 465 {f(y)})">{under}</g>'

    bursts = [Burst(2.0, hx, hy, "heart", 9, seed=4, dur=1.0), Burst(1.36, hx, hy - 60, "sparkle", 8, seed=5, dur=0.6)]

    def frame(t: float) -> str:
        s = tl.state_at(t)
        return (
            background(t)
            + character(s, falling_acorn(t, s))
            + "".join(b.svg(t) for b in bursts)
            + sticker_text(line1, W / 2, 300, 96, t - 0.15, fill="#FFFFFF", stagger=0.04)
            + sticker_text(line2, W / 2, 410, 58, t - 0.75, fill=PALETTE["mint"], stagger=0.025)
        )

    events = [
        (0.1, "outro_jingle", 0.8), (0.15, "pop", 0.8), (0.45, "pop", 0.6),
        (0.95, "whoosh", 0.6), (1.35, "boing", 0.9), (1.4, "squeak", 0.5),
        (1.85, "sparkle", 0.6), (2.4, "pop", 0.5),
    ]
    return duration, frame, events


def showreel():
    """~13 s tour of looks and movements with labels."""
    segments = [
        # (label, duration, base look, cues, actions, sound events relative to segment start)
        ("sip coffee", 2.2, State(outfit="hoodie", hat="headphones", prop="coffee", pose="hold"),
         [Cue(0, "cozy")], [Action(0.4, "sip", 1.4)], [(0.8, "sip", 0.7)]),
        ("snack time", 2.2, State(outfit="sweater", hat="beanie", prop="cookie", pose="hold"),
         [Cue(0, "happy")], [Action(0.3, "munch", 1.6)], [(0.6, "crunch", 0.8), (1.1, "crunch", 0.7)]),
        ("coding", 2.2, State(outfit="tshirt_green", hat="cap", glasses=True, prop="laptop", pose="hold"),
         [Cue(0, "thinking"), Cue(1.4, "confident")], [Action(0.2, "type", 1.6)], [(0.2 + i * 0.09, "tap", 0.5) for i in range(17)]),
        ("drawing", 2.0, State(outfit="tshirt", prop="sketchbook", pose="hold"),
         [Cue(0, "neutral"), Cue(1.2, "happy")], [Action(1.2, "nod", 0.6)], [(1.2, "sparkle", 0.4)]),
        ("dance!", 2.2, State(outfit="hoodie", hat="party"),
         [Cue(0, "happy", "excited")], [Action(0.1, "dance", 2.0)], [(0.1, "jingle", 0.6)]),
        ("celebrate", 1.8, State(outfit="tshirt", hat="party"),
         [Cue(0, "excited")], [Action(0.2, "celebrate", 0.7), Action(0.95, "celebrate", 0.7)], [(0.25, "boing", 0.6), (1.0, "boing", 0.6)]),
    ]
    starts, t0 = [], 0.0
    for seg in segments:
        starts.append(t0)
        t0 += seg[1]
    duration = t0
    timelines = [Timeline(seg[1], cues=seg[3], actions=seg[4], base=seg[2], seed=i) for i, seg in enumerate(segments)]
    bursts = [Burst(starts[5] + 0.3, W / 2, 500, "confetti", 30, seed=9, dur=1.4)]

    def frame(t: float) -> str:
        i = max(j for j, s0 in enumerate(starts) if s0 <= t)
        lt = t - starts[i]
        return (
            background(t)
            + character(timelines[i].state_at(lt))
            + "".join(b.svg(t) for b in bursts)
            + sticker_text(segments[i][0], W / 2, 300, 92, lt, fill=PALETTE["yellow"], stagger=0.035)
        )

    events = [(starts[i] + 0.0, "pop", 0.6) for i in range(len(segments))]
    for i, seg in enumerate(segments):
        events += [(starts[i] + dt, name, g) for dt, name, g in seg[5]]
    return duration, frame, events
