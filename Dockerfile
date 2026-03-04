# =============================================================================
# GeoMemo — Docker Image
# Runs the FastAPI backend + contains scraper dependencies.
# The scraper is triggered externally (host cron → docker exec).
#
# ARCHITECTURE:
#   - In dev/sandbox: code is volume-mounted, so git pull + restart works
#   - In production:  code is baked in via COPY (no volume mounts)
# =============================================================================

FROM python:3.11-slim

# System dependencies for psycopg2, lxml, scrapy, and SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (heavy layer — cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
# NOTE: In dev, these are overridden by docker-compose volume mounts.
#       In production (no volume mounts), the baked-in code is used.
COPY geomemo_api/    ./geomemo_api/
COPY geomemo_scraper/ ./geomemo_scraper/
COPY geomemo_newsletter/ ./geomemo_newsletter/

EXPOSE 8000

# Health check — hits the /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start FastAPI with --app-dir so absolute imports (from config import ...) work
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/geomemo_api"]
