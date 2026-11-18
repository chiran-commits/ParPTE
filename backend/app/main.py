"""ParPTE API.  Run:  uvicorn app.main:app --reload  (from /backend)"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, FRONTEND_DIST
from .db import init_db
from .routes import admin, auth, mock, practice

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="ParPTE API", version="1.0.0", description="AI scoring for PTE Academic practice", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, practice.router, mock.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the built frontend (single-container deployment)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = FRONTEND_DIST / path
        if path and f.is_file() and FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(FRONTEND_DIST / "index.html")
