# Production Dockerfile for Token Guard Proxy
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and pyproject
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application source code
COPY . /app/token_guard

ENV TOKEN_GUARD_HOST=0.0.0.0
ENV TOKEN_GUARD_PORT=8088
ENV PYTHONPATH=/app

EXPOSE 8088

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8088/metrics || exit 1

# Run with multi-worker uvicorn
CMD ["uvicorn", "token_guard.server:app", "--host", "0.0.0.0", "--port", "8088", "--workers", "4"]
