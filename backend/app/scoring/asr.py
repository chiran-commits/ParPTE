"""Speech recognition.

Engines, best first:
  1. faster-whisper (server, CPU or GPU) — word timestamps + word confidence. Prompted to KEEP fillers
     ("um", "uh") because hesitations matter for oral fluency.
  2. Browser transcript (Web Speech API, sent by the frontend) — words only; timings are estimated by
     spreading words over the speech segments detected in the audio.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .audio import AcousticFeatures
from .text import tokens

log = logging.getLogger(__name__)

FILLER_PROMPT = "Umm, let me think like, hmm... Okay, uh, here's what I'm, like, thinking."


@dataclass
class Word:
    w: str
    start: float
    end: float
    prob: float = 0.9


@dataclass
class Transcript:
    text: str
    words: list[Word] = field(default_factory=list)
    engine: str = "none"
    timed: bool = False  # True when timings come from the recogniser, not estimated


@lru_cache(maxsize=1)
def _whisper():
    if os.getenv("PARPTE_DISABLE_ML") == "1" or os.getenv("ASR_ENGINE", "auto") == "browser":
        return None
    try:
        from faster_whisper import WhisperModel

        size = os.getenv("WHISPER_MODEL", "base.en")
        device = os.getenv("WHISPER_DEVICE", "auto")
        compute = os.getenv("WHISPER_COMPUTE", "int8")
        m = WhisperModel(size, device=device, compute_type=compute)
        log.info("Loaded faster-whisper %s on %s", size, device)
        return m
    except Exception as e:
        log.info("faster-whisper unavailable (%s) — using browser transcripts", e)
        return None


def whisper_available() -> bool:
    return _whisper() is not None


def transcribe(wave: np.ndarray | None, client_text: str | None, ac: AcousticFeatures, confidence: float | None = None) -> Transcript:
    m = _whisper()
    if m is not None and wave is not None and len(wave) > 1600:
        try:
            # faster-whisper accepts the waveform directly — no temporary file (those are locked on Windows)
            segs, _ = m.transcribe(wave.astype(np.float32), language="en", word_timestamps=True, initial_prompt=FILLER_PROMPT,
                                   vad_filter=False, beam_size=5, condition_on_previous_text=False, temperature=0.0)
            words: list[Word] = []
            for s in segs:
                for w in s.words or []:
                    t = w.word.strip()
                    if t:
                        words.append(Word(t, float(w.start), float(w.end), float(w.probability)))
            text = " ".join(w.w for w in words)
            return Transcript(text=text, words=words, engine="whisper", timed=True)
        except Exception as e:  # pragma: no cover
            log.warning("whisper failed: %s", e)
    text = (client_text or "").strip()
    conf = confidence if confidence and 0 < confidence <= 1 else 0.8  # Chrome often reports 0 for final results
    return Transcript(text=text, words=_spread(tokens(text, lower=False), ac, conf), engine="browser" if text else "none")


def _spread(words: list[str], ac: AcousticFeatures, conf: float = 0.8) -> list[Word]:
    """Estimate word timings by distributing words over detected speech segments by character length."""
    if not words:
        return []
    segs = ac.segments or [(0.0, max(ac.duration, 0.4 * len(words)))]
    total_speech = sum(e - s for s, e in segs) or 1.0
    total_chars = sum(len(w) + 2 for w in words)
    out, si, cursor = [], 0, segs[0][0]
    for w in words:
        dur = (len(w) + 2) / total_chars * total_speech
        while si < len(segs) - 1 and cursor + dur * 0.5 > segs[si][1]:
            si += 1
            cursor = max(cursor, segs[si][0])
        start = max(cursor, segs[si][0])
        out.append(Word(w, start, start + dur, conf))
        cursor = start + dur
    return out
