from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
                       pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | pro | premium
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_score: Mapped[int] = mapped_column(Integer, default=79)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    accent: Mapped[str] = mapped_column(String(10), default="en-GB")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    attempts = relationship("Attempt", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def effective_plan(self) -> str:
        if self.is_admin:
            return "premium"
        if self.plan != "free" and self.plan_expires_at and self.plan_expires_at.replace(tzinfo=timezone.utc) < now():
            return "free"
        return self.plan

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "role": self.role, "plan": self.effective_plan(),
                "plan_expires_at": self.plan_expires_at.isoformat() if self.plan_expires_at else None,
                "target_score": self.target_score, "exam_date": self.exam_date.isoformat() if self.exam_date else None,
                "accent": self.accent, "created_at": self.created_at.isoformat() if self.created_at else None}


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(64), index=True)
    task: Mapped[str] = mapped_column(String(64), index=True)
    module: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    band: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict] = mapped_column(JSON)
    response: Mapped[dict] = mapped_column(JSON)
    mock_id: Mapped[int | None] = mapped_column(ForeignKey("mocks.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    user = relationship("User", back_populates="attempts")

    def public(self, full: bool = False) -> dict:
        d = {"id": self.id, "question_id": self.question_id, "task": self.task, "module": self.module, "score": self.score,
             "max": self.max_score, "band": self.band, "created_at": self.created_at.isoformat(), "mock_id": self.mock_id,
             "traits": self.result.get("traits", [])}
        if full:
            d["result"], d["response"] = self.result, self.response
        return d


class Mock(Base):
    __tablename__ = "mocks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    question_ids: Mapped[list] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomQuestion(Base):
    __tablename__ = "custom_questions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Usage(Base):
    __tablename__ = "usage"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    ai_scores: Mapped[int] = mapped_column(Integer, default=0)


def init_db() -> None:
    Base.metadata.create_all(engine)
    from . import bank

    with SessionLocal() as s:
        for cq in s.query(CustomQuestion).all():
            try:
                bank.register_extra(cq.task, cq.data | {"id": cq.id})
            except Exception:  # a malformed custom question must not take the app down
                pass


__all__ = ["engine", "SessionLocal", "User", "Attempt", "Mock", "CustomQuestion", "Usage", "init_db", "now", "json"]
