from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import bank
from ..config import AI_TASKS, MAX_AUDIO_MB, PLANS
from ..db import Attempt, Usage, User, now
from ..scoring import models, phoneme, score_item, semantic, sphinx, vad
from ..scoring.asr import whisper_available
from ..scoring.audio import AudioDecodeError
from ..scoring.overall import aggregate
from ..security import current_user, get_db
from ..tasks import MOCK_BLUEPRINT, MODULES, TASKS

router = APIRouter(prefix="/api", tags=["practice"])


_DECODE_STATUS: dict = {}


def decode_status() -> str:
    if "v" not in _DECODE_STATUS:
        from ..scoring.audio import ffmpeg_self_test

        err = ffmpeg_self_test()
        _DECODE_STATUS["v"] = "ok" if err is None else err
    return _DECODE_STATUS["v"]


@router.get("/meta")
def meta():
    counts = bank.counts()
    return {
        "tasks": [dict(v, count=counts[k], skills=[s for s, _, _ in v["skills"]]) for k, v in TASKS.items()],
        "modules": MODULES,
        "plans": PLANS,
        "mock_blueprint": MOCK_BLUEPRINT,
        "engines": {"asr": "whisper" if whisper_available() else "browser",
                    "pronunciation": "phoneme+gop" if phoneme.available() else ("gop" if sphinx.available() else "proxy"),
                    "vad": "silero" if vad.available() else "energy", "decode": decode_status(), "grammar": "languagetool" if os.getenv("LANGUAGETOOL_URL") else "rules",
                    "coach": "claude" if os.getenv("ANTHROPIC_API_KEY") else "rules",
                    "similarity": semantic.engine_name(), **models.status()},
    }


def _best_by_question(db: Session, user: User, task: str | None = None) -> dict[str, dict]:
    q = db.query(Attempt).filter(Attempt.user_id == user.id)
    if task:
        q = q.filter(Attempt.task == task)
    best: dict[str, dict] = {}
    for a in q.all():
        cur = best.setdefault(a.question_id, {"attempts": 0, "best": None, "last": None})
        cur["attempts"] += 1
        pct = a.score / a.max_score if a.max_score else 0
        cur["best"] = max(cur["best"] or 0, pct)
        cur["last"] = a.created_at.isoformat()
    return best


@router.get("/questions")
def list_questions(task: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if task not in TASKS:
        raise HTTPException(404, "Unknown task")
    stats = _best_by_question(db, user, task)
    return [bank.public(q) | {"stats": stats.get(q["id"])} for q in bank.all_questions(task)]


@router.get("/questions/{qid}")
def get_question(qid: str, user: User = Depends(current_user)):
    q = bank.get(qid)
    if not q:
        raise HTTPException(404, "Question not found")
    return bank.public(q)


def check_quota(db: Session, user: User, task: str) -> Usage | None:
    if task not in AI_TASKS:
        return None
    limit = PLANS[user.effective_plan()]["daily_ai_scores"]
    u = db.query(Usage).filter_by(user_id=user.id, day=date.today()).first()
    if not u:
        u = Usage(user_id=user.id, day=date.today(), ai_scores=0)
        db.add(u)
    if limit is not None and u.ai_scores >= limit:
        raise HTTPException(402, f"You've used today's {limit} free AI scores. Upgrade to Pro for unlimited scoring.")
    return u


def run_scoring(db: Session, user: User, qid: str, response: str, audio: UploadFile | None, mock_id: int | None = None) -> tuple[Attempt, dict]:
    q = bank.get(qid)
    if not q:
        raise HTTPException(404, "Question not found")
    try:
        resp = json.loads(response or "{}")
    except json.JSONDecodeError:
        raise HTTPException(422, "Malformed response payload")
    data = None
    if audio is not None:
        data = audio.file.read(MAX_AUDIO_MB * 1024 * 1024 + 1)
        if len(data) > MAX_AUDIO_MB * 1024 * 1024:
            raise HTTPException(413, "Recording too large")
    usage = check_quota(db, user, q["task"]) if mock_id is None else None
    try:
        result = score_item(q["task"], q, resp, data)
    except AudioDecodeError as e:
        raise HTTPException(422, str(e))
    result["reveal"] = bank.reveal(q)
    att = Attempt(user_id=user.id, question_id=qid, task=q["task"], module=TASKS[q["task"]]["module"], score=result["score"],
                  max_score=result["max"], band=result.get("band"), result=result, response=resp, mock_id=mock_id)
    db.add(att)
    if usage:
        usage.ai_scores += 1
    db.commit()
    return att, result


@router.post("/score/{qid}")
def score(qid: str, response: str = Form("{}"), audio: UploadFile | None = File(None),
          user: User = Depends(current_user), db: Session = Depends(get_db)):
    att, result = run_scoring(db, user, qid, response, audio)
    return {"attempt_id": att.id, **result}


@router.get("/attempts")
def attempts(task: str | None = None, question_id: str | None = None, limit: int = 50,
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Attempt).filter(Attempt.user_id == user.id)
    if task:
        q = q.filter(Attempt.task == task)
    if question_id:
        q = q.filter(Attempt.question_id == question_id)
    return [a.public() for a in q.order_by(Attempt.created_at.desc()).limit(min(limit, 500)).all()]


@router.get("/attempts/{aid}")
def attempt(aid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Attempt, aid)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    return a.public(full=True)


@router.get("/progress")
def progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    since = now() - timedelta(days=90)
    atts = db.query(Attempt).filter(Attempt.user_id == user.id, Attempt.created_at >= since).order_by(Attempt.created_at).all()
    latest: dict[str, Attempt] = {}
    for a in atts:
        latest[a.question_id] = a  # most recent attempt per question reflects current ability
    items = [{"task": a.task, "score": a.score, "max": a.max_score, "traits": a.result.get("traits", [])} for a in latest.values()]
    predicted = aggregate(items)

    per_task: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "pct_sum": 0.0})
    for a in atts:
        if a.max_score:
            per_task[a.task]["attempts"] += 1
            per_task[a.task]["pct_sum"] += a.score / a.max_score
    tasks = {t: {"attempts": v["attempts"], "avg": round(100 * v["pct_sum"] / v["attempts"])} for t, v in per_task.items()}

    days: dict[str, int] = defaultdict(int)
    for a in atts:
        days[a.created_at.date().isoformat()] += 1
    streak, d = 0, date.today()
    while days.get(d.isoformat()):
        streak += 1
        d -= timedelta(days=1)

    # weekly trend of predicted overall (cumulative up to each week)
    trend = []
    for w in range(11, -1, -1):
        end = now() - timedelta(weeks=w)
        lat: dict[str, Attempt] = {}
        for a in atts:
            if a.created_at.replace(tzinfo=end.tzinfo) <= end:
                lat[a.question_id] = a
        if lat:
            agg = aggregate([{"task": a.task, "score": a.score, "max": a.max_score, "traits": a.result.get("traits", [])} for a in lat.values()])
            trend.append({"week": end.date().isoformat(), "overall": agg["overall"], **agg["skills"]})
    usage = db.query(Usage).filter_by(user_id=user.id, day=date.today()).first()
    limit = PLANS[user.effective_plan()]["daily_ai_scores"]
    return {"predicted": predicted, "tasks": tasks, "activity": dict(days), "streak": streak, "total_attempts": len(atts),
            "trend": trend, "target": user.target_score,
            "quota": {"used": usage.ai_scores if usage else 0, "limit": limit}}
