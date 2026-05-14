#!/bin/bash
set -e

KOKORO_DIR=/app/models/kokoro
ONNX_FILE="$KOKORO_DIR/kokoro-v0_19.onnx"
VOICES_FILE="$KOKORO_DIR/voices.bin"
DONE_FILE="$KOKORO_DIR/.done"

mkdir -p "$KOKORO_DIR"

# Only download for the celery worker process (which actually runs TTS generation)
# The backend (uvicorn) doesn't need the model files
if echo "$@" | grep -q "celery"; then
  if [ ! -f "$DONE_FILE" ]; then
    echo "[DialogueForge] Downloading Kokoro TTS model (~310MB)..."
    wget -q -O "$ONNX_FILE" \
      https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx
    echo "[DialogueForge] Downloading Kokoro voices..."
    wget -q -O "$VOICES_FILE" \
      https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
    touch "$DONE_FILE"
    echo "[DialogueForge] Kokoro models ready."
  else
    echo "[DialogueForge] Kokoro models found."
  fi
fi

exec "$@"
