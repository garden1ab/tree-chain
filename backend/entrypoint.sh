#!/usr/bin/env bash
set -e

KOKORO_DIR=/app/models/kokoro
ONNX_FILE="$KOKORO_DIR/kokoro-v0_19.onnx"
VOICES_FILE="$KOKORO_DIR/voices.bin"
DONE_FILE="$KOKORO_DIR/.done"

mkdir -p "$KOKORO_DIR"

echo "[DialogueForge] Starting container with command: $@"

# Only worker downloads the model
if [[ "$1" == "celery" ]]; then
    echo "[DialogueForge] Celery worker detected."

    if [ ! -f "$DONE_FILE" ]; then
        echo "[DialogueForge] Downloading Kokoro ONNX model..."

        wget --show-progress -O "$ONNX_FILE" \
          https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx

        echo "[DialogueForge] Downloading voices..."

        wget --show-progress -O "$VOICES_FILE" \
          https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

        if [ -f "$ONNX_FILE" ] && [ -f "$VOICES_FILE" ]; then
            touch "$DONE_FILE"
            echo "[DialogueForge] Models downloaded successfully."
        else
            echo "[DialogueForge] Model download failed."
            exit 1
        fi
    else
        echo "[DialogueForge] Existing models detected."
    fi
fi

exec "$@"
