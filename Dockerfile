# ---------- build the React frontend
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- API + static site
FROM python:3.12-slim
ARG ML=0
ENV PYTHONUNBUFFERED=1 ENV=production FRONTEND_DIST=/app/frontend/dist MODELS_DIR=/app/backend/models
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$ML" = "1" ]; then pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-ml.txt; fi
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}"]
