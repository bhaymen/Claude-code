"""Turn a timeline (expression/pose cues + mouth track) into per-frame rig States.

Procedural life on top of the cues:
- blinks at random 2-5 s intervals (deterministic per seed)
- breathing bob and tail sway (slow sines)
- eased arm interpolation when the pose changes
- a small squash bounce on emphasis times
- head tilt while "thinking"
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace

from .rig import EXPRESSIONS, POSES, Arm, State


@dataclass(frozen=True)
class Cue:
    t: float
    expression: str | None = None
    pose: str | None = None


@dataclass(frozen=True)
class MouthKey:
    """Mouth shape starting at time ``t`` (same format as Rhubarb's TSV output)."""

    t: float
    shape: str


POSE_BLEND_S = 0.22
BLINK_S = 0.16
BOUNCE_S = 0.28


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


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
        emphasis: list[float] | None = None,
        seed: int = 7,
    ) -> None:
        self.duration = duration
        self.cues = sorted(cues, key=lambda c: c.t)
        self.mouth = sorted(mouth or [], key=lambda m: m.t)
        self.emphasis = sorted(emphasis or [])
        rng = random.Random(seed)
        self.blinks: list[float] = []
        t = rng.uniform(0.8, 2.0)
        while t < duration:
            self.blinks.append(t)
            if rng.random() < 0.15:  # occasional double blink
                self.blinks.append(t + 0.32)
            t += rng.uniform(2.0, 5.0)

    # -- lookups -----------------------------------------------------------
    def _active(self, t: float, attr: str) -> tuple[str, float, str]:
        """Return (current value, time it started, previous value) for a cue attribute."""
        cur, start, prev = ("idle" if attr == "pose" else "neutral"), 0.0, None
        for c in self.cues:
            if c.t > t:
                break
            v = getattr(c, attr)
            if v is not None and v != cur:
                prev, cur, start = cur, v, c.t
        return cur, start, prev or cur

    def _mouth_at(self, t: float, default: str) -> str:
        shape = None
        for m in self.mouth:
            if m.t > t:
                break
            shape = m.shape
        return shape if shape is not None else default

    # -- main --------------------------------------------------------------
    def state_at(self, t: float, background: str | None = None) -> State:
        expr, _, _ = self._active(t, "expression")
        pose, p_start, p_prev = self._active(t, "pose")
        base = replace(State(background=background), **EXPRESSIONS[expr])

        k = _ease((t - p_start) / POSE_BLEND_S)
        prev_arms, new_arms = POSES[p_prev], POSES[pose]
        arms = (_lerp_arm(prev_arms[0], new_arms[0], k), _lerp_arm(prev_arms[1], new_arms[1], k))

        eye_open = base.eye_open
        for b in self.blinks:
            if b <= t < b + BLINK_S:
                phase = (t - b) / BLINK_S
                eye_open = min(eye_open, abs(1 - 2 * phase))  # 1 -> 0 -> 1
                break

        squash = 1.0
        for e in self.emphasis:
            if e <= t < e + BOUNCE_S:
                ph = (t - e) / BOUNCE_S
                squash = 1.0 + 0.06 * math.sin(ph * math.pi * 2) * (1 - ph)
                break

        mouth = self._mouth_at(t, "X" if base.mouth in ("X", "A") else base.mouth) if self.mouth else base.mouth
        tilt = -6.0 if expr == "thinking" else 2.0 * math.sin(t * 0.9)
        return replace(
            base,
            arms=arms,
            eye_open=eye_open,
            mouth=mouth,
            bob=7.0 * math.sin(2 * math.pi * t / 2.6),
            tail_sway=4.0 * math.sin(2 * math.pi * t / 3.3 + 0.7),
            head_tilt=tilt,
            squash=squash,
        )
