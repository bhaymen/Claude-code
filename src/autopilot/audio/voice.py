"""Byte's voice: Kokoro-82M text-to-speech (local, free, Apache-2.0) + a cute pitch-up.

Pipeline: text -> Kokoro (ONNX, CPU) -> 24 kHz wav -> FFmpeg rubberband pitch shift
(formants shifted too, for a small-animal timbre) -> loudness normalised wav.

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
    semitones: float = 4.0  # pitch shift up
    formant: str = "shifted"  # "shifted" = small creature timbre, "preserved" = higher-pitched human
    lang: str = "en-us"


BYTE_VOICE = VoiceStyle()


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
    ratio = 2 ** (style.semitones / 12)
    filt = f"rubberband=pitch={ratio:.4f}:formant={style.formant}:transients=smooth,loudnorm=I=-16:TP=-1.5:LRA=11"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", filt, "-ar", "44100", "-ac", "1", str(out_wav)],
        check=True,
    )
    raw.unlink(missing_ok=True)
    return out_wav


def duration(wav: str | Path) -> float:
    info = sf.info(str(wav))
    return info.frames / info.samplerate
