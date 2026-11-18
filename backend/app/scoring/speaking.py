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

from . import models, phoneme
from .asr import Transcript, transcribe
from .audio import AcousticFeatures, acoustic_features, decode
from .semantic import similarity
from .text import FILLERS, align, keypoint_hits, lcs_len, tokens

log = logging.getLogger(__name__)

SPEAKING_TASKS = {"read_aloud", "repeat_sentence", "describe_image", "retell_lecture", "answer_short_question",
                  "summarize_group_discussion", "respond_to_situation"}


def _t(name, score, mx, note="", raw=None):
    s = float(max(0, min(mx, score)))
    return {"name": name, "score": round(s), "max": mx, "raw": round(raw if raw is not None else s, 2), "note": note}


# =================================================================== fluency
def fluency_features(tr: Transcript, ac: AcousticFeatures) -> dict:
    words = [w for w in tr.words if tokens(w.w)]
    lw = [tokens(w.w)[0] for w in words]
    fillers = sum(1 for t in lw if t in FILLERS)
    lexical = [w for w, t in zip(words, lw) if t not in FILLERS]
    n = len(lexical)
    # repetitions ("the the") and false starts (truncated word followed by the full word: "pro- problem")
    reps = sum(1 for a, b in zip(lw, lw[1:]) if a == b and a not in FILLERS)
    false_starts = sum(1 for a, b in zip(lw, lw[1:]) if len(a) >= 2 and b.startswith(a) and b != a)
    false_starts += sum(1 for w in words if w.w.endswith("-"))
    # inter-word gaps
    gaps = [b.start - a.end for a, b in zip(words, words[1:])]
    if tr.timed:
        hes_pauses = sum(1 for g in gaps if 0.5 <= g < 1.0)
        long_pauses = sum(1 for g in gaps if g >= 1.0)
    else:
        hes_pauses = sum(1 for p in ac.pauses if 0.5 <= p < 1.0)
        long_pauses = ac.n_long_pauses
    # run lengths of words without a >=0.4 s break
    runs, cur = [], 0
    for i, w in enumerate(words):
        cur += 1
        if i < len(gaps) and gaps[i] >= 0.4:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    span = (words[-1].end - words[0].start) if len(words) >= 2 else max(ac.speech_time, 0.1)
    phon = ac.speech_time if ac.speech_time > 0 else span
    return {
        "n_words": n, "fillers": fillers, "repetitions": reps, "false_starts": false_starts,
        "hesitation_pauses": hes_pauses, "long_pauses": long_pauses,
        "speech_rate_wpm": 60 * n / span if span > 0 else 0.0,
        "articulation_rate_wpm": 60 * n / phon if phon > 0 else 0.0,
        "mean_run": float(np.mean(runs)) if runs else 0.0, "longest_run": max(runs) if runs else 0,
        "initial_silence": ac.initial_silence, "pitch_st_std": ac.pitch_st_std,
        "mean_word_prob": float(np.mean([w.prob for w in lexical])) if lexical else 0.0,
        "low_prob_ratio": float(np.mean([w.prob < 0.5 for w in lexical])) if lexical else 1.0,
    }


def fluency_score(f: dict, task: str) -> tuple[float, list[str]]:
    """Maps the PTE oral-fluency rubric (Native-like 5 … Disfluent 0) onto measured features."""
    tips = []
    n = f["n_words"]
    if n < 3:
        return 0.0, ["Too little speech was detected to assess fluency."]
    hes = f["fillers"] + f["hesitation_pauses"]
    breaks = f["repetitions"] + f["false_starts"]
    s = 5.0
    s -= 0.45 * min(hes, 6)
    s -= 1.1 * min(f["long_pauses"], 3)
    s -= 0.5 * min(breaks, 4)
    wpm = f["speech_rate_wpm"]
    lo, hi = (105, 185) if task in {"read_aloud", "repeat_sentence"} else (95, 180)
    if wpm < lo:
        s -= min(2.0, (lo - wpm) / 25)
        tips.append(f"Your pace was {wpm:.0f} words/min — aim for about {lo + 25}–{hi - 15}.")
    elif wpm > hi + 25:
        s -= min(1.5, (wpm - hi - 25) / 30)
        tips.append(f"You spoke very fast ({wpm:.0f} wpm); slow down slightly for clearer phrasing.")
    if f["mean_run"] < 3 and n >= 6:
        s -= 1.0
        tips.append("Speech sounded staccato — group words into phrases of 4–7 words.")
    if 0 < f["pitch_st_std"] < 1.4 and n >= 10:
        s -= 0.4
        tips.append("Intonation was quite flat; let your voice rise and fall naturally and stress key words.")
    if f["fillers"]:
        tips.append(f"Avoid fillers (um/uh): {f['fillers']} detected.")
    if f["long_pauses"]:
        tips.append(f"{f['long_pauses']} long pause(s) — keep going even if you make a mistake; never stop for >1 s.")
    if breaks:
        tips.append(f"{breaks} repetition(s)/false start(s) — don't correct yourself, just continue.")
    if f["initial_silence"] > 2.5:
        tips.append("Start speaking within 1–2 s of the tone — the real test closes the microphone after 3 s of silence.")
    return max(0.0, min(5.0, s)), tips


# =================================================================== pronunciation
def pronunciation_score(wave, tr: Transcript, f: dict, ref_words: list[str] | None, match_rate: float | None) -> tuple[float, dict, list[str]]:
    tips: list[str] = []
    info: dict = {"engine": "proxy"}
    words = ref_words if ref_words else [tokens(w.w)[0] for w in tr.words if tokens(w.w) and tokens(w.w)[0] not in FILLERS]
    ph = phoneme.analyse(wave, words) if wave is not None else None
    if ph:
        info = {"engine": "phoneme", **ph}
        pa = ph["phoneme_accuracy"]
        s = 5 * np.clip((pa - 0.5) / 0.4, 0, 1)
        weak = [w["word"] for w in ph["words"] if w["accuracy"] < 0.6][:8]
        if weak:
            tips.append("Words to practise: " + ", ".join(weak) + ".")
    else:
        # Proxy: how intelligible the speech was to the recogniser, plus recogniser confidence.
        conf = f.get("mean_word_prob", 0.0)
        intel = match_rate if match_rate is not None else 1 - f.get("low_prob_ratio", 0.5)
        s = 5 * np.clip((0.6 * intel + 0.4 * conf - 0.45) / 0.47, 0, 1)
        info["intelligibility"] = round(float(intel), 3)
        info["confidence"] = round(float(conf), 3)
    feats = f | ({"phoneme_accuracy": ph["phoneme_accuracy"], "phoneme_confidence": ph["phoneme_confidence"]} if ph else {})
    reg = models.speaking_traits(feats)
    info["learned_traits"] = reg
    ssl = models.speaking_ssl(wave) if wave is not None else None
    learned = [m["accuracy"] / 2 for m in (reg, ssl) if m]
    if learned:
        s = 0.5 * s + 0.5 * float(np.mean(learned))
        info["learned"] = True
    if s < 3.5:
        tips.append("Pronounce word endings (-s, -ed, -t) clearly and stress the right syllable.")
    return float(s), info, tips


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


# =================================================================== training features
# The Kaggle notebook (kaggle/01_speaking_pronunciation_fluency.ipynb) calls extract_features() so the
# regressor is trained on exactly the features the server computes at scoring time.
SPEAKING_FEATURES = ["n_words", "fillers", "repetitions", "false_starts", "hesitation_pauses", "long_pauses", "speech_rate_wpm",
                     "articulation_rate_wpm", "mean_run", "longest_run", "initial_silence", "pitch_st_std", "mean_word_prob",
                     "low_prob_ratio", "phoneme_accuracy", "phoneme_confidence"]


def extract_features(wave, reference_text: str | None = None, client_transcript: str | None = None) -> dict:
    ac = acoustic_features(wave)
    tr = transcribe(wave, client_transcript, ac)
    f = fluency_features(tr, ac)
    words = tokens(reference_text) if reference_text else [t for t in tokens(tr.text) if t not in FILLERS]
    ph = phoneme.analyse(wave, words)
    f["phoneme_accuracy"] = ph["phoneme_accuracy"] if ph else 0.0
    f["phoneme_confidence"] = ph["phoneme_confidence"] if ph else 0.0
    f["transcript"] = tr.text
    return f


# =================================================================== entry point
def score(task: str, q: dict, audio: bytes | None, client_transcript: str | None = None,
          client_confidence: float | None = None) -> dict:
    wave = decode(audio) if audio else None
    ac = acoustic_features(wave)
    tr = transcribe(wave, client_transcript, ac, confidence=client_confidence)
    text = tr.text
    f = fluency_features(tr, ac)
    feedback: list[str] = []
    detail: dict = {"transcript": text, "asr_engine": tr.engine, "acoustics": ac.as_dict(),
                    "fluency_features": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in f.items()}}

    if task == "answer_short_question":
        answers = [a.lower() for a in q.get("answers", [])]
        low = " " + " ".join(tokens(text)) + " "
        ok = any(f" {' '.join(tokens(a))} " in low for a in answers)
        if not ok:
            feedback.append(f"Expected: {q.get('answers', ['?'])[0]}. Answer with one or a few words.")
        return {"score": 1 if ok else 0, "max": 1, "traits": [_t("Vocabulary", 1 if ok else 0, 1)], "feedback": feedback,
                "detail": detail | {"expected": q.get("answers", [])}}

    ref_words = None
    match_rate = None
    if task == "read_aloud":
        c, cd = _ra_content(q["text"], text)
        content = _t("Content", c, 5, f"{cd['correct']}/{cd['total']} words correct, {cd['errors']} error(s)", c)
        ref_words, match_rate = tokens(q["text"]), cd["match_rate"]
        detail.update(cd)
        if cd["errors"]:
            feedback.append("Read every word exactly as written — each omission, insertion or substitution is an error.")
    elif task == "repeat_sentence":
        c, cd = _rs_content(q["text"], text)
        content = _t("Content", c, 3, f"{cd['in_sequence']}/{cd['total']} words in sequence", c)
        ref_words, match_rate = tokens(q["text"]), cd["match_rate"]
        detail.update(cd)
        if c < 3:
            feedback.append("Repeat the sentence word-for-word; if you lose part of it, keep speaking fluently anyway.")
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

    fl, fl_tips = fluency_score(f, task)
    pr, pr_info, pr_tips = pronunciation_score(wave, tr, f, ref_words, match_rate)
    reg = pr_info.get("learned_traits")
    if reg:  # blend learned fluency (speechocean762 fluency/prosody → 0–5)
        fl = 0.6 * fl + 0.4 * ((reg["fluency"] + reg["prosodic"]) / 4)
    detail["pronunciation"] = pr_info
    traits = [content, _t("Oral Fluency", fl, 5, "", fl), _t("Pronunciation", pr, 5, "", pr)]

    if f["n_words"] == 0:
        traits = [dict(t, score=0, raw=0.0) for t in traits]
        feedback = ["No speech detected. Check your microphone and start speaking right after the tone."]
    elif content["score"] == 0 and task not in {"read_aloud", "repeat_sentence"}:
        traits = [dict(t, score=0, raw=0.0, note="Content is 0, so the response is not scored further")
                  if t["name"] != "Content" else dict(t, raw=0.0) for t in traits]
        feedback.insert(0, "Your response wasn't relevant enough to score — in PTE this gives 0 for all traits.")
    else:
        feedback += fl_tips + pr_tips
    score_ = round(sum(t["raw"] for t in traits), 1)  # precise total; traits display as whole bands
    return {"score": score_, "max": sum(t["max"] for t in traits), "traits": traits, "feedback": feedback, "detail": detail}
