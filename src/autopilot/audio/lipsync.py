"""Mouth tracks and word timings for Byte's voice lines.

- Mouth shapes: Rhubarb Lip Sync (MIT) in phonetic mode, which works on the
  pitched-up voice. Fallback when Rhubarb is missing: loudness-driven mouth.
- Word timings: faster-whisper (tiny.en, CPU, int8). Fallback: words spread over
  the voiced regions in proportion to their length.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from ..character.animator import MouthKey

RHUBARB_CANDIDATES = (
    os.environ.get("RHUBARB_BIN", ""),
    str(Path.home() / "tools" / "rhubarb" / "rhubarb"),
    shutil.which("rhubarb") or "",
)
WHISPER_DIR = Path.home() / "models" / "whisper"


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


def _rhubarb_bin() -> str | None:
    for c in RHUBARB_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def mouth_track(wav: str | Path, dialog: str | None = None) -> list[MouthKey]:
    """Mouth keys for a voice line (Rhubarb, or a loudness fallback)."""
    rb = _rhubarb_bin()
    if rb:
        cmd = [rb, "-f", "tsv", "-r", "phonetic", "--extendedShapes", "GHX", "-q", str(wav)]
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            if dialog:
                fh.write(dialog)
        if dialog:
            cmd += ["--dialogFile", fh.name]
        try:
            out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
        finally:
            Path(fh.name).unlink(missing_ok=True)
        keys = []
        for line in out.strip().splitlines():
            t, shape = line.split("\t")
            keys.append(MouthKey(float(t), shape.strip()))
        return keys
    return loudness_mouth(wav)


def loudness_mouth(wav: str | Path, step: float = 1 / 15) -> list[MouthKey]:
    """Fallback: map short-time loudness to closed / half / open mouth shapes."""
    x, sr = sf.read(str(wav), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = int(sr * step)
    rms = np.array([np.sqrt(np.mean(x[i : i + hop] ** 2) + 1e-12) for i in range(0, len(x), hop)])
    ref = np.percentile(rms, 95) or 1.0
    keys, prev = [], None
    for i, r in enumerate(rms / ref):
        shape = "X" if r < 0.08 else "B" if r < 0.3 else "C" if r < 0.6 else "D"
        if shape != prev:
            keys.append(MouthKey(i * step, shape))
            prev = shape
    return keys


_WHISPER = None


def word_timings(wav: str | Path, text: str | None = None) -> list[Word]:
    """Word-level timestamps for a voice line."""
    global _WHISPER
    try:
        from faster_whisper import WhisperModel

        if _WHISPER is None:
            _WHISPER = WhisperModel("tiny.en", device="cpu", compute_type="int8", download_root=str(WHISPER_DIR))
        segs, _ = _WHISPER.transcribe(str(wav), word_timestamps=True, initial_prompt=text)
        words = [Word(w.start, w.end, w.word.strip()) for s in segs for w in s.words if w.word.strip()]
        if words:
            return words
    except Exception:  # noqa: BLE001 - any failure falls back to the estimate below
        pass
    return estimate_word_timings(wav, text or "")


def estimate_word_timings(wav: str | Path, text: str) -> list[Word]:
    """Spread the script's words over the audio in proportion to their length."""
    words = text.split()
    if not words:
        return []
    x, sr = sf.read(str(wav), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    voiced = np.flatnonzero(np.abs(x) > 0.02)
    t0, t1 = (voiced[0] / sr, voiced[-1] / sr) if len(voiced) else (0.0, len(x) / sr)
    weights = np.array([len(w) + 2 for w in words], dtype=float)
    edges = t0 + (t1 - t0) * np.concatenate([[0], np.cumsum(weights)]) / weights.sum()
    return [Word(float(a), float(b), w) for a, b, w in zip(edges[:-1], edges[1:], words)]
