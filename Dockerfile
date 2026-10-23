# path: Dockerfile
# Production Dockerfile for Nebius Serverless AI & Container Deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for SQLCipher and sqlite-vec
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlcipher-dev \
    sqlite3 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (including sqlcipher3)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create volume mount points for persistent encrypted DB and sandbox
RUN mkdir -p /app/data/sandbox

# Default environment configuration
ENV PYTHONUNBUFFERED=1
ENV MEMORY_ENCRYPTION=on
ENV MEMORY_DB_PATH=/app/data/memory.db
ENV SANDBOX_ROOT=/app/data/sandbox
ENV DAILY_COST_CAP_USD=5.00
ENV RATE_LIMIT_RPM=30

# Expose HTTP port
EXPOSE 8000

# Container health probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Launch uvicorn production server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
