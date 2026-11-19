"""Byte's voice: Kokoro-82M text-to-speech (local, free, Apache-2.0), natural and warm.

Pipeline: text -> Kokoro (ONNX, CPU) -> 24 kHz wav -> optional pitch shift -> warm EQ and
gentle compression -> loudness-normalised wav.

Model files (not in git; ~120 MB) are downloaded once by ``ensure_models``.
"""

from __future__ import annotations

import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

MODEL_DIR = Path.home() / "models"
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")


@dataclass(frozen=True)
class VoiceStyle:
    voice: str = "af_heart"
    speed: float = 1.05
    semitones: float = 0.0  # pitch shift (0 = natural voice)
    formant: str = "preserved"  # "shifted" = small creature timbre, "preserved" = keeps a human timbre
    lang: str = "en-us"
    warmth: bool = True  # gentle low-shelf boost + soft compression for a cosy, close-mic feel


# Natural, deep and warm (no pitch-up). Pick from the candidates video.
BYTE_VOICE = VoiceStyle(voice="am_michael", speed=0.95)


def ensure_models(model_dir: Path = MODEL_DIR) -> tuple[Path, Path]:
    model_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in MODEL_FILES:
        p = model_dir / name
        if not p.exists():
            urllib.request.urlretrieve(MODEL_URL + name, p)
        paths.append(p)
    return paths[0], paths[1]


_KOKORO = None


def _kokoro():
    global _KOKORO
    if _KOKORO is None:
        from kokoro_onnx import Kokoro

        model, voices = ensure_models()
        _KOKORO = Kokoro(str(model), str(voices))
    return _KOKORO


def speak(text: str, out_wav: str | Path, style: VoiceStyle = BYTE_VOICE) -> Path:
    """Synthesize ``text`` in Byte's voice and write a mono wav. Returns the path."""
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    samples, sr = _kokoro().create(text, voice=style.voice, speed=style.speed, lang=style.lang)
    raw = out_wav.with_suffix(".raw.wav")
    sf.write(raw, np.asarray(samples, dtype=np.float32), sr)
    filters = []
    if style.semitones:
        ratio = 2 ** (style.semitones / 12)
        filters.append(f"rubberband=pitch={ratio:.4f}:formant={style.formant}:transients=smooth")
    if style.warmth:
        filters += [
            "lowshelf=f=180:g=3",  # body
            "highshelf=f=7000:g=-2",  # soften sibilance
            "acompressor=threshold=-20dB:ratio=2.5:attack=15:release=200",
        ]
    filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    filt = ",".join(filters)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", filt, "-ar", "44100", "-ac", "1", str(out_wav)],
        check=True,
    )
    raw.unlink(missing_ok=True)
    return out_wav


def duration(wav: str | Path) -> float:
    info = sf.info(str(wav))
    return info.frames / info.samplerate
