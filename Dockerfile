FROM python:3.11-slim

# Install system dependencies including ffmpeg and libopus for voice/music
# cache-bust: v2
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
# cache-bust: v2 - forces reinstall of yt-dlp and PyNaCl
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 5000

CMD ["python3", "bot.py"]
