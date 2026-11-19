"""Byte's wardrobe: outfits, hats/accessories and held props.

Everything is plain SVG strings drawn in the rig's coordinate system
(viewBox 1000x1100). Props are held at a centre point (default (500, 720)) and
expose paw targets so the rig can place the paws on them with inverse kinematics.
"""

from __future__ import annotations

import math

from .style import OUTLINE_W, PALETTE, ellipse, f, outlined, smooth_closed, thick_line

P = PALETTE

# ---------------------------------------------------------------- outfits ---
OUTFITS: dict[str, dict] = {
    "tshirt": dict(color=P["navy"], shade=P["navy_shade"], sleeves="short", print=True),
    "tshirt_green": dict(color="#2F6B57", shade="#23503F", sleeves="short", print=True),
    "hoodie": dict(color="#5BBFAE", shade="#3E9E8E", sleeves="long", print=True, hood=True, strings=True, print_color=P["navy"]),
    "sweater": dict(color=P["red"], shade="#C24646", sleeves="long", print=False, stripes=P["cream"]),
    "none": dict(),
}
SHIRT_PRINTS = ("</>", "{ }", "Hello World")


def _print(text: str, color: str) -> str:
    font = 'font-family="DejaVu Sans Mono, monospace" font-weight="bold" text-anchor="middle"'
    if text == "Hello World":
        return (
            f'<text x="500" y="760" {font} font-size="38" fill="{color}">Hello</text>'
            f'<text x="500" y="800" {font} font-size="38" fill="{color}">World</text>'
        )
    safe = text.replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="500" y="795" {font} font-size="66" fill="{color}">{safe}</text>'


def outfit_torso(name: str, print_text: str, body_path: str, hem_side: float, hem_mid: float) -> str:
    """Shirt area clipped to the body, with hem and optional print/stripes."""
    o = OUTFITS[name]
    if not o:
        return ""
    ctrl = 2 * hem_mid - hem_side
    hem = f"M 240 {hem_side} Q 500 {ctrl} 760 {hem_side}"
    area = f"M 220 560 L 780 560 L 780 {hem_side} Q 500 {ctrl} 220 {hem_side} Z"
    stripes = ""
    if o.get("stripes"):
        stripes = "".join(
            f'<rect x="220" y="{y}" width="560" height="20" fill="{o["stripes"]}"/>' for y in range(610, int(hem_side) + 40, 52)
        )
    strings = ""
    if o.get("strings"):
        for x0, x1 in ((470, 460), (530, 540)):
            strings += f'<path d="M {x0} 625 L {x1} 705" stroke="{P["cream"]}" stroke-width="8" stroke-linecap="round"/>'
            strings += f'<rect x="{x1 - 6}" y="700" width="12" height="18" rx="4" fill="{P["navy"]}"/>'
    pr = _print(print_text, o.get("print_color", P["mint"])) if o.get("print") else ""
    return (
        f'<clipPath id="outfitclip"><path d="{body_path}"/></clipPath>'
        f'<g clip-path="url(#outfitclip)"><path d="{area}" fill="{o["color"]}"/>{stripes}'
        f'<path d="{hem}" fill="none" stroke="{o["shade"]}" stroke-width="26"/>'
        f'<path d="{hem}" fill="none" stroke="{P["outline"]}" stroke-width="{OUTLINE_W}"/></g>'
        f"{pr}{strings}"
    )


def hood(name: str) -> str:
    """Hood bunched behind the neck (drawn before the head)."""
    o = OUTFITS[name]
    if not o.get("hood"):
        return ""
    d = "M 300 640 C 290 560, 390 560, 500 575 C 610 560, 710 560, 700 640 C 640 690, 360 690, 300 640 Z"
    return outlined(d, o["shade"])


def sleeve(name: str, sx: float, sy: float, ex: float, ey: float, hx: float, hy: float, arm_w: float) -> str:
    o = OUTFITS[name]
    if not o:
        return ""
    if o["sleeves"] == "short":
        mx, my = sx + (ex - sx) * 0.45, sy + (ey - sy) * 0.45
        return thick_line(f"M {f(sx)} {f(sy)} L {f(mx)} {f(my)}", o["color"], arm_w + 6, cap="butt")
    # long sleeve down to just before the paw, with a cuff
    cx, cy = ex + (hx - ex) * 0.8, ey + (hy - ey) * 0.8
    kx, ky = ex + (hx - ex) * 0.62, ey + (hy - ey) * 0.62
    d = f"M {f(sx)} {f(sy)} L {f(ex)} {f(ey)} L {f(cx)} {f(cy)}"
    return thick_line(d, o["color"], arm_w + 6, cap="butt") + (
        f'<path d="M {f(kx)} {f(ky)} L {f(cx)} {f(cy)}" stroke="{o["shade"]}" stroke-width="{arm_w + 6}"/>'
    )


# ------------------------------------------------------------------- hats ---
HATS = ("beanie", "cap", "party", "headphones")


def hat(name: str | None) -> str:
    """Accessory drawn on top of the head (inside the head group)."""
    o = P["outline"]
    if not name:
        return ""
    if name == "beanie":
        dome = "M 345 285 C 340 165, 660 165, 655 285 Z"
        brim = "M 335 262 Q 500 240 665 262 L 668 302 Q 500 282 332 302 Z"
        ribs = "".join(
            f'<path d="M {x} {262 - (abs(500 - x) < 150) * 0} L {x} 300" stroke="#2C8079" stroke-width="5" stroke-linecap="round"/>'
            for x in range(355, 660, 26)
        )
        return (
            outlined(dome, "#3AA39A")
            + outlined(brim, "#3AA39A")
            + f'<clipPath id="brimclip"><path d="{brim}"/></clipPath><g clip-path="url(#brimclip)">{ribs}</g>'
            + outlined(brim, "none")
            + ellipse(500, 168, 34, 32, P["cream"])
        )
    if name == "cap":  # worn backwards: the adjuster opening shows the forehead
        dome = "M 340 292 C 335 160, 665 160, 660 292 Q 500 268 340 292 Z"
        opening = "M 455 288 Q 455 240 500 240 Q 545 240 545 288 Z"
        return (
            outlined(dome, P["navy"])
            + f'<path d="M 500 175 L 500 270" stroke="{P["navy_shade"]}" stroke-width="6"/>'
            + outlined(opening, P["fur"], OUTLINE_W * 0.8)
            + f'<path d="M 462 262 L 538 262" stroke="{P["mint"]}" stroke-width="10" stroke-linecap="round"/>'
            + ellipse(500, 172, 14, 10, P["mint"], width=7)
        )
    if name == "party":
        cone = "M 440 225 L 585 205 L 545 45 Z"
        stripes = "".join(
            f'<path d="M {440 + k * 14} {225 - k * 50} L {585 - k * 10} {205 - k * 46}" stroke="{c}" stroke-width="16"/>'
            for k, c in ((0.6, P["yellow"]), (1.6, P["mint"]), (2.5, P["yellow"]))
        )
        return (
            f'<clipPath id="coneclip"><path d="{cone}"/></clipPath>'
            + outlined(cone, P["pink"])
            + f'<g clip-path="url(#coneclip)">{stripes}</g>'
            + outlined(cone, "none")
            + ellipse(545, 42, 22, 22, P["yellow"])
        )
    if name == "headphones":
        band = "M 268 410 C 250 120, 750 120, 732 410"
        out = thick_line(band, P["navy"], 26)
        for cx in (258, 742):
            out += f'<rect x="{cx - 34}" y="352" width="68" height="118" rx="30" fill="{P["navy"]}" stroke="{o}" stroke-width="{OUTLINE_W}"/>'
            out += f'<rect x="{cx - 18}" y="372" width="36" height="78" rx="16" fill="{P["mint"]}"/>'
        return out
    raise ValueError(f"unknown hat {name!r}")


# ------------------------------------------------------------------ props ---
# paw targets relative to the prop centre: (left paw, right paw)
PAW_TARGETS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "acorn": ((-62, 10), (62, 10)),
    "coffee": ((-64, 18), (64, 18)),
    "cookie": ((-66, 22), (66, 22)),
    "laptop": ((-58, 70), (58, 70)),
    "sketchbook": ((-108, 30), (64, -38)),
}
PROPS = tuple(PAW_TARGETS)


def _acorn(cx: float, cy: float) -> str:
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
        f'<path d="M {cx + k} {cy - 104} L {cx + k + 56} {cy + 18}" stroke="{P["acorn_cap_light"]}" stroke-width="6"/>'
        f'<path d="M {cx + k} {cy - 104} L {cx + k - 56} {cy + 18}" stroke="{P["acorn_cap_light"]}" stroke-width="6"/>'
        for k in range(-150, 190, 32)
    )
    stem = f"M {cx - 6} {cy - 82} Q {cx - 4} {cy - 116} {cx + 20} {cy - 124}"
    return (
        thick_line(stem, P["acorn_cap"], 11)
        + outlined(nut, P["acorn"])
        + f'<path d="M {cx + 28} {cy + 14} Q {cx + 38} {cy + 46} {cx + 20} {cy + 76}" fill="none" '
        f'stroke="{P["acorn_light"]}" stroke-width="11" stroke-linecap="round"/>'
        + f'<clipPath id="acorncap"><path d="{cap}"/></clipPath>'
        + f'<path d="{cap}" fill="{P["acorn_cap"]}"/><g clip-path="url(#acorncap)">{hatch}</g>'
        + outlined(cap, "none")
    )


def _coffee(cx: float, cy: float, steam_phase: float = 0.0) -> str:
    w, h = 116, 124
    x0, y0, yb = cx - w / 2, cy - h / 2, cy + h / 2
    body = (
        f"M {x0} {y0} L {x0 + w} {y0} L {x0 + w - 6} {yb - 14} "
        f"Q {x0 + w - 8} {yb} {cx} {yb} Q {x0 + 8} {yb} {x0 + 6} {yb - 14} Z"
    )
    handle = f"M {x0 + w - 4} {y0 + 28} C {x0 + w + 46} {y0 + 24}, {x0 + w + 46} {y0 + 92}, {x0 + w - 8} {y0 + 88}"
    steam = ""
    for i, dx in enumerate((-26, 0, 26)):
        sway = 8 * math.sin(steam_phase * 2 * math.pi + i * 1.7)
        steam += (
            f'<path d="M {cx + dx} {y0 - 16} C {cx + dx - 16 + sway} {y0 - 44}, {cx + dx + 16 + sway} {y0 - 62}, '
            f'{cx + dx + sway} {y0 - 90}" fill="none" stroke="{P["steam"]}" stroke-width="9" stroke-linecap="round" opacity="0.9"/>'
        )
    return (
        steam
        + thick_line(handle, P["mug"], 20)
        + outlined(body, P["mug"])
        + f'<ellipse cx="{cx}" cy="{y0 + 4}" rx="{w / 2 - 10}" ry="11" fill="{P["coffee"]}"/>'
        + f'<rect x="{x0 + 3}" y="{y0 + 52}" width="{w - 7}" height="32" fill="{P["mint"]}"/>'
        + f'<text x="{cx}" y="{y0 + 78}" font-family="DejaVu Sans Mono, monospace" font-size="27" font-weight="bold" '
        f'fill="{P["navy"]}" text-anchor="middle">&lt;/&gt;</text>'
        + outlined(body, "none")
    )


def _cookie(cx: float, cy: float, bites: int = 1) -> str:
    r = 74
    bite_centres = []
    if bites >= 1:
        bite_centres += [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (-0.95, -0.6, -0.25)]
    if bites >= 2:
        bite_centres += [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (0.35, 0.75)]
    pts = []
    for i in range(140):
        a = 2 * math.pi * i / 140
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        for bx, by in bite_centres:
            rb = 30
            dx, dy = px - bx, py - by
            dist = math.hypot(dx, dy)
            if dist < rb:  # push the point inward until it sits on the bite circle
                ux, uy = (cx - px) / r, (cy - py) / r
                for _ in range(40):
                    px, py = px + ux * 2, py + uy * 2
                    if math.hypot(px - bx, py - by) >= rb:
                        break
        pts.append((px, py))
    shape = smooth_closed(pts)
    chips = "".join(
        f'<ellipse cx="{f(cx + dx)}" cy="{f(cy + dy)}" rx="11" ry="9" fill="{P["choc"]}" transform="rotate({rot} {f(cx + dx)} {f(cy + dy)})"/>'
        for dx, dy, rot in ((-34, -18, 20), (12, -40, -10), (30, 14, 35), (-14, 32, 0), (-46, 22, -25), (40, -12, 10))
    )
    return (
        f'<clipPath id="cookieclip"><path d="{shape}"/></clipPath>'
        + outlined(shape, P["cookie"])
        + f'<g clip-path="url(#cookieclip)"><circle cx="{cx - 18}" cy="{cy - 20}" r="40" fill="{P["cookie_light"]}" opacity="0.6"/>{chips}</g>'
        + outlined(shape, "none")
    )


def _laptop(cx: float, cy: float) -> str:
    lid = f"M {cx - 118} {cy - 95} Q {cx - 118} {cy - 108} {cx - 104} {cy - 108} L {cx + 104} {cy - 108} Q {cx + 118} {cy - 108} {cx + 118} {cy - 95} L {cx + 118} {cy + 58} L {cx - 118} {cy + 58} Z"
    deck = f"M {cx - 128} {cy + 58} L {cx + 128} {cy + 58} L {cx + 142} {cy + 86} Q {cx + 142} {cy + 94} {cx + 132} {cy + 94} L {cx - 132} {cy + 94} Q {cx - 142} {cy + 94} {cx - 142} {cy + 86} Z"
    sticker = (
        ellipse(cx, cy - 25, 44, 44, P["mint"], width=7)
        + f'<text x="{cx}" y="{cy - 12}" font-family="DejaVu Sans Mono, monospace" font-size="34" font-weight="bold" '
        f'fill="{P["navy"]}" text-anchor="middle">&lt;/&gt;</text>'
    )
    heart = f'<path d="M {cx + 70} {cy + 20} c -8 -10 -24 -2 -14 10 l 14 12 l 14 -12 c 10 -12 -6 -20 -14 -10 Z" fill="{P["pink"]}"/>'
    return outlined(lid, P["laptop"]) + sticker + heart + outlined(deck, P["laptop_shade"])


def _sketchbook(cx: float, cy: float) -> str:
    x0, y0, w, h = cx - 140, cy - 70, 190, 165
    pad = f"M {x0} {y0} L {x0 + w} {y0} L {x0 + w} {y0 + h} L {x0} {y0 + h} Z"
    rings = "".join(
        f'<path d="M {x} {y0 - 14} L {x} {y0 + 12}" stroke="{P["laptop_shade"]}" stroke-width="9" stroke-linecap="round"/>'
        for x in range(int(x0) + 22, int(x0 + w) - 10, 26)
    )
    g = "#7A7A86"
    # a doodle of a little acorn and a heart
    doodle = (
        f'<path d="M {x0 + 55} {y0 + 70} C {x0 + 52} {y0 + 110}, {x0 + 78} {y0 + 132}, {x0 + 85} {y0 + 134} '
        f'C {x0 + 92} {y0 + 132}, {x0 + 118} {y0 + 110}, {x0 + 115} {y0 + 70}" fill="none" stroke="{g}" stroke-width="5" stroke-linecap="round"/>'
        f'<path d="M {x0 + 45} {y0 + 72} Q {x0 + 85} {y0 + 30} {x0 + 125} {y0 + 72} Z" fill="none" stroke="{g}" stroke-width="5" stroke-linejoin="round"/>'
        f'<path d="M {x0 + 85} {y0 + 50} L {x0 + 90} {y0 + 36}" stroke="{g}" stroke-width="5" stroke-linecap="round"/>'
        f'<path d="M {x0 + 150} {y0 + 60} c -6 -8 -18 -2 -11 8 l 11 10 l 11 -10 c 7 -10 -5 -16 -11 -8 Z" fill="{P["pink"]}"/>'
    )
    return outlined(pad, P["paper"]) + doodle + rings


def _pencil(cx: float, cy: float) -> str:
    # held by the right paw, pointing down-left onto the pad
    x1, y1 = cx + 92, cy - 80
    x2, y2 = cx + 30, cy + 10
    tip = f"M {x2} {y2} L {x2 - 22} {y2 + 30}"
    return thick_line(f"M {x1} {y1} L {x2} {y2}", P["pencil"], 18) + thick_line(tip, P["pencil_tip"], 12)


def prop(name: str | None, cx: float = 500.0, cy: float = 720.0, t: float = 0.0) -> tuple[str, str]:
    """Return (svg under the paws, svg over the paws) for a held prop."""
    if not name:
        return "", ""
    if name == "acorn":
        return _acorn(cx, cy), ""
    if name == "coffee":
        return _coffee(cx, cy, t), ""
    if name == "cookie":
        return _cookie(cx, cy), ""
    if name == "laptop":
        return _laptop(cx, cy), ""
    if name == "sketchbook":
        return _sketchbook(cx, cy), _pencil(cx, cy)
    raise ValueError(f"unknown prop {name!r}")
