from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENV = os.getenv("ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'parpte.db'}")
# Hosts like Neon, Supabase, Render and Railway hand out postgres:// URLs; SQLAlchemy needs the driver name.
for _prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(_prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(_prefix):]
SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-insecure-key-change-me-before-deploying-0123456789" if ENV == "development" else secrets.token_urlsafe(48))
TOKEN_DAYS = int(os.getenv("TOKEN_DAYS", "30"))
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", ROOT.parent / "frontend" / "dist"))
MAX_AUDIO_MB = 12

# Subscription plans. Admins (the developer) always get everything for free.
PLANS = {
    "free": {"name": "Free", "price_usd": 0, "daily_ai_scores": 15, "mocks": ["mini"],
             "features": ["All 22 question types", "15 AI-scored answers per day", "Mini mock test", "Progress tracking"]},
    "pro": {"name": "Pro", "price_usd": 9, "daily_ai_scores": None, "mocks": ["mini", "full"],
            "features": ["Unlimited AI scoring", "Full & mini mock tests", "Detailed trait feedback", "Word-level pronunciation review"]},
    "premium": {"name": "Premium", "price_usd": 19, "daily_ai_scores": None, "mocks": ["mini", "full"],
                "features": ["Everything in Pro", "Priority scoring queue", "Score prediction report", "Early access to new questions"]},
}

# Tasks that consume an "AI score" (open responses). Objective tasks are always free.
AI_TASKS = {"read_aloud", "repeat_sentence", "describe_image", "retell_lecture", "answer_short_question",
            "summarize_group_discussion", "respond_to_situation", "summarize_written_text", "write_essay",
            "summarize_spoken_text"}
