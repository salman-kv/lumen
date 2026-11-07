# Stage 1: build the React frontend
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: FastAPI backend serving the API and the built frontend
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY sample_data /app/sample_data
COPY --from=web /web/dist /app/frontend/dist
ENV DATA_DIR=/data \
    FASTEMBED_CACHE_PATH=/app/models \
    SEED_DEMO=true \
    PATH="/app/backend/.venv/bin:$PATH"
# Bake the small System 1 models (about 150 MB) into the image so the first question is not slow.
RUN mkdir -p /data /app/models \
 && python -c "from app import models_s1; models_s1.warmup()" \
 && useradd -m -u 1000 app && chown -R app /data /app/models
USER app
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
