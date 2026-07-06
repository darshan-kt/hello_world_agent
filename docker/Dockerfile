# ──────────────────────────────────────────────────────────
# Hello Agent — Dockerfile
# Multi-stage build for a lean production image
# ──────────────────────────────────────────────────────────

# ── Stage 1: Builder (install deps) ─────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime (lean final image) ─────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY agent/       ./agent/
COPY api/         ./api/
COPY web/         ./web/
COPY config.py    .
COPY main.py      .

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create data directory for persistent memory
RUN mkdir -p /app/data

# Expose web UI port
EXPOSE 8000

# Non-root user for security
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

ENTRYPOINT ["/entrypoint.sh"]
