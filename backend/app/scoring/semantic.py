"""Semantic similarity. Uses sentence-transformers when installed (pro engine), else a lexical cosine."""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from .text import tfidf_cosine

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _model():
    if os.getenv("PARPTE_DISABLE_ML") == "1":
        return None
    try:
        from sentence_transformers import SentenceTransformer

        name = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        m = SentenceTransformer(name, device="cpu")
        log.info("Loaded embedding model %s", name)
        return m
    except Exception as e:
        log.info("sentence-transformers not available (%s); using lexical similarity", e)
        return None


def similarity(a: str, b: str) -> float:
    """0..1 similarity between a response and a source text."""
    if not a.strip() or not b.strip():
        return 0.0
    m = _model()
    lexical = tfidf_cosine(a, b)
    if m is None:
        return lexical
    import numpy as np

    va, vb = m.encode([a, b], normalize_embeddings=True)
    sem = float(np.clip(np.dot(va, vb), 0, 1))
    # embeddings alone reward on-topic waffle; blend with lexical overlap of source ideas
    return 0.7 * sem + 0.3 * lexical


def engine_name() -> str:
    return "embeddings" if _model() is not None else "lexical"
