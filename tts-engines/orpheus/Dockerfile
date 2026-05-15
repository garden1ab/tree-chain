FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn[standard]==0.34.0 \
    httpx \
    numpy

COPY server.py .

ENV ORPHEUS_API_URL=http://orpheus-llm:5006/v1/completions
ENV ORPHEUS_SAMPLE_RATE=24000

EXPOSE 8899

HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
  CMD curl -f http://localhost:8899/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8899", "--workers", "1"]
