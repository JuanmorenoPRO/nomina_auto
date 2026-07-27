# Stage 1: build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: backend + static files
FROM python:3.12-slim
WORKDIR /app/backend
RUN pip install uv --no-cache-dir
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
ENV PYTHONPATH=/app/backend/src
ENV STATIC_DIR=/app/frontend/dist
CMD sh -c "uv run --no-sync alembic upgrade head && \
  uv run --no-sync uvicorn nomina.infraestructura.api.app:crear_app \
  --factory --host 0.0.0.0 --port ${PORT:-8001}"
