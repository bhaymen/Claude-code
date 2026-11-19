"""Turn a timeline (cues, actions, mouth track) into per-frame rig States.

- **Cues** switch expression, pose, outfit, hat or prop at a time.
- **Actions** are short movements layered on top: hop, nod, dance, wave,
  sip, munch, type, celebrate, wink, pop_in.
- **Mouth track** keys come from Rhubarb Lip Sync (or are hand-made).

Procedural life is always on: blinks every 2-5 s, breathing bob, tail sway,
and eased arm blending when the pose changes.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from .rig import EXPRESSIONS, Arm, State, arms_for

ACTIONS = ("hop", "nod", "dance", "wave", "sip", "munch", "type", "celebrate", "wink", "pop_in")


@dataclass(frozen=True)
class Cue:
    t: float
    expression: str | None = None
    pose: str | None = None
    outfit: str | None = None
    hat: str | None = None  # use "" to remove
    prop: str | None = None  # use "" to remove


@dataclass(frozen=True)
class Action:
    t: float
    name: str
    dur: float = 0.6


@dataclass(frozen=True)
class MouthKey:
    """Mouth shape starting at time ``t`` (same format as Rhubarb's TSV output)."""

    t: float
    shape: str


POSE_BLEND_S = 0.22
BLINK_S = 0.16


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _bump(p: float, a: float, b: float) -> float:
    """0 -> 1 -> 0 envelope that rises over [0,a], holds, and falls over [b,1]."""
    if p < a:
        return _ease(p / a)
    if p > b:
        return _ease((1 - p) / (1 - b))
    return 1.0


def _lerp_arm(a: Arm, b: Arm, k: float) -> Arm:
    return Arm(
        upper=a.upper + (b.upper - a.upper) * k,
        elbow=a.elbow + (b.elbow - a.elbow) * k,
        hand=b.hand if k > 0.5 else a.hand,
        front=b.front if k > 0.5 else a.front,
    )


class Timeline:
    def __init__(
        self,
        duration: float,
        cues: list[Cue],
        mouth: list[MouthKey] | None = None,
        actions: list[Action] | None = None,
        base: State | None = None,
        seed: int = 7,
    ) -> None:
        self.duration = duration
        self.cues = sorted(cues, key=lambda c: c.t)
        self.mouth = sorted(mouth or [], key=lambda m: m.t)
        self.actions = sorted(actions or [], key=lambda a: a.t)
        for a in self.actions:
            if a.name not in ACTIONS:
                raise ValueError(f"unknown action {a.name!r}")
        self.base = base or State()
        rng = random.Random(seed)
        self.blinks: list[float] = []
        t = rng.uniform(0.8, 2.0)
        while t < duration:
            self.blinks.append(t)
            if rng.random() < 0.15:  # occasional double blink
                self.blinks.append(t + 0.32)
            t += rng.uniform(2.0, 5.0)

    # -- lookups -----------------------------------------------------------
    def _look_at(self, t: float) -> tuple[State, float, State]:
        """Cue-driven state now, when the last pose change happened, and the state before it."""
        cur = self.base
        prev, changed_at = self.base, 0.0
        for c in self.cues:
            if c.t > t:
                break
            nxt = cur
            if c.expression:
                nxt = nxt.with_expression(c.expression)
            if c.outfit:
                nxt = replace(nxt, outfit=c.outfit)
            if c.hat is not None:
                nxt = replace(nxt, hat=c.hat or None)
            if c.prop is not None:
                nxt = replace(nxt, prop=c.prop or None)
            if c.pose and c.pose != cur.pose:
                prev, changed_at = cur, c.t
                nxt = replace(nxt, pose=c.pose)
            cur = nxt
        return cur, changed_at, prev

    def _mouth_at(self, t: float) -> str | None:
        shape = None
        for m in self.mouth:
            if m.t > t:
                break
            shape = m.shape
        return shape

    # -- main --------------------------------------------------------------
    def state_at(self, t: float, background: str | None = None) -> State:
        s, p_start, prev = self._look_at(t)
        s = replace(s, background=background if background is not None else s.background, t=t)

        # blend arms after a pose change
        k = _ease((t - p_start) / POSE_BLEND_S)
        a_prev, a_new = arms_for(prev), arms_for(s)
        arms = (_lerp_arm(a_prev[0], a_new[0], k), _lerp_arm(a_prev[1], a_new[1], k))

        # procedural life
        eye_open = s.eye_open
        for b in self.blinks:
            if b <= t < b + BLINK_S:
                eye_open = min(eye_open, abs(1 - 2 * (t - b) / BLINK_S))
                break
        bob = 7.0 * math.sin(2 * math.pi * t / 2.6)
        tail = 4.0 * math.sin(2 * math.pi * t / 3.3 + 0.7)
        tilt = -6.0 if s.brows == "skeptical" else 2.0 * math.sin(t * 0.9)
        mouth = self._mouth_at(t) if self.mouth else None
        s = replace(
            s,
            arms=arms,
            eye_open=eye_open,
            bob=bob,
            tail_sway=tail,
            head_tilt=tilt,
            mouth=mouth if mouth is not None else s.mouth,
        )

        for a in self.actions:
            if a.t <= t < a.t + a.dur:
                s = self._apply(a, (t - a.t) / a.dur, t, s)
        return s

    # -- actions -----------------------------------------------------------
    def _apply(self, a: Action, p: float, t: float, s: State) -> State:
        name = a.name
        if name in ("hop", "celebrate"):
            if p < 0.15:  # anticipation
                s = replace(s, squash=1 - 0.1 * _ease(p / 0.15))
            elif p < 0.85:  # airborne
                q = (p - 0.15) / 0.7
                s = replace(s, bob=s.bob - 120 * math.sin(math.pi * q), squash=1.05, tail_sway=s.tail_sway - 10 * math.sin(math.pi * q))
            else:  # landing, with follow-through: the head and tail settle a beat later
                q = (p - 0.85) / 0.15
                s = replace(
                    s,
                    squash=1 - 0.08 * math.sin(math.pi * q),
                    head_dy=10 * math.sin(math.pi * min(1.0, q * 1.4)),
                    tail_sway=s.tail_sway + 8 * math.sin(math.pi * q) * (1 - q),
                )
            if name == "celebrate":
                s = replace(s.with_expression("excited"), arms=(Arm(155, 20, "open"), Arm(155, 20, "open")), bob=s.bob, squash=s.squash)
            return s
        if name == "pop_in":  # rise from below the frame with overshoot
            rise = 1 - _ease(min(1.0, p / 0.55))
            over = math.sin(math.pi * min(1.0, max(0.0, (p - 0.45) / 0.55))) * (1 - p)
            return replace(s, bob=s.bob + 900 * rise - 60 * over, squash=1.08 if p < 0.5 else 1 - 0.08 * over)
        if name == "nod":
            return replace(s, head_dy=14 * math.sin(2 * math.pi * p * 2) * (1 - p))
        if name == "dance":
            w = math.sin(2 * math.pi * p * 3)
            return replace(
                s,
                body_tilt=7 * w,
                head_tilt=s.head_tilt - 6 * w,
                bob=s.bob - 18 * abs(w),
                tail_sway=s.tail_sway + 10 * w,
                eye_style="happy",
            )
        if name == "wave":
            left = s.arms[0] if s.arms else Arm(10, -124)
            return replace(s, arms=(left, Arm(150 + 14 * math.sin(2 * math.pi * p * 3), 25, "open")))
        if name == "wink":
            return replace(s, eye_style="wink")
        if name == "sip" and s.prop:
            lift = _bump(p, 0.25, 0.75)
            s = replace(s, prop_offset=(0.0, -150 * lift), arms=None, pose="hold")
            if lift > 0.6:
                s = replace(s, eye_style="happy", mouth="F", blush=0.9)
            return s
        if name == "munch" and s.prop:
            lift = _bump(p, 0.2, 0.8)
            chew = ("B", "F", "A", "C")[int(t / 0.11) % 4] if lift > 0.6 else s.mouth
            return replace(
                s,
                prop_offset=(0.0, -95 * lift),
                arms=None,
                pose="hold",
                mouth=chew,
                eye_style="happy" if lift > 0.6 else s.eye_style,
                head_dy=4 * math.sin(t * 50) * lift,
            )
        if name == "type" and s.prop:
            tap = int(t / 0.09)
            return replace(s, arms=None, pose="hold", paw_jitter=(-9.0 * (tap % 2), -9.0 * ((tap + 1) % 2)), look=(0.0, 0.6))
        return s


def state_preview(expression: str) -> State:
    """Small helper for sheets: base state with an expression applied."""
    return State().with_expression(expression) if expression in EXPRESSIONS else State()
