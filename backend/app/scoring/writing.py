"""Writing scorers: Summarize Written Text, Write Essay, Summarize Spoken Text.

Trait maxima follow the PTE Academic score guide as updated on 7 Aug 2025:
  SWT  content 4 · form 1 · grammar 2 · vocabulary 2                                    = 9
  WE   content 6 · form 2 · DSC 6 · grammar 2 · GLR 6 · vocabulary 2 · spelling 2        = 26
  SST  content 4 · form 2 · grammar 2 · vocabulary 2 · spelling 2                       = 12
If Content or Form is 0, the whole response scores 0 (Pearson rule).
"""
from __future__ import annotations

import re
import statistics

from . import models
from .lexicon import connective_profile, grammar_issues, sophistication, spelling_errors, SUBORDINATORS
from .semantic import similarity
from .text import keypoint_hits, paragraphs, sentences, tokens, type_token_ratio


def _trait(name, score, mx, note=""):
    return {"name": name, "score": round(float(max(0, min(mx, score))), 1), "max": mx, "note": note}


def _finish(traits: list[dict], feedback: list[str], detail: dict, gate_names=("Content", "Form")) -> dict:
    gated = any(t["name"] in gate_names and t["score"] == 0 for t in traits)
    if gated:
        for t in traits:
            if t["score"]:
                t["note"] = (t["note"] + " " if t["note"] else "") + "(not counted — Content or Form is 0)"
            t["score"] = 0
    score = sum(t["score"] for t in traits)
    mx = sum(t["max"] for t in traits)
    return {"score": round(score, 1), "max": mx, "traits": traits, "feedback": feedback, "detail": detail}


def _count_sentences(text: str) -> int:
    t = re.sub(r"\b(e\.g|i\.e|etc|vs|Dr|Mr|Mrs|Ms|U\.S|approx)\.", lambda m: m.group(0).replace(".", ""), text.strip())
    ends = re.findall(r"[.!?](?=\s+[A-Z0-9\"']|\s*$)", t)
    return max(1, len(ends)) if t else 0


def _grammar_points(text: str, words: int, mx: int = 2) -> tuple[int, list[dict]]:
    issues = grammar_issues(text)
    if text.strip() and not re.search(r"[.!?][\"')\]]*\s*$", text.strip()):
        issues.append({"code": "end-punct", "message": "Finish with a full stop", "text": text.strip()[-12:], "offset": len(text)})
    per100 = len(issues) / max(words, 1) * 100
    model = models.essay_traits(text) if words >= 30 else None
    if model:
        m = ((model["grammar"] + model["conventions"]) / 2 - 1) / 4 * mx
        rule = mx if per100 <= 0.6 else (mx / 2 if per100 <= 2.5 else 0)
        pts = round(0.5 * m + 0.5 * rule)
    else:
        pts = mx if len(issues) == 0 or per100 <= 0.6 else (1 if per100 <= 2.5 else 0)
    return int(pts), issues


def _vocab_points(toks: list[str], spell_errs: int, text: str) -> int:
    soph = sophistication(toks)
    lex = soph["rare_ratio"] * 0.6 + soph["academic_ratio"] * 1.4 + max(0, soph["avg_word_len"] - 4.2) * 0.08
    model = models.essay_traits(text) if len(toks) >= 30 else None
    pts = 2 if lex >= 0.14 else (1 if lex >= 0.06 else 0)
    if model:
        m = ((model["vocabulary"] + model["phraseology"]) / 2 - 1) / 4 * 2
        pts = round(0.5 * pts + 0.5 * m)
    if spell_errs >= 3:
        pts = min(pts, 1)
    return int(pts)


TEMPLATE_PHRASES = [
    "in this day and age", "it is an undeniable fact", "plays a pivotal role", "in a nutshell", "hotly debated", "pros and cons",
    "this essay will discuss", "a burning issue", "since time immemorial", "every coin has two sides", "double-edged sword",
    "last but not least", "the topic of whether", "has been a matter of debate", "a myriad of", "it is a widely held belief",
    "with the advent of", "in today's modern world", "from my point of view, i firmly believe", "the aforementioned",
    "to put it in a nutshell", "taking everything into consideration", "a plethora of", "it goes without saying",
]


def template_ratio(text: str) -> tuple[float, list[str]]:
    """Share of the response made of stock template phrases (Pearson penalises memorised content since 2025)."""
    low = re.sub(r"\s+", " ", text.lower())
    found = [p for p in TEMPLATE_PHRASES if p in low]
    words = max(1, len(tokens(text)))
    return sum(len(p.split()) for p in found) / words, found


def copied_ratio(response: str, source: str, n: int = 6) -> float:
    """Fraction of the response's words that sit inside 6-word runs copied verbatim from the source."""
    r, src = tokens(response), tokens(source)
    if len(r) < n or len(src) < n:
        return 0.0
    grams = {tuple(src[i : i + n]) for i in range(len(src) - n + 1)}
    covered = [False] * len(r)
    for i in range(len(r) - n + 1):
        if tuple(r[i : i + n]) in grams:
            for j in range(i, i + n):
                covered[j] = True
    return sum(covered) / len(r)


def _spell_points(n: int) -> int:
    return 2 if n == 0 else (1 if n == 1 else 0)


# ======================================================================= SWT
def summarize_written_text(response: str, q: dict) -> dict:
    words = len(tokens(response))
    n_sent = _count_sentences(response)
    form_ok = 5 <= words <= 75 and n_sent == 1
    feedback = []
    if words < 5 or words > 75:
        feedback.append(f"Your summary has {words} words; it must be 5–75 words.")
    if n_sent != 1:
        feedback.append(f"Write exactly ONE sentence (found {n_sent}). Join ideas with ', and', ', which', 'while' or ';'.")

    hits = keypoint_hits(response, q.get("key_points", []))
    cover = sum(h["covered"] for h in hits) / max(1, len(hits))
    sim = similarity(response, q.get("passage", ""))
    raw = 0.75 * cover + 0.25 * min(1.0, sim / 0.45)
    content = round(4 * raw)
    if cover == 0 and sim < 0.12:
        content = 0
    copied = copied_ratio(response, q.get("passage", ""))
    if copied > 0.75 and cover < 0.6:
        content = min(content, 1)
        feedback.append("Most of your summary is copied word for word from one part of the text. Combine the main ideas from the whole passage in your own words.")
    elif copied > 0.6:
        content = min(content, 3)
        feedback.append("Paraphrase more. Long stretches are copied straight from the passage.")
    missed = [h["label"] for h in hits if not h["covered"]]
    if missed:
        feedback.append("Key ideas missing: " + "; ".join(missed) + ".")

    spell = spelling_errors(response, set(tokens(q.get("passage", ""))))
    grammar, issues = _grammar_points(response, words)
    vocab = _vocab_points(tokens(response), len(spell), response)
    if spell:
        feedback.append("Spelling: " + ", ".join(f"{s['word']}→{s['suggestion']}" for s in spell if s["suggestion"]))

    traits = [
        _trait("Content", content, 4, f"{sum(h['covered'] for h in hits)}/{len(hits)} key ideas"),
        _trait("Form", 1 if form_ok else 0, 1, f"{words} words, {n_sent} sentence(s)"),
        _trait("Grammar", grammar, 2, f"{len(issues)} issue(s)"),
        _trait("Vocabulary", vocab, 2),
    ]
    return _finish(traits, feedback, {"word_count": words, "key_points": hits, "grammar": issues, "spelling": spell,
                                      "similarity": round(sim, 3), "copied_ratio": round(copied, 2)})


# ======================================================================= Essay
def _essay_form(text: str, words: int) -> int:
    if not text.strip():
        return 0
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        return 0  # all capitals
    if len(re.findall(r"^\s*[-*•]\s", text, re.M)) >= 3:
        return 0  # bullet points
    if 200 <= words <= 300:
        return 2
    if 120 <= words <= 199 or 301 <= words <= 380:
        return 1
    return 0


def write_essay(response: str, q: dict) -> dict:
    toks = tokens(response)
    words = len(toks)
    paras = paragraphs(response)
    sents = sentences(response)
    feedback: list[str] = []

    form = _essay_form(response, words)
    if form < 2:
        feedback.append(f"Aim for 200–300 words (you wrote {words}).")

    # ---------- content
    prompt = q.get("prompt", "")
    hits = keypoint_hits(response, q.get("key_points", []))
    cover = sum(h["covered"] for h in hits) / max(1, len(hits)) if hits else 0.0
    sim = similarity(response, prompt)
    relevance = max(cover, min(1.0, sim / 0.35)) if hits else min(1.0, sim / 0.35)
    conn = connective_profile(response)
    position = 1.0 if ("opinion" in conn or re.search(r"\b(i (agree|disagree|believe|think|argue)|this essay will)\b", response, re.I)) else 0.4
    n_examples = len(conn.get("example", [])) + len(re.findall(r"\b(for example|for instance|such as|a case in point)\b", response, re.I))
    body = max(0, len(paras) - 2)
    support = 0.35 * min(body, 2) / 2 + 0.35 * min(n_examples, 2) / 2 + 0.3 * min(len(sents), 12) / 12
    content_raw = 0.45 * relevance + 0.2 * position + 0.35 * support
    content = round(6 * content_raw)
    if relevance < 0.15:
        content = 0
        feedback.append("The essay does not appear to address the prompt — this scores 0 in PTE.")
    tpl, tpl_found = template_ratio(response)
    if tpl > 0.12:
        content = min(content, 3)
        feedback.append("A large part of the essay is stock template phrases (" + ", ".join(f"'{t}'" for t in tpl_found[:3])
                        + "). Since 2025 Pearson lowers scores for memorised content. Use your own ideas and examples.")
    elif tpl > 0.06:
        content = min(content, 5)
        feedback.append("Cut the stock phrases (" + ", ".join(f"'{t}'" for t in tpl_found[:3]) + ") and spend the words on your argument.")
    off = [i + 1 for i, p in enumerate(paras[1:-1], start=1) if len(tokens(p)) > 25 and similarity(p, prompt) < 0.05]
    if off and content > 2:
        content -= 1
        feedback.append(f"Paragraph {', '.join(map(str, off))} drifts away from the question. Link every paragraph back to the prompt.")
    for h in hits:
        if not h["covered"]:
            feedback.append(f"Address this part of the prompt more directly: {h['label']}.")
    if n_examples == 0:
        feedback.append("Support each argument with a specific example ('For instance, ...').")

    # ---------- development, structure & coherence
    has_intro = len(paras) >= 1 and (tokens(paras[0]) and (position == 1.0 or similarity(paras[0], prompt) > 0.15))
    has_concl = len(paras) >= 2 and bool(re.search(r"\b(in conclusion|to conclude|to sum up|overall|in summary|all in all|ultimately)\b",
                                                   paras[-1], re.I))
    para_score = {0: 0, 1: 0.15, 2: 0.4, 3: 0.75}.get(len(paras), 1.0)
    variety = min(1.0, len(conn) / 5)
    sp_per_para = len(sents) / max(1, len(paras))
    dsc_raw = 0.35 * para_score + 0.15 * has_intro + 0.15 * has_concl + 0.25 * variety + 0.1 * min(1.0, sp_per_para / 2.5)
    model = models.essay_traits(response) if words >= 60 else None
    dsc = 6 * dsc_raw
    if model:
        dsc = 0.55 * dsc + 0.45 * ((model["cohesion"] - 1) / 4 * 6)
    if len(paras) < 4:
        dsc = min(dsc, 4)
        feedback.append("Use 4–5 paragraphs: introduction, two or three body paragraphs, conclusion.")
    if len(conn) < 3:
        dsc = min(dsc, 4)
    if not has_concl:
        feedback.append("Open the final paragraph with a clear conclusion marker ('In conclusion, ...').")

    # ---------- general linguistic range
    lens = [len(tokens(s)) for s in sents] or [0]
    sd = statistics.pstdev(lens) if len(lens) > 1 else 0
    subord = sum(1 for t in toks if t in SUBORDINATORS) / max(1, len(sents))
    passive = len(re.findall(r"\b(is|are|was|were|been|being|be)\s+\w+(ed|en)\b", response, re.I))
    ttr = type_token_ratio(toks)
    glr_raw = (0.25 * min(1.0, sd / 7) + 0.25 * min(1.0, subord / 1.2) + 0.15 * min(1.0, passive / 2)
               + 0.35 * min(1.0, max(0, ttr - 0.55) / 0.25))
    glr = 6 * glr_raw
    if words < 200 or len(sents) < 8:
        glr = min(glr, 4)  # too little text to show a wide range
    if model:
        glr = 0.5 * glr + 0.5 * (((model["syntax"] + model["vocabulary"]) / 2 - 1) / 4 * 6)

    # ---------- enabling traits
    spell = spelling_errors(response, set(tokens(prompt)))
    grammar, issues = _grammar_points(response, words)
    vocab = _vocab_points(toks, len(spell), response)
    if spell:
        feedback.append("Spelling: " + ", ".join(f"{s['word']}→{s['suggestion']}" for s in spell[:8] if s["suggestion"]))
    if issues:
        feedback.append("Grammar: " + "; ".join(sorted({i["message"] for i in issues}))[:300])

    traits = [
        _trait("Content", content, 6, f"relevance {relevance:.0%}"),
        _trait("Form", form, 2, f"{words} words"),
        _trait("Development, Structure & Coherence", round(dsc), 6, f"{len(paras)} paragraphs, {len(conn)} linker types"),
        _trait("Grammar", grammar, 2, f"{len(issues)} issue(s)"),
        _trait("General Linguistic Range", round(glr), 6),
        _trait("Vocabulary Range", vocab, 2),
        _trait("Spelling", _spell_points(len(spell)), 2, f"{len(spell)} error(s)"),
    ]
    return _finish(traits, feedback, {"word_count": words, "paragraphs": len(paras), "key_points": hits,
                                      "connectives": conn, "grammar": issues, "spelling": spell, "template_ratio": round(tpl, 2),
                                      "model": "ellipse" if model else "rules"})


# ======================================================================= SST
def summarize_spoken_text(response: str, q: dict) -> dict:
    toks = tokens(response)
    words = len(toks)
    form = 2 if 50 <= words <= 70 else (1 if 40 <= words <= 49 or 71 <= words <= 100 else 0)
    feedback = []
    if form < 2:
        feedback.append(f"Write 50–70 words (you wrote {words}).")
    hits = keypoint_hits(response, q.get("key_points", []))
    cover = sum(h["covered"] for h in hits) / max(1, len(hits))
    sim = similarity(response, q.get("transcript", ""))
    content = round(4 * (0.75 * cover + 0.25 * min(1.0, sim / 0.4)))
    if cover == 0 and sim < 0.1:
        content = 0
    missed = [h["label"] for h in hits if not h["covered"]]
    if missed:
        feedback.append("Points from the lecture you missed: " + "; ".join(missed) + ".")
    spell = spelling_errors(response, set(tokens(q.get("transcript", ""))))
    grammar, issues = _grammar_points(response, words)
    vocab = _vocab_points(toks, len(spell), response)
    traits = [
        _trait("Content", content, 4, f"{sum(h['covered'] for h in hits)}/{len(hits)} key points"),
        _trait("Form", form, 2, f"{words} words"),
        _trait("Grammar", grammar, 2, f"{len(issues)} issue(s)"),
        _trait("Vocabulary", vocab, 2),
        _trait("Spelling", _spell_points(len(spell)), 2, f"{len(spell)} error(s)"),
    ]
    return _finish(traits, feedback, {"word_count": words, "key_points": hits, "grammar": issues, "spelling": spell})
