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
#   ./start.sh kokoro       # Start only Kokoro (CPU, fast, ~310MB)
#   ./start.sh chatterbox   # Start only Chatterbox (CPU/GPU, best quality)
#   ./start.sh orpheus      # Start only Orpheus (GPU needed for speed)
#   ./start.sh all          # Start everything

set -e
cd "$(dirname "$0")"

ENGINE="${1:-kokoro}"

echo "═══════════════════════════════════════════════"
echo " DialogueForge TTS Engines"
echo "═══════════════════════════════════════════════"

case "$ENGINE" in
  kokoro)
    echo "Starting Kokoro (CPU, fast, 26 voices)..."
    echo "Web UI: http://localhost:8880"
    docker compose --profile kokoro up -d --build
    ;;
  chatterbox)
    echo "Starting Chatterbox (best quality, voice cloning)..."
    echo "Web UI: http://localhost:4123"
    docker compose --profile chatterbox up -d
    ;;
  orpheus)
    echo "Starting Orpheus (emotion tags, 8 voices)..."
    echo "First run will download ~3GB model from HuggingFace..."
    echo "Web UI: http://localhost:8899"
    docker compose --profile orpheus up -d --build
    ;;
  all)
    echo "Starting all TTS engines..."
    echo ""
    echo "  Kokoro:     http://localhost:8880  (CPU)"
    echo "  Chatterbox: http://localhost:4123  (CPU/GPU)"
    echo "  Orpheus:    http://localhost:8899  (GPU recommended)"
    echo ""
    docker compose --profile all up -d --build
    ;;
  stop|down)
    echo "Stopping all TTS engines..."
    docker compose --profile all down
    ;;
  *)
    echo "Unknown command: $ENGINE"
    echo "Usage: $0 [kokoro|chatterbox|orpheus|all|stop]"
    exit 1
    ;;
esac

echo ""
echo "View logs: docker compose logs -f"
echo "Stop:      ./start.sh stop"
