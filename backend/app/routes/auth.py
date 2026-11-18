from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import ADMIN_EMAILS, ENV
from ..db import User
from ..security import current_user, get_db, hash_password, make_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Register(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class Login(BaseModel):
    email: str
    password: str


class Profile(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    target_score: int | None = Field(default=None, ge=10, le=90)
    exam_date: date | None = None
    accent: str | None = Field(default=None, pattern=r"^en-(GB|US|AU|IN)$")


@router.post("/register")
def register(body: Register, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists")
    first = db.query(User).count() == 0
    role = "admin" if email in ADMIN_EMAILS or (first and not ADMIN_EMAILS and ENV == "development") else "user"
    u = User(email=email, name=body.name.strip() or email.split("@")[0], password_hash=hash_password(body.password), role=role)
    db.add(u)
    db.commit()
    return {"token": make_token(u), "user": u.public()}


@router.post("/login")
def login(body: Login, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if u.email in ADMIN_EMAILS and u.role != "admin":
        u.role = "admin"
        db.commit()
    return {"token": make_token(u), "user": u.public()}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user.public()


@router.patch("/me")
def update_me(body: Profile, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.merge(user)
    db.commit()
    return user.public()
