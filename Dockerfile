# FreightGuard Dockerfile
# Multi-stage lightweight Python container for FreightGuard
FROM python:3.12-slim AS base

WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and static assets
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run_server.py .

# Create data directory for SQLite WAL database
RUN mkdir -p /app/data

# Expose HTTP port
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

# Launch production server
CMD ["python", "run_server.py"]
