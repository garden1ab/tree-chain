#!/usr/bin/env bash
set -e

KOKORO_DIR="/app/models/kokoro"

ONNX_FILE="$KOKORO_DIR/kokoro-v0_19.onnx"
VOICES_FILE="$KOKORO_DIR/voices.bin"

ONNX_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx"
VOICES_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

mkdir -p "$KOKORO_DIR"

echo "[DialogueForge] Container starting..."
echo "[DialogueForge] Command: $@"

download_models() {

    echo "[DialogueForge] Checking Kokoro model files..."

    if [ ! -s "$ONNX_FILE" ]; then
        echo "[DialogueForge] Downloading kokoro-v0_19.onnx (~310MB)..."

        wget \
            --tries=5 \
            --timeout=60 \
            --waitretry=5 \
            --retry-connrefused \
            --show-progress \
            -O "$ONNX_FILE" \
            "$ONNX_URL"

        echo "[DialogueForge] ONNX model download complete."
    else
        echo "[DialogueForge] ONNX model already exists."
    fi

    if [ ! -s "$VOICES_FILE" ]; then
        echo "[DialogueForge] Downloading voices.bin..."

        wget \
            --tries=5 \
            --timeout=60 \
            --waitretry=5 \
            --retry-connrefused \
            --show-progress \
            -O "$VOICES_FILE" \
            "$VOICES_URL"

        echo "[DialogueForge] Voices file download complete."
    else
        echo "[DialogueForge] Voices file already exists."
    fi

    if [ ! -s "$ONNX_FILE" ] || [ ! -s "$VOICES_FILE" ]; then
        echo "[DialogueForge] ERROR: Kokoro model download failed."
        exit 1
    fi

    echo "[DialogueForge] Kokoro models ready."
}

# Only Celery workers need TTS models
if [[ "$1" == "celery" ]]; then
    echo "[DialogueForge] Celery worker detected."

    download_models
else
    echo "[DialogueForge] API container detected. Skipping model download."
fi

echo "[DialogueForge] Launching process..."

exec "$@"
