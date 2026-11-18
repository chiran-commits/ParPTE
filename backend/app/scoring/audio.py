"""Audio decoding and acoustic features (pure numpy — no ML needed).

Pauses, phonation time, initial latency and pitch variation computed here feed the oral-fluency
scorer whether or not Whisper is available.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
SR = 16000


def decode(data: bytes) -> np.ndarray | None:
    """Any browser format (webm/opus, ogg, mp4, wav) → mono float32 @16 kHz. Needs ffmpeg on PATH."""
    if not data:
        return None
    if data[:4] == b"RIFF":
        try:
            import io
            import wave

            with wave.open(io.BytesIO(data)) as w:
                if w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2:
                    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        except Exception:
            pass
    ff = shutil.which("ffmpeg")
    if not ff:
        log.warning("ffmpeg not found — cannot decode audio")
        return None
    with tempfile.NamedTemporaryFile(suffix=".bin") as f:
        f.write(data)
        f.flush()
        try:
            out = subprocess.run([ff, "-nostdin", "-loglevel", "error", "-i", f.name, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                                 capture_output=True, timeout=60, check=True).stdout
        except Exception as e:
            log.warning("ffmpeg decode failed: %s", e)
            return None
    return np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768 if out else None


def write_wav(wave: np.ndarray, path: str | Path) -> str:
    import wave as wv

    pcm = (np.clip(wave, -1, 1) * 32767).astype(np.int16)
    with wv.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return str(path)


@dataclass
class AcousticFeatures:
    duration: float = 0.0
    speech_time: float = 0.0
    initial_silence: float = 0.0
    segments: list[tuple[float, float]] = field(default_factory=list)
    pauses: list[float] = field(default_factory=list)  # gaps between speech segments (s)
    pitch_st_std: float = 0.0  # pitch variation in semitones (intonation)
    snr_db: float = 0.0

    @property
    def n_pauses(self) -> int:
        return sum(1 for p in self.pauses if p >= 0.45)

    @property
    def n_long_pauses(self) -> int:
        return sum(1 for p in self.pauses if p >= 1.0)

    def as_dict(self) -> dict:
        return {
            "duration": round(self.duration, 2), "speech_time": round(self.speech_time, 2),
            "initial_silence": round(self.initial_silence, 2), "n_segments": len(self.segments),
            "n_pauses": self.n_pauses, "n_long_pauses": self.n_long_pauses,
            "max_pause": round(max(self.pauses), 2) if self.pauses else 0.0,
            "mean_pause": round(float(np.mean(self.pauses)), 2) if self.pauses else 0.0,
            "pitch_st_std": round(self.pitch_st_std, 2), "snr_db": round(self.snr_db, 1),
        }


def acoustic_features(wave: np.ndarray | None) -> AcousticFeatures:
    f = AcousticFeatures()
    if wave is None or len(wave) < SR * 0.2:
        return f
    f.duration = len(wave) / SR
    frame, hop = int(0.025 * SR), int(0.010 * SR)
    n = 1 + (len(wave) - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    frames = wave[idx] * np.hanning(frame)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-10)
    db = 20 * np.log10(rms + 1e-10)
    floor, peak = np.percentile(db, 10), np.percentile(db, 98)
    f.snr_db = float(peak - floor)
    thr = max(floor + 9.0, peak - 32.0)
    voiced = db > thr
    # smoothing: close gaps < 150 ms, drop blips < 80 ms
    voiced = _close_gaps(voiced, 15)
    voiced = _drop_short(voiced, 8)
    segs = _runs(voiced)
    f.segments = [(s * hop / SR, (e * hop + frame) / SR) for s, e in segs]
    if f.segments:
        f.initial_silence = f.segments[0][0]
        f.speech_time = sum(e - s for s, e in f.segments)
        f.pauses = [f.segments[i + 1][0] - f.segments[i][1] for i in range(len(f.segments) - 1)]
    f.pitch_st_std = _pitch_variation(wave, voiced, hop, frame)
    return f


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def _close_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    m = mask.copy()
    runs = _runs(m)
    for (s1, e1), (s2, _) in zip(runs, runs[1:]):
        if s2 - e1 - 1 <= max_gap:
            m[e1:s2] = True
    return m


def _drop_short(mask: np.ndarray, min_len: int) -> np.ndarray:
    m = mask.copy()
    for s, e in _runs(m):
        if e - s + 1 < min_len:
            m[s : e + 1] = False
    return m


def _pitch_variation(wave, voiced, hop, frame) -> float:
    """Autocorrelation F0 on voiced frames → std in semitones. Monotone speech ≈ <1.5 st."""
    win = int(0.04 * SR)
    f0s = []
    lo, hi = SR // 400, SR // 70
    for i in np.flatnonzero(voiced)[::3]:
        s = i * hop
        x = wave[s : s + win]
        if len(x) < win:
            break
        x = x - x.mean()
        ac = np.correlate(x, x, "full")[win - 1 :]
        if ac[0] <= 0:
            continue
        seg = ac[lo:hi]
        k = int(np.argmax(seg)) + lo
        if ac[k] / ac[0] > 0.45:
            f0s.append(SR / k)
    if len(f0s) < 10:
        return 0.0
    st = 12 * np.log2(np.array(f0s) / np.median(f0s))
    st = st[np.abs(st) < 12]
    return float(np.std(st)) if len(st) else 0.0
