"""Byte the squirrel: a parametric, code-drawn character rig (v3, kawaii dev squirrel).

Style: chubby fluffy squirrel, big shiny eyes, puffy pointy cheeks, tiny smile,
rosy blush, paws held together at the chest, a round cream "developer belly"
poking out under the outfit, and a big fluffy curled tail. Outfits, hats and
held props come from :mod:`.wardrobe`.

Every frame is described by a :class:`State` and turned into an SVG string by
:func:`render_svg`, so blinking, lip-sync, tail sway, head nods, hops and pose
changes are continuous parameters an animator can interpolate.

Coordinate system: SVG viewBox ``0 0 1000 1100``; y grows downwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from . import wardrobe
from .style import (
    OUTLINE_W,
    PALETTE,
    VIEWBOX,
    bezier,
    direction,
    ellipse,
    f,
    outlined,
    smooth_closed,
)

# Rhubarb Lip Sync mouth set (Preston Blair): A-H plus X (rest).
MOUTHS = ("X", "A", "B", "C", "D", "E", "F", "G", "H")
EYE_STYLES = ("normal", "happy", "wide", "sparkle", "wink")
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
    "paws": (Arm(10, -124), Arm(10, -124)),  # paws held together at the chest
    "hold": (Arm(14, -112), Arm(14, -112)),  # paws on a held prop (IK-placed when a prop is set)
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

EXPRESSIONS: dict[str, dict] = {
    "neutral": dict(eye_style="normal", brows="neutral", mouth="X"),
    "happy": dict(eye_style="happy", brows="raised", mouth="C"),
    "surprised": dict(eye_style="wide", brows="raised", mouth="F"),
    "thinking": dict(eye_style="normal", brows="skeptical", mouth="A", look=(0.5, -0.6), eye_open=0.85),
    "confident": dict(eye_style="normal", brows="neutral", mouth="X", eye_open=0.8),
    "worried": dict(eye_style="normal", brows="worried", mouth="E"),
    "excited": dict(eye_style="sparkle", brows="raised", mouth="D"),
    "annoyed": dict(eye_style="normal", brows="frown", mouth="A", eye_open=0.65),
    "wink": dict(eye_style="wink", brows="raised", mouth="X"),
    "cozy": dict(eye_style="happy", brows="neutral", mouth="X"),
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
    head_dy: float = 0.0  # nods
    body_tilt: float = 0.0  # degrees, whole character rocks around the feet
    bob: float = 0.0  # vertical offset of the whole body, px (hops are negative)
    squash: float = 1.0  # vertical scale for emphasis bounces
    tail_sway: float = 0.0  # degrees
    blush: float = 0.7  # opacity
    glasses: bool = False
    outfit: str = "tshirt"
    shirt_print: str = "</>"
    hat: str | None = None  # beanie | cap | party | headphones
    prop: str | None = None  # acorn | coffee | cookie | laptop | sketchbook (held)
    prop_offset: tuple[float, float] = (0.0, 0.0)  # move the held prop (sip, munch)
    paw_jitter: tuple[float, float] = (0.0, 0.0)  # extra paw y offsets (typing)
    mug: bool = False  # coffee mug on the floor next to the squirrel
    t: float = 0.0  # time, for small looping details such as steam
    arms: tuple[Arm, Arm] | None = None  # overrides pose when set
    background: str | None = None  # colour, "scene" (light bg + soft circle) or None = transparent

    def with_expression(self, name: str) -> "State":
        return replace(self, **EXPRESSIONS[name])


# ------------------------------------------------------------------- tail ---
_TAIL_CURVE = ((610, 960), (850, 985), (880, 660), (780, 480))
_TAIL_TIP_CURL = ((780, 480), (730, 390), (790, 300), (860, 330))


def _tail_shape(scale: float, fluff: float, samples: int = 90) -> str:
    left, right = [], []
    for i in range(samples + 1):
        g = i / samples
        if g < 0.72:
            x, y, tx, ty = bezier(_TAIL_CURVE, g / 0.72)
        else:
            x, y, tx, ty = bezier(_TAIL_TIP_CURL, (g - 0.72) / 0.28)
        nx, ny = -ty, tx
        width = (42 + 82 * math.sin(math.pi * min(1.0, g * 1.15)) ** 0.7) * scale
        width = max(width * (1 - 0.25 * max(0.0, g - 0.8) / 0.2), 58 * scale)
        bump = fluff * abs(math.sin(g * math.pi * 13)) * min(1.0, (1 - g) / 0.12)  # fluffy scallops, smooth tip
        left.append((x + nx * (width + bump), y + ny * (width + bump)))
        right.append((x - nx * (width + bump), y - ny * (width + bump)))
    cap = []  # rounded tip
    for k in range(1, 8):
        th = math.pi * k / 8
        cap.append((x + width * (nx * math.cos(th) + tx * math.sin(th)), y + width * (ny * math.cos(th) + ty * math.sin(th))))
    return smooth_closed(left + cap + right[::-1])


def _tail(sway: float) -> str:
    return (
        f'<g transform="rotate({f(sway)} 610 950)">'
        f"{outlined(_tail_shape(1.0, 14), PALETTE['fur'])}"
        f'<path d="{_tail_shape(0.42, 5)}" fill="{PALETTE["stripe"]}" opacity="0.55"/>'
        "</g>"
    )


# ------------------------------------------------------------------- body ---
_BODY = (
    "M 500 585 C 665 585, 720 760, 715 875 C 710 990, 625 1022, 500 1022 "
    "C 375 1022, 290 990, 285 875 C 280 760, 335 585, 500 585 Z"
)
_HEM_Y_SIDE, _HEM_Y_MID = 868.0, 800.0  # the shirt rides up in the middle


def _body(s: State) -> str:
    o = PALETTE["outline"]
    feet = ellipse(408, 1018, 84, 40, PALETTE["fur"]) + ellipse(592, 1018, 84, 40, PALETTE["fur"])
    toes = "".join(
        f'<path d="M {x} 1006 L {x} 1032" stroke="{o}" stroke-width="6" stroke-linecap="round"/>' for x in (388, 424, 576, 612)
    )
    if s.outfit == "none":  # no clothes: full cream tummy
        belly = "M 500 690 C 600 690, 650 790, 640 880 C 632 950, 580 990, 500 990 C 420 990, 368 950, 360 880 C 350 790, 400 690, 500 690 Z"
        return feet + toes + outlined(_BODY, PALETTE["fur"]) + f'<path d="{belly}" fill="{PALETTE["cream"]}"/>' + (
            f'<path d="M 488 925 Q 500 940 512 925" fill="none" stroke="{o}" stroke-width="6" stroke-linecap="round"/>'
        )
    # the belly pokes out below the hem, a little wider than the body line
    belly = "M 345 840 C 330 900, 360 975, 500 985 C 640 975, 670 900, 655 840 C 600 800, 400 800, 345 840 Z"
    return (
        feet
        + toes
        + outlined(_BODY, PALETTE["fur"])
        + outlined(belly, PALETTE["cream"])
        + f'<path d="M 488 925 Q 500 940 512 925" fill="none" stroke="{o}" stroke-width="6" stroke-linecap="round"/>'
        + wardrobe.outfit_torso(s.outfit, s.shirt_print, _BODY, _HEM_Y_SIDE, _HEM_Y_MID)
        + outlined(_BODY, "none")
    )


# ------------------------------------------------------------------- arms ---
SHOULDERS = {-1: (380.0, 675.0), 1: (620.0, 675.0)}
UPPER_LEN, FORE_LEN, ARM_W = 72.0, 88.0, 62.0
PAW_OFFSET = 8.0


def reach(side: int, target: tuple[float, float], hand: str = "paw") -> Arm:
    """Two-bone inverse kinematics: an Arm whose paw centre lands on ``target``.

    The elbow always bends outward, away from the body.
    """
    sx, sy = SHOULDERS[side]
    tx, ty = target
    l1, l2 = UPPER_LEN, FORE_LEN + PAW_OFFSET
    dx, dy = tx - sx, ty - sy
    d = math.hypot(dx, dy) or 1e-6
    d_c = min(max(d, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    base = math.atan2(dy, dx)
    alpha = math.acos(max(-1.0, min(1.0, (l1 * l1 + d_c * d_c - l2 * l2) / (2 * l1 * d_c))))
    best = None
    for sgn in (1, -1):
        a = base + sgn * alpha
        ex, ey = sx + l1 * math.cos(a), sy + l1 * math.sin(a)
        if best is None or side * (ex - sx) > side * (best[0] - sx):
            best = (ex, ey)
    ex, ey = best
    px, py = sx + dx / d * d_c, sy + dy / d * d_c
    ux, uy = (ex - sx) / l1, (ey - sy) / l1
    fx, fy = px - ex, py - ey
    fn = math.hypot(fx, fy) or 1e-6
    fx, fy = fx / fn, fy / fn
    upper = math.degrees(math.atan2(side * ux, uy))
    fore = math.degrees(math.atan2(side * fx, fy))
    elbow = (fore - upper + 180) % 360 - 180
    return Arm(upper, elbow, hand)


def prop_centre(s: State) -> tuple[float, float]:
    return 500.0 + s.prop_offset[0], 720.0 + s.prop_offset[1]


def arms_for(s: State) -> tuple[Arm, Arm]:
    if s.arms is not None:
        return s.arms
    if s.prop and s.pose in ("hold", "paws"):
        cx, cy = prop_centre(s)
        (lx, ly), (rx, ry) = wardrobe.PAW_TARGETS[s.prop]
        jl, jr = s.paw_jitter
        return reach(-1, (cx + lx, cy + ly + jl)), reach(1, (cx + rx, cy + ry + jr))
    return POSES[s.pose]


def _arm(side: int, arm: Arm, outfit: str) -> tuple[str, str]:
    """Return (arm svg, paw svg) so a prop can sit between them."""
    sx, sy = SHOULDERS[side]
    ux, uy = direction(side, arm.upper)
    ex, ey = sx + ux * UPPER_LEN, sy + uy * UPPER_LEN
    fx, fy = direction(side, arm.upper + arm.elbow)
    hx, hy = ex + fx * FORE_LEN, ey + fy * FORE_LEN
    o = PALETTE["outline"]
    limb = f"M {f(sx)} {f(sy)} L {f(ex)} {f(ey)} L {f(hx)} {f(hy)}"
    arm_svg = (
        f'<path d="{limb}" fill="none" stroke="{o}" stroke-width="{ARM_W + 2 * OUTLINE_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="{limb}" fill="none" stroke="{PALETTE["fur"]}" stroke-width="{ARM_W}" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        + wardrobe.sleeve(outfit, sx, sy, ex, ey, hx, hy, ARM_W)
    )
    px, py = hx + fx * PAW_OFFSET, hy + fy * PAW_OFFSET
    paw = []
    if arm.hand == "point":
        tip_x, tip_y = px + fx * 56, py + fy * 56
        paw.append(
            f'<path d="M {f(px)} {f(py)} L {f(tip_x)} {f(tip_y)}" stroke="{o}" '
            f'stroke-width="{22 + 2 * OUTLINE_W}" stroke-linecap="round"/>'
            f'<path d="M {f(px)} {f(py)} L {f(tip_x)} {f(tip_y)}" stroke="{PALETTE["fur"]}" '
            'stroke-width="22" stroke-linecap="round"/>'
        )
    if arm.hand == "open":
        nx, ny = -fy, fx
        for k in (-1, 0, 1):
            cx, cy = px + fx * 28 + nx * k * 18, py + fy * 28 + ny * k * 18
            paw.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="12" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="8"/>')
    paw.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="33" fill="{PALETTE["fur"]}" stroke="{o}" stroke-width="{OUTLINE_W}"/>')
    if arm.hand == "paw":  # tiny finger creases
        nx, ny = -fy, fx
        for k in (-1, 1):
            ax, ay = px + fx * 12 + nx * k * 9, py + fy * 12 + ny * k * 9
            bx, by = px + fx * 30 + nx * k * 9, py + fy * 30 + ny * k * 9
            paw.append(f'<path d="M {f(ax)} {f(ay)} L {f(bx)} {f(by)}" stroke="{o}" stroke-width="5" stroke-linecap="round"/>')
    return arm_svg, "".join(paw)


def _floor_mug(cx: float = 150.0, base_y: float = 1030.0, t: float = 0.0) -> str:
    under, _ = wardrobe.prop("coffee", cx, base_y - 62, t)
    return under


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
    style = s.eye_style
    if style == "wink":
        style = "happy" if side == 1 else "normal"
    if style == "happy" or openness < 0.12:
        bend = -26 if style == "happy" else 10
        return (
            f'<path d="M {f(cx - 32)} {f(cy + 8)} Q {f(cx)} {f(cy + 8 + bend)} {f(cx + 32)} {f(cy + 8)}" '
            f'fill="none" stroke="{o}" stroke-width="12" stroke-linecap="round"/>'
        )
    rx, ry = (46, 56) if style == "wide" else (40, 50)
    ry *= openness
    ex, ey = cx + lx * 8, cy + ly * 8
    cid = f"eyeclip{side}"
    out = [
        f'<clipPath id="{cid}"><ellipse cx="{f(ex)}" cy="{f(ey)}" rx="{rx}" ry="{f(ry)}"/></clipPath>',
        f'<ellipse cx="{f(ex)}" cy="{f(ey)}" rx="{rx}" ry="{f(ry)}" fill="{o}"/>',
        f'<g clip-path="url(#{cid})"><ellipse cx="{f(ex)}" cy="{f(ey + ry * 0.75)}" rx="{rx}" ry="{f(ry * 0.55)}" '
        f'fill="{PALETTE["eye_lower"]}"/></g>',
    ]
    if openness > 0.35:
        hs = 1.2 if style == "sparkle" else 1.0
        out.append(
            f'<circle cx="{f(ex + 13)}" cy="{f(ey - ry * 0.38)}" r="{f(16 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
            f'<circle cx="{f(ex - 14)}" cy="{f(ey + ry * 0.36)}" r="{f(7.5 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
            f'<circle cx="{f(ex + 18)}" cy="{f(ey + ry * 0.2)}" r="{f(3.5 * hs)}" fill="{PALETTE["eye_shine"]}"/>'
        )
        if style == "sparkle":
            sx, sy = ex - 12, ey - ry * 0.1
            out.append(
                f'<path d="M {f(sx)} {f(sy - 12)} L {f(sx + 3)} {f(sy - 3)} L {f(sx + 12)} {f(sy)} '
                f'L {f(sx + 3)} {f(sy + 3)} L {f(sx)} {f(sy + 12)} L {f(sx - 3)} {f(sy + 3)} '
                f'L {f(sx - 12)} {f(sy)} L {f(sx - 3)} {f(sy - 3)} Z" fill="{PALETTE["eye_shine"]}"/>'
            )
    return "".join(out)


def _glasses() -> str:
    g = PALETTE["glasses"]
    out = []
    for side in (-1, 1):
        cx, cy = EYES[side]
        out.append(
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="72" fill="{PALETTE["lens"]}" fill-opacity="0.15" '
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
            f'<path d="M {f(x_outer)} {f(base_y + outer)} Q {f(cx)} {f(base_y - 8 + (outer + inner) / 2)} '
            f'{f(x_inner)} {f(base_y + inner)}" fill="none" stroke="{o}" stroke-width="10" stroke-linecap="round"/>'
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
    parts.append(wardrobe.hat(s.hat))
    px, py = HEAD_PIVOT
    return f'<g transform="translate(0 {f(s.head_dy)}) rotate({f(s.head_tilt)} {f(px)} {f(py)})">{"".join(parts)}</g>'


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


def validate(s: State) -> None:
    if s.pose not in POSES and s.arms is None:
        raise ValueError(f"unknown pose {s.pose!r}")
    if s.eye_style not in EYE_STYLES:
        raise ValueError(f"unknown eye style {s.eye_style!r}")
    if s.brows not in BROWS:
        raise ValueError(f"unknown brows {s.brows!r}")
    if s.outfit not in wardrobe.OUTFITS:
        raise ValueError(f"unknown outfit {s.outfit!r}")
    if s.hat is not None and s.hat not in wardrobe.HATS:
        raise ValueError(f"unknown hat {s.hat!r}")
    if s.prop is not None and s.prop not in wardrobe.PROPS:
        raise ValueError(f"unknown prop {s.prop!r}")


def character_group(s: State) -> str:
    """The character (and floor mug) as an SVG group, without the <svg> wrapper."""
    validate(s)
    left, right = arms_for(s)
    arms = [(_arm(side, a, s.outfit), a.front) for side, a in ((-1, left), (1, right))]
    back = "".join(a + p for (a, p), front in arms if not front)
    front_arms = "".join(a for (a, _), front in arms if front)
    front_paws = "".join(p for (_, p), front in arms if front)
    prop_under, prop_over = ("", "")
    if s.prop and s.pose in ("hold", "paws"):
        cx, cy = prop_centre(s)
        prop_under, prop_over = wardrobe.prop(s.prop, cx, cy, s.t)

    sq = s.squash
    stretch_x = 1 / math.sqrt(sq) if sq > 0 else 1
    body_tf = (
        f"translate(-35 {f(s.bob)}) rotate({f(s.body_tilt)} 500 1030) "
        f"translate(500 1050) scale({stretch_x:.4f} {sq:.4f}) translate(-500 -1050)"
    )
    return (
        f"{_floor_mug(t=s.t) if s.mug else ''}"
        f'<g transform="{body_tf}">'
        f"{_tail(s.tail_sway)}{back}{_body(s)}{wardrobe.hood(s.outfit)}{_head(s)}"
        f"{front_arms}{prop_under}{front_paws}{prop_over}"
        "</g>"
    )


def render_svg(s: State, size: tuple[int, int] | None = None) -> str:
    """Return a complete SVG document for one frame of the character."""
    vw, vh = VIEWBOX
    w, h = size or VIEWBOX
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{w}" height="{h}">'
        f"{_background(s.background)}{character_group(s)}</svg>"
    )


def state_for(expression: str = "neutral", pose: str = "paws", **kw) -> State:
    """Convenience: a State with an expression preset and a pose applied."""
    return replace(State(pose=pose).with_expression(expression), **kw)
