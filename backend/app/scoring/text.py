"""Text utilities shared by every scorer: tokenising, stemming, alignment, keyword coverage."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)*|\d+(?:[.,]\d+)?%?")
SENT_END_RE = re.compile(r"[.!?]+(?=\s|$)")

FILLERS = {"um", "uh", "erm", "er", "ah", "hmm", "mm", "uhm", "umm", "eh"}

STOPWORDS = set(
    """a an the and or but if then than so of to in on at by for with from as is are was were be been being
    it its this that these those there here which who whom whose what when where why how not no nor do does did
    has have had having i me my we our you your he him his she her they them their can could will would shall
    should may might must about into over under up down out off very also just more most such some any each
    other only own same too both all few further once again while during before after above below between""".split()
)

NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80",
    "ninety": "90", "hundred": "100", "percent": "%",
}


def normalize(text: str) -> str:
    return (text or "").replace("’", "'").replace("‘", "'").strip()


def tokens(text: str, lower: bool = True) -> list[str]:
    toks = WORD_RE.findall(normalize(text))
    return [t.lower() for t in toks] if lower else toks


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and t not in FILLERS]


def sentences(text: str) -> list[str]:
    text = normalize(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", normalize(text)) if p.strip()]


_SUFFIXES = (
    "ational", "tional", "ization", "fulness", "ousness", "iveness", "ements", "ement", "ments", "ment",
    "ness", "ities", "ity", "ings", "ing", "edly", "ies", "ied", "ers", "er", "ed", "ly", "es", "s",
)


def stem(word: str) -> str:
    """Tiny, dependency-free suffix stripper. Good enough for keyword matching."""
    w = word.lower()
    if w in NUMBER_WORDS:
        return NUMBER_WORDS[w]
    if len(w) <= 4:
        return w.rstrip("s") if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    if w.endswith("i"):
        w = w[:-1] + "y"
    return w


def stems(text: str) -> list[str]:
    return [stem(t) for t in content_tokens(text)]


# ---------------------------------------------------------------- alignment
@dataclass
class AlignedWord:
    ref: str | None
    hyp: str | None
    op: str  # "ok" | "sub" | "del" (missed) | "ins" (extra)


def _eq(a: str, b: str) -> bool:
    if a == b:
        return True
    return stem(a) == stem(b) and (a.rstrip("s") == b.rstrip("s"))


def align(ref: list[str], hyp: list[str]) -> list[AlignedWord]:
    """Levenshtein alignment at word level (used for Read Aloud content scoring)."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if _eq(ref[i - 1], hyp[j - 1]) else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    out: list[AlignedWord] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (0 if _eq(ref[i - 1], hyp[j - 1]) else 1):
            op = "ok" if _eq(ref[i - 1], hyp[j - 1]) else "sub"
            out.append(AlignedWord(ref[i - 1], hyp[j - 1], op))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            out.append(AlignedWord(ref[i - 1], None, "del"))
            i -= 1
        else:
            out.append(AlignedWord(None, hyp[j - 1], "ins"))
            j -= 1
    out.reverse()
    return out


def lcs_len(a: list[str], b: list[str]) -> int:
    """Longest common subsequence: words spoken in the correct sequence (Repeat Sentence)."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if _eq(x, y) else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------- key points
def keypoint_hits(text: str, key_points: list[dict]) -> list[dict]:
    """Each key point: {"label": str, "keywords": [["word", "synonym"], ...], "min": int}.

    A key point is covered when at least `min` (default: ceil(60%)) of its keyword groups
    appear (by stem) in the response.
    """
    have = set(stems(text)) | set(tokens(text))
    results = []
    for kp in key_points or []:
        groups = kp.get("keywords") or []
        hit_groups = 0
        for g in groups:
            alts = g if isinstance(g, list) else [g]
            if any(_phrase_in(a, have, text) for a in alts):
                hit_groups += 1
        need = kp.get("min") or max(1, math.ceil(len(groups) * 0.6))
        results.append({"label": kp.get("label", ""), "covered": hit_groups >= need, "hits": hit_groups, "of": len(groups)})
    return results


def _phrase_in(phrase: str, have: set[str], raw: str) -> bool:
    parts = tokens(phrase)
    if len(parts) > 1:
        return all(stem(p) in have or p in have or p in STOPWORDS for p in parts)
    return bool(parts) and (stem(parts[0]) in have or parts[0] in have)


# ---------------------------------------------------------------- similarity (lite)
def tfidf_cosine(a: str, b: str) -> float:
    ta, tb = Counter(stems(a)), Counter(stems(b))
    if not ta or not tb:
        return 0.0
    vocab = set(ta) | set(tb)
    # idf over the two docs only rewards shared rare-ish words; use log-scaled tf instead
    dot = sum((1 + math.log(ta[w])) * (1 + math.log(tb[w])) for w in vocab if w in ta and w in tb)
    na = math.sqrt(sum((1 + math.log(c)) ** 2 for c in ta.values()))
    nb = math.sqrt(sum((1 + math.log(c)) ** 2 for c in tb.values()))
    return dot / (na * nb) if na and nb else 0.0


def type_token_ratio(toks: list[str], window: int = 50) -> float:
    """Moving-average TTR — length-robust lexical diversity."""
    if not toks:
        return 0.0
    if len(toks) <= window:
        return len(set(toks)) / len(toks)
    vals = [len(set(toks[i : i + window])) / window for i in range(0, len(toks) - window + 1)]
    return sum(vals) / len(vals)
