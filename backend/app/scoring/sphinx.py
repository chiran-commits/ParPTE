"""Acoustic alignment and Goodness-of-Pronunciation (GOP) with PocketSphinx.

PocketSphinx ships its US-English acoustic model inside the pip package, so this runs on any small CPU
server with no downloads. For every response we:

1. Decode the audio against a grammar built from the words the speaker should have said (the reference
   text for Read Aloud / Repeat Sentence, the transcript otherwise), allowing optional fillers ("um",
   "uh") between words. This gives real word timings, filled pauses and silent pauses.
2. Run a phone-level alignment and read each phone's acoustic score. Scores are normalised per frame by
   the best-scoring senone, so a phone that matches the model well scores near 0 and a mispronounced
   phone scores strongly negative. This is the classic GOP measure (Witt & Young, 2000).
3. Run a free phone-loop recogniser and measure how often it hears the phone that was expected.

The learned model (scoring/models.py) maps these measurements onto expert pronunciation and fluency
ratings; it was trained on speechocean762 with exactly this code.
"""
from __future__ import annotations

import logging
import math
import os
import re
import threading
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

log = logging.getLogger(__name__)

UNITS_PER_NAT = 10000 / 1024  # PocketSphinx log-base-1.0001 scores, shifted by 10 bits
FRAME = 0.01  # seconds per frame
FILLER_WORDS = ["um", "uh", "ah", "er", "hmm"]

_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n: int) -> list[str]:
    if n < 20:
        return [_ONES[n]]
    if n < 100:
        return [_TENS[n // 10]] + ([_ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [_ONES[n // 100], "hundred"] + (["and"] + number_words(n % 100) if n % 100 else [])
    if 1900 < n < 2100 and n % 100:
        return number_words(n // 100) + number_words(n % 100)  # years: nineteen ninety
    if n < 1_000_000:
        return number_words(n // 1000) + ["thousand"] + (number_words(n % 1000) if n % 1000 else [])
    return [str(n)]


@lru_cache(maxsize=1)
def _paths():
    try:
        import pocketsphinx

        base = os.path.join(pocketsphinx.get_model_path(), "en-us")
        return {"hmm": os.path.join(base, "en-us"), "dict": os.path.join(base, "cmudict-en-us.dict"),
                "phone_lm": os.path.join(base, "en-us-phone.lm.bin")}
    except Exception as e:  # pragma: no cover
        log.info("PocketSphinx unavailable: %s", e)
        return None


def available() -> bool:
    return _paths() is not None and os.getenv("PARPTE_DISABLE_SPHINX") != "1"


_ALT_COUNT: dict[str, int] = {}


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, list[str]]:
    lex: dict[str, list[str]] = {}
    p = _paths()
    if not p:
        return lex
    with open(p["dict"], encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            base = re.sub(r"\(\d+\)$", "", parts[0])
            _ALT_COUNT[base] = _ALT_COUNT.get(base, 0) + 1
            if "(" not in parts[0]:
                lex.setdefault(parts[0], parts[1:])
    return lex


_UK_US = [(r"isation$", "ization"), (r"isations$", "izations"), (r"ise$", "ize"), (r"ised$", "ized"), (r"ises$", "izes"),
          (r"ising$", "izing"), (r"yse$", "yze"), (r"ysed$", "yzed"), (r"our$", "or"), (r"ours$", "ors"), (r"ourite$", "orite"),
          (r"oural$", "oral"), (r"tre$", "ter"), (r"tres$", "ters"), (r"ogue$", "og"), (r"ence$", "ense"), (r"ll(ed|ing)$", r"l\1"),
          (r"^maths$", "math"), (r"ae", "e")]
_LTS = [("tion", "SH AH N"), ("sion", "ZH AH N"), ("igh", "AY"), ("tch", "CH"), ("ch", "CH"), ("sh", "SH"), ("th", "TH"),
        ("ph", "F"), ("ck", "K"), ("ng", "NG"), ("qu", "K W"), ("wh", "W"), ("oo", "UW"), ("ee", "IY"), ("ea", "IY"),
        ("ai", "EY"), ("ay", "EY"), ("ou", "AW"), ("ow", "OW"), ("oi", "OY"), ("oy", "OY"), ("au", "AO"), ("aw", "AO"),
        ("er", "ER"), ("ir", "ER"), ("ur", "ER"), ("ar", "AA R"), ("or", "AO R"), ("ie", "IY"), ("ey", "IY"),
        ("a", "AE"), ("e", "EH"), ("i", "IH"), ("o", "AA"), ("u", "AH"), ("b", "B"), ("d", "D"), ("f", "F"), ("g", "G"),
        ("h", "HH"), ("j", "JH"), ("k", "K"), ("l", "L"), ("m", "M"), ("n", "N"), ("p", "P"), ("r", "R"), ("s", "S"),
        ("t", "T"), ("v", "V"), ("w", "W"), ("x", "K S"), ("z", "Z")]
_ACCENTS = str.maketrans("àáâäãåçèéêëìíîïñòóôöõùúûüýÿ", "aaaaaaceeeeiiiinooooouuuuyy")
_extra: dict[str, str] = {}  # words added to the decoders' dictionary at runtime


def pronounce(word: str) -> list[str] | None:
    """Phones for a word missing from CMUdict: UK→US spelling, compound split, then letter-to-sound rules."""
    lex = _lexicon()
    w = word.translate(_ACCENTS)
    if w in lex:
        return lex[w]
    for pat, rep in _UK_US:
        cand = re.sub(pat, rep, w)
        if cand != w and cand in lex:
            return lex[cand]
    for i in range(3, len(w) - 2):  # compounds: microbiome → micro + biome
        a, b = w[:i], w[i:]
        if a in lex and b in lex:
            return lex[a] + lex[b]
    if not w.isalpha():
        return None
    letters = re.sub(r"(.)\1", r"\1", w)  # doubled consonants
    if letters.endswith("e") and len(letters) > 3:
        letters = letters[:-1]  # silent final e
    out, i = [], 0
    while i < len(letters):
        for g, ph in _LTS:
            if letters.startswith(g, i):
                if g == "c":
                    pass
                out += ph.split()
                i += len(g)
                break
        else:
            if letters[i] == "c":
                out.append("S" if i + 1 < len(letters) and letters[i + 1] in "eiy" else "K")
            elif letters[i] == "y":
                out.append("Y" if i == 0 else "IY")
            i += 1
    return out or None


_VOWEL_SET = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}


def non_rhotic(phones: list[str]) -> list[str] | None:
    """British/Australian-style variant: drop R after a vowel unless a vowel follows; ER → AH."""
    out, changed = [], False
    for i, p in enumerate(phones):
        nxt = phones[i + 1] if i + 1 < len(phones) else None
        if p == "R" and out and out[-1] in _VOWEL_SET and (nxt is None or nxt not in _VOWEL_SET):
            changed = True
            continue
        if p == "ER" and (nxt is None or nxt not in _VOWEL_SET):
            out.append("AH")
            changed = True
            continue
        out.append(p)
    return out if changed else None


def _ensure_words(d, words: list[str], seen: set | None = None) -> None:
    """Add runtime words and British (non-rhotic) alternative pronunciations to a decoder's dictionary.
    `seen` tracks what a long-lived decoder already has — adding a word twice corrupts PocketSphinx's dict."""
    if seen is None:
        seen = set()
    lex = _lexicon()
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        base = lex.get(w) or (_extra[w].split() if w in _extra else None)
        try:
            if w in _extra:
                d.add_word(w, _extra[w], update=True)
            alt = non_rhotic(base) if base else None
            if alt:  # alternates must be numbered consecutively after the dictionary's own: word(2), word(3)…
                d.add_word(f"{w}({_ALT_COUNT.get(w, 1) + 1})", " ".join(alt), update=True)
        except Exception:
            pass


def normalise_words(words: list[str]) -> tuple[list[str], list[int]]:
    """Lower-case, expand numbers, drop words missing from the dictionary.
    Returns the alignable words and, for each, the index of the source word it came from."""
    lex = _lexicon()
    out, src = [], []
    for i, w in enumerate(words):
        w = w.lower().replace("’", "'").strip(".,;:!?\"()")
        if not w:
            continue
        if re.fullmatch(r"\d+", w):
            for x in number_words(int(w)):
                out.append(x)
                src.append(i)
            continue
        w = w.rstrip("%")
        if w in lex:
            out.append(w)
            src.append(i)
        elif w.endswith("'s") and w[:-2] in lex:
            out.append(w[:-2])
            src.append(i)
        elif w in _extra or (ph := pronounce(w)):
            if w not in _extra:
                _extra[w] = " ".join(ph)
            out.append(w)
            src.append(i)
    return out, src


def expected_syllables(words: list[str]) -> int:
    lex = _lexicon()
    n = 0
    for w in words:
        phones = lex.get(w) or _extra.get(w, "").split()
        n += sum(1 for p in phones if p[-1].isdigit() or p in VOWELS) or 1
    return n


@dataclass
class Phone:
    p: str
    start: float
    dur: float
    gop: float  # nats per frame relative to the best senone (≤ 0; closer to 0 is better)
    heard: bool = True  # free phone recogniser agreed with the expected phone


@dataclass
class AlignedWord:
    w: str
    start: float
    end: float
    gop: float
    phones: list[Phone] = field(default_factory=list)
    src: int = -1


@dataclass
class SphinxResult:
    words: list[AlignedWord]
    fillers: list[tuple[float, float]]
    pauses: list[tuple[float, float, int]]  # (start, end, index of the word the pause follows)
    ok: bool
    agreement: float
    duration: float
    coverage: float = 1.0

    def features(self) -> dict:
        wg = np.array([w.gop for w in self.words]) if self.words else np.array([-12.0])
        missing = int(round(len(self.words) * (1 / self.coverage - 1))) if 0 < self.coverage < 1 else 0
        if missing:  # words the aligner could not place count as badly pronounced
            wg = np.concatenate([wg, np.full(missing, -8.0)])
        wd = np.array([w.end - w.start for w in self.words]) if self.words else np.array([0.0])
        ph = [p for w in self.words for p in w.phones]
        pg = np.array([p.gop for p in ph]) if ph else None
        return {
            "sx_ok": float(self.ok),
            "gop_mean": float(wg.mean()),
            "gop_median": float(np.median(wg)),
            "gop_p10": float(np.percentile(wg, 10)),
            "gop_min": float(wg.min()),
            "gop_low_ratio": float((wg < -4.0).mean()),
            "gop_very_low_ratio": float((wg < -6.0).mean()),
            "gop_std": float(wg.std()),
            "word_dur_cv": float(wd.std() / (wd.mean() + 1e-6)),
            "phone_gop_p10": float(np.percentile(pg, 10)) if pg is not None else 0.0,
            "has_phones": float(pg is not None),
            "sx_fillers": float(len(self.fillers)),
            "sx_long_fillers": float(sum(1 for a, b in self.fillers if b - a >= 0.25)),
            "sx_pauses": float(sum(1 for s, e, _ in self.pauses if e - s >= 0.25)),
            "sx_long_pauses": float(sum(1 for s, e, _ in self.pauses if e - s >= 1.0)),
            "sx_pause_time": float(sum(e - s for s, e, _ in self.pauses)),
        }


VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}


_local = threading.local()


def _decoder(**kw):
    """A fresh decoder (≈0.2 s to build). Used for the phone pass, which must not reuse a decoder."""
    from pocketsphinx import Decoder

    p = _paths()
    return Decoder(hmm=p["hmm"], dict=p["dict"], lm=None, samprate=16000, loglevel="ERROR", **kw)


def _shared(wide: bool = False) -> "Decoder":
    """One reusable decoder per thread for the grammar and word-alignment passes (safe to reuse).
    The wide-beam variant is the fallback for long passages, where the default beam loses the path."""
    key = "wide" if wide else "default"
    d = getattr(_local, key, None)
    if d is None:
        d = _decoder(beam=1e-100, pbeam=1e-100, wbeam=1e-80) if wide else _decoder(beam=1e-80, pbeam=1e-80, wbeam=1e-60)
        setattr(_local, key, d)
        setattr(_local, key + "_seen", set())
    return d


def _prepare(wide: bool, words: list[str]):
    d = _shared(wide)
    _ensure_words(d, words, getattr(_local, ("wide" if wide else "default") + "_seen"))
    return d


def _grammar(words: list[str]) -> str:
    body = " ".join(f"[<f>] {w}" for w in words) + " [<f>]"
    return f"#JSGF V1.0;\ngrammar g;\n<f> = {' | '.join(FILLER_WORDS)};\npublic <utt> = {body};\n"


def _trim(wave: np.ndarray) -> tuple[np.ndarray, float]:
    """Cut leading/trailing non-speech (±0.25 s) — edge noise is the main cause of alignment failures."""
    from .audio import acoustic_features

    ac = acoustic_features(wave, neural=True)
    if not ac.segments:
        return wave, 0.0
    a = max(0, int((ac.segments[0][0] - 0.25) * 16000))
    b = min(len(wave), int((ac.segments[-1][1] + 0.25) * 16000))
    return wave[a:b], a / 16000


def _real(sg) -> list:
    return [x for x in sg if not x[0].startswith("<") and not x[0].startswith("[") and not x[0].startswith("+")]


def _covers(sg, words: list[str]) -> bool:
    return len(_real(sg)) == len(words)


def _segs(d) -> list[tuple[str, float, float, float]]:
    out = []
    for s in d.seg():
        name = re.sub(r"\(\d+\)$", "", s.word)
        frames = s.end_frame - s.start_frame + 1
        gop = (math.log(s.ascore) if s.ascore > 0 else -700.0) / max(1, frames)
        out.append((name, s.start_frame * FRAME, (s.end_frame + 1) * FRAME, gop))
    return out


def analyse(wave: np.ndarray, words: list[str], phones: bool = True) -> SphinxResult | None:
    """Align `words` (already normalised) to `wave` (float32, 16 kHz).

    Word-level GOP comes from the word alignment pass (robust — it succeeds on ~100 % of recordings and
    correlates r≈0.68 with expert pronunciation ratings on speechocean762). Phone-level detail is added
    when the second, stricter pass succeeds.
    """
    if not available() or wave is None or len(wave) < 1600 or not words:
        return None
    duration = len(wave) / 16000
    filler_times: list[tuple[float, float]] = []
    wave, offset = _trim(wave)
    raw = (np.clip(wave, -1, 1) * 32767).astype(np.int16).tobytes()
    # ---- pass 1: grammar decode with optional fillers → which fillers were spoken, and where
    seq = list(words)
    grammar_ok = False
    for wide in (False, True):
        try:
            d = _prepare(wide, words)
            d.add_jsgf_string("g", _grammar(words))
            d.activate_search("g")
            d.start_utt()
            d.process_raw(raw, full_utt=True)
            d.end_utt()
            if d.hyp():
                sg = _segs(d)
                filler_times = [(st, en) for w, st, en, _ in sg if w in FILLER_WORDS]
                dec = [w for w, *_ in sg if not w.startswith("<") and not w.startswith("[")]
                if any(w not in FILLER_WORDS for w in dec):
                    seq, grammar_ok = dec, True
                    break
        except Exception as e:
            log.debug("grammar decode failed: %s", e)
    # ---- pass 2: word alignment → timings, silences, word-level GOP
    timeline: list[tuple[str, float, float, float]] = []
    partial: list[tuple[str, float, float, float]] = []
    d = None
    # Pronunciation is judged against the plain expected words: letting the aligner insert fillers would let it
    # "explain away" badly pronounced stretches as fillers. Fillers are counted from pass 1 instead.
    for attempt, wide in ((list(words), False), (list(words), True), (seq, True)):
        try:
            d = _prepare(wide, attempt)
            d.set_align_text(" ".join(attempt))
            d.start_utt()
            d.process_raw(raw, full_utt=True)
            d.end_utt()
            if d.hyp():
                sg = _segs(d)
                if _covers(sg, attempt):
                    timeline = sg
                    break
                if len(_real(sg)) > len(_real(partial)):
                    partial = sg
        except Exception as e:
            log.debug("word alignment failed: %s", e)
    if not timeline:
        timeline = _chunked_alignment(wave, list(words))
    coverage = 1.0
    if not timeline and partial:
        timeline = partial  # best partial alignment; the unaligned tail counts as poorly pronounced
        coverage = min(1.0, len(_real(partial)) / len(words))
    if not timeline:
        return SphinxResult([], [], [], False, 0.0, duration)
    aligned, fillers, pauses = [], [(a + offset, b + offset) for a, b in filler_times], []
    for name, st, en, gop in timeline:
        st, en = st + offset, en + offset
        if name in FILLER_WORDS:
            continue
        elif name.startswith("<") or name.startswith("[") or name.startswith("+"):
            if aligned and en - st >= 0.15:
                pauses.append((st, en, len(aligned) - 1))
        else:
            aligned.append(AlignedWord(name, st, en, gop))
    # fillers only count between the first and last real word (edge noise is often mis-decoded as "uh")
    if aligned:
        fillers = [(a, b) for a, b in fillers if a > aligned[0].start and b < aligned[-1].end]
    # ---- pass 3 (optional): phone alignment for per-sound feedback (fresh decoder — reusing one after a
    # silent sub-word failure can crash PocketSphinx)
    if phones:
        ph_words = _align(raw, [w.w for w in aligned]) or _align(raw, [w.w for w in aligned], wide=True)
        if len(ph_words) == len(aligned):
            for aw, pw in zip(aligned, ph_words):
                aw.phones = [Phone(p.p, p.start + offset, p.dur, p.gop) for p in pw.phones]
    res = SphinxResult(aligned, fillers, pauses, grammar_ok, 0.0, duration)
    res.coverage = coverage
    return res


def _align_segs(raw: bytes, words: list[str]) -> tuple[list, float] | None:
    for wide in (False, True):
        try:
            d = _prepare(wide, words)
            d.set_align_text(" ".join(words))
            d.start_utt()
            d.process_raw(raw, full_utt=True)
            d.end_utt()
            if d.hyp():
                sg = _segs(d)
                if not _covers(sg, words):
                    continue
                frames = sum(max(1, int(round((en - st) / FRAME))) for _, st, en, _ in sg)
                total = sum(g * max(1, int(round((en - st) / FRAME))) for w, st, en, g in sg if not w.startswith("<"))
                return sg, total / max(1, frames)
        except Exception:
            pass
    return None


def _chunked_alignment(wave: np.ndarray, words: list[str]) -> list[tuple[str, float, float, float]]:
    """Long-passage fallback: cut the audio at silences and align it piece by piece, letting each piece's
    word boundary move ±3 words around the syllable-proportional estimate and keeping the best fit."""
    from .audio import acoustic_features

    segs = acoustic_features(wave).segments
    if len(segs) < 2 or len(words) < 6:
        return []
    # group speech segments into chunks of ~4–8 s, cutting at the gaps between them
    chunks, cur = [], [segs[0][0], segs[0][1]]
    for a, b in segs[1:]:
        if b - cur[0] > 7.0 and a - cur[1] >= 0.2:
            chunks.append(tuple(cur))
            cur = [a, b]
        else:
            cur[1] = b
    chunks.append(tuple(cur))
    if len(chunks) < 2:
        return []
    syl = [max(1, expected_syllables([w])) for w in words]
    total_speech = sum(b - a for a, b in chunks)
    out, i = [], 0
    for k, (a, b) in enumerate(chunks):
        lo, hi = max(0, int((a - 0.15) * 16000)), min(len(wave), int((b + 0.15) * 16000))
        raw = (np.clip(wave[lo:hi], -1, 1) * 32767).astype(np.int16).tobytes()
        if k == len(chunks) - 1:
            cands = [len(words)]
        else:
            share = (b - a) / total_speech * sum(syl)
            acc, est = 0, i
            while est < len(words) and acc + syl[est] <= share:
                acc += syl[est]
                est += 1
            cands = sorted({min(len(words), max(i + 1, est + d)) for d in range(-3, 4)})
        best = None
        chunk_end = (hi - lo) / 16000
        for j in cands:
            r = _align_segs(raw, words[i:j])
            if not r:
                continue
            last_word_end = max((en for w, st, en, _ in r[0] if not w.startswith("<") and not w.startswith("[")), default=0.0)
            # too few words leaves trailing speech aligned to silence; penalise unexplained time at the end
            fit = r[1] - 6.0 * max(0.0, chunk_end - last_word_end - 0.35)
            if best is None or fit > best[1]:
                best = (r[0], fit, j)
        if best is None:
            return []
        out += [(w, st + lo / 16000, en + lo / 16000, g) for w, st, en, g in best[0]]
        i = best[2]
        if i >= len(words):
            break
    return out


def _align(raw: bytes, seq: list[str], wide: bool = False) -> list[AlignedWord]:
    if not seq:
        return []
    try:
        d = _decoder(beam=1e-100, pbeam=1e-100, wbeam=1e-80) if wide else _decoder(beam=1e-80, pbeam=1e-80, wbeam=1e-60)
        _ensure_words(d, seq)
        d.set_align_text(" ".join(seq))
        d.start_utt()
        d.process_raw(raw, full_utt=True)
        d.end_utt()
        d.set_alignment()
        d.start_utt()
        d.process_raw(raw, full_utt=True)
        d.end_utt()
        out = []
        for wd in d.get_alignment():
            name = re.sub(r"\(\d+\)$", "", wd.name)
            if name.startswith("<") or name.startswith("[") or name in FILLER_WORDS:
                continue
            phones = [Phone(p.name, p.start * FRAME, p.duration * FRAME, p.score / UNITS_PER_NAT / max(1, p.duration)) for p in wd]
            gop = float(np.average([p.gop for p in phones], weights=[p.dur for p in phones])) if phones else -10.0
            out.append(AlignedWord(name, wd.start * FRAME, (wd.start + wd.duration) * FRAME, gop, phones))
        return out
    except Exception as e:
        log.debug("phone alignment failed: %s", e)
        return []


_PHONE_CLASS = {"AH": "AH", "AX": "AH", "ER": "ER", "IH": "IH", "IY": "IY", "Z": "S", "S": "S"}


def _agreement(raw: bytes, aligned: list[AlignedWord]) -> float:
    try:
        d = _decoder(allphone=_paths()["phone_lm"], backtrace=True, lw=2.0, beam=1e-20, pbeam=1e-20)
        d.start_utt()
        d.process_raw(raw, full_utt=True)
        d.end_utt()
        free = [(s.word, s.start_frame * FRAME, (s.end_frame + 1) * FRAME) for s in d.seg()]
    except Exception:
        return 0.0
    hits = total = 0
    j = 0
    for w in aligned:
        for p in w.phones:
            mid = p.start + p.dur / 2
            while j < len(free) - 1 and free[j][2] <= mid:
                j += 1
            heard = free[j][0] if free else ""
            same = _PHONE_CLASS.get(heard, heard) == _PHONE_CLASS.get(p.p, p.p)
            p.heard = same
            hits += same
            total += 1
    return hits / total if total else 0.0
