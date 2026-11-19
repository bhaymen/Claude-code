"""Cute sound effects and a tiny jingle, synthesized from scratch with numpy.

No samples, no licences: every sound is generated in code, so the library is
free to use commercially and identical on every machine.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def _env(n: int, attack: float = 0.005, decay: float = 8.0) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-decay * t)


def _sweep(f0: float, f1: float, dur: float, curve: float = 1.0) -> np.ndarray:
    t = _t(dur)
    freq = f0 + (f1 - f0) * (t / dur) ** curve
    return np.sin(2 * np.pi * np.cumsum(freq) / SR)


def _lowpass(x: np.ndarray, k: int) -> np.ndarray:
    k = max(1, int(k))
    return np.convolve(x, np.ones(k) / k, mode="same")


def _norm(x: np.ndarray, peak: float = 0.8) -> np.ndarray:
    m = np.max(np.abs(x)) or 1.0
    return (x / m * peak).astype(np.float32)


# ------------------------------------------------------------------ sounds ---
def pop() -> np.ndarray:
    """Bubbly pop: fast downward pitch blip."""
    x = _sweep(1400, 380, 0.09, 0.5) * _env(int(0.09 * SR), 0.001, 38)
    return _norm(x, 0.85)


def boing() -> np.ndarray:
    """Springy boing with a decaying wobble."""
    t = _t(0.55)
    wob = 1 + 0.25 * np.sin(2 * np.pi * 18 * t) * np.exp(-5 * t)
    freq = (180 + 260 * (1 - np.exp(-9 * t))) * wob
    x = np.sin(2 * np.pi * np.cumsum(freq) / SR) * _env(len(t), 0.003, 5.5)
    return _norm(x + 0.3 * np.sin(2 * np.pi * np.cumsum(freq * 2) / SR) * _env(len(t), 0.003, 9), 0.8)


def whoosh(dur: float = 0.42) -> np.ndarray:
    """Airy whoosh: noise with a rising-then-falling envelope and moving lowpass."""
    rng = np.random.default_rng(3)
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    # crude moving filter: blend a heavily and a lightly smoothed copy over time
    dark, bright = _lowpass(noise, 40), _lowpass(noise, 6)
    mix = np.sin(np.linspace(0, np.pi, n))
    x = (dark * (1 - mix) + bright * mix) * np.sin(np.linspace(0, np.pi, n)) ** 2
    return _norm(x, 0.55)


def sparkle() -> np.ndarray:
    """Twinkly chime arpeggio (C6 E6 G6 C7)."""
    out = np.zeros(int(0.9 * SR))
    for i, f0 in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):
        start = int(i * 0.07 * SR)
        t = _t(0.6)
        tone = (np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * f0 * 2.01 * t)) * _env(len(t), 0.002, 7)
        out[start : start + len(tone)] += tone[: len(out) - start]
    return _norm(out, 0.6)


def tap() -> np.ndarray:
    """Keyboard tap."""
    rng = np.random.default_rng(5)
    n = int(0.035 * SR)
    x = _lowpass(rng.standard_normal(n), 3) * _env(n, 0.0005, 120)
    return _norm(x, 0.5)


def sip() -> np.ndarray:
    """Little slurp: filtered noise with a wobbling envelope."""
    rng = np.random.default_rng(7)
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    x = _lowpass(rng.standard_normal(n), 14) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * t)) * np.sin(np.pi * t / t[-1])
    return _norm(x, 0.45)


def crunch() -> np.ndarray:
    """Cookie crunch: a few crackly bursts."""
    rng = np.random.default_rng(11)
    out = np.zeros(int(0.35 * SR))
    for start in (0.0, 0.06, 0.13, 0.21):
        n = int(0.07 * SR)
        burst = _lowpass(rng.standard_normal(n), 2) * _env(n, 0.001, 45)
        s = int(start * SR)
        out[s : s + n] += burst[: len(out) - s]
    return _norm(out, 0.6)


def squeak() -> np.ndarray:
    """Cute rising squeak (the squirrel's 'eek!')."""
    t = _t(0.18)
    x = _sweep(1200, 2600, 0.18, 0.7) * np.sin(np.pi * t / t[-1]) ** 0.5
    vib = 1 + 0.05 * np.sin(2 * np.pi * 30 * t)
    return _norm(x * vib, 0.55)


def _marimba(f0: float, dur: float = 0.5) -> np.ndarray:
    t = _t(dur)
    return (np.sin(2 * np.pi * f0 * t) + 0.25 * np.sin(2 * np.pi * f0 * 4 * t) * np.exp(-30 * t)) * _env(len(t), 0.002, 6)


def jingle(notes=((0.0, 523.25), (0.12, 659.25), (0.24, 783.99), (0.40, 1046.5)), tail: float = 0.6) -> np.ndarray:
    """Short bright marimba sting (default: C E G C)."""
    total = notes[-1][0] + tail
    out = np.zeros(int(total * SR))
    for start, f0 in notes:
        tone = _marimba(f0)
        s = int(start * SR)
        out[s : s + len(tone)] += tone[: len(out) - s]
    return _norm(out, 0.6)


def outro_jingle() -> np.ndarray:
    """Descending-then-up 'see you!' sting (G E C ... G C)."""
    return jingle(((0.0, 783.99), (0.12, 659.25), (0.24, 523.25), (0.48, 783.99), (0.60, 1046.5)), tail=0.8)


LIBRARY = {
    "pop": pop,
    "boing": boing,
    "whoosh": whoosh,
    "sparkle": sparkle,
    "tap": tap,
    "sip": sip,
    "crunch": crunch,
    "squeak": squeak,
    "jingle": jingle,
    "outro_jingle": outro_jingle,
}


# -------------------------------------------------------------------- mix ---
def mix(events: list[tuple[float, str, float]], duration: float) -> np.ndarray:
    """Place (time, sound name, gain) events on a silent track of ``duration`` seconds."""
    out = np.zeros(int(duration * SR), dtype=np.float32)
    for t0, name, gain in events:
        snd = LIBRARY[name]() * gain
        s = int(t0 * SR)
        if s >= len(out):
            continue
        n = min(len(snd), len(out) - s)
        out[s : s + n] += snd[:n]
    peak = np.max(np.abs(out)) or 1.0
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def write_wav(path: str | Path, x: np.ndarray) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def export_library(out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, fn in LIBRARY.items():
        p = out / f"{name}.wav"
        write_wav(p, fn())
        paths.append(p)
    return paths
