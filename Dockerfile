FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 forge && chown -R forge:forge /app
USER forge

# Install netcat for database health check in entrypoint
USER root
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd && rm -rf /var/lib/apt/lists/*
USER forge

# Environment
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Run with entrypoint (handles migrations)
ENTRYPOINT ["./entrypoint.sh"]
