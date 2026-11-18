"""Single entry point: score_item(task, question, response) → result dict.

Every result has the shape {"score", "max", "traits": [{name, score, max, note}], "feedback": [...], "detail": {...}}.
"""
from __future__ import annotations

from . import objective, speaking, writing
from .overall import item_band


def score_item(task: str, q: dict, response: dict, audio: bytes | None = None) -> dict:
    r = response or {}
    if task in speaking.SPEAKING_TASKS:
        res = speaking.score(task, q, audio, r.get("transcript"), r.get("confidence"))
    elif task == "personal_introduction":
        res = {"score": 0, "max": 0, "traits": [], "feedback": ["Personal Introduction is not scored; it is sent to institutions."],
               "detail": {}}
    elif task == "summarize_written_text":
        res = writing.summarize_written_text(r.get("text", ""), q)
    elif task == "write_essay":
        res = writing.write_essay(r.get("text", ""), q)
    elif task == "summarize_spoken_text":
        res = writing.summarize_spoken_text(r.get("text", ""), q)
    elif task in ("mcq_single_reading", "mcq_single_listening", "highlight_correct_summary", "select_missing_word"):
        res = objective.mcq_single(r.get("answer"), q["answer"])
    elif task in ("mcq_multiple_reading", "mcq_multiple_listening"):
        res = objective.mcq_multiple(r.get("answers", []), q["answers"])
    elif task in ("rw_fill_blanks", "reading_fill_blanks", "listening_fill_blanks"):
        res = objective.fill_blanks(r.get("blanks", {}), [b["answer"] if isinstance(b, dict) else b for b in q["blanks"]])
    elif task == "reorder_paragraphs":
        res = objective.reorder(r.get("order", []), q["answer"])
    elif task == "highlight_incorrect_words":
        res = objective.highlight_incorrect(r.get("selected", []), [w["index"] for w in q["substitutions"]])
    elif task == "write_from_dictation":
        res = objective.write_from_dictation(r.get("text", ""), q["text"])
    else:
        raise ValueError(f"Unknown task type: {task}")
    res.setdefault("feedback", [])
    res["task"] = task
    res["band"] = item_band(res)
    return res
