"""Question bank: loads JSON items, expands templates, and produces answer-free public views.

Templates
  {{answer|opt1|opt2|...}}  Reading & Writing FIB (dropdown options; the answer must be among them)
  {{answer}}                Reading FIB (drag & drop; extra `distractors`) and Listening FIB (typed)
Highlight Incorrect Words items list `substitutions` [{actual, shown}]; indices are computed here.
Questions added through the admin API are stored in the database and merged with the JSON bank.
"""
from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from pathlib import Path

from ..tasks import TASKS

DATA = Path(__file__).parent / "data"
BLANK_RE = re.compile(r"\{\{(.+?)\}\}")


def _parse_blanks(text: str) -> tuple[list[dict], list[dict]]:
    segments, blanks, pos = [], [], 0
    for m in BLANK_RE.finditer(text):
        if m.start() > pos:
            segments.append({"t": text[pos : m.start()]})
        parts = [p.strip() for p in m.group(1).split("|")]
        ans, opts = parts[0], list(dict.fromkeys(parts[1:])) or []
        if opts and ans not in opts:
            opts.insert(0, ans)
        segments.append({"blank": len(blanks)})
        blanks.append({"answer": ans, "options": opts})
        pos = m.end()
    if pos < len(text):
        segments.append({"t": text[pos:]})
    return segments, blanks


def _plain(text: str) -> str:
    return BLANK_RE.sub(lambda m: m.group(1).split("|")[0], text)


def prepare(task: str, raw: dict) -> dict:
    q = dict(raw)
    q["task"] = task
    if task in ("rw_fill_blanks", "reading_fill_blanks", "listening_fill_blanks"):
        q["segments"], q["blanks"] = _parse_blanks(raw["text"])
        q["full_text"] = _plain(raw["text"])
        rng = random.Random(q["id"])
        for b in q["blanks"]:
            if b["options"]:
                rng.shuffle(b["options"])
        if task == "reading_fill_blanks":
            pool = [b["answer"] for b in q["blanks"]] + raw.get("distractors", [])
            rng.shuffle(pool)
            q["pool"] = pool
    if task == "highlight_incorrect_words":
        words = raw["transcript"].split()
        subs, used = [], set()
        for s in raw["substitutions"]:
            for i, w in enumerate(words):
                core = re.sub(r"[^\w'-]", "", w).lower()
                if i not in used and core == s["actual"].lower():
                    subs.append({"index": i, "actual": s["actual"], "shown": s["shown"]})
                    used.add(i)
                    break
            else:
                raise ValueError(f"{raw['id']}: '{s['actual']}' not found in transcript")
        shown = list(words)
        for s in subs:
            shown[s["index"]] = re.sub(re.escape(s["actual"]), s["shown"], words[s["index"]], flags=re.I)
        q["substitutions"], q["shown_words"] = subs, shown
    return q


@lru_cache(maxsize=1)
def _json_bank() -> dict[str, list[dict]]:
    bank: dict[str, list[dict]] = {t: [] for t in TASKS}
    for f in sorted(DATA.glob("*.json")):
        for task, items in json.loads(f.read_text(encoding="utf-8")).items():
            if task not in TASKS:
                raise ValueError(f"{f.name}: unknown task '{task}'")
            bank[task].extend(prepare(task, it) for it in items)
    return bank


_extra: dict[str, dict] = {}  # questions from the database (admin-created), keyed by id


def register_extra(task: str, raw: dict) -> dict:
    q = prepare(task, raw)
    _extra[q["id"]] = q
    return q


def all_questions(task: str | None = None) -> list[dict]:
    items = [q for qs in _json_bank().values() for q in qs] + list(_extra.values())
    return [q for q in items if task is None or q["task"] == task]


def get(qid: str) -> dict | None:
    return _extra.get(qid) or next((q for q in all_questions() if q["id"] == qid), None)


def counts() -> dict[str, int]:
    out = {t: 0 for t in TASKS}
    for q in all_questions():
        out[q["task"]] += 1
    return out


# ---------------------------------------------------------------- public (answer-free) view
def public(q: dict) -> dict:
    """What the browser receives before answering. `audio_text` is only ever spoken via TTS, never displayed."""
    t = q["task"]
    base = {k: q.get(k) for k in ("id", "task", "title", "difficulty", "audio_url") if q.get(k) is not None}
    if t in ("read_aloud",):
        base["text"] = q["text"]
    elif t == "personal_introduction":
        base["prompt"] = q["prompt"]
    elif t in ("repeat_sentence", "write_from_dictation"):
        base["audio_text"] = q["text"]
    elif t == "answer_short_question":
        base["audio_text"] = q["question"]
    elif t == "describe_image":
        base["chart"] = q["chart"]
    elif t in ("retell_lecture", "summarize_spoken_text"):
        base["audio_text"] = q["transcript"]
    elif t == "summarize_group_discussion":
        base["audio_turns"] = q["turns"]
    elif t == "respond_to_situation":
        base["situation"] = q["situation"]
        base["audio_text"] = q["situation"]
    elif t == "summarize_written_text":
        base["passage"] = q["passage"]
    elif t == "write_essay":
        base["prompt"] = q["prompt"]
    elif t in ("mcq_single_reading", "mcq_multiple_reading"):
        base.update(passage=q["passage"], question=q["question"], options=q["options"])
    elif t in ("mcq_single_listening", "mcq_multiple_listening"):
        base.update(audio_text=q["transcript"], question=q["question"], options=q["options"])
    elif t in ("highlight_correct_summary", "select_missing_word"):
        base.update(audio_text=q["transcript"], options=q["options"])
    elif t == "rw_fill_blanks":
        base.update(segments=q["segments"], blanks=[{"options": b["options"]} for b in q["blanks"]])
    elif t == "reading_fill_blanks":
        base.update(segments=q["segments"], blanks=[{} for _ in q["blanks"]], pool=q["pool"])
    elif t == "listening_fill_blanks":
        base.update(segments=q["segments"], blanks=[{} for _ in q["blanks"]], audio_text=q["full_text"])
    elif t == "reorder_paragraphs":
        paras = list(q["paragraphs"])
        random.Random(q["id"] + "ro").shuffle(paras)
        if [p["id"] for p in paras] == q["answer"]:
            paras.reverse()
        base["paragraphs"] = paras
    elif t == "highlight_incorrect_words":
        base.update(shown_words=q["shown_words"], audio_text=q["transcript"])
    return base


def reveal(q: dict) -> dict:
    """Shown after scoring: the answer key / model content for review."""
    t = q["task"]
    keys = ("text", "transcript", "turns", "answers", "answer", "key_points", "substitutions", "full_text", "passage",
            "question", "situation", "functions", "sample_answer")
    out = {k: q[k] for k in keys if k in q}
    if t in ("rw_fill_blanks", "reading_fill_blanks", "listening_fill_blanks"):
        out["blank_answers"] = [b["answer"] for b in q["blanks"]]
    return out
