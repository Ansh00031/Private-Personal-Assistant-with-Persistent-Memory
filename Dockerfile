# path: Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for SQLCipher and sqlite-vec
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlcipher-dev \
    sqlite3 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/sandbox

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]