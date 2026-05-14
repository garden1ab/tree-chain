FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/outputs /app/models/kokoro

# Startup script downloads Kokoro models on first run if not present
RUN echo '#!/bin/bash\n\
set -e\n\
KOKORO_DIR=/app/models/kokoro\n\
if [ ! -f "$KOKORO_DIR/kokoro-v0_19.onnx" ]; then\n\
  echo "[DialogueForge] Downloading Kokoro TTS model (~310MB)..."\n\
  wget -q --show-progress -O "$KOKORO_DIR/kokoro-v0_19.onnx" \\\n\
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx\n\
  echo "[DialogueForge] Downloading Kokoro voices..."\n\
  wget -q -O "$KOKORO_DIR/voices.bin" \\\n\
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin\n\
  echo "[DialogueForge] Kokoro models ready."\n\
else\n\
  echo "[DialogueForge] Kokoro models already downloaded."\n\
fi\n\
exec "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
