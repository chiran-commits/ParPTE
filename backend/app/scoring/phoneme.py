"""Phoneme-level pronunciation analysis (pro engine).

A wav2vec2 CTC model fine-tuned to output IPA phonemes listens to the audio; we compare what it heard
against the expected phonemes of the words (from g2p_en / CMUdict). Phoneme accuracy and per-word
mispronunciations drive the Pronunciation trait. Install with `pip install -r requirements-ml.txt`.
"""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache

import numpy as np

log = logging.getLogger(__name__)

# ARPAbet → simplified IPA classes shared with the normaliser below
ARPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "EH": "ɛ", "ER": "ɚ", "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "r", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}
_NORM = [("ː", ""), ("ˈ", ""), ("ˌ", ""), ("əʊ", "oʊ"), ("iə", "ɪr"), ("ɛə", "ɛr"), ("ɹ", "r"), ("ɾ", "t"),
         ("ɐ", "ʌ"), ("ə", "ʌ"), ("ᵻ", "ɪ"), ("ɝ", "ɚ"), ("ɜ", "ɚ"), ("ɫ", "l"), ("ɒ", "ɑ"), ("g", "ɡ"), ("ʔ", "t"),
         ("n̩", "n"), ("l̩", "l"), ("o", "oʊ"), ("e", "eɪ")]


def _norm(p: str) -> str:
    p = p.strip()
    for a, b in _NORM:
        if a in ("o", "e"):
            if p == a:
                p = b
            continue
        p = p.replace(a, b)
    return p


@lru_cache(maxsize=1)
def _model():
    if os.getenv("PARPTE_DISABLE_ML") == "1":
        return None
    try:
        import torch  # noqa: F401
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        name = os.getenv("PHONEME_MODEL", "facebook/wav2vec2-lv-60-espeak-cv-ft")
        proc = AutoProcessor.from_pretrained(name)
        model = Wav2Vec2ForCTC.from_pretrained(name).eval().to(os.getenv("PHONEME_DEVICE", "cpu"))
        log.info("Loaded phoneme model %s", name)
        return proc, model
    except Exception as e:
        log.info("Phoneme model unavailable (%s) — pronunciation uses ASR-confidence proxy", e)
        return None


@lru_cache(maxsize=1)
def _g2p():
    try:
        from g2p_en import G2p

        return G2p()
    except Exception as e:
        log.info("g2p_en unavailable: %s", e)
        return None


def available() -> bool:
    return _model() is not None and _g2p() is not None


def expected_phonemes(words: list[str]) -> list[tuple[str, list[str]]]:
    g = _g2p()
    out = []
    for w in words:
        phs = [ARPA.get(re.sub(r"\d", "", p)) for p in g(w)] if g else []
        out.append((w, [_norm(p) for p in phs if p]))
    return out


def recognise(wave: np.ndarray) -> tuple[list[str], float]:
    """Returns recognised phonemes and mean posterior confidence of emitted frames."""
    import torch

    proc, model = _model()
    inputs = proc(wave, sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values.to(model.device)).logits[0].float().cpu()
    probs = torch.softmax(logits, -1)
    ids = torch.argmax(logits, -1)
    conf = probs.max(-1).values
    blank = proc.tokenizer.pad_token_id
    keep = ids != blank
    mean_conf = float(conf[keep].mean()) if keep.any() else 0.0
    text = proc.batch_decode(ids[None])[0]
    return [_norm(p) for p in text.split() if p.strip()], mean_conf


def _edit_ops(ref: list[str], hyp: list[str]) -> tuple[int, list[int]]:
    """Edit distance and, for every ref position, 1 if it was matched correctly."""
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), dtype=np.int32)
    d[:, 0] = np.arange(n + 1)
    d[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    ok = [0] * n
    i, j = n, m
    while i > 0 and j > 0:
        if d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            ok[i - 1] = int(ref[i - 1] == hyp[j - 1])
            i, j = i - 1, j - 1
        elif d[i, j] == d[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    return int(d[n, m]), ok


def analyse(wave: np.ndarray, words: list[str]) -> dict | None:
    """Phoneme accuracy for the given words (expected script for RA/RS, recognised words otherwise)."""
    if not available() or wave is None or not words:
        return None
    try:
        exp = expected_phonemes(words)
        ref = [p for _, ps in exp for p in ps]
        hyp, conf = recognise(wave)
        if not ref:
            return None
        dist, ok = _edit_ops(ref, hyp)
        per = dist / len(ref)
        word_scores, k = [], 0
        for w, ps in exp:
            n = len(ps)
            acc = sum(ok[k : k + n]) / n if n else 1.0
            word_scores.append({"word": w, "accuracy": round(acc, 2)})
            k += n
        return {"phoneme_accuracy": max(0.0, 1 - per), "phoneme_confidence": conf, "words": word_scores,
                "n_expected": len(ref), "n_heard": len(hyp)}
    except Exception as e:  # pragma: no cover
        log.warning("phoneme analysis failed: %s", e)
        return None
