#!/bin/bash
set -e

KOKORO_DIR=/app/models/kokoro
ONNX_FILE="$KOKORO_DIR/kokoro-v0_19.onnx"
VOICES_FILE="$KOKORO_DIR/voices.bin"
DONE_FILE="$KOKORO_DIR/.done"
LOCK_FILE="$KOKORO_DIR/.downloading"

mkdir -p "$KOKORO_DIR"

download_kokoro() {
  # If already fully downloaded, skip
  if [ -f "$DONE_FILE" ]; then
    echo "[DialogueForge] Kokoro models found."
    return
  fi

  # Wait if another container is currently downloading
  WAIT_COUNT=0
  while [ -f "$LOCK_FILE" ] && [ $WAIT_COUNT -lt 300 ]; do
    echo "[DialogueForge] Waiting for Kokoro download..."
    sleep 5
    WAIT_COUNT=$((WAIT_COUNT + 5))
  done

  # Re-check after waiting
  if [ -f "$DONE_FILE" ]; then
    echo "[DialogueForge] Kokoro models ready (downloaded by another container)."
    return
  fi

  # Download
  touch "$LOCK_FILE"
  echo "[DialogueForge] Downloading Kokoro TTS model (~310MB)..."
  wget -q -O "$ONNX_FILE" \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx
  echo "[DialogueForge] Downloading Kokoro voices..."
  wget -q -O "$VOICES_FILE" \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
  touch "$DONE_FILE"
  rm -f "$LOCK_FILE"
  echo "[DialogueForge] Kokoro models ready."
}

# Run download in background so the app starts immediately
download_kokoro &

exec "$@"
