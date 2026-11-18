"""Reading & Listening objective scoring — follows Pearson's published rules exactly.

* Correct/incorrect (1/0): MCQ single answer, Highlight Correct Summary, Select Missing Word.
* Partial credit with negative marking (+1 / -1, floor 0): MCQ multiple answers, Highlight Incorrect Words.
* Partial credit, no negative marking: Fill in the Blanks (each blank), Reorder Paragraphs (each correct
  adjacent pair), Write From Dictation (each correct word).
"""
from __future__ import annotations

from collections import Counter

from .text import tokens


def _result(score: float, max_score: float, detail: dict | None = None) -> dict:
    return {
        "score": max(0.0, float(score)),
        "max": float(max_score),
        "traits": [{"name": "Correctness", "score": max(0.0, float(score)), "max": float(max_score)}],
        "detail": detail or {},
    }


def mcq_single(answer: str | None, correct: str) -> dict:
    ok = answer is not None and answer == correct
    return _result(1 if ok else 0, 1, {"correct": correct, "chosen": answer})


def mcq_multiple(answers: list[str], correct: list[str]) -> dict:
    a, c = set(answers or []), set(correct)
    plus, minus = len(a & c), len(a - c)
    return _result(max(0, plus - minus), len(c), {"correct": sorted(c), "chosen": sorted(a), "right": plus, "wrong": minus})


def fill_blanks(answers: dict[str, str] | list[str], correct: list[str] | list[list[str]], case_sensitive: bool = False) -> dict:
    """`correct[i]` may be a string or a list of acceptable strings."""
    if isinstance(answers, dict):
        answers = [answers.get(str(i), "") for i in range(len(correct))]
    per = []
    for i, exp in enumerate(correct):
        accepted = exp if isinstance(exp, list) else [exp]
        given = (answers[i] if i < len(answers) else "") or ""
        g = given.strip() if case_sensitive else given.strip().lower()
        ok = any(g == (x if case_sensitive else x.lower()) for x in accepted)
        per.append({"blank": i, "given": given, "correct": accepted[0], "ok": ok})
    return _result(sum(p["ok"] for p in per), len(correct), {"blanks": per})


def reorder(order: list[str], correct: list[str]) -> dict:
    correct_pairs = {(correct[i], correct[i + 1]) for i in range(len(correct) - 1)}
    given_pairs = [(order[i], order[i + 1]) for i in range(len(order) - 1)] if order else []
    hits = [p for p in given_pairs if p in correct_pairs]
    return _result(len(hits), len(correct_pairs), {"correct_order": correct, "your_order": order,
                                                   "correct_pairs": [list(p) for p in hits]})


def highlight_incorrect(selected: list[int], incorrect_indices: list[int]) -> dict:
    s, c = set(selected or []), set(incorrect_indices)
    plus, minus = len(s & c), len(s - c)
    return _result(max(0, plus - minus), len(c), {"correct": sorted(c), "chosen": sorted(s), "right": plus, "wrong": minus})


def write_from_dictation(text: str, reference: str) -> dict:
    """One point per correctly spelled word of the reference that appears in the response (order-free, multiset)."""
    ref = tokens(reference)
    hyp = Counter(tokens(text))
    per = []
    for w in ref:
        ok = hyp[w] > 0
        if ok:
            hyp[w] -= 1
        per.append({"word": w, "ok": ok})
    score = sum(p["ok"] for p in per)
    res = _result(score, len(ref), {"words": per, "reference": reference})
    res["traits"] = [{"name": "Words", "score": score, "max": len(ref)}]
    return res
