# ============================================
# world-novel — Multi-Stage Docker Build
# Stage 1: Build frontend
# Stage 2: Python runtime
# ============================================

# ── Stage 1: Frontend Build ──────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci --silent
COPY web/ .
RUN npm run build

# ── Stage 2: Python Runtime ──────────────
FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy Python project files
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Non-root user
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]

CMD ["uv", "run", "novel-creator", "web", "--host", "0.0.0.0", "--port", "8000"]
