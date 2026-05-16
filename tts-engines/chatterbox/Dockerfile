FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch first (CPU version - smaller, works without GPU)
RUN pip install --no-cache-dir \
    torch==2.6.0 \
    torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Install Chatterbox + web dependencies
RUN pip install --no-cache-dir \
    chatterbox-tts \
    fastapi==0.115.6 \
    uvicorn[standard]==0.34.0 \
    python-multipart==0.0.20 \
    numpy<2.0

COPY server.py .

RUN mkdir -p /app/voices /app/models

EXPOSE 4123

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "4123"]
