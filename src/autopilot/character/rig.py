"""Byte the squirrel: a parametric, code-drawn character rig.

Every frame is described by a :class:`State` and turned into an SVG string by
:func:`render_svg`. Nothing is a static image, so blinking, lip-sync, tail sway,
head tilt and pose changes are all continuous parameters that an animator can
interpolate.

Coordinate system: SVG viewBox ``0 0 1000 1100``; y grows downwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

# ---------------------------------------------------------------- palette ---
PALETTE = {
    "outline": "#3B2416",
    "fur": "#E8833A",
    "fur_shade": "#C9662A",
    "cream": "#FBE3C4",
    "ear_inner": "#F7B3A0",
    "blush": "#F48F8F",
    "eye": "#2A1A12",
    "eye_shine": "#FFFFFF",
    "glasses": "#2B3A67",
    "lens": "#CFE8FF",
    "hoodie": "#22A699",
    "hoodie_shade": "#178A7E",
    "hoodie_light": "#5CCDBE",
    "mouth": "#5A1E1E",
    "tongue": "#E86A6A",
    "teeth": "#FFFFFF",
    "nose": "#5A2E1E",
}

OUTLINE_W = 9
VIEWBOX = (1000, 1100)

# Rhubarb Lip Sync mouth set (Preston Blair): A-H plus X (rest).
MOUTHS = ("X", "A", "B", "C", "D", "E", "F", "G", "H")
EYE_STYLES = ("normal", "happy", "wide", "sparkle")
BROWS = ("neutral", "raised", "frown", "worried", "skeptical")


# -------------------------------------------------------------- arm poses ---
@dataclass(frozen=True)
class Arm:
    """Two-segment arm. Angles in degrees, measured from straight down.

    ``upper`` rotates the upper arm outward (90 = horizontal, 180 = straight up,
    negative = across the body). ``elbow`` is added to get the forearm direction.
    """

    upper: float = 20
    elbow: float = -40
    hand: str = "paw"  # paw | point | open
    front: bool = True  # drawn in front of the body/head


POSES: dict[str, tuple[Arm, Arm]] = {
    # (viewer-left arm, viewer-right arm)
    "idle": (Arm(18, -48), Arm(18, -48)),
    "wave": (Arm(18, -48), Arm(150, 25, "open")),
    "point_right": (Arm(18, -48), Arm(98, -4, "point")),
    "point_left": (Arm(98, -4, "point"), Arm(18, -48)),
    "point_up": (Arm(18, -48), Arm(165, 8, "point")),
    "thinking": (Arm(18, -48), Arm(150, 50, "paw")),
    "excited": (Arm(155, 20, "open"), Arm(155, 20, "open")),
    "shrug": (Arm(105, 65, "open"), Arm(105, 65, "open")),
    "explain": (Arm(18, -48), Arm(65, 45, "open")),
}

EXPRESSIONS: dict[str, dict] = {
    "neutral": dict(eye_style="normal", brows="neutral", mouth="X"),
    "happy": dict(eye_style="happy", brows="raised", mouth="C"),
    "surprised": dict(eye_style="wide", brows="raised", mouth="F"),
    "thinking": dict(eye_style="normal", brows="skeptical", mouth="A", look=(0.5, -0.6), eye_open=0.8),
    "confident": dict(eye_style="normal", brows="neutral", mouth="X", eye_open=0.75),
    "worried": dict(eye_style="normal", brows="worried", mouth="E"),
    "excited": dict(eye_style="sparkle", brows="raised", mouth="D"),
    "annoyed": dict(eye_style="normal", brows="frown", mouth="A", eye_open=0.6),
}


@dataclass(frozen=True)
class State:
    pose: str = "idle"
    eye_style: str = "normal"
    eye_open: float = 1.0  # 0 closed .. 1 open (blinks animate this)
    look: tuple[float, float] = (0.0, 0.0)  # pupil offset, each -1..1
    brows: str = "neutral"
    mouth: str = "X"
    head_tilt: float = 0.0  # degrees
    bob: float = 0.0  # vertical offset of the whole body, px
    squash: float = 1.0  # vertical scale for emphasis bounces
    tail_sway: float = 0.0  # degrees
    blush: float = 0.55  # opacity
    arms: tuple[Arm, Arm] | None = None  # overrides pose when set
    background: str | None = None  # e.g. "#FFFFFF"; None = transparent

    def with_expression(self, name: str) -> "State":
        return replace(self, **EXPRESSIONS[name])


# ---------------------------------------------------------------- helpers ---
def _f(x: float) -> str:
    return f"{x:.1f}"


def _outlined(path_d: str, fill: str, width: float = OUTLINE_W) -> str:
    return (
        f'<path d="{path_d}" fill="{fill}" stroke="{PALETTE["outline"]}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'
    )


def _dir(side: int, angle: float) -> tuple[float, float]:
    a = math.radians(angle)
    return side * math.sin(a), math.cos(a)


# ------------------------------------------------------------------- tail ---
def _bezier(p, t):
    """Point and tangent on a cubic Bezier given 4 control points."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p
    u = 1 - t
    x = u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3
    y = u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3
    dx = 3 * u * u * (x1 - x0) + 6 * u * t * (x2 - x1) + 3 * t * t * (x3 - x2)
    dy = 3 * u * u * (y1 - y0) + 6 * u * t * (y2 - y1) + 3 * t * t * (y3 - y2)
    n = math.hypot(dx, dy) or 1.0
    return x, y, dx / n, dy / n


def _smooth_closed(points) -> str:
    """Closed Catmull-Rom spline through points, as an SVG path."""
    n = len(points)
    d = [f"M {_f(points[0][0])} {_f(points[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C {_f(c1[0])} {_f(c1[1])}, {_f(c2[0])} {_f(c2[1])}, {_f(p2[0])} {_f(p2[1])}")
    return " ".join(d) + " Z"


# Tail centreline: from behind the hoodie, out to the right, up past the ear, curling in.
_TAIL_CURVE = ((560, 960), (830, 990), (900, 640), (790, 420))
_TAIL_TIP_CURL = ((790, 420), (730, 300), (640, 330), (690, 410))


def _tail_shape(scale: float, fluff: float, samples: int = 70) -> str:
    left, right = [], []
    for i in range(samples + 1):
        g = i / samples  # 0..1 along the whole tail
        if g < 0.78:
            x, y, tx, ty = _bezier(_TAIL_CURVE, g / 0.78)
        else:
            x, y, tx, ty = _bezier(_TAIL_TIP_CURL, (g - 0.78) / 0.22)
        nx, ny = -ty, tx
        width = (40 + 92 * math.sin(math.pi * min(1.0, g * 1.25)) ** 0.8) * scale
        width *= 1.0 - 0.55 * max(0.0, g - 0.78) / 0.22  # taper into the curl
        bump = fluff * abs(math.sin(g * math.pi * 11))
        left.append((x + nx * (width + bump), y + ny * (width + bump)))
        right.append((x - nx * (width + bump * 0.6), y - ny * (width + bump * 0.6)))
    return _smooth_closed(left + right[::-1])


def _tail(sway: float) -> str:
    body = _tail_shape(1.0, 16)
    stripe = _tail_shape(0.42, 8)
    o = PALETTE["outline"]
    return (
        f'<g transform="rotate({_f(sway)} 560 960)">'
        f'<path d="{body}" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="{OUTLINE_W}" stroke-linejoin="round"/>'
        f'<path d="{stripe}" fill="{PALETTE["fur_shade"]}" opacity="0.45"/>'
        "</g>"
    )


# ------------------------------------------------------------- body/hood ---
def _body() -> str:
    hoodie = "M 345 1015 C 335 870, 370 715, 500 700 C 630 715, 665 870, 655 1015 Q 500 1040 345 1015 Z"
    pocket = "M 420 905 Q 500 885 580 905 L 595 985 Q 500 1000 405 985 Z"
    logo = (
        f'<text x="500" y="852" font-family="DejaVu Sans Mono, monospace" font-size="62" '
        f'font-weight="bold" fill="#FFFFFF" text-anchor="middle">&lt;/&gt;</text>'
    )
    strings = (
        f'<path d="M 470 735 L 462 815" stroke="{PALETTE["hoodie_light"]}" stroke-width="9" stroke-linecap="round"/>'
        f'<path d="M 530 735 L 538 815" stroke="{PALETTE["hoodie_light"]}" stroke-width="9" stroke-linecap="round"/>'
        f'<circle cx="462" cy="822" r="9" fill="{PALETTE["hoodie_light"]}"/>'
        f'<circle cx="538" cy="822" r="9" fill="{PALETTE["hoodie_light"]}"/>'
    )
    feet = (
        _outlined("M 365 1025 a 78 40 0 1 0 156 0 a 78 40 0 1 0 -156 0 Z", PALETTE["fur"])
        + _outlined("M 479 1025 a 78 40 0 1 0 156 0 a 78 40 0 1 0 -156 0 Z", PALETTE["fur"])
    )
    hood = _outlined("M 335 700 Q 500 610 665 700 Q 660 760 500 765 Q 340 760 335 700 Z", PALETTE["hoodie_shade"])
    return (
        feet
        + _outlined(hoodie, PALETTE["hoodie"])
        + f'<path d="{pocket}" fill="{PALETTE["hoodie_shade"]}" opacity="0.6"/>'
        + hood
        + strings
        + logo
    )


# ------------------------------------------------------------------- arms ---
SHOULDERS = {-1: (395.0, 760.0), 1: (605.0, 760.0)}
UPPER_LEN, FORE_LEN, SLEEVE_W = 105.0, 95.0, 62.0


def _arm(side: int, arm: Arm) -> str:
    sx, sy = SHOULDERS[side]
    ux, uy = _dir(side, arm.upper)
    ex, ey = sx + ux * UPPER_LEN, sy + uy * UPPER_LEN
    fx, fy = _dir(side, arm.upper + arm.elbow)
    hx, hy = ex + fx * FORE_LEN, ey + fy * FORE_LEN
    o = PALETTE["outline"]
    sleeve = f"M {_f(sx)} {_f(sy)} L {_f(ex)} {_f(ey)} L {_f(hx)} {_f(hy)}"
    parts = [
        f'<path d="{sleeve}" fill="none" stroke="{o}" stroke-width="{SLEEVE_W + 2 * OUTLINE_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
        f'<path d="{sleeve}" fill="none" stroke="{PALETTE["hoodie"]}" stroke-width="{SLEEVE_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    # paw at the end of the sleeve
    px, py = hx + fx * 22, hy + fy * 22
    if arm.hand == "point":
        tip_x, tip_y = px + fx * 62, py + fy * 62
        parts.append(
            f'<path d="M {_f(px)} {_f(py)} L {_f(tip_x)} {_f(tip_y)}" stroke="{o}" '
            f'stroke-width="{26 + 2 * OUTLINE_W}" stroke-linecap="round"/>'
            f'<path d="M {_f(px)} {_f(py)} L {_f(tip_x)} {_f(tip_y)}" stroke="{PALETTE["fur"]}" '
            'stroke-width="26" stroke-linecap="round"/>'
        )
    r = 36 if arm.hand == "open" else 33
    parts.append(
        f'<circle cx="{_f(px)}" cy="{_f(py)}" r="{r}" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="{OUTLINE_W}"/>'
    )
    if arm.hand == "open":  # three little finger bumps pointing along the forearm
        nx, ny = -fy, fx
        for k in (-1, 0, 1):
            cx = px + fx * 30 + nx * k * 20
            cy = py + fy * 30 + ny * k * 20
            parts.append(
                f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="13" fill="{PALETTE["fur"]}" '
                f'stroke="{o}" stroke-width="{OUTLINE_W * 0.8:.1f}"/>'
            )
        parts.append(f'<circle cx="{_f(px)}" cy="{_f(py)}" r="{r - 5}" fill="{PALETTE["fur"]}"/>')
    # cuff
    cx, cy = hx - fx * 6, hy - fy * 6
    parts.append(
        f'<path d="M {_f(cx)} {_f(cy)} L {_f(hx)} {_f(hy)}" stroke="{PALETTE["hoodie_shade"]}" '
        f'stroke-width="{SLEEVE_W}" stroke-linecap="butt"/>'
    )
    return "".join(parts)


# ------------------------------------------------------------------- head ---
HEAD_PIVOT = (500.0, 700.0)
EYES = {-1: (412.0, 455.0), 1: (588.0, 455.0)}


def _head_silhouette() -> list[str]:
    """Fur shapes that share one outline (ears, cheek tufts, head)."""
    return [
        # ears
        "M 300 330 C 260 230, 270 140, 300 95 C 345 140, 390 220, 400 280 Z",
        "M 700 330 C 740 230, 730 140, 700 95 C 655 140, 610 220, 600 280 Z",
        # cheek tufts
        "M 290 520 L 238 548 L 290 562 L 248 600 L 320 598 Z",
        "M 710 520 L 762 548 L 710 562 L 752 600 L 680 598 Z",
        # head
        "M 500 225 C 670 225, 745 330, 745 455 C 745 595, 640 670, 500 670 "
        "C 360 670, 255 595, 255 455 C 255 330, 330 225, 500 225 Z",
    ]


def _eye(side: int, s: State) -> str:
    cx, cy = EYES[side]
    o = PALETTE["eye"]
    lx, ly = s.look
    style = s.eye_style
    openness = max(0.0, min(1.0, s.eye_open))
    if style == "happy" or openness < 0.12:
        # closed / happy: a curved line (^ for happy, u-ish for blink)
        bend = -26 if style == "happy" else 10
        return (
            f'<path d="M {_f(cx - 36)} {_f(cy + 6)} Q {_f(cx)} {_f(cy + 6 + bend)} {_f(cx + 36)} {_f(cy + 6)}" '
            f'fill="none" stroke="{o}" stroke-width="11" stroke-linecap="round"/>'
        )
    rx, ry = (40, 54) if style == "wide" else (36, 47)
    ry *= openness
    ex, ey = cx + lx * 8, cy + ly * 8
    out = [f'<ellipse cx="{_f(ex)}" cy="{_f(ey)}" rx="{rx}" ry="{_f(ry)}" fill="{o}"/>']
    if openness > 0.35:
        hs = 1.25 if style == "sparkle" else 1.0
        out.append(
            f'<circle cx="{_f(ex + 12)}" cy="{_f(ey - ry * 0.38)}" r="{_f(13 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
            f'<circle cx="{_f(ex - 13)}" cy="{_f(ey + ry * 0.35)}" r="{_f(6 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
        )
        if style == "sparkle":
            sx, sy = ex - 8, ey - ry * 0.05
            out.append(
                f'<path d="M {_f(sx)} {_f(sy - 11)} L {_f(sx + 3)} {_f(sy - 3)} L {_f(sx + 11)} {_f(sy)} '
                f'L {_f(sx + 3)} {_f(sy + 3)} L {_f(sx)} {_f(sy + 11)} L {_f(sx - 3)} {_f(sy + 3)} '
                f'L {_f(sx - 11)} {_f(sy)} L {_f(sx - 3)} {_f(sy - 3)} Z" fill="{PALETTE["eye_shine"]}"/>'
            )
    return "".join(out)


def _glasses() -> str:
    g = PALETTE["glasses"]
    out = []
    for side in (-1, 1):
        cx, cy = EYES[side]
        out.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="76" fill="{PALETTE["lens"]}" fill-opacity="0.10" '
            f'stroke="{g}" stroke-width="15"/>'
        )
        # lens glint
        out.append(
            f'<path d="M {_f(cx + 22)} {_f(cy - 52)} Q {_f(cx + 50)} {_f(cy - 40)} {_f(cx + 56)} {_f(cy - 14)}" '
            'fill="none" stroke="#FFFFFF" stroke-width="9" stroke-linecap="round" opacity="0.85"/>'
        )
    out.append(f'<path d="M 488 448 Q 500 432 512 448" fill="none" stroke="{g}" stroke-width="13" stroke-linecap="round"/>')
    out.append(f'<path d="M 336 440 L 262 425" stroke="{g}" stroke-width="13" stroke-linecap="round"/>')
    out.append(f'<path d="M 664 440 L 738 425" stroke="{g}" stroke-width="13" stroke-linecap="round"/>')
    return "".join(out)


_BROW_SHAPES = {
    # (left_outer_dy, left_inner_dy) relative offsets; right brow mirrors
    "neutral": (0, 0),
    "raised": (-22, -26),
    "frown": (-8, 18),
    "worried": (12, -18),
}


def _brows(kind: str) -> str:
    o = PALETTE["outline"]
    out = []
    for side in (-1, 1):
        cx = EYES[side][0]
        base_y = 352
        if kind == "skeptical":
            outer, inner = ((-24, -28) if side == 1 else (4, 4))
        else:
            outer, inner = _BROW_SHAPES[kind]
        x_outer, x_inner = cx + side * 40, cx - side * 34
        out.append(
            f'<path d="M {_f(x_outer)} {_f(base_y + outer)} Q {_f(cx)} {_f(base_y - 14 + (outer + inner) / 2)} '
            f'{_f(x_inner)} {_f(base_y + inner)}" fill="none" stroke="{o}" stroke-width="15" stroke-linecap="round"/>'
        )
    return "".join(out)


def _mouth(shape: str) -> str:
    o = PALETTE["outline"]
    m, t, w = PALETTE["mouth"], PALETTE["tongue"], PALETTE["teeth"]
    x, y = 500.0, 592.0

    def line(d: str, width: float = 9) -> str:
        return f'<path d="{d}" fill="none" stroke="{o}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'

    def opening(d: str, tongue: bool = True, teeth: bool = True) -> str:
        clip_id = f"mclip{shape}"
        parts = [f'<clipPath id="{clip_id}"><path d="{d}"/></clipPath>', f'<path d="{d}" fill="{m}"/>']
        inner = []
        if tongue:
            inner.append(f'<ellipse cx="{x}" cy="{y + 48}" rx="38" ry="24" fill="{t}"/>')
        if teeth:  # the squirrel's two buck teeth
            inner.append(f'<rect x="{x - 17}" y="{y - 30}" width="16" height="26" rx="4" fill="{w}"/>')
            inner.append(f'<rect x="{x + 1}" y="{y - 30}" width="16" height="26" rx="4" fill="{w}"/>')
        parts.append(f'<g clip-path="url(#{clip_id})">{"".join(inner)}</g>')
        parts.append(f'<path d="{d}" fill="none" stroke="{o}" stroke-width="9" stroke-linejoin="round"/>')
        return "".join(parts)

    cat_smile = f"M {x - 44} {y - 18} Q {x - 22} {y + 6} {x} {y - 14} Q {x + 22} {y + 6} {x + 44} {y - 18}"
    teeth_small = (
        f'<rect x="{x - 15}" y="{y - 14}" width="14" height="20" rx="4" fill="{w}" stroke="{o}" stroke-width="5"/>'
        f'<rect x="{x + 1}" y="{y - 14}" width="14" height="20" rx="4" fill="{w}" stroke="{o}" stroke-width="5"/>'
    )
    if shape == "X":  # rest: closed smile with buck teeth peeking
        return teeth_small + line(cat_smile)
    if shape == "A":  # M B P: lips pressed
        return line(f"M {x - 38} {y - 10} Q {x} {y + 2} {x + 38} {y - 10}")
    if shape == "B":  # K S T etc: slightly open, teeth visible
        return opening(f"M {x - 40} {y - 16} Q {x} {y - 22} {x + 40} {y - 16} Q {x} {y + 14} {x - 40} {y - 16} Z", tongue=False)
    if shape == "C":  # EH AE: open
        return opening(f"M {x - 46} {y - 18} Q {x} {y - 26} {x + 46} {y - 18} Q {x + 30} {y + 42} {x} {y + 44} Q {x - 30} {y + 42} {x - 46} {y - 18} Z")
    if shape == "D":  # AA: wide open
        return opening(f"M {x - 56} {y - 20} Q {x} {y - 30} {x + 56} {y - 20} Q {x + 46} {y + 58} {x} {y + 62} Q {x - 46} {y + 58} {x - 56} {y - 20} Z")
    if shape == "E":  # AO ER: rounded, slightly open
        return opening(f"M {x - 34} {y - 4} Q {x} {y - 28} {x + 34} {y - 4} Q {x + 30} {y + 40} {x} {y + 42} Q {x - 30} {y + 40} {x - 34} {y - 4} Z", teeth=False)
    if shape == "F":  # UW OW W: small "o"
        return opening(f"M {x - 20} {y + 8} a 20 24 0 1 0 40 0 a 20 24 0 1 0 -40 0 Z", teeth=False)
    if shape == "G":  # F V: teeth on lower lip
        return opening(f"M {x - 42} {y - 14} Q {x} {y - 20} {x + 42} {y - 14} Q {x} {y + 18} {x - 42} {y - 14} Z", tongue=False) + line(
            f"M {x - 30} {y + 8} Q {x} {y + 18} {x + 30} {y + 8}", 7
        )
    if shape == "H":  # L: open, tongue up behind teeth
        d = f"M {x - 46} {y - 18} Q {x} {y - 26} {x + 46} {y - 18} Q {x + 30} {y + 40} {x} {y + 42} Q {x - 30} {y + 40} {x - 46} {y - 18} Z"
        return opening(d) + f'<ellipse cx="{x}" cy="{y + 2}" rx="20" ry="12" fill="{t}"/>'
    raise ValueError(f"unknown mouth shape {shape!r}")


def _head(s: State) -> str:
    sil = _head_silhouette()
    o = PALETTE["outline"]
    parts = []
    # one shared outline: stroke every fur shape first, then fill on top
    for d in sil:
        parts.append(f'<path d="{d}" fill="{o}" stroke="{o}" stroke-width="{OUTLINE_W * 2}" stroke-linejoin="round"/>')
    for d in sil:
        parts.append(f'<path d="{d}" fill="{PALETTE["fur"]}"/>')
    # inner ears
    parts.append(f'<path d="M 312 300 C 290 230, 296 170, 307 140 C 335 175, 360 225, 368 270 Z" fill="{PALETTE["ear_inner"]}"/>')
    parts.append(f'<path d="M 688 300 C 710 230, 704 170, 693 140 C 665 175, 640 225, 632 270 Z" fill="{PALETTE["ear_inner"]}"/>')
    # forehead fur tuft
    parts.append(
        f'<path d="M 455 232 Q 480 180 500 226 Q 520 175 548 234" fill="{PALETTE["fur"]}" stroke="{o}" '
        f'stroke-width="{OUTLINE_W}" stroke-linejoin="round"/>'
    )
    parts.append(f'<path d="M 450 240 L 552 240 L 552 260 L 450 260 Z" fill="{PALETTE["fur"]}"/>')
    # muzzle + belly-coloured face patch
    parts.append(f'<ellipse cx="500" cy="578" rx="130" ry="86" fill="{PALETTE["cream"]}"/>')
    # blush
    for cx in (342, 658):
        parts.append(f'<ellipse cx="{cx}" cy="560" rx="40" ry="24" fill="{PALETTE["blush"]}" opacity="{s.blush:.2f}"/>')
    parts.append(_eye(-1, s))
    parts.append(_eye(1, s))
    parts.append(_glasses())
    parts.append(_brows(s.brows))
    # nose
    parts.append(
        f'<path d="M 476 526 Q 500 516 524 526 Q 520 548 500 553 Q 480 548 476 526 Z" fill="{PALETTE["nose"]}"/>'
        f'<ellipse cx="492" cy="528" rx="7" ry="4" fill="#FFFFFF" opacity="0.7"/>'
    )
    parts.append(_mouth(s.mouth))
    px, py = HEAD_PIVOT
    return f'<g transform="rotate({_f(s.head_tilt)} {_f(px)} {_f(py)})">{"".join(parts)}</g>'


# ----------------------------------------------------------------- render ---
def render_svg(s: State, size: tuple[int, int] | None = None) -> str:
    """Return a complete SVG document for one frame of the character."""
    if s.pose not in POSES and s.arms is None:
        raise ValueError(f"unknown pose {s.pose!r}")
    if s.eye_style not in EYE_STYLES:
        raise ValueError(f"unknown eye style {s.eye_style!r}")
    if s.brows not in BROWS:
        raise ValueError(f"unknown brows {s.brows!r}")
    left, right = s.arms or POSES[s.pose]
    vw, vh = VIEWBOX
    w, h = size or VIEWBOX

    back = "".join(_arm(side, a) for side, a in ((-1, left), (1, right)) if not a.front)
    front = "".join(_arm(side, a) for side, a in ((-1, left), (1, right)) if a.front)

    # squash/stretch around the feet, plus the breathing bob
    sq = s.squash
    stretch_x = 1 / math.sqrt(sq) if sq > 0 else 1
    body_tf = (
        f"translate(0 {_f(s.bob)}) translate(500 1050) scale({stretch_x:.4f} {sq:.4f}) translate(-500 -1050)"
    )
    bg = f'<rect width="{vw}" height="{vh}" fill="{s.background}"/>' if s.background else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{w}" height="{h}">'
        f"{bg}<g transform=\"{body_tf}\">"
        f"{_tail(s.tail_sway)}{back}{_body()}{_head(s)}{front}"
        "</g></svg>"
    )


def state_for(expression: str = "neutral", pose: str = "idle", **kw) -> State:
    """Convenience: a State with an expression preset and a pose applied."""
    return replace(State(pose=pose).with_expression(expression), **kw)
