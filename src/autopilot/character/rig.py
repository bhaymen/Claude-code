"""Byte the squirrel: a parametric, code-drawn character rig (v2, chibi style).

Style: round chubby body, thick dark outline, warm brown fur, white muzzle and
belly, forehead stripes, big curled tail, round glasses, and an acorn prop.

Every frame is described by a :class:`State` and turned into an SVG string by
:func:`render_svg`. Nothing is a static image, so blinking, lip-sync, tail sway,
head tilt and pose changes are continuous parameters an animator can interpolate.

Coordinate system: SVG viewBox ``0 0 1000 1100``; y grows downwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

# ---------------------------------------------------------------- palette ---
PALETTE = {
    "outline": "#2B1D14",
    "fur": "#D98A4E",
    "fur_shade": "#B86C34",
    "stripe": "#A65A28",
    "white": "#FFF8EE",
    "ear_inner": "#EDB48A",
    "blush": "#F2928A",
    "eye": "#1E140E",
    "eye_shine": "#FFFFFF",
    "glasses": "#2B1D14",
    "lens": "#D8EEFF",
    "mouth": "#5A1E1E",
    "tongue": "#E86A6A",
    "teeth": "#FFFFFF",
    "nose": "#1E140E",
    "acorn_cap": "#7A4A22",
    "acorn_cap_light": "#9C6534",
    "acorn": "#C98B4A",
    "acorn_light": "#E2AC6E",
}

OUTLINE_W = 14
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
    "hold": (Arm(15, -135), Arm(15, -135)),  # hugging the acorn
    "idle": (Arm(12, -30), Arm(12, -30)),
    "wave": (Arm(12, -30), Arm(150, 25, "open")),
    "point_right": (Arm(12, -30), Arm(98, -4, "point")),
    "point_left": (Arm(98, -4, "point"), Arm(12, -30)),
    "point_up": (Arm(12, -30), Arm(165, 8, "point")),
    "thinking": (Arm(12, -30), Arm(145, 55, "paw")),
    "excited": (Arm(155, 20, "open"), Arm(155, 20, "open")),
    "shrug": (Arm(105, 65, "open"), Arm(105, 65, "open")),
    "explain": (Arm(12, -30), Arm(65, 45, "open")),
}
PROP_POSES = {"hold"}  # poses that show the acorn

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
    pose: str = "hold"
    eye_style: str = "normal"
    eye_open: float = 1.0  # 0 closed .. 1 open (blinks animate this)
    look: tuple[float, float] = (0.0, 0.0)  # pupil offset, each -1..1
    brows: str = "neutral"
    mouth: str = "X"
    head_tilt: float = 0.0  # degrees
    bob: float = 0.0  # vertical offset of the whole body, px
    squash: float = 1.0  # vertical scale for emphasis bounces
    tail_sway: float = 0.0  # degrees
    blush: float = 0.6  # opacity
    glasses: bool = True
    show_prop: bool | None = None  # None = automatic from the pose
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


def _ellipse(cx, cy, rx, ry, fill, outline=True) -> str:
    stroke = f' stroke="{PALETTE["outline"]}" stroke-width="{OUTLINE_W}"' if outline else ""
    return f'<ellipse cx="{_f(cx)}" cy="{_f(cy)}" rx="{_f(rx)}" ry="{_f(ry)}" fill="{fill}"{stroke}/>'


def _dir(side: int, angle: float) -> tuple[float, float]:
    a = math.radians(angle)
    return side * math.sin(a), math.cos(a)


def _bezier(p, t):
    """Point and unit tangent on a cubic Bezier given 4 control points."""
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


# ------------------------------------------------------------------- tail ---
# Centreline: from behind the body, out to the right, up to head height, curling outward.
_TAIL_CURVE = ((600, 960), (860, 980), (900, 640), (780, 470))
_TAIL_TIP_CURL = ((780, 470), (735, 370), (800, 290), (880, 320))


def _tail_shape(scale: float, samples: int = 80) -> str:
    left, right = [], []
    for i in range(samples + 1):
        g = i / samples
        if g < 0.72:
            x, y, tx, ty = _bezier(_TAIL_CURVE, g / 0.72)
        else:
            x, y, tx, ty = _bezier(_TAIL_TIP_CURL, (g - 0.72) / 0.28)
        nx, ny = -ty, tx
        width = (45 + 85 * math.sin(math.pi * min(1.0, g * 1.15)) ** 0.7) * scale
        width = max(width * (1 - 0.25 * max(0.0, g - 0.8) / 0.2), 62 * scale)
        left.append((x + nx * width, y + ny * width))
        right.append((x - nx * width, y - ny * width))
    # rounded cap at the tip: half circle from the left edge, over the tip, to the right edge
    cap = []
    for k in range(1, 8):
        th = math.pi * k / 8
        cap.append((x + width * (nx * math.cos(th) + tx * math.sin(th)), y + width * (ny * math.cos(th) + ty * math.sin(th))))
    return _smooth_closed(left + cap + right[::-1])


def _tail(sway: float) -> str:
    return (
        f'<g transform="rotate({_f(sway)} 600 950)">'
        f"{_outlined(_tail_shape(1.0), PALETTE['fur'])}"
        f'<path d="{_tail_shape(0.38)}" fill="{PALETTE["stripe"]}" opacity="0.75"/>'
        "</g>"
    )


# ------------------------------------------------------------------- body ---
def _body() -> str:
    body = (
        "M 500 600 C 650 600, 700 760, 690 880 C 680 990, 600 1010, 500 1010 "
        "C 400 1010, 320 990, 310 880 C 300 760, 350 600, 500 600 Z"
    )
    belly = (
        "M 500 720 C 580 720, 610 820, 600 900 C 592 965, 550 985, 500 985 "
        "C 450 985, 408 965, 400 900 C 390 820, 420 720, 500 720 Z"
    )
    feet = _ellipse(405, 1012, 82, 40, PALETTE["fur"]) + _ellipse(595, 1012, 82, 40, PALETTE["fur"])
    toe_lines = "".join(
        f'<path d="M {x} 1000 L {x} 1030" stroke="{PALETTE["outline"]}" stroke-width="7" stroke-linecap="round"/>'
        for x in (385, 420, 575, 610)
    )
    return feet + toe_lines + _outlined(body, PALETTE["fur"]) + f'<path d="{belly}" fill="{PALETTE["white"]}"/>'


# ------------------------------------------------------------------- arms ---
SHOULDERS = {-1: (395.0, 700.0), 1: (605.0, 700.0)}
UPPER_LEN, FORE_LEN, ARM_W = 80.0, 70.0, 66.0


def _arm(side: int, arm: Arm) -> tuple[str, str]:
    """Return (arm svg, paw svg) so a prop can sit between them."""
    sx, sy = SHOULDERS[side]
    ux, uy = _dir(side, arm.upper)
    ex, ey = sx + ux * UPPER_LEN, sy + uy * UPPER_LEN
    fx, fy = _dir(side, arm.upper + arm.elbow)
    hx, hy = ex + fx * FORE_LEN, ey + fy * FORE_LEN
    o = PALETTE["outline"]
    limb = f"M {_f(sx)} {_f(sy)} L {_f(ex)} {_f(ey)} L {_f(hx)} {_f(hy)}"
    arm_svg = (
        f'<path d="{limb}" fill="none" stroke="{o}" stroke-width="{ARM_W + 2 * OUTLINE_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="{limb}" fill="none" stroke="{PALETTE["fur"]}" stroke-width="{ARM_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )
    px, py = hx + fx * 8, hy + fy * 8
    paw = []
    if arm.hand == "point":
        tip_x, tip_y = px + fx * 58, py + fy * 58
        paw.append(
            f'<path d="M {_f(px)} {_f(py)} L {_f(tip_x)} {_f(tip_y)}" stroke="{o}" '
            f'stroke-width="{24 + 2 * OUTLINE_W}" stroke-linecap="round"/>'
            f'<path d="M {_f(px)} {_f(py)} L {_f(tip_x)} {_f(tip_y)}" stroke="{PALETTE["fur"]}" '
            'stroke-width="24" stroke-linecap="round"/>'
        )
    if arm.hand == "open":
        nx, ny = -fy, fx
        for k in (-1, 0, 1):
            cx, cy = px + fx * 30 + nx * k * 19, py + fy * 30 + ny * k * 19
            paw.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="13" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="10"/>')
    paw.append(f'<circle cx="{_f(px)}" cy="{_f(py)}" r="36" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="{OUTLINE_W}"/>')
    if arm.hand == "paw":  # little finger creases
        nx, ny = -fy, fx
        for k in (-1, 1):
            ax, ay = px + fx * 14 + nx * k * 10, py + fy * 14 + ny * k * 10
            bx, by = px + fx * 34 + nx * k * 10, py + fy * 34 + ny * k * 10
            paw.append(f'<path d="M {_f(ax)} {_f(ay)} L {_f(bx)} {_f(by)}" stroke="{o}" stroke-width="6" stroke-linecap="round"/>')
    return arm_svg, "".join(paw)


def _acorn(cx: float = 500.0, cy: float = 735.0) -> str:
    o = PALETTE["outline"]
    nut = (
        f"M {cx - 62} {cy - 10} C {cx - 66} {cy + 60}, {cx - 25} {cy + 105}, {cx} {cy + 112} "
        f"C {cx + 25} {cy + 105}, {cx + 66} {cy + 60}, {cx + 62} {cy - 10} Z"
    )
    cap = (
        f"M {cx - 80} {cy - 6} C {cx - 85} {cy - 70}, {cx - 40} {cy - 92}, {cx} {cy - 92} "
        f"C {cx + 40} {cy - 92}, {cx + 85} {cy - 70}, {cx + 80} {cy - 6} "
        f"C {cx + 40} {cy + 8}, {cx - 40} {cy + 8}, {cx - 80} {cy - 6} Z"
    )
    hatch = "".join(
        f'<path d="M {cx + k} {cy - 110} L {cx + k + 60} {cy + 20}" stroke="{PALETTE["acorn_cap_light"]}" stroke-width="7"/>'
        f'<path d="M {cx + k} {cy - 110} L {cx + k - 60} {cy + 20}" stroke="{PALETTE["acorn_cap_light"]}" stroke-width="7"/>'
        for k in range(-160, 200, 34)
    )
    stem = f"M {cx - 6} {cy - 88} Q {cx - 4} {cy - 125} {cx + 22} {cy - 132}"
    return (
        f'<path d="{stem}" fill="none" stroke="{o}" stroke-width="{12 + OUTLINE_W}" stroke-linecap="round"/>'
        f'<path d="{stem}" fill="none" stroke="{PALETTE["acorn_cap"]}" stroke-width="12" stroke-linecap="round"/>'
        + _outlined(nut, PALETTE["acorn"])
        + f'<path d="M {cx + 30} {cy + 15} Q {cx + 40} {cy + 50} {cx + 22} {cy + 82}" fill="none" '
        f'stroke="{PALETTE["acorn_light"]}" stroke-width="12" stroke-linecap="round"/>'
        + f'<clipPath id="acorncap"><path d="{cap}"/></clipPath>'
        + f'<path d="{cap}" fill="{PALETTE["acorn_cap"]}"/>'
        + f'<g clip-path="url(#acorncap)">{hatch}</g>'
        + f'<path d="{cap}" fill="none" stroke="{o}" stroke-width="{OUTLINE_W}" stroke-linejoin="round"/>'
    )


# ------------------------------------------------------------------- head ---
HEAD_PIVOT = (500.0, 640.0)
EYES = {-1: (410.0, 430.0), 1: (590.0, 430.0)}


def _head_silhouette() -> list[str]:
    """Fur shapes that share one outline (ears + head)."""
    return [
        "M 300 300 C 270 230, 290 160, 345 150 C 395 145, 425 200, 420 250 Z",
        "M 700 300 C 730 230, 710 160, 655 150 C 605 145, 575 200, 580 250 Z",
        "M 500 215 C 680 215, 755 320, 755 430 C 755 560, 650 625, 500 625 "
        "C 350 625, 245 560, 245 430 C 245 320, 320 215, 500 215 Z",
    ]


def _eye(side: int, s: State) -> str:
    cx, cy = EYES[side]
    o = PALETTE["eye"]
    lx, ly = s.look
    openness = max(0.0, min(1.0, s.eye_open))
    if s.eye_style == "happy" or openness < 0.12:
        bend = -22 if s.eye_style == "happy" else 8
        return (
            f'<path d="M {_f(cx - 26)} {_f(cy + 6)} Q {_f(cx)} {_f(cy + 6 + bend)} {_f(cx + 26)} {_f(cy + 6)}" '
            f'fill="none" stroke="{o}" stroke-width="12" stroke-linecap="round"/>'
        )
    rx, ry = (30, 38) if s.eye_style == "wide" else (25, 32)
    ry *= openness
    ex, ey = cx + lx * 7, cy + ly * 7
    out = [f'<ellipse cx="{_f(ex)}" cy="{_f(ey)}" rx="{rx}" ry="{_f(ry)}" fill="{o}"/>']
    if openness > 0.35:
        hs = 1.25 if s.eye_style == "sparkle" else 1.0
        out.append(
            f'<circle cx="{_f(ex + 8)}" cy="{_f(ey - ry * 0.4)}" r="{_f(9 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
            f'<circle cx="{_f(ex - 9)}" cy="{_f(ey + ry * 0.38)}" r="{_f(4.5 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
        )
    return "".join(out)


def _glasses() -> str:
    g = PALETTE["glasses"]
    out = []
    for side in (-1, 1):
        cx, cy = EYES[side]
        out.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="60" fill="{PALETTE["lens"]}" fill-opacity="0.18" '
            f'stroke="{g}" stroke-width="11"/>'
            f'<path d="M {_f(cx + 18)} {_f(cy - 42)} Q {_f(cx + 40)} {_f(cy - 32)} {_f(cx + 44)} {_f(cy - 12)}" '
            'fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" opacity="0.9"/>'
        )
    out.append(f'<path d="M 470 425 Q 500 405 530 425" fill="none" stroke="{g}" stroke-width="11" stroke-linecap="round"/>')
    out.append(f'<path d="M 350 420 L 255 405" stroke="{g}" stroke-width="10" stroke-linecap="round"/>')
    out.append(f'<path d="M 650 420 L 745 405" stroke="{g}" stroke-width="10" stroke-linecap="round"/>')
    return "".join(out)


_BROW_SHAPES = {"neutral": (0, 0), "raised": (-18, -22), "frown": (-6, 16), "worried": (10, -16)}


def _brows(kind: str) -> str:
    o = PALETTE["outline"]
    out = []
    for side in (-1, 1):
        cx = EYES[side][0]
        base_y = 345
        if kind == "skeptical":
            outer, inner = (-20, -24) if side == 1 else (4, 4)
        else:
            outer, inner = _BROW_SHAPES[kind]
        x_outer, x_inner = cx + side * 30, cx - side * 26
        out.append(
            f'<path d="M {_f(x_outer)} {_f(base_y + outer)} Q {_f(cx)} {_f(base_y - 10 + (outer + inner) / 2)} '
            f'{_f(x_inner)} {_f(base_y + inner)}" fill="none" stroke="{o}" stroke-width="12" stroke-linecap="round"/>'
        )
    return "".join(out)


def _mouth(shape: str) -> str:
    """Mouth shapes drawn around (500, 530), sized for the chibi face."""
    o = PALETTE["outline"]
    m, t, w = PALETTE["mouth"], PALETTE["tongue"], PALETTE["teeth"]
    x, y = 500.0, 530.0

    def line(d: str, width: float = 10) -> str:
        return f'<path d="{d}" fill="none" stroke="{o}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'

    def opening(d: str, tongue: bool = True, teeth: bool = True) -> str:
        cid = f"mclip{shape}"
        inner = []
        if tongue:
            inner.append(f'<ellipse cx="{x}" cy="{y + 40}" rx="30" ry="20" fill="{t}"/>')
        if teeth:  # two little buck teeth
            inner.append(f'<rect x="{x - 14}" y="{y - 26}" width="13" height="20" rx="3" fill="{w}"/>')
            inner.append(f'<rect x="{x + 1}" y="{y - 26}" width="13" height="20" rx="3" fill="{w}"/>')
        return (
            f'<clipPath id="{cid}"><path d="{d}"/></clipPath><path d="{d}" fill="{m}"/>'
            f'<g clip-path="url(#{cid})">{"".join(inner)}</g>'
            f'<path d="{d}" fill="none" stroke="{o}" stroke-width="9" stroke-linejoin="round"/>'
        )

    w_mouth = f"M {x - 36} {y - 14} Q {x - 18} {y + 8} {x} {y - 10} Q {x + 18} {y + 8} {x + 36} {y - 14}"
    if shape == "X":  # rest: the "w" cat mouth
        return line(w_mouth)
    if shape == "A":  # M B P
        return line(f"M {x - 30} {y - 8} Q {x} {y + 2} {x + 30} {y - 8}")
    if shape == "B":  # K S T
        return opening(f"M {x - 32} {y - 14} Q {x} {y - 18} {x + 32} {y - 14} Q {x} {y + 12} {x - 32} {y - 14} Z", tongue=False)
    if shape == "C":  # EH AE
        return opening(f"M {x - 36} {y - 14} Q {x} {y - 20} {x + 36} {y - 14} Q {x + 24} {y + 34} {x} {y + 36} Q {x - 24} {y + 34} {x - 36} {y - 14} Z")
    if shape == "D":  # AA
        return opening(f"M {x - 44} {y - 16} Q {x} {y - 24} {x + 44} {y - 16} Q {x + 36} {y + 48} {x} {y + 52} Q {x - 36} {y + 48} {x - 44} {y - 16} Z")
    if shape == "E":  # AO ER
        return opening(f"M {x - 28} {y - 4} Q {x} {y - 22} {x + 28} {y - 4} Q {x + 24} {y + 32} {x} {y + 34} Q {x - 24} {y + 32} {x - 28} {y - 4} Z", teeth=False)
    if shape == "F":  # UW OW W
        return opening(f"M {x - 16} {y + 6} a 16 20 0 1 0 32 0 a 16 20 0 1 0 -32 0 Z", teeth=False)
    if shape == "G":  # F V
        return opening(f"M {x - 34} {y - 12} Q {x} {y - 16} {x + 34} {y - 12} Q {x} {y + 14} {x - 34} {y - 12} Z", tongue=False) + line(
            f"M {x - 24} {y + 6} Q {x} {y + 14} {x + 24} {y + 6}", 7
        )
    if shape == "H":  # L
        d = f"M {x - 36} {y - 14} Q {x} {y - 20} {x + 36} {y - 14} Q {x + 24} {y + 32} {x} {y + 34} Q {x - 24} {y + 32} {x - 36} {y - 14} Z"
        return opening(d) + f'<ellipse cx="{x}" cy="{y + 2}" rx="16" ry="10" fill="{t}"/>'
    raise ValueError(f"unknown mouth shape {shape!r}")


def _head(s: State) -> str:
    o = PALETTE["outline"]
    sil = _head_silhouette()
    parts = []
    for d in sil:  # one shared outline: stroke every fur shape, then fill on top
        parts.append(f'<path d="{d}" fill="{o}" stroke="{o}" stroke-width="{OUTLINE_W * 2}" stroke-linejoin="round"/>')
    for d in sil:
        parts.append(f'<path d="{d}" fill="{PALETTE["fur"]}"/>')
    parts.append(f'<path d="M 320 280 C 305 230, 318 190, 348 185 C 378 182, 395 215, 392 245 Z" fill="{PALETTE["ear_inner"]}"/>')
    parts.append(f'<path d="M 680 280 C 695 230, 682 190, 652 185 C 622 182, 605 215, 608 245 Z" fill="{PALETTE["ear_inner"]}"/>')
    for dx, top, bot in ((-34, 250, 318), (0, 236, 330), (34, 250, 318)):  # forehead stripes
        parts.append(
            f'<path d="M {500 + dx} {top} L {500 + dx * 0.9} {bot}" stroke="{PALETTE["stripe"]}" '
            'stroke-width="15" stroke-linecap="round"/>'
        )
    parts.append(  # white muzzle
        f'<path d="M 500 462 C 545 440, 600 470, 598 520 C 596 572, 550 590, 500 588 '
        f'C 450 590, 404 572, 402 520 C 400 470, 455 440, 500 462 Z" fill="{PALETTE["white"]}"/>'
    )
    for cx in (330, 670):
        parts.append(f'<ellipse cx="{cx}" cy="510" rx="40" ry="24" fill="{PALETTE["blush"]}" opacity="{s.blush:.2f}"/>')
    parts.append(_eye(-1, s))
    parts.append(_eye(1, s))
    if s.glasses:
        parts.append(_glasses())
    parts.append(_brows(s.brows))
    parts.append(
        f'<path d="M 474 478 Q 500 466 526 478 Q 522 500 500 506 Q 478 500 474 478 Z" fill="{PALETTE["nose"]}"/>'
        '<ellipse cx="490" cy="480" rx="7" ry="4" fill="#FFFFFF" opacity="0.6"/>'
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
    show_prop = s.show_prop if s.show_prop is not None else s.pose in PROP_POSES

    arms = [(_arm(side, a), a.front) for side, a in ((-1, left), (1, right))]
    back = "".join(a + p for (a, p), front in arms if not front)
    front_arms = "".join(a for (a, _), front in arms if front)
    front_paws = "".join(p for (_, p), front in arms if front)
    prop = _acorn() if show_prop else ""

    sq = s.squash
    stretch_x = 1 / math.sqrt(sq) if sq > 0 else 1
    body_tf = f"translate(0 {_f(s.bob)}) translate(500 1050) scale({stretch_x:.4f} {sq:.4f}) translate(-500 -1050)"
    bg = f'<rect width="{vw}" height="{vh}" fill="{s.background}"/>' if s.background else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{w}" height="{h}">'
        f'{bg}<g transform="{body_tf}">'
        f"{_tail(s.tail_sway)}{back}{_body()}{_head(s)}{front_arms}{prop}{front_paws}"
        "</g></svg>"
    )


def state_for(expression: str = "neutral", pose: str = "hold", **kw) -> State:
    """Convenience: a State with an expression preset and a pose applied."""
    return replace(State(pose=pose).with_expression(expression), **kw)
