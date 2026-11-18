"""Loaders for the models you train on Kaggle (see /kaggle). Every loader is optional:
if an artefact is missing, the rule-based scorer is used on its own.

Expected layout inside MODELS_DIR (default: backend/models):

    essay_traits/model.onnx, tokenizer.json, config.json   ← kaggle/02_writing_traits_ellipse.ipynb
    speaking_traits.joblib                                 ← kaggle/01_speaking_pronunciation_fluency.ipynb (part A)
    speaking_ssl/model.onnx, config.json                   ← kaggle/01_speaking_pronunciation_fluency.ipynb (part B)
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

MODELS_DIR = Path(os.getenv("MODELS_DIR", Path(__file__).resolve().parents[2] / "models"))


def _disabled() -> bool:
    return os.getenv("PARPTE_DISABLE_ML") == "1"


# ------------------------------------------------------------------ essay traits (ELLIPSE, 1–5 scale)
@lru_cache(maxsize=1)
def _essay_session():
    d = MODELS_DIR / "essay_traits"
    if _disabled() or not (d / "model.onnx").exists():
        return None
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        cfg = json.loads((d / "config.json").read_text())
        tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        tok.enable_truncation(cfg.get("max_len", 512))
        sess = ort.InferenceSession(str(d / "model.onnx"), providers=["CPUExecutionProvider"])
        log.info("Loaded essay trait model (%s)", cfg.get("base_model"))
        return sess, tok, cfg
    except Exception as e:
        log.warning("Could not load essay model: %s", e)
        return None


@lru_cache(maxsize=512)
def essay_traits(text: str) -> dict | None:
    """Returns {cohesion, syntax, vocabulary, phraseology, grammar, conventions} on a 1–5 scale, or None."""
    s = _essay_session()
    if s is None or not text.strip():
        return None
    import numpy as np

    sess, tok, cfg = s
    enc = tok.encode(text)
    feeds = {"input_ids": np.array([enc.ids], dtype=np.int64), "attention_mask": np.array([enc.attention_mask], dtype=np.int64)}
    feeds = {k: v for k, v in feeds.items() if k in {i.name for i in sess.get_inputs()}}
    out = sess.run(None, feeds)[0][0]
    targets = cfg.get("targets", ["cohesion", "syntax", "vocabulary", "phraseology", "grammar", "conventions"])
    return {t: float(np.clip(v, 1, 5)) for t, v in zip(targets, out)}


# ------------------------------------------------------------------ speaking: feature regressor (speechocean762, 0–10)
@lru_cache(maxsize=1)
def _speaking_reg():
    p = MODELS_DIR / "speaking_traits.joblib"
    if os.getenv("PARPTE_DISABLE_TRAINED") == "1" or not p.exists():  # small shipped model: on unless explicitly disabled
        return None
    try:
        import joblib

        bundle = joblib.load(p)
        log.info("Loaded speaking trait regressor v%s", bundle.get("version"))
        return bundle
    except Exception as e:
        log.warning("Could not load speaking regressor: %s", e)
        return None


def speaking_traits(features: dict) -> dict | None:
    """features → {accuracy, fluency, prosodic} on speechocean762's 0–10 scale."""
    b = _speaking_reg()
    if b is None:
        return None
    import numpy as np

    x = np.array([[float(features.get(f, 0.0) or 0.0) for f in b["feature_names"]]])
    return {k: float(np.clip(m.predict(x)[0], 0, 10)) for k, m in b["models"].items()}


def speaking_metrics() -> dict | None:
    b = _speaking_reg()
    return b.get("metrics") if b else None


# ------------------------------------------------------------------ speaking: fine-tuned SSL model on raw audio
@lru_cache(maxsize=1)
def _speaking_ssl():
    d = MODELS_DIR / "speaking_ssl"
    if _disabled() or not (d / "model.onnx").exists():
        return None
    try:
        import onnxruntime as ort

        cfg = json.loads((d / "config.json").read_text())
        return ort.InferenceSession(str(d / "model.onnx"), providers=["CPUExecutionProvider"]), cfg
    except Exception as e:
        log.warning("Could not load SSL speaking model: %s", e)
        return None


def speaking_ssl(wave) -> dict | None:
    s = _speaking_ssl()
    if s is None or wave is None or len(wave) < 1600:
        return None
    import numpy as np

    sess, cfg = s
    w = wave[: 16000 * cfg.get("max_seconds", 30)].astype(np.float32)
    w = (w - w.mean()) / (w.std() + 1e-7)
    out = sess.run(None, {sess.get_inputs()[0].name: w[None, :]})[0][0]
    return {t: float(np.clip(v, 0, 10)) for t, v in zip(cfg.get("targets", ["accuracy", "fluency", "prosodic"]), out)}


def status() -> dict:
    m = speaking_metrics() or {}
    return {
        "models_dir": str(MODELS_DIR),
        "essay_traits": _essay_session() is not None,
        "speaking_traits": _speaking_reg() is not None,
        "speaking_ssl": _speaking_ssl() is not None,
        "speaking_model_quality": ", ".join(f"{k} r={v['test_pcc']}" for k, v in m.items() if k != "completeness") if m else "",
    }
