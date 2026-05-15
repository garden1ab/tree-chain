#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# DialogueForge TTS Engine Setup
# ═══════════════════════════════════════════════════════════════
#
# This starts the TTS model services that DialogueForge connects to.
# Run this SEPARATELY from the main DialogueForge docker-compose.
#
# Each engine runs independently with its own Web UI for testing.
#
# Usage:
#   ./start.sh              # Start all engines
#   ./start.sh kokoro       # Start only Kokoro (CPU, fast)
#   ./start.sh chatterbox   # Start only Chatterbox (GPU, best quality)
#   ./start.sh orpheus      # Start only Orpheus (GPU, emotion control)

set -e
cd "$(dirname "$0")"

ENGINE="${1:-all}"

echo "═══════════════════════════════════════════════"
echo " DialogueForge TTS Engines"
echo "═══════════════════════════════════════════════"

case "$ENGINE" in
  kokoro)
    echo "Starting Kokoro (CPU, fast, 26 voices)..."
    echo "Web UI: http://localhost:8880"
    docker compose up kokoro -d --build
    ;;
  chatterbox)
    echo "Starting Chatterbox (GPU, best quality, voice cloning)..."
    echo "Web UI: http://localhost:4123"
    docker compose up chatterbox -d
    ;;
  orpheus)
    echo "Starting Orpheus (GPU, emotion tags, 8 voices)..."
    echo "  Step 1: Downloading model (first time only)..."
    docker compose run --rm orpheus-init
    echo "  Step 2: Starting LLM server + API..."
    docker compose up orpheus-llm orpheus-api -d
    echo "Web UI: http://localhost:8899"
    ;;
  all)
    echo "Starting all TTS engines..."
    echo ""
    echo "  Kokoro:     http://localhost:8880  (CPU)"
    echo "  Chatterbox: http://localhost:4123  (GPU)"
    echo "  Orpheus:    http://localhost:8899  (GPU)"
    echo ""
    docker compose run --rm orpheus-init 2>/dev/null || true
    docker compose up -d --build
    ;;
  *)
    echo "Unknown engine: $ENGINE"
    echo "Usage: $0 [kokoro|chatterbox|orpheus|all]"
    exit 1
    ;;
esac

echo ""
echo "TTS engines starting. First run downloads models (~300MB-3GB)."
echo "Check logs: docker compose logs -f"
echo ""
echo "DialogueForge will auto-detect running engines."
