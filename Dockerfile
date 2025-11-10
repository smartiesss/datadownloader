# Multi-stage build for ETH Options Tick Data Collector
# Optimized for NAS deployment (QNAP/TerraMaster)

FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user (non-root for security)
RUN useradd -m -u 1000 collector && \
    mkdir -p /app/logs /app/data && \
    chown -R collector:collector /app

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=collector:collector scripts/ ./scripts/
COPY --chown=collector:collector config/ ./config/
COPY --chown=collector:collector schema/ ./schema/

# Switch to non-root user
USER collector

# Health check (check if process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD pgrep -f ws_tick_collector || exit 1

# Environment variables (overridable via docker-compose)
ENV PYTHONUNBUFFERED=1 \
    POSTGRES_HOST=timescaledb \
    POSTGRES_PORT=5432 \
    POSTGRES_DB=crypto_data \
    POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=changeme \
    LOG_LEVEL=INFO

# Expose metrics port (for future Prometheus integration)
EXPOSE 9090

# Run collector
CMD ["python", "-m", "scripts.ws_tick_collector"]
