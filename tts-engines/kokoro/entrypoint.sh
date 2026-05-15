#!/bin/bash
set -e

MODEL_DIR="${MODEL_DIR:-/app/models}"
ONNX_FILE="$MODEL_DIR/kokoro-v0_19.onnx"
VOICES_FILE="$MODEL_DIR/voices.bin"
DONE_FILE="$MODEL_DIR/.done"

mkdir -p "$MODEL_DIR"

if [ ! -f "$DONE_FILE" ]; then
  echo "[Kokoro] Downloading model (~310MB)..."
  wget -q --show-progress -O "$ONNX_FILE" \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx
  echo "[Kokoro] Downloading voices..."
  wget -q -O "$VOICES_FILE" \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
  touch "$DONE_FILE"
  echo "[Kokoro] Models ready."
else
  echo "[Kokoro] Models found."
fi

exec "$@"
