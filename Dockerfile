FROM python:3.11-slim

# Install system dependencies including ffmpeg and libopus for voice/music
# cache-bust: v3
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        ffmpeg \
        libopus0 \
        libopus-dev \
        libffi-dev \
        libnacl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# cache-bust: v7 - fix debug endpoint + health check cookie path
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

# Render injects PORT env var; expose it (actual value set at runtime)
EXPOSE 10000

CMD ["gunicorn", "--worker-class", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "--workers", "1", "--bind", "0.0.0.0:10000", "--timeout", "120", "wsgi:app"]
