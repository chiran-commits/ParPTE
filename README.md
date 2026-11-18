# ParPTE

PTE Academic practice platform with AI scoring for all four skills. It covers all 22 question types in the current (August 2025) format, mock tests, a progress dashboard with 10–90 score predictions, and subscription plans ready for commercial use.

> ParPTE is independent and not affiliated with Pearson. Pearson's scoring model is private. ParPTE follows the **published** PTE Academic trait rubric and scores with speech and language models, so its scores are close estimates, not official results.

## What's inside

| | |
|---|---|
| **Speaking** (8 types) | Read Aloud, Repeat Sentence, Describe Image, Re-tell Lecture, Answer Short Question, **Summarize Group Discussion**, **Respond to a Situation**, Personal Introduction. Scored on content, oral fluency and pronunciation, with word-by-word Read Aloud review, pause/hesitation detection, per-word pronunciation and PTE's 3-second silence cut-off. |
| **Writing** | Summarize Written Text and Write Essay on the 2025 trait scales (essay content /6, DSC /6, GLR /6 …), with the content/form zero rule, spelling, grammar and vocabulary range. |
| **Reading** (5 types) | Pearson's partial-credit rules: negative marking for multiple-answer questions, adjacent-pair scoring for Re-order Paragraphs, per-blank scoring. |
| **Listening** (8 types) | Audio plays once (with replay in practice mode). WFD is scored per word, HIW uses +1/−1 marking, SST is fully trait-scored. |
| **Mock tests** | Full, mini and single-section tests in exam order. Scores stay hidden until you finish. |
| **Dashboard** | Predicted overall and per-skill score on the 10–90 scale against your target, weekly trend, weakest question types, skills profile. |
| **Business** | Free / Pro / Premium plans, daily AI-scoring quota, admin panel (users, plans, add questions), payment-provider hook. Accounts listed in `ADMIN_EMAILS` get everything free. |

## Quick start (development)

Requirements: Python 3.11+, Node 20+, `ffmpeg` on your PATH.

```bash
# 1. API
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
ADMIN_EMAILS=you@example.com uvicorn app.main:app --reload          # http://127.0.0.1:8000/docs

# 2. Web app (second terminal)
cd frontend
npm install
npm run dev                                                         # http://localhost:5173
```

Register with the email you put in `ADMIN_EMAILS` and your account gets developer access: every plan feature, free. In development, if `ADMIN_EMAILS` is empty, the **first** account registered becomes admin.

Speaking works out of the box in **Chrome or Edge**: the browser transcribes your speech, and the server measures pauses, pace and intonation from the recording.

## The full AI engine

```bash
cd backend
pip install -r requirements-ml.txt     # Whisper, wav2vec2 phoneme model, sentence embeddings, ONNX runtime
uvicorn app.main:app
```

On first start the server downloads its models (about 1.5 GB, then cached). After that:

* **Whisper** transcribes on the server with word timings and keeps fillers like "um", so fluency is measured precisely and every browser works.
* **A phoneme model** compares the sounds you made with the sounds each word needs, which gives real pronunciation scores and per-word feedback.
* **Sentence embeddings** judge content relevance for Describe Image, Re-tell Lecture, the summaries and essays.

**Settings → Scoring engine** in the app shows what's active. `WHISPER_MODEL=small.en` is more accurate than `base.en` if you have the CPU or GPU for it.

## Training the models on Kaggle (free GPU)

See [`kaggle/README.md`](kaggle/README.md). Two notebooks train on Kaggle's GPUs, so the heavy compute runs there and costs nothing:

1. `01_speaking_pronunciation_fluency.ipynb`: pronunciation and fluency models on speechocean762 (expert-rated L2 speech).
2. `02_writing_traits_ellipse.ipynb`: a DeBERTa-v3 essay-trait model on the ELLIPSE learner-essay corpus.

Unzip the outputs into `backend/models/` and restart. The server blends them with the rubric scorer automatically.

## Deploy

```bash
cp .env.example .env        # set SECRET_KEY and ADMIN_EMAILS
docker compose up --build   # app + Postgres on http://localhost:8000
```

The Docker image builds the frontend and serves it from FastAPI, so you deploy a single container. It works on Railway, Render, Fly.io, a VPS, or any container host. Use `ML=0` as a build arg for a small image without the speech models. Commercial setup (payments, content, legal) is covered in [`docs/COMMERCIAL.md`](docs/COMMERCIAL.md).

### Frontend on Vercel, backend elsewhere

Vercel can't run the API (it needs ffmpeg, a database and long audio processing), but it can host the frontend:

1. Deploy the backend container (Render, Railway, Fly.io or a VPS) with `SECRET_KEY`, `ADMIN_EMAILS`, `DATABASE_URL` (any Postgres, e.g. Neon or Supabase) and `CORS_ORIGINS=https://your-app.vercel.app`.
2. On Vercel, import the repo with **Root Directory** `frontend` (Vite is detected automatically) and set the environment variable `VITE_API_URL=https://your-backend-host`.
3. Redeploy. `frontend/vercel.json` already routes every page to the single-page app.

## Project layout

```
backend/
  app/
    scoring/        # the engine: text, lexicon, audio, asr, phoneme, speaking, writing, objective, overall, models
    bank/data/      # original question bank (JSON) — add more here or from the admin panel
    routes/         # auth, practice, mock tests, admin + billing
    tasks.py        # 22 task types: timings, modules, integrated-skill weights, mock blueprints
  tests/            # 24 tests incl. real synthesized speech through the speaking pipeline
  models/           # drop Kaggle-trained models here
frontend/src/
  tasks/            # exam-style players for every question type
  pages/            # landing, dashboard, practice, mock tests, plans, settings, admin
  lib/audio.ts      # recorder with silence cut-off, TTS prompts, browser speech recognition
kaggle/             # training notebooks
docs/               # SCORING.md, COMMERCIAL.md
```

## Tests

```bash
cd backend && pytest -q                 # needs ffmpeg; speaking tests also use espeak-ng if installed
cd frontend && npm run build
```

## Roadmap ideas

* Pre-rendered neural voices for listening audio (Piper / a TTS service) instead of browser TTS
* Calibrate `scoring/overall.py → CURVE` against real PTE results from your users
* Payment provider integration (PayHere / Stripe / Paddle): stub in `routes/admin.py`
* Larger question bank. The JSON format is documented in `app/bank/__init__.py`
