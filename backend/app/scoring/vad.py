"""Neural voice-activity detection (Silero VAD v5, MIT licence, bundled as a 2 MB ONNX file).

Much more reliable than an energy threshold when there is background noise, breathing or a fan, so
pauses are measured from real speech boundaries.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
MODEL = Path(__file__).parent / "assets" / "silero_vad.onnx"
CHUNK, CONTEXT, SR = 512, 64, 16000


@lru_cache(maxsize=1)
def _session():
    try:
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.inter_op_num_threads = so.intra_op_num_threads = 1
        return ort.InferenceSession(str(MODEL), sess_options=so, providers=["CPUExecutionProvider"])
    except Exception as e:  # pragma: no cover
        log.info("Silero VAD unavailable (%s) — using energy VAD", e)
        return None


def available() -> bool:
    return MODEL.exists() and _session() is not None


def speech_probs(wave: np.ndarray) -> np.ndarray | None:
    """Speech probability for every 32 ms frame."""
    s = _session()
    if s is None or wave is None or len(wave) < CHUNK:
        return None
    state = np.zeros((2, 1, 128), dtype=np.float32)
    ctx = np.zeros((1, CONTEXT), dtype=np.float32)
    sr = np.array(SR, dtype=np.int64)
    n = len(wave) // CHUNK
    out = np.empty(n, dtype=np.float32)
    for i in range(n):
        x = np.concatenate([ctx, wave[None, i * CHUNK : (i + 1) * CHUNK].astype(np.float32)], axis=1)
        p, state = s.run(None, {"input": x, "state": state, "sr": sr})
        out[i] = p[0, 0]
        ctx = x[:, -CONTEXT:]
    return out


def segments(wave: np.ndarray, on: float = 0.5, off: float = 0.35, min_speech: float = 0.08, min_gap: float = 0.12) -> list[tuple[float, float]] | None:
    probs = speech_probs(wave)
    if probs is None:
        return None
    step = CHUNK / SR
    segs, start, active = [], 0.0, False
    for i, p in enumerate(probs):
        t = i * step
        if not active and p >= on:
            active, start = True, t
        elif active and p < off:
            active = False
            segs.append((start, t))
    if active:
        segs.append((start, len(probs) * step))
    merged: list[tuple[float, float]] = []
    for s, e in segs:
        if merged and s - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return [(s, e) for s, e in merged if e - s >= min_speech]
