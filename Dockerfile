# Multi-stage Dockerfile for xFACE
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime libraries for OpenCV plus curl for the health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data

# Unprivileged user; the "video" group grants access to /dev/video* devices
RUN useradd --create-home --uid 1000 --groups video xface \
    && mkdir -p /app/data \
    && chown xface:xface /app/data

COPY --chown=xface:xface . .

USER xface

EXPOSE 5000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fs http://localhost:5000/api/v1/system/status > /dev/null || exit 1

# A single worker process is required: the camera and recognition worker are in-process singletons.
# Threads serve concurrent MJPEG/SSE streams.
CMD ["gunicorn", "--workers", "1", "--threads", "32", "--timeout", "120", "--bind", "0.0.0.0:5000", "run:app"]
