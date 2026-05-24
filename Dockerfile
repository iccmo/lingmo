# ============================================================
# Stage 1: Build frontend
# ============================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Run Python backend
# ============================================================
FROM python:3.12-slim

# System dependencies: ffmpeg for TTS audio conversion, curl for healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install edge-tts separately (for TTS)
RUN pip install --no-cache-dir edge-tts

# Copy application code
COPY novel_writer/ novel_writer/
COPY publish_chapter.py .
COPY wechat_call.py .
COPY wechat_vision.py .

# Copy frontend dist from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Create data directory for SQLite persistence
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "novel_writer.server:app", "--host", "0.0.0.0", "--port", "8000"]
