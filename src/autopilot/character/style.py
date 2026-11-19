"""Shared palette and SVG drawing helpers for Byte and the wardrobe."""

from __future__ import annotations

import math

VIEWBOX = (1000, 1100)
OUTLINE_W = 11

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
    "mint": "#8FE3C8",
    "navy": "#26365E",
    "navy_shade": "#1C2848",
    "mug": "#FFFFFF",
    "coffee": "#6B3E26",
    "steam": "#E9DCCB",
    "acorn_cap": "#7A4A22",
    "acorn_cap_light": "#9C6534",
    "acorn": "#C98B4A",
    "acorn_light": "#E2AC6E",
    "cookie": "#D9A35E",
    "cookie_light": "#EBC184",
    "choc": "#5A3220",
    "laptop": "#C9D0DA",
    "laptop_shade": "#9AA4B3",
    "paper": "#FFFFFF",
    "pencil": "#F6C445",
    "pencil_tip": "#F2C9A0",
    "red": "#E25D5D",
    "yellow": "#FFD166",
    "pink": "#FF8FB1",
    "bg": "#FFF6EA",
    "bg_circle": "#FFE6C7",
}


def f(x: float) -> str:
    return f"{x:.1f}"


def outlined(path_d: str, fill: str, width: float = OUTLINE_W) -> str:
    return (
        f'<path d="{path_d}" fill="{fill}" stroke="{PALETTE["outline"]}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'
    )


def ellipse(cx, cy, rx, ry, fill, outline=True, width: float = OUTLINE_W) -> str:
    stroke = f' stroke="{PALETTE["outline"]}" stroke-width="{width}"' if outline else ""
    return f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" fill="{fill}"{stroke}/>'


def thick_line(d: str, color: str, width: float, cap: str = "round") -> str:
    """A stroked path with an outline (outline stroke underneath, colour on top)."""
    o = PALETTE["outline"]
    return (
        f'<path d="{d}" fill="none" stroke="{o}" stroke-width="{width + 2 * OUTLINE_W}" '
        f'stroke-linecap="{cap}" stroke-linejoin="round"/>'
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="{cap}" stroke-linejoin="round"/>'
    )


def direction(side: int, angle: float) -> tuple[float, float]:
    a = math.radians(angle)
    return side * math.sin(a), math.cos(a)


def bezier(p, t):
    """Point and unit tangent on a cubic Bezier given 4 control points."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p
    u = 1 - t
    x = u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3
    y = u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3
    dx = 3 * u * u * (x1 - x0) + 6 * u * t * (x2 - x1) + 3 * t * t * (x3 - x2)
    dy = 3 * u * u * (y1 - y0) + 6 * u * t * (y2 - y1) + 3 * t * t * (y3 - y2)
    n = math.hypot(dx, dy) or 1.0
    return x, y, dx / n, dy / n


def smooth_closed(points) -> str:
    """Closed Catmull-Rom spline through points, as an SVG path."""
    n = len(points)
    d = [f"M {f(points[0][0])} {f(points[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C {f(c1[0])} {f(c1[1])}, {f(c2[0])} {f(c2[1])}, {f(p2[0])} {f(p2[1])}")
    return " ".join(d) + " Z"


def star(cx: float, cy: float, r: float, fill: str, points: int = 4, inner: float = 0.35) -> str:
    pts = []
    for i in range(points * 2):
        rr = r if i % 2 == 0 else r * inner
        a = math.pi * i / points - math.pi / 2
        pts.append(f"{f(cx + rr * math.cos(a))},{f(cy + rr * math.sin(a))}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'
