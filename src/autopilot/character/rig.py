"""Byte the squirrel: a parametric, code-drawn character rig (v3, kawaii dev squirrel).

Style: chubby fluffy squirrel, big shiny eyes, puffy pointy cheeks, tiny smile,
rosy blush, paws held together at the chest, a slightly-too-small navy t-shirt
riding up over a round cream "developer belly", a big fluffy curled tail, and an
optional coffee mug. Soft dark-brown outlines, warm flat colours.

Every frame is described by a :class:`State` and turned into an SVG string by
:func:`render_svg`, so blinking, lip-sync, tail sway, head tilt and pose changes
are continuous parameters an animator can interpolate.

Coordinate system: SVG viewBox ``0 0 1000 1100``; y grows downwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

# ---------------------------------------------------------------- palette ---
PALETTE = {
    "outline": "#4A2E20",
    "fur": "#E0884A",
    "fur_shade": "#C46E34",
    "stripe": "#B8642E",
    "cream": "#FFF1DC",
    "ear_inner": "#F4B79A",
    "blush": "#F58D8D",
    "eye": "#2A1A12",
    "eye_lower": "#6B4430",
    "eye_shine": "#FFFFFF",
    "glasses": "#2E3550",
    "lens": "#D8EEFF",
    "mouth": "#6A2424",
    "tongue": "#EE7272",
    "teeth": "#FFFFFF",
    "nose": "#3A2218",
    "shirt": "#26365E",
    "shirt_shade": "#1C2848",
    "shirt_print": "#8FE3C8",
    "mug": "#FFFFFF",
    "mug_band": "#8FE3C8",
    "coffee": "#6B3E26",
    "steam": "#E9DCCB",
    "acorn_cap": "#7A4A22",
    "acorn_cap_light": "#9C6534",
    "acorn": "#C98B4A",
    "acorn_light": "#E2AC6E",
    "bg": "#FFF6EA",
    "bg_circle": "#FFE6C7",
}

OUTLINE_W = 11
VIEWBOX = (1000, 1100)

# Rhubarb Lip Sync mouth set (Preston Blair): A-H plus X (rest).
MOUTHS = ("X", "A", "B", "C", "D", "E", "F", "G", "H")
EYE_STYLES = ("normal", "happy", "wide", "sparkle")
BROWS = ("neutral", "raised", "frown", "worried", "skeptical")
SHIRT_PRINTS = ("</>", "{ }", "Hello World")


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
    "paws": (Arm(10, -124), Arm(10, -124)),  # paws held together at the chest
    "hold": (Arm(14, -112), Arm(14, -112)),  # hugging the acorn prop
    "idle": (Arm(14, -28), Arm(14, -28)),
    "wave": (Arm(10, -124), Arm(150, 25, "open")),
    "point_right": (Arm(10, -124), Arm(98, -4, "point")),
    "point_left": (Arm(98, -4, "point"), Arm(10, -124)),
    "point_up": (Arm(10, -124), Arm(165, 8, "point")),
    "thinking": (Arm(10, -124), Arm(140, 60, "paw")),
    "excited": (Arm(155, 20, "open"), Arm(155, 20, "open")),
    "shrug": (Arm(105, 65, "open"), Arm(105, 65, "open")),
    "explain": (Arm(10, -124), Arm(65, 45, "open")),
}
PROP_POSES = {"hold"}  # poses that show the acorn

EXPRESSIONS: dict[str, dict] = {
    "neutral": dict(eye_style="normal", brows="neutral", mouth="X"),
    "happy": dict(eye_style="happy", brows="raised", mouth="C"),
    "surprised": dict(eye_style="wide", brows="raised", mouth="F"),
    "thinking": dict(eye_style="normal", brows="skeptical", mouth="A", look=(0.5, -0.6), eye_open=0.85),
    "confident": dict(eye_style="normal", brows="neutral", mouth="X", eye_open=0.8),
    "worried": dict(eye_style="normal", brows="worried", mouth="E"),
    "excited": dict(eye_style="sparkle", brows="raised", mouth="D"),
    "annoyed": dict(eye_style="normal", brows="frown", mouth="A", eye_open=0.65),
}


@dataclass(frozen=True)
class State:
    pose: str = "paws"
    eye_style: str = "normal"
    eye_open: float = 1.0  # 0 closed .. 1 open (blinks animate this)
    look: tuple[float, float] = (0.0, 0.0)  # pupil offset, each -1..1
    brows: str = "neutral"
    mouth: str = "X"
    head_tilt: float = 0.0  # degrees
    bob: float = 0.0  # vertical offset of the whole body, px
    squash: float = 1.0  # vertical scale for emphasis bounces
    tail_sway: float = 0.0  # degrees
    blush: float = 0.7  # opacity
    glasses: bool = False
    shirt_print: str = "</>"
    mug: bool = False  # coffee mug next to the squirrel
    show_prop: bool | None = None  # acorn; None = automatic from the pose
    arms: tuple[Arm, Arm] | None = None  # overrides pose when set
    background: str | None = None  # colour, "scene" (light bg + soft circle) or None = transparent

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
_TAIL_CURVE = ((610, 960), (850, 985), (880, 660), (780, 480))
_TAIL_TIP_CURL = ((780, 480), (730, 390), (790, 300), (860, 330))


def _tail_shape(scale: float, fluff: float, samples: int = 90) -> str:
    left, right = [], []
    for i in range(samples + 1):
        g = i / samples
        if g < 0.72:
            x, y, tx, ty = _bezier(_TAIL_CURVE, g / 0.72)
        else:
            x, y, tx, ty = _bezier(_TAIL_TIP_CURL, (g - 0.72) / 0.28)
        nx, ny = -ty, tx
        width = (42 + 82 * math.sin(math.pi * min(1.0, g * 1.15)) ** 0.7) * scale
        width = max(width * (1 - 0.25 * max(0.0, g - 0.8) / 0.2), 58 * scale)
        bump = fluff * abs(math.sin(g * math.pi * 13)) * min(1.0, (1 - g) / 0.12)  # fluffy scallops, smooth tip
        left.append((x + nx * (width + bump), y + ny * (width + bump)))
        right.append((x - nx * (width + bump), y - ny * (width + bump)))
    cap = []  # rounded tip
    w = width
    for k in range(1, 8):
        th = math.pi * k / 8
        cap.append((x + w * (nx * math.cos(th) + tx * math.sin(th)), y + w * (ny * math.cos(th) + ty * math.sin(th))))
    return _smooth_closed(left + cap + right[::-1])


def _tail(sway: float) -> str:
    return (
        f'<g transform="rotate({_f(sway)} 610 950)">'
        f"{_outlined(_tail_shape(1.0, 14), PALETTE['fur'])}"
        f'<path d="{_tail_shape(0.42, 5)}" fill="{PALETTE["stripe"]}" opacity="0.55"/>'
        "</g>"
    )


# ------------------------------------------------------------------- body ---
_BODY = (
    "M 500 585 C 665 585, 720 760, 715 875 C 710 990, 625 1022, 500 1022 "
    "C 375 1022, 290 990, 285 875 C 280 760, 335 585, 500 585 Z"
)
_HEM_Y_SIDE, _HEM_Y_MID = 868.0, 800.0  # the shirt rides up in the middle


def _shirt_print(text: str) -> str:
    if text == "Hello World":
        return (
            f'<text x="500" y="760" font-family="DejaVu Sans Mono, monospace" font-size="38" font-weight="bold" '
            f'fill="{PALETTE["shirt_print"]}" text-anchor="middle">Hello</text>'
            f'<text x="500" y="800" font-family="DejaVu Sans Mono, monospace" font-size="38" font-weight="bold" '
            f'fill="{PALETTE["shirt_print"]}" text-anchor="middle">World</text>'
        )
    safe = text.replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<text x="500" y="795" font-family="DejaVu Sans Mono, monospace" font-size="66" font-weight="bold" '
        f'fill="{PALETTE["shirt_print"]}" text-anchor="middle">{safe}</text>'
    )


def _body(s: State) -> str:
    o = PALETTE["outline"]
    feet = _ellipse(408, 1018, 84, 40, PALETTE["fur"]) + _ellipse(592, 1018, 84, 40, PALETTE["fur"])
    toes = "".join(
        f'<path d="M {x} 1006 L {x} 1032" stroke="{o}" stroke-width="6" stroke-linecap="round"/>' for x in (388, 424, 576, 612)
    )
    hem = f"M 240 {_HEM_Y_SIDE} Q 500 {2 * _HEM_Y_MID - _HEM_Y_SIDE} 760 {_HEM_Y_SIDE}"
    shirt_area = f"M 220 560 L 780 560 L 780 {_HEM_Y_SIDE} Q 500 {2 * _HEM_Y_MID - _HEM_Y_SIDE} 220 {_HEM_Y_SIDE} Z"
    # the belly pokes out below the hem, a little wider than the body line
    belly = "M 345 840 C 330 900, 360 975, 500 985 C 640 975, 670 900, 655 840 C 600 800, 400 800, 345 840 Z"
    return (
        feet
        + toes
        + _outlined(_BODY, PALETTE["fur"])
        + f'<clipPath id="bodyclip"><path d="{_BODY}"/></clipPath>'
        + _outlined(belly, PALETTE["cream"])
        + f'<path d="M 488 925 Q 500 940 512 925" fill="none" stroke="{o}" stroke-width="6" stroke-linecap="round"/>'
        + f'<g clip-path="url(#bodyclip)"><path d="{shirt_area}" fill="{PALETTE["shirt"]}"/>'
        + f'<path d="{hem}" fill="none" stroke="{PALETTE["shirt_shade"]}" stroke-width="26"/>'
        + f'<path d="{hem}" fill="none" stroke="{o}" stroke-width="{OUTLINE_W}"/></g>'
        + _outlined(_BODY, "none")
        + _shirt_print(s.shirt_print)
    )


# ------------------------------------------------------------------- arms ---
SHOULDERS = {-1: (380.0, 675.0), 1: (620.0, 675.0)}
UPPER_LEN, FORE_LEN, ARM_W = 72.0, 88.0, 62.0


def _arm(side: int, arm: Arm) -> tuple[str, str]:
    """Return (arm svg, paw svg) so a prop can sit between them."""
    sx, sy = SHOULDERS[side]
    ux, uy = _dir(side, arm.upper)
    ex, ey = sx + ux * UPPER_LEN, sy + uy * UPPER_LEN
    fx, fy = _dir(side, arm.upper + arm.elbow)
    hx, hy = ex + fx * FORE_LEN, ey + fy * FORE_LEN
    o = PALETTE["outline"]
    limb = f"M {_f(sx)} {_f(sy)} L {_f(ex)} {_f(ey)} L {_f(hx)} {_f(hy)}"
    sleeve_end = (sx + ux * UPPER_LEN * 0.45, sy + uy * UPPER_LEN * 0.45)
    sleeve = f"M {_f(sx)} {_f(sy)} L {_f(sleeve_end[0])} {_f(sleeve_end[1])}"
    arm_svg = (
        f'<path d="{limb}" fill="none" stroke="{o}" stroke-width="{ARM_W + 2 * OUTLINE_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="{limb}" fill="none" stroke="{PALETTE["fur"]}" stroke-width="{ARM_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        # short t-shirt sleeve
        f'<path d="{sleeve}" fill="none" stroke="{o}" stroke-width="{ARM_W + 6 + 2 * OUTLINE_W}" stroke-linecap="butt"/>'
        f'<path d="{sleeve}" fill="none" stroke="{PALETTE["shirt"]}" stroke-width="{ARM_W + 6}" stroke-linecap="butt"/>'
    )
    px, py = hx + fx * 8, hy + fy * 8
    paw = []
    if arm.hand == "point":
        tip_x, tip_y = px + fx * 56, py + fy * 56
        paw.append(
            f'<path d="M {_f(px)} {_f(py)} L {_f(tip_x)} {_f(tip_y)}" stroke="{o}" '
            f'stroke-width="{22 + 2 * OUTLINE_W}" stroke-linecap="round"/>'
            f'<path d="M {_f(px)} {_f(py)} L {_f(tip_x)} {_f(tip_y)}" stroke="{PALETTE["fur"]}" '
            'stroke-width="22" stroke-linecap="round"/>'
        )
    if arm.hand == "open":
        nx, ny = -fy, fx
        for k in (-1, 0, 1):
            cx, cy = px + fx * 28 + nx * k * 18, py + fy * 28 + ny * k * 18
            paw.append(f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="12" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="8"/>')
    paw.append(f'<circle cx="{_f(px)}" cy="{_f(py)}" r="33" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="{OUTLINE_W}"/>')
    if arm.hand == "paw":  # tiny finger creases
        nx, ny = -fy, fx
        for k in (-1, 1):
            ax, ay = px + fx * 12 + nx * k * 9, py + fy * 12 + ny * k * 9
            bx, by = px + fx * 30 + nx * k * 9, py + fy * 30 + ny * k * 9
            paw.append(f'<path d="M {_f(ax)} {_f(ay)} L {_f(bx)} {_f(by)}" stroke="{o}" stroke-width="5" stroke-linecap="round"/>')
    return arm_svg, "".join(paw)


# ------------------------------------------------------------------ props ---
def _acorn(cx: float = 500.0, cy: float = 720.0) -> str:
    o = PALETTE["outline"]
    nut = (
        f"M {cx - 58} {cy - 10} C {cx - 62} {cy + 55}, {cx - 24} {cy + 98}, {cx} {cy + 104} "
        f"C {cx + 24} {cy + 98}, {cx + 62} {cy + 55}, {cx + 58} {cy - 10} Z"
    )
    cap = (
        f"M {cx - 75} {cy - 6} C {cx - 80} {cy - 66}, {cx - 38} {cy - 86}, {cx} {cy - 86} "
        f"C {cx + 38} {cy - 86}, {cx + 80} {cy - 66}, {cx + 75} {cy - 6} "
        f"C {cx + 38} {cy + 8}, {cx - 38} {cy + 8}, {cx - 75} {cy - 6} Z"
    )
    hatch = "".join(
        f'<path d="M {cx + k} {cy - 104} L {cx + k + 56} {cy + 18}" stroke="{PALETTE["acorn_cap_light"]}" stroke-width="6"/>'
        f'<path d="M {cx + k} {cy - 104} L {cx + k - 56} {cy + 18}" stroke="{PALETTE["acorn_cap_light"]}" stroke-width="6"/>'
        for k in range(-150, 190, 32)
    )
    stem = f"M {cx - 6} {cy - 82} Q {cx - 4} {cy - 116} {cx + 20} {cy - 124}"
    return (
        f'<path d="{stem}" fill="none" stroke="{o}" stroke-width="{11 + OUTLINE_W}" stroke-linecap="round"/>'
        f'<path d="{stem}" fill="none" stroke="{PALETTE["acorn_cap"]}" stroke-width="11" stroke-linecap="round"/>'
        + _outlined(nut, PALETTE["acorn"])
        + f'<path d="M {cx + 28} {cy + 14} Q {cx + 38} {cy + 46} {cx + 20} {cy + 76}" fill="none" '
        f'stroke="{PALETTE["acorn_light"]}" stroke-width="11" stroke-linecap="round"/>'
        + f'<clipPath id="acorncap"><path d="{cap}"/></clipPath>'
        + f'<path d="{cap}" fill="{PALETTE["acorn_cap"]}"/>'
        + f'<g clip-path="url(#acorncap)">{hatch}</g>'
        + f'<path d="{cap}" fill="none" stroke="{o}" stroke-width="{OUTLINE_W}" stroke-linejoin="round"/>'
    )


def _mug(cx: float = 150.0, base_y: float = 1030.0) -> str:
    o = PALETTE["outline"]
    w, h = 130, 140
    x0, y0 = cx - w / 2, base_y - h
    body = (
        f"M {x0} {y0} L {x0 + w} {y0} L {x0 + w - 6} {base_y - 14} "
        f"Q {x0 + w - 8} {base_y} {cx} {base_y} Q {x0 + 8} {base_y} {x0 + 6} {base_y - 14} Z"
    )
    handle = f"M {x0 + w - 4} {y0 + 30} C {x0 + w + 50} {y0 + 25}, {x0 + w + 50} {y0 + 100}, {x0 + w - 8} {y0 + 95}"
    steam = "".join(
        f'<path d="M {cx + dx} {y0 - 20} C {cx + dx - 18} {y0 - 50}, {cx + dx + 18} {y0 - 70}, {cx + dx} {y0 - 100}" '
        f'fill="none" stroke="{PALETTE["steam"]}" stroke-width="10" stroke-linecap="round"/>'
        for dx in (-28, 0, 28)
    )
    return (
        steam
        + f'<path d="{handle}" fill="none" stroke="{o}" stroke-width="{22 + OUTLINE_W}" stroke-linecap="round"/>'
        + f'<path d="{handle}" fill="none" stroke="{PALETTE["mug"]}" stroke-width="22" stroke-linecap="round"/>'
        + _outlined(body, PALETTE["mug"])
        + f'<ellipse cx="{cx}" cy="{y0 + 4}" rx="{w / 2 - 10}" ry="12" fill="{PALETTE["coffee"]}"/>'
        + f'<rect x="{x0 + 3}" y="{y0 + 58}" width="{w - 7}" height="34" fill="{PALETTE["mug_band"]}"/>'
        + f'<text x="{cx}" y="{y0 + 86}" font-family="DejaVu Sans Mono, monospace" font-size="30" font-weight="bold" '
        f'fill="{PALETTE["shirt"]}" text-anchor="middle">{{ }}</text>'
        + _outlined(body, "none")
    )


# ------------------------------------------------------------------- head ---
HEAD_PIVOT = (500.0, 620.0)
EYES = {-1: (402.0, 410.0), 1: (598.0, 410.0)}

# head with puffy, slightly pointy cheeks (as if storing an acorn)
_HEAD = (
    "M 500 195 C 670 195, 752 295, 752 400 "
    "C 752 440, 770 470, 800 500 "  # right cheek point
    "C 770 515, 760 545, 730 572 "
    "C 670 625, 590 640, 500 640 "
    "C 410 640, 330 625, 270 572 "
    "C 240 545, 230 515, 200 500 "  # left cheek point
    "C 230 470, 248 440, 248 400 "
    "C 248 295, 330 195, 500 195 Z"
)
_EARS = (
    "M 310 290 C 280 220, 290 140, 330 110 L 342 82 L 356 112 C 400 130, 425 200, 420 250 Z",
    "M 690 290 C 720 220, 710 140, 670 110 L 658 82 L 644 112 C 600 130, 575 200, 580 250 Z",
)
_TOP_FLUFF = "M 455 205 Q 470 160 492 198 Q 505 150 522 198 Q 540 165 548 208 Z"
_FACE_CREAM = (
    "M 500 462 C 565 440, 660 452, 735 505 C 720 560, 640 625, 500 628 "
    "C 360 625, 280 560, 265 505 C 340 452, 435 440, 500 462 Z"
)


def _eye(side: int, s: State) -> str:
    cx, cy = EYES[side]
    o = PALETTE["eye"]
    lx, ly = s.look
    openness = max(0.0, min(1.0, s.eye_open))
    if s.eye_style == "happy" or openness < 0.12:
        bend = -26 if s.eye_style == "happy" else 10
        return (
            f'<path d="M {_f(cx - 32)} {_f(cy + 8)} Q {_f(cx)} {_f(cy + 8 + bend)} {_f(cx + 32)} {_f(cy + 8)}" '
            f'fill="none" stroke="{o}" stroke-width="12" stroke-linecap="round"/>'
        )
    rx, ry = (46, 56) if s.eye_style == "wide" else (40, 50)
    ry *= openness
    ex, ey = cx + lx * 8, cy + ly * 8
    cid = f"eyeclip{side}"
    out = [
        f'<clipPath id="{cid}"><ellipse cx="{_f(ex)}" cy="{_f(ey)}" rx="{rx}" ry="{_f(ry)}"/></clipPath>',
        f'<ellipse cx="{_f(ex)}" cy="{_f(ey)}" rx="{rx}" ry="{_f(ry)}" fill="{o}"/>',
        # warm lower crescent for a glossy look
        f'<g clip-path="url(#{cid})"><ellipse cx="{_f(ex)}" cy="{_f(ey + ry * 0.75)}" rx="{rx}" ry="{_f(ry * 0.55)}" '
        f'fill="{PALETTE["eye_lower"]}"/></g>',
    ]
    if openness > 0.35:
        hs = 1.2 if s.eye_style == "sparkle" else 1.0
        out.append(
            f'<circle cx="{_f(ex + 13)}" cy="{_f(ey - ry * 0.38)}" r="{_f(16 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
            f'<circle cx="{_f(ex - 14)}" cy="{_f(ey + ry * 0.36)}" r="{_f(7.5 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
            f'<circle cx="{_f(ex + 18)}" cy="{_f(ey + ry * 0.2)}" r="{_f(3.5 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
        )
        if s.eye_style == "sparkle":
            sx, sy = ex - 12, ey - ry * 0.1
            out.append(
                f'<path d="M {_f(sx)} {_f(sy - 12)} L {_f(sx + 3)} {_f(sy - 3)} L {_f(sx + 12)} {_f(sy)} '
                f'L {_f(sx + 3)} {_f(sy + 3)} L {_f(sx)} {_f(sy + 12)} L {_f(sx - 3)} {_f(sy + 3)} '
                f'L {_f(sx - 12)} {_f(sy)} L {_f(sx - 3)} {_f(sy - 3)} Z" fill="{PALETTE["eye_shine"]}"/>'
            )
    return "".join(out)


def _glasses() -> str:
    g = PALETTE["glasses"]
    out = []
    for side in (-1, 1):
        cx, cy = EYES[side]
        out.append(
            f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="72" fill="{PALETTE["lens"]}" fill-opacity="0.15" '
            f'stroke="{g}" stroke-width="10"/>'
        )
    out.append(f'<path d="M 474 405 Q 500 388 526 405" fill="none" stroke="{g}" stroke-width="10" stroke-linecap="round"/>')
    out.append(f'<path d="M 330 400 L 252 388" stroke="{g}" stroke-width="9" stroke-linecap="round"/>')
    out.append(f'<path d="M 670 400 L 748 388" stroke="{g}" stroke-width="9" stroke-linecap="round"/>')
    return "".join(out)


_BROW_SHAPES = {"neutral": (0, 0), "raised": (-16, -20), "frown": (-6, 14), "worried": (10, -14)}


def _brows(kind: str) -> str:
    o = PALETTE["outline"]
    out = []
    for side in (-1, 1):
        cx = EYES[side][0]
        base_y = 322
        if kind == "skeptical":
            outer, inner = (-18, -22) if side == 1 else (4, 4)
        else:
            outer, inner = _BROW_SHAPES[kind]
        x_outer, x_inner = cx + side * 26, cx - side * 22
        out.append(
            f'<path d="M {_f(x_outer)} {_f(base_y + outer)} Q {_f(cx)} {_f(base_y - 8 + (outer + inner) / 2)} '
            f'{_f(x_inner)} {_f(base_y + inner)}" fill="none" stroke="{o}" stroke-width="10" stroke-linecap="round"/>'
        )
    return "".join(out)


def _mouth(shape: str) -> str:
    """Tiny mouth shapes, drawn large around (500, 515) and scaled down."""
    o = PALETTE["outline"]
    m, t, w = PALETTE["mouth"], PALETTE["tongue"], PALETTE["teeth"]
    x, y = 500.0, 515.0

    def line(d: str, width: float = 13) -> str:
        return f'<path d="{d}" fill="none" stroke="{o}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'

    def opening(d: str, tongue: bool = True, teeth: bool = True) -> str:
        cid = f"mclip{shape}"
        inner = []
        if tongue:
            inner.append(f'<ellipse cx="{x}" cy="{y + 40}" rx="30" ry="20" fill="{t}"/>')
        if teeth:
            inner.append(f'<rect x="{x - 14}" y="{y - 26}" width="13" height="20" rx="3" fill="{w}"/>')
            inner.append(f'<rect x="{x + 1}" y="{y - 26}" width="13" height="20" rx="3" fill="{w}"/>')
        return (
            f'<clipPath id="{cid}"><path d="{d}"/></clipPath><path d="{d}" fill="{m}"/>'
            f'<g clip-path="url(#{cid})">{"".join(inner)}</g>'
            f'<path d="{d}" fill="none" stroke="{o}" stroke-width="11" stroke-linejoin="round"/>'
        )

    if shape == "X":  # rest: tiny "w" smile
        g = line(f"M {x - 34} {y - 12} Q {x - 17} {y + 10} {x} {y - 8} Q {x + 17} {y + 10} {x + 34} {y - 12}")
    elif shape == "A":
        g = line(f"M {x - 30} {y - 8} Q {x} {y + 2} {x + 30} {y - 8}")
    elif shape == "B":
        g = opening(f"M {x - 32} {y - 14} Q {x} {y - 18} {x + 32} {y - 14} Q {x} {y + 12} {x - 32} {y - 14} Z", tongue=False)
    elif shape == "C":
        g = opening(f"M {x - 36} {y - 14} Q {x} {y - 20} {x + 36} {y - 14} Q {x + 24} {y + 34} {x} {y + 36} Q {x - 24} {y + 34} {x - 36} {y - 14} Z")
    elif shape == "D":
        g = opening(f"M {x - 44} {y - 16} Q {x} {y - 24} {x + 44} {y - 16} Q {x + 36} {y + 48} {x} {y + 52} Q {x - 36} {y + 48} {x - 44} {y - 16} Z")
    elif shape == "E":
        g = opening(f"M {x - 28} {y - 4} Q {x} {y - 22} {x + 28} {y - 4} Q {x + 24} {y + 32} {x} {y + 34} Q {x - 24} {y + 32} {x - 28} {y - 4} Z", teeth=False)
    elif shape == "F":
        g = opening(f"M {x - 16} {y + 6} a 16 20 0 1 0 32 0 a 16 20 0 1 0 -32 0 Z", teeth=False)
    elif shape == "G":
        g = opening(f"M {x - 34} {y - 12} Q {x} {y - 16} {x + 34} {y - 12} Q {x} {y + 14} {x - 34} {y - 12} Z", tongue=False) + line(
            f"M {x - 24} {y + 6} Q {x} {y + 14} {x + 24} {y + 6}", 9
        )
    elif shape == "H":
        d = f"M {x - 36} {y - 14} Q {x} {y - 20} {x + 36} {y - 14} Q {x + 24} {y + 32} {x} {y + 34} Q {x - 24} {y + 32} {x - 36} {y - 14} Z"
        g = opening(d) + f'<ellipse cx="{x}" cy="{y + 2}" rx="16" ry="10" fill="{t}"/>'
    else:
        raise ValueError(f"unknown mouth shape {shape!r}")
    return f'<g transform="translate({x} {y}) scale(0.72) translate({-x} {-y})">{g}</g>'


def _head(s: State) -> str:
    o = PALETTE["outline"]
    sil = [*_EARS, _TOP_FLUFF, _HEAD]
    parts = []
    for d in sil:  # one shared soft outline: stroke every fur shape, then fill on top
        parts.append(f'<path d="{d}" fill="{o}" stroke="{o}" stroke-width="{OUTLINE_W * 2}" stroke-linejoin="round"/>')
    for d in sil:
        parts.append(f'<path d="{d}" fill="{PALETTE["fur"]}"/>')
    parts.append(f'<path d="M 326 268 C 308 215, 318 160, 342 140 C 372 160, 392 205, 392 240 Z" fill="{PALETTE["ear_inner"]}"/>')
    parts.append(f'<path d="M 674 268 C 692 215, 682 160, 658 140 C 628 160, 608 205, 608 240 Z" fill="{PALETTE["ear_inner"]}"/>')
    for dx, top, bot in ((-30, 232, 290), (0, 220, 300), (30, 232, 290)):  # forehead stripes
        parts.append(
            f'<path d="M {500 + dx} {top} L {500 + dx * 0.9} {bot}" stroke="{PALETTE["stripe"]}" '
            'stroke-width="13" stroke-linecap="round" opacity="0.8"/>'
        )
    parts.append(f'<path d="{_FACE_CREAM}" fill="{PALETTE["cream"]}"/>')
    for cx in (318, 682):
        parts.append(f'<ellipse cx="{cx}" cy="498" rx="44" ry="26" fill="{PALETTE["blush"]}" opacity="{s.blush:.2f}"/>')
        parts.append(f'<ellipse cx="{cx - 12}" cy="490" rx="9" ry="5" fill="#FFFFFF" opacity="0.55"/>')
    parts.append(_eye(-1, s))
    parts.append(_eye(1, s))
    if s.glasses:
        parts.append(_glasses())
    parts.append(_brows(s.brows))
    parts.append(
        f'<path d="M 482 466 Q 500 458 518 466 Q 515 482 500 487 Q 485 482 482 466 Z" fill="{PALETTE["nose"]}"/>'
        '<ellipse cx="493" cy="467" rx="5" ry="3" fill="#FFFFFF" opacity="0.6"/>'
    )
    parts.append(_mouth(s.mouth))
    px, py = HEAD_PIVOT
    return f'<g transform="rotate({_f(s.head_tilt)} {_f(px)} {_f(py)})">{"".join(parts)}</g>'


# ----------------------------------------------------------------- render ---
def _background(kind: str | None) -> str:
    vw, vh = VIEWBOX
    if not kind:
        return ""
    if kind == "scene":
        return (
            f'<rect width="{vw}" height="{vh}" fill="{PALETTE["bg"]}"/>'
            f'<circle cx="500" cy="560" r="450" fill="{PALETTE["bg_circle"]}"/>'
            '<ellipse cx="500" cy="1040" rx="380" ry="34" fill="#000000" opacity="0.06"/>'
        )
    return f'<rect width="{vw}" height="{vh}" fill="{kind}"/>'


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
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{w}" height="{h}">'
        f"{_background(s.background)}"
        f"{_mug() if s.mug else ''}"
        f'<g transform="translate(-35 0) {body_tf}">'
        f"{_tail(s.tail_sway)}{back}{_body(s)}{_head(s)}{front_arms}{prop}{front_paws}"
        "</g></svg>"
    )


def state_for(expression: str = "neutral", pose: str = "paws", **kw) -> State:
    """Convenience: a State with an expression preset and a pose applied."""
    return replace(State(pose=pose).with_expression(expression), **kw)
