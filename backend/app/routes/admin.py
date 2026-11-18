from __future__ import annotations

import os
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import bank
from ..config import PLANS
from ..db import Attempt, CustomQuestion, User
from ..security import admin_user, current_user, get_db
from ..tasks import TASKS

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/admin/stats")
def stats(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return {
        "users": db.query(User).count(),
        "by_plan": dict(db.query(User.plan, func.count()).group_by(User.plan).all()),
        "attempts": db.query(Attempt).count(),
        "questions": bank.counts(),
    }


@router.get("/admin/users")
def users(q: str = "", _: User = Depends(admin_user), db: Session = Depends(get_db)):
    qs = db.query(User)
    if q:
        qs = qs.filter(User.email.contains(q.lower()))
    return [u.public() | {"attempts": len(u.attempts)} for u in qs.order_by(User.created_at.desc()).limit(200).all()]


class UserPatch(BaseModel):
    plan: str | None = None
    role: str | None = None
    plan_expires_at: datetime | None = None


@router.patch("/admin/users/{uid}")
def patch_user(uid: int, body: UserPatch, me: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if body.plan is not None:
        if body.plan not in PLANS:
            raise HTTPException(422, "Unknown plan")
        u.plan = body.plan
    if body.role is not None:
        if body.role not in ("user", "admin"):
            raise HTTPException(422, "Unknown role")
        if u.id == me.id and body.role != "admin":
            raise HTTPException(422, "You can't remove your own admin role")
        u.role = body.role
    if "plan_expires_at" in body.model_fields_set:
        u.plan_expires_at = body.plan_expires_at
    db.commit()
    return u.public()


class NewQuestion(BaseModel):
    task: str
    data: dict


@router.post("/admin/questions")
def add_question(body: NewQuestion, me: User = Depends(admin_user), db: Session = Depends(get_db)):
    if body.task not in TASKS:
        raise HTTPException(422, "Unknown task")
    qid = body.data.get("id") or f"{TASKS[body.task]['abbr'].lower()}-c{db.query(CustomQuestion).count() + 1:03d}"
    if not re.fullmatch(r"[a-z0-9-]{3,64}", qid) or bank.get(qid):
        raise HTTPException(422, "Invalid or duplicate question id")
    data = body.data | {"id": qid}
    try:
        q = bank.register_extra(body.task, data)
        bank.public(q)  # validates required fields exist
    except Exception as e:
        bank._extra.pop(qid, None)
        raise HTTPException(422, f"Invalid question: {e}")
    db.add(CustomQuestion(id=qid, task=body.task, data=data, created_by=me.id))
    db.commit()
    return bank.public(q)


@router.delete("/admin/questions/{qid}")
def delete_question(qid: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    cq = db.get(CustomQuestion, qid)
    if not cq:
        raise HTTPException(404, "Only admin-created questions can be deleted")
    db.delete(cq)
    bank._extra.pop(qid, None)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ billing (provider-agnostic stub)
class Checkout(BaseModel):
    plan: str


@router.post("/billing/checkout")
def checkout(body: Checkout, user: User = Depends(current_user)):
    """Wire a payment provider here. PayHere suits Sri Lanka-based merchants; Stripe/Paddle/Lemon Squeezy work
    internationally. On a successful payment webhook, set user.plan and user.plan_expires_at. See docs/COMMERCIAL.md."""
    if body.plan not in PLANS or body.plan == "free":
        raise HTTPException(422, "Unknown plan")
    provider = os.getenv("BILLING_PROVIDER")
    if not provider:
        raise HTTPException(501, "Payments aren't switched on yet. The site owner can upgrade your account from the admin panel.")
    raise HTTPException(501, f"Billing provider '{provider}' is configured but its integration is not implemented yet.")
