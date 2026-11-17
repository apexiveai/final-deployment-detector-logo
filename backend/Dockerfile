
# =========================================================
# APEXIVEAI GLOBAL TRADEMARK INTELLIGENCE
# Production Backend Dockerfile
# Python 3.12 + FastAPI + OpenCLIP + Qdrant
# =========================================================

FROM python:3.12-slim

# Application environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8081

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./requirements.txt

RUN python -m pip install --upgrade pip && \
    python -m pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install -r requirements.txt

# Copy application source
COPY app/ ./app/

# Create non-root application user
RUN groupadd --system appuser && \
    useradd --system --gid appuser --home-dir /app appuser && \
    chown -R appuser:appuser /app

USER appuser

# API port
EXPOSE 8081

# Start FastAPI
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8081}"]
