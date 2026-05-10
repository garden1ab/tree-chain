#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# ── Colours ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${CYAN}[DialogueForge]${NC} $*"; }
ok()    { echo -e "${GREEN}[DialogueForge]${NC} $*"; }
err()   { echo -e "${RED}[DialogueForge]${NC} $*" >&2; }

# ── Preflight ────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || { err "Docker is not installed."; exit 1; }
command -v docker compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || {
  err "docker compose / docker-compose not found."; exit 1;
}

COMPOSE_CMD="docker compose"
if ! docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
fi

# ── .env ─────────────────────────────────────────────────
if [ ! -f .env ]; then
  info "Creating .env from .env.example …"
  cp .env.example .env
  info "⚠  Edit .env to add your ELEVENLABS_API_KEY before generating audio."
fi

# ── Build & launch ───────────────────────────────────────
info "Building containers …"
$COMPOSE_CMD build

info "Starting services …"
$COMPOSE_CMD up -d

echo ""
ok "═══════════════════════════════════════════════"
ok "  DialogueForge is running!"
ok "  Frontend:  http://localhost:3000"
ok "  API:       http://localhost:3000/api"
ok "  API Docs:  http://localhost:3000/api/docs"
ok "═══════════════════════════════════════════════"
echo ""
info "Logs:   $COMPOSE_CMD logs -f"
info "Stop:   $COMPOSE_CMD down"
