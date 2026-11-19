"""Speaking scorers for all 8 PTE Academic speaking task types.

Trait maxima (PTE Academic score guide, Aug 2025 update):
  Read Aloud            content (per word, shown /5) · oral fluency 5 · pronunciation 5
  Repeat Sentence       content 3 · oral fluency 5 · pronunciation 5
  Describe Image        content 6 · oral fluency 5 · pronunciation 5
  Re-tell Lecture       content 6 · oral fluency 5 · pronunciation 5
  Summarize Group Disc. content 6 · oral fluency 5 · pronunciation 5
  Respond to Situation  content 6 · oral fluency 5 · pronunciation 5
  Answer Short Question vocabulary 1
For open-response tasks, Content 0 ⇒ the whole item scores 0 (Pearson rule).
"""
from __future__ import annotations

import logging
import re

import numpy as np

from . import models, phoneme, sphinx
from .asr import Transcript, transcribe
from .audio import AcousticFeatures, AudioDecodeError, acoustic_features, decode
from .semantic import similarity
from .text import FILLERS, STOPWORDS, align, keypoint_hits, lcs_len, tokens

log = logging.getLogger(__name__)

SPEAKING_TASKS = {"read_aloud", "repeat_sentence", "describe_image", "retell_lecture", "answer_short_question",
                  "summarize_group_discussion", "respond_to_situation"}


def _t(name, score, mx, note="", raw=None):
    s = float(max(0, min(mx, score)))
    return {"name": name, "score": round(s), "max": mx, "raw": round(raw if raw is not None else s, 2), "note": note}


# =================================================================== helpers
def interp(x: float, xs: list[float], ys: list[float]) -> float:
    return float(np.interp(x, xs, ys))


def so_to_pte(x: float) -> float:
    """speechocean762 expert scale (0–10) → PTE trait band (0–5)."""
    return interp(x, [3.0, 4.5, 6.0, 7.3, 8.5, 9.5], [0, 1, 2, 3, 4, 5])


FUNCTION_WORDS = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "and", "or", "but", "is", "are", "was", "were",
                  "my", "your", "their", "his", "her", "its", "this", "that", "these", "those", "from", "by", "as", "be"}

PHONE_TIPS = {
    "TH": "the 'th' in think (tongue between the teeth)", "DH": "the 'th' in this (voiced, tongue between the teeth)",
    "V": "'v' (top teeth on the lower lip, voiced)", "W": "'w' (rounded lips, no teeth)", "R": "the English 'r' (tongue doesn't touch the roof)",
    "L": "'l' (tongue tip on the ridge behind the teeth)", "Z": "'z' (a buzzing 's')", "ZH": "the 's' in measure",
    "SH": "'sh'", "CH": "'ch'", "JH": "'j' as in job", "NG": "'ng' as in sing", "IY": "the long 'ee' in see",
    "IH": "the short 'i' in sit", "AE": "the 'a' in cat (open mouth)", "AH": "the 'u' in cup", "ER": "the 'ir' in bird",
    "UW": "the long 'oo' in food", "UH": "the short 'oo' in book", "OW": "the 'o' in go", "EY": "the 'ay' in day",
    "AY": "the 'i' in time", "AW": "the 'ow' in now", "OY": "the 'oy' in boy", "AA": "the 'a' in father", "AO": "the 'aw' in law",
    "EH": "the 'e' in bed", "T": "a crisp final 't'", "D": "a clear final 'd'", "S": "a clear final 's'", "K": "'k'", "P": "'p'",
    "B": "'b'", "G": "'g'", "F": "'f'", "HH": "'h'", "M": "'m'", "N": "'n'", "Y": "'y' as in yes",
}


# =================================================================== disfluencies from the transcript
def transcript_disfluencies(tr: Transcript) -> dict:
    lw = [tokens(w.w)[0] for w in tr.words if tokens(w.w)]
    reps = sum(1 for a, b in zip(lw, lw[1:]) if a == b and a not in FILLERS)
    reps += sum(1 for i in range(len(lw) - 3) if lw[i : i + 2] == lw[i + 2 : i + 4])  # "the cat the cat"
    false_starts = sum(1 for a, b in zip(lw, lw[1:]) if len(a) >= 2 and b.startswith(a) and b != a)
    false_starts += sum(1 for w in tr.words if w.w.endswith("-"))
    lexical = [w for w, t in zip([w for w in tr.words if tokens(w.w)], lw) if t not in FILLERS]
    return {"n_words": len(lexical), "t_fillers": sum(t in FILLERS for t in lw), "repetitions": reps, "false_starts": false_starts,
            "mean_word_prob": float(np.mean([w.prob for w in lexical])) if lexical else 0.0}


# =================================================================== oral fluency
def fluency_rule(f: dict, d: dict, sx, task: str) -> tuple[float, float, list[str], dict]:
    """Evidence-based mapping of the PTE oral-fluency rubric. Returns (score, cap, tips, evidence).

    A high band needs positive evidence — long runs of speech, a natural rate, no long pauses — rather than
    merely the absence of detected problems. The cap encodes the rubric's hard limits (e.g. Good (3) allows
    no long pauses; Intermediate (2) allows one; two or more ⇒ Limited)."""
    tips: list[str] = []
    syl = f["syllables"]
    if syl < 3 and d["n_words"] < 3:
        return 0.0, 0.0, ["Too little speech was detected to assess fluency."], {}
    mid_phrase = 0
    if sx is not None:
        for st, en, i in sx.pauses:
            if en - st >= 0.3 and 0 <= i < len(sx.words) and sx.words[i].w in FUNCTION_WORDS:
                mid_phrase += 1
    # Hard evidence only: fillers the recogniser transcribed, or acoustic fillers lasting ≥0.25 s (short "uh"
    # detections fire even for fluent speakers). Long pauses come from the neural VAD. The learned model
    # still sees the raw counts.
    sx_long_fillers = sum(1 for a, b in sx.fillers if b - a >= 0.25) if sx is not None else 0
    fillers = int(max(sx_long_fillers, d["t_fillers"]))
    long_p = int(f["n_long_pauses"])
    hes = fillers + mid_phrase
    breaks = d["repetitions"] + d["false_starts"]
    short = task in {"repeat_sentence", "answer_short_question"}
    mlr_score = interp(f["mlr_syl"], [1.5, 3, 5, 7, 10], [0.5, 2, 3.2, 4.2, 5])
    if short and f["n_pauses"] == 0:
        mlr_score = max(mlr_score, 4.5)  # a short sentence said in one breath has no room for longer runs
    rate = f["speech_rate_sps"]
    # anchors from speechocean762: 2.0 syllables/s for expert fluency ≤4, 2.9 for 6–7, 3.6 for 9–10
    rate_score = interp(rate, [1.4, 2.0, 2.5, 2.9, 3.25, 3.55, 3.85], [0.3, 1.3, 2.2, 3.0, 3.8, 4.5, 5])
    if rate > 5.8:  # fluent native speech rarely exceeds ~5.5 syllables/s; beyond that words blur together
        rate_score -= min(3.0, (rate - 5.8) * 2.0)
    s = 0.5 * mlr_score + 0.5 * rate_score
    s -= 0.45 * max(0, hes - 1) + 0.6 * breaks + 0.8 * long_p
    if 0 < f["pitch_st_std"] < 1.2 and syl >= 12:
        s -= 0.4
    cap = 5.0
    if long_p >= 2:
        cap = 1.5
    elif long_p == 1:
        cap = 2.5
    if hes >= 5:
        cap = min(cap, 2.0)
    elif hes >= 3:
        cap = min(cap, 3.0)
    elif hes >= 2:
        cap = min(cap, 4.0)
    if breaks >= 3:
        cap = min(cap, 2.5)
    elif breaks >= 1:
        cap = min(cap, 4.0)
    if f["mlr_syl"] < 3 and syl >= 12:
        cap = min(cap, 2.0)
    if rate > 7.5:
        cap = min(cap, 2.0)
    elif rate > 6.5:
        cap = min(cap, 3.0)
    # tips with specifics
    if long_p:
        where = [sx.words[i].w for st, en, i in sx.pauses if en - st >= 1.0 and i < len(sx.words)][:3] if sx else []
        tips.append(f"{long_p} long pause(s){' after: ' + ', '.join(where) if where else ''}. In PTE a single long pause caps fluency at Intermediate. Keep talking even after a mistake.")
    if fillers:
        tips.append(f"{fillers} filler(s) (um/uh) detected. Replace them with a short silent breath at a natural break.")
    if mid_phrase:
        tips.append(f"{mid_phrase} hesitation(s) in the middle of a phrase (e.g. after 'the' or 'of'). Pause only at commas and full stops.")
    if breaks:
        tips.append(f"{breaks} repetition(s) or restart(s). Don't go back to fix a word; carry on.")
    if rate < 2.4 and syl >= 8:
        tips.append(f"Your pace was slow ({rate:.1f} syllables/s). Aim for 3–4 syllables per second, like a news reader.")
    elif rate > 6.0:
        tips.append(f"You rushed ({rate:.1f} syllables/s). Slow slightly so words don't run together.")
    if f["mlr_syl"] < 4 and syl >= 12:
        tips.append(f"Speech came in short bursts (about {f['mlr_syl']:.0f} syllables between pauses). Join words into phrases of 5–8 words.")
    if 0 < f["pitch_st_std"] < 1.2 and syl >= 12:
        tips.append("Your intonation was flat. Let your voice rise and fall and stress the key words.")
    if f["initial_silence"] > 2.5:
        tips.append("You started late. Begin within 1–2 s of the tone; the real test closes the microphone after 3 s of silence.")
    ev = {"syllables_per_sec": round(rate, 2), "syllables_between_pauses": round(f["mlr_syl"], 1), "long_pauses": long_p,
          "fillers": fillers, "mid_phrase_hesitations": mid_phrase, "repetitions_restarts": breaks,
          "pitch_variation_semitones": round(f["pitch_st_std"], 2)}
    return max(0.0, min(5.0, s)), cap, tips, ev


# =================================================================== pronunciation
def pronunciation_rule(f: dict) -> float:
    """Word-level GOP (calibrated on speechocean762) → 0–5."""
    # anchors from speechocean762: mean word GOP is −3.4 for expert accuracy ≤4, −2.4 for 6–7, −1.7 for 9–10
    s = interp(f["gop_mean"], [-4.0, -3.3, -2.8, -2.3, -1.9, -1.6], [0, 1, 2, 3, 4, 5])
    s -= 2.5 * max(0.0, f["gop_low_ratio"] - 0.08) + 3.0 * f["gop_very_low_ratio"]
    return max(0.0, min(5.0, s))


def word_feedback(sx, limit: int = 8) -> tuple[list[dict], list[str]]:
    """Per-word pronunciation verdicts and the sounds that most often went wrong."""
    if sx is None or not sx.words:
        return [], []
    g = np.array([w.gop for w in sx.words])
    med = float(np.median(g))
    out, sounds = [], {}
    for w in sx.words:
        bad = w.gop < -4.0 or (w.gop < med - 1.8 and w.gop < -3.0)
        weak = not bad and (w.gop < -3.0 or w.gop < med - 1.2)
        worst = min(w.phones, key=lambda p: p.gop) if w.phones else None
        if (bad or weak) and worst is not None and worst.gop < -4.0:
            key = re.sub(r"\d", "", worst.p)
            sounds[key] = sounds.get(key, 0) + 1
        out.append({"word": w.w, "level": "bad" if bad else "weak" if weak else "good", "gop": round(w.gop, 2),
                    "sound": re.sub(r"\d", "", worst.p) if (bad or weak) and worst is not None else None})
    top = [PHONE_TIPS.get(k, k) for k, _ in sorted(sounds.items(), key=lambda kv: -kv[1])[:3]]
    return out, top


def coherence(text: str) -> tuple[float, str | None]:
    """Penalise keyword lists and word salad in open responses: natural English is ~40–50 % function words."""
    toks = [t for t in tokens(text) if t not in FILLERS]
    n = len(toks)
    if n < 8:
        return 1.0, None
    fw = sum(t in STOPWORDS for t in toks) / n
    uniq = len(set(toks)) / n
    factor, msg = 1.0, None
    if fw < 0.16:
        factor, msg = 0.35, "This sounded like a list of keywords, not sentences. PTE content needs connected, meaningful sentences."
    elif fw < 0.26:
        factor, msg = 0.7, "Some of your answer was disconnected words. Use full sentences that link your ideas."
    if uniq < 0.45:
        factor, msg = min(factor, 0.6), "You repeated the same words a lot. Vary your wording and add new information."
    return factor, msg


# =================================================================== content
def _ra_content(ref_text: str, hyp_text: str) -> tuple[float, dict]:
    ref, hyp = tokens(ref_text), [t for t in tokens(hyp_text) if t not in FILLERS]
    al = align(ref, hyp)
    errors = sum(1 for a in al if a.op != "ok")
    correct = sum(1 for a in al if a.op == "ok")
    acc = max(0.0, (len(ref) - errors) / len(ref)) if ref else 0.0
    return 5 * acc, {"alignment": [a.__dict__ for a in al], "errors": errors, "correct": correct, "total": len(ref),
                     "match_rate": correct / max(1, len([a for a in al if a.hyp]))}


def _rs_content(ref_text: str, hyp_text: str) -> tuple[float, dict]:
    ref, hyp = tokens(ref_text), [t for t in tokens(hyp_text) if t not in FILLERS]
    seq = lcs_len(ref, hyp)
    ratio = seq / len(ref) if ref else 0
    score = 3 if ratio >= 0.999 else 2 if ratio >= 0.5 else 1 if ratio > 0.1 else 0
    al = align(ref, hyp)
    return score, {"alignment": [a.__dict__ for a in al], "in_sequence": seq, "total": len(ref), "ratio": round(ratio, 3),
                   "match_rate": sum(1 for a in al if a.op == "ok") / max(1, len([a for a in al if a.hyp]))}


_TREND = r"\b(increase|increased|rise|rose|grow|grew|growth|decline|declined|decrease|fell|drop|dropped|peak|peaked|steady|stable|fluctuat\w*|surge\w*|plummet\w*)\b"
_COMPARE = r"\b(highest|lowest|largest|smallest|more than|less than|compared|whereas|while|twice|half|majority|minority|followed by|than)\b"
_CONCLUDE = r"\b(in conclusion|overall|to conclude|in summary|it is clear|it can be seen|we can see|this shows|this indicates)\b"


def _di_content(text: str, q: dict) -> tuple[float, dict, list[str]]:
    hits = keypoint_hits(text, q.get("key_points", []))
    cover = sum(h["covered"] for h in hits) / max(1, len(hits))
    numbers = len(re.findall(r"\b\d+(?:\.\d+)?\b|percent|per cent", text, re.I))
    numbers += sum(1 for t in tokens(text) if t in {"one", "two", "three", "four", "five", "ten", "twenty", "thirty", "forty",
                                                       "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million"})
    feats = {"trend": bool(re.search(_TREND, text, re.I)), "comparison": bool(re.search(_COMPARE, text, re.I)),
             "conclusion": bool(re.search(_CONCLUDE, text, re.I)), "data_points": numbers}
    structure = (0.3 * feats["trend"] + 0.3 * feats["comparison"] + 0.2 * feats["conclusion"] + 0.2 * min(1, numbers / 3))
    raw = 6 * (0.65 * cover + 0.35 * structure)
    tips = [f"Mention: {h['label']}." for h in hits if not h["covered"]][:4]
    if not feats["conclusion"]:
        tips.append("Finish with an overall conclusion ('Overall, the chart shows ...').")
    if numbers < 2:
        tips.append("Quote specific figures from the image.")
    return raw, {"key_points": hits, **feats}, tips


def _open_content(text: str, q: dict, source: str, speakers: list[str] | None = None) -> tuple[float, dict, list[str]]:
    hits = keypoint_hits(text, q.get("key_points", []))
    cover = sum(h["covered"] for h in hits) / max(1, len(hits))
    sim = similarity(text, source)
    raw = 6 * (0.7 * cover + 0.3 * min(1.0, sim / 0.4))
    tips = [f"Missed: {h['label']}." for h in hits if not h["covered"]][:5]
    detail = {"key_points": hits, "similarity": round(sim, 3)}
    if speakers:
        # Summarize Group Discussion: every speaker's view must be reported
        covered_by = {s: any(h["covered"] for h in hits if h["label"].lower().startswith(s.lower())) for s in speakers}
        missing = [s for s, ok in covered_by.items() if not ok]
        if missing:
            raw = min(raw, 6 * (1 - len(missing) / len(speakers)) + 0.5)
            tips.insert(0, "You didn't report the view of: " + ", ".join(missing) + ".")
        detail["speakers_covered"] = covered_by
    return raw, detail, tips


def _rts_content(text: str, q: dict) -> tuple[float, dict, list[str]]:
    funcs = q.get("functions", [])
    low = text.lower()
    done = [{"label": fn["label"], "ok": any(re.search(p, low) for p in fn["patterns"])} for fn in funcs]
    fcov = sum(d["ok"] for d in done) / max(1, len(done))
    polite = bool(re.search(r"\b(could|would|may i|i was wondering|i'm sorry|i am sorry|apologi[sz]e|please|thank you|appreciate)\b", low))
    first_person = bool(re.search(r"\b(i|i'm|i'd|my|we)\b", low))
    hits = keypoint_hits(text, q.get("key_points", []))
    rel = sum(h["covered"] for h in hits) / max(1, len(hits)) if hits else similarity(text, q.get("situation", "")) / 0.3
    raw = 6 * (0.5 * fcov + 0.25 * min(1.0, rel) + 0.15 * polite + 0.1 * first_person)
    tips = [f"You didn't {d['label'].lower()}." for d in done if not d["ok"]]
    if not polite:
        tips.append("Use polite, situation-appropriate language (Could I…, Would it be possible…, I'm sorry…).")
    if not first_person:
        tips.append("Respond in the first person, as if you are actually in the situation.")
    return raw, {"functions": done, "polite": polite, "key_points": hits}, tips


# =================================================================== acoustic features (model inputs)
# These are computed from the audio and the words the speaker was meant to say — never from a browser
# transcript — so a recogniser that "tidies up" speech can't hide pauses, fillers or mispronunciations.
# training/train_speaking.py fits the trait models on speechocean762 with exactly this function.
SPEAKING_FEATURES = [
    "span", "speech_time", "phonation_ratio", "syllables", "speech_rate_sps", "articulation_rate_sps", "mlr_syl",
    "pauses_per_min", "n_pauses", "n_long_pauses", "mean_pause", "max_pause", "initial_silence",
    "pitch_st_std", "intensity_std", "syl_ratio", "words_per_sec",
    "gop_mean", "gop_median", "gop_p10", "gop_min", "gop_low_ratio", "gop_very_low_ratio", "gop_std", "word_dur_cv",
    "sx_fillers", "sx_pauses", "sx_long_pauses", "sx_pause_time",
]


def acoustic_model_features(wave, words: list[str], ac: AcousticFeatures | None = None, sx=None) -> dict:
    from . import sphinx

    ac = ac or acoustic_features(wave)
    norm, _ = sphinx.normalise_words(words)
    if sx is None:
        sx = sphinx.analyse(wave, norm, phones=False) if norm else None
    f: dict = {}
    segs = ac.segments
    span = (segs[-1][1] - segs[0][0]) if segs else 0.0
    f["span"] = span
    f["speech_time"] = ac.speech_time
    f["phonation_ratio"] = ac.speech_time / span if span else 0.0
    f["syllables"] = float(ac.syllables)
    f["speech_rate_sps"] = ac.syllables / span if span else 0.0
    f["articulation_rate_sps"] = ac.syllables / ac.speech_time if ac.speech_time else 0.0
    # mean length of run: syllables between pauses of ≥ 250 ms
    runs, cur, k = [], 0, 0
    st = ac.syllable_times
    for i, (s0, e0) in enumerate(segs):
        while k < len(st) and st[k] <= e0:
            cur += st[k] >= s0
            k += 1
        nxt = segs[i + 1][0] if i + 1 < len(segs) else None
        if nxt is None or nxt - e0 >= 0.25:
            runs.append(cur)
            cur = 0
    f["mlr_syl"] = float(np.mean(runs)) if runs else 0.0
    p = [x for x in ac.pauses if x >= 0.25]
    f["n_pauses"] = float(len(p))
    f["pauses_per_min"] = 60 * len(p) / span if span else 0.0
    f["n_long_pauses"] = float(sum(1 for x in p if x >= 1.0))
    f["mean_pause"] = float(np.mean(p)) if p else 0.0
    f["max_pause"] = float(max(p)) if p else 0.0
    f["initial_silence"] = ac.initial_silence
    f["pitch_st_std"] = ac.pitch_st_std
    f["intensity_std"] = ac.intensity_std
    exp_syl = sphinx.expected_syllables(norm) if norm else 0
    f["syl_ratio"] = ac.syllables / exp_syl if exp_syl else 0.0
    f["words_per_sec"] = len(norm) / span if span else 0.0
    sxf = sx.features() if sx else {}
    for k2 in ["gop_mean", "gop_median", "gop_p10", "gop_min", "gop_low_ratio", "gop_very_low_ratio", "gop_std", "word_dur_cv",
               "sx_fillers", "sx_pauses", "sx_long_pauses", "sx_pause_time"]:
        f[k2] = float(sxf.get(k2, 0.0 if not k2.startswith("gop") else -12.0))
    return f


def extract_features(wave, reference_text: str | None = None, client_transcript: str | None = None) -> dict:
    """Training/inference helper: model features for one recording of `reference_text`."""
    words = tokens(reference_text or client_transcript or "", lower=True)
    return acoustic_model_features(wave, words)


# =================================================================== entry point
def _intended_words(al: list) -> list[str]:
    """What the speaker was trying to say, in the order they said it (Read Aloud / Repeat Sentence):
    matched and substituted words use the reference word (a substitution is evidence of a mispronunciation),
    inserted words use what was heard, skipped words are left out."""
    out = []
    for a in al:
        if a.op in ("ok", "sub"):
            out.append(a.ref)
        elif a.op == "ins":
            out.append(a.hyp)
    return out


def score(task: str, q: dict, audio: bytes | None, client_transcript: str | None = None,
          client_confidence: float | None = None) -> dict:
    if not audio and task != "answer_short_question":
        raise AudioDecodeError("No recording was received. Check that the browser has microphone permission and try again.")
    wave = decode(audio) if audio else None  # raises AudioDecodeError rather than silently scoring the transcript
    ac = acoustic_features(wave)
    tr = transcribe(wave, client_transcript, ac, confidence=client_confidence)
    text = tr.text
    d = transcript_disfluencies(tr)
    feedback: list[str] = []
    detail: dict = {"transcript": text, "asr_engine": tr.engine, "acoustics": ac.as_dict()}

    if task == "answer_short_question":
        answers = [a.lower() for a in q.get("answers", [])]
        low = " " + " ".join(tokens(text)) + " "
        ok = any(f" {' '.join(tokens(a))} " in low for a in answers)
        if not ok:
            feedback.append(f"Expected: {q.get('answers', ['?'])[0]}. Answer with one or a few words.")
        return {"score": 1 if ok else 0, "max": 1, "traits": [_t("Vocabulary", 1 if ok else 0, 1)], "feedback": feedback,
                "detail": detail | {"expected": q.get("answers", [])}}

    # ---------------- content
    intended: list[str] = [t for t in tokens(text) if t not in FILLERS]
    word_acc = None
    if task == "read_aloud":
        c, cd = _ra_content(q["text"], text)
        content = _t("Content", c, 5, f"{cd['correct']}/{cd['total']} words correct, {cd['errors']} error(s)", c)
        word_acc = cd["correct"] / max(1, cd["total"])
        detail.update(cd)
        if cd["errors"]:
            feedback.append("Read every word exactly as written. Each omission, insertion or substitution is an error.")
    elif task == "repeat_sentence":
        c, cd = _rs_content(q["text"], text)
        content = _t("Content", c, 3, f"{cd['in_sequence']}/{cd['total']} words in sequence", c)
        word_acc = cd["in_sequence"] / max(1, cd["total"])
        detail.update(cd)
        if c < 3:
            feedback.append("Repeat the sentence word for word. If you lose part of it, keep speaking fluently anyway.")
    elif task == "describe_image":
        c, cd, tips = _di_content(text, q)
        content = _t("Content", c, 6, "", c)
        detail.update(cd)
        feedback += tips
    elif task == "retell_lecture":
        c, cd, tips = _open_content(text, q, q.get("transcript", ""))
        content = _t("Content", c, 6, "", c)
        detail.update(cd)
        feedback += tips
    elif task == "summarize_group_discussion":
        speakers = sorted({t["speaker"] for t in q.get("turns", [])})
        source = " ".join(t["text"] for t in q.get("turns", []))
        c, cd, tips = _open_content(text, q, source, speakers)
        content = _t("Content", c, 6, "", c)
        detail.update(cd)
        feedback += tips
    elif task == "respond_to_situation":
        c, cd, tips = _rts_content(text, q)
        content = _t("Content", c, 6, "", c)
        detail.update(cd)
        feedback += tips
    else:
        raise ValueError(f"unknown speaking task {task}")

    if task in ("read_aloud", "repeat_sentence"):
        intended = _intended_words([type("A", (), x) for x in detail["alignment"]]) if text else tokens(q["text"])
    else:
        factor, msg = coherence(text)
        if factor < 1:
            content = _t("Content", content["raw"] * factor, content["max"], content["note"], content["raw"] * factor)
            feedback.insert(0, msg)
        detail["coherence"] = round(factor, 2)

    # ---------------- acoustic analysis (independent of the transcript's wording quality)
    norm, _ = sphinx.normalise_words(intended)
    sx = sphinx.analyse(wave, norm, phones=True) if wave is not None and norm else None
    aligned_ok = sx is not None and len(sx.words) > 0
    f = acoustic_model_features(wave, intended, ac, sx) if wave is not None else None
    # The trained model needs a successful alignment; without one its GOP inputs are meaningless.
    learned = models.speaking_traits(f) if f and aligned_ok else None

    if f is None or (f["syllables"] < 3 and d["n_words"] == 0):
        traits = [dict(content, score=0, raw=0.0), _t("Oral Fluency", 0, 5), _t("Pronunciation", 0, 5)]
        return {"score": 0, "max": sum(t["max"] for t in traits), "traits": traits,
                "feedback": ["No speech detected. Check your microphone and start speaking right after the tone."], "detail": detail}

    # ---------------- oral fluency
    fl_rule, fl_cap, fl_tips, fl_ev = fluency_rule(f, d, sx, task)
    fl = fl_rule
    if learned:
        fl = 0.55 * so_to_pte((learned["fluency"] + learned["prosodic"]) / 2) + 0.45 * fl_rule
    fl = min(fl, fl_cap)

    # ---------------- pronunciation
    if aligned_ok:
        pr_rule = pronunciation_rule(f)
    else:
        # Couldn't align the audio to the words (unusual accent, heavy noise, or speech unrelated to the text):
        # fall back to how intelligible the speech was to the recogniser, and say so.
        match = detail.get("match_rate", 0.7)
        rate_ok = 1.0 if 1.8 <= f["speech_rate_sps"] <= 6.0 else 0.6
        # without sound-level evidence the score can't certify more than "Good" (3/5)
        pr_rule = min(3.0, 5 * float(np.clip((0.6 * match + 0.4 * d["mean_word_prob"] - 0.45) / 0.5, 0, 1)) * rate_ok)
        feedback.append("We couldn't measure your pronunciation sound by sound for this recording, so this score is an estimate. "
                        "Recording in a quiet room with the microphone close to your mouth helps.")
    pr = pr_rule
    if learned:
        pr = 0.65 * so_to_pte(learned["accuracy"]) + 0.35 * pr_rule
    ph = phoneme.analyse(wave, norm) if phoneme.available() else None  # wav2vec2 (pro engine), if installed
    if ph:
        pr = 0.5 * pr + 0.5 * 5 * float(np.clip((ph["phoneme_accuracy"] - 0.5) / 0.4, 0, 1))
    ssl = models.speaking_ssl(wave)
    if ssl:
        pr = 0.6 * pr + 0.4 * so_to_pte(ssl["accuracy"])
        fl = min(fl_cap, 0.6 * fl + 0.4 * so_to_pte((ssl["fluency"] + ssl["prosodic"]) / 2))
    words_fb, sounds = word_feedback(sx)
    bad_ratio = np.mean([w["level"] == "bad" for w in words_fb]) if words_fb else 0.0
    if bad_ratio > 0.3:
        pr = min(pr, 2.5)
    elif bad_ratio > 0.15:
        pr = min(pr, 3.5)

    # Read Aloud / Repeat Sentence: fluency and pronunciation are judged on the text. Reading only part of
    # it, or saying words out of order, can't earn top marks for how it sounded.
    if word_acc is not None:
        cap = 1 + 4 * word_acc
        fl, pr = min(fl, cap), min(pr, cap)

    detail["fluency"] = fl_ev
    detail["pronunciation"] = {"engine": "phoneme+gop" if ph else "gop", "words": words_fb, "sounds_to_practise": sounds,
                               "learned_model": bool(learned)}
    detail["model_features"] = {k: round(float(v), 3) for k, v in f.items()}
    if learned:
        detail["expert_scale"] = {k: round(v, 1) for k, v in learned.items()}  # 0–10, speechocean762 scale

    traits = [content, _t("Oral Fluency", fl, 5, "", fl), _t("Pronunciation", pr, 5, "", pr)]
    if content["score"] == 0 and task not in {"read_aloud", "repeat_sentence"}:
        traits = [dict(t, score=0, raw=0.0, note="Content is 0, so the response is not scored further")
                  if t["name"] != "Content" else dict(t, raw=0.0) for t in traits]
        feedback.insert(0, "Your response wasn't relevant enough to score. In PTE this gives 0 for all traits.")
    else:
        feedback += fl_tips
        bad_words = [w["word"] for w in words_fb if w["level"] == "bad"][:8]
        if bad_words:
            feedback.append("Mispronounced: " + ", ".join(bad_words) + ".")
        if sounds:
            feedback.append("Sounds to practise: " + "; ".join(sounds) + ".")
    score_ = round(sum(t["raw"] for t in traits), 1)
    return {"score": score_, "max": sum(t["max"] for t in traits), "traits": traits, "feedback": feedback, "detail": detail}
