from __future__ import annotations

import random

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import bank
from ..config import PLANS
from ..db import Attempt, Mock, User, now
from ..scoring import coach
from ..scoring.overall import aggregate
from ..security import current_user, get_db
from ..tasks import MOCK_BLUEPRINT, TASKS
from .practice import run_scoring

router = APIRouter(prefix="/api/mock", tags=["mock"])

# Pearson's section order
ORDER = ["personal_introduction", "read_aloud", "repeat_sentence", "describe_image", "retell_lecture", "answer_short_question",
         "summarize_group_discussion", "respond_to_situation", "summarize_written_text", "write_essay",
         "rw_fill_blanks", "mcq_multiple_reading", "reorder_paragraphs", "reading_fill_blanks", "mcq_single_reading",
         "summarize_spoken_text", "mcq_multiple_listening", "listening_fill_blanks", "highlight_correct_summary",
         "mcq_single_listening", "select_missing_word", "highlight_incorrect_words", "write_from_dictation"]


class NewMock(BaseModel):
    kind: str = "mini"
    module: str | None = None  # sectional mock: speaking | writing | reading | listening


@router.post("")
def create(body: NewMock, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.kind not in MOCK_BLUEPRINT:
        raise HTTPException(422, "Unknown mock type")
    if body.kind not in PLANS[user.effective_plan()]["mocks"]:
        raise HTTPException(402, "Full mock tests are available on the Pro plan.")
    rng = random.Random()
    ids: list[str] = []
    for task in ORDER:
        n = MOCK_BLUEPRINT[body.kind].get(task, 0)
        if body.module and TASKS[task]["module"] != body.module:
            continue
        pool = bank.all_questions(task)
        ids += [q["id"] for q in rng.sample(pool, min(n, len(pool)))]
    m = Mock(user_id=user.id, kind=body.kind if not body.module else f"{body.kind}:{body.module}", question_ids=ids)
    db.add(m)
    db.commit()
    return _view(m)


def _view(m: Mock, with_questions: bool = True) -> dict:
    d = {"id": m.id, "kind": m.kind, "created_at": m.created_at.isoformat(), "finished_at": m.finished_at.isoformat() if m.finished_at else None,
         "result": m.result, "count": len(m.question_ids)}
    if with_questions:
        d["questions"] = [bank.public(q) for q in (bank.get(i) for i in m.question_ids) if q]
    return d


def _own(db: Session, user: User, mid: int) -> Mock:
    m = db.get(Mock, mid)
    if not m or m.user_id != user.id:
        raise HTTPException(404, "Mock test not found")
    return m


@router.get("")
def list_mocks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ms = db.query(Mock).filter_by(user_id=user.id).order_by(Mock.created_at.desc()).limit(50).all()
    return [_view(m, with_questions=False) for m in ms]


@router.get("/{mid}")
def get_mock(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _own(db, user, mid)
    d = _view(m)
    d["answered"] = [a.question_id for a in db.query(Attempt).filter_by(mock_id=m.id).all()]
    return d


@router.post("/{mid}/answer/{qid}")
def answer(mid: int, qid: str, response: str = Form("{}"), audio: UploadFile | None = File(None),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _own(db, user, mid)
    if m.finished_at:
        raise HTTPException(409, "This mock test is already finished")
    if qid not in m.question_ids:
        raise HTTPException(422, "Question is not part of this mock test")
    db.query(Attempt).filter_by(mock_id=m.id, question_id=qid).delete()
    att, _ = run_scoring(db, user, qid, response, audio, mock_id=m.id)
    return {"ok": True, "attempt_id": att.id}  # scores stay hidden until the test is finished, like the real exam


@router.post("/{mid}/finish")
def finish(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _own(db, user, mid)
    atts = {a.question_id: a for a in db.query(Attempt).filter_by(mock_id=m.id).all()}
    items = []
    for qid in m.question_ids:
        q = bank.get(qid)
        if not q:
            continue
        a = atts.get(qid)
        if a:
            items.append({"task": a.task, "score": a.score, "max": a.max_score, "traits": a.result.get("traits", []),
                          "question_id": qid, "attempt_id": a.id})
        elif TASKS[q["task"]]["scored"]:
            # unanswered = 0 points; use the task's typical maximum so it counts against the score
            items.append({"task": q["task"], "score": 0, "max": 1, "traits": [], "question_id": qid, "attempt_id": None})
    agg = aggregate(items)
    agg["breakdown"] = items
    agg["coach"] = coach.mock_summary(agg, items, {k: v["name"] for k, v in TASKS.items()}, user.target_score)
    m.result, m.finished_at = agg, now()
    db.commit()
    return _view(m, with_questions=False)
