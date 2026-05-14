#!/bin/bash
set -e

KOKORO_DIR=/app/models/kokoro
ONNX_FILE="$KOKORO_DIR/kokoro-v0_19.onnx"
VOICES_FILE="$KOKORO_DIR/voices.bin"
LOCK_FILE="$KOKORO_DIR/.downloading"

mkdir -p "$KOKORO_DIR"

# Wait if another container is currently downloading
WAIT_COUNT=0
while [ -f "$LOCK_FILE" ] && [ $WAIT_COUNT -lt 120 ]; do
  echo "[DialogueForge] Waiting for another container to finish downloading Kokoro models..."
  sleep 5
  WAIT_COUNT=$((WAIT_COUNT + 5))
done

# Download if model file doesn't exist or is too small (incomplete download)
if [ ! -f "$ONNX_FILE" ] || [ "$(stat -c%s "$ONNX_FILE" 2>/dev/null || echo 0)" -lt 1000000 ]; then
  touch "$LOCK_FILE"
  echo "[DialogueForge] Downloading Kokoro TTS model (~310MB)..."
  wget -q -O "$ONNX_FILE.tmp" \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx && \
    mv "$ONNX_FILE.tmp" "$ONNX_FILE"
  echo "[DialogueForge] Downloading Kokoro voices..."
  wget -q -O "$VOICES_FILE.tmp" \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin && \
    mv "$VOICES_FILE.tmp" "$VOICES_FILE"
  rm -f "$LOCK_FILE"
  echo "[DialogueForge] Kokoro models ready."
else
  echo "[DialogueForge] Kokoro models found."
fi

exec "$@"
