#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

COMPOSE_CMD="docker compose"
if ! docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
fi

echo "[DialogueForge] Tearing down containers and volumes …"
$COMPOSE_CMD down -v --remove-orphans
echo "[DialogueForge] Rebuilding from scratch …"
$COMPOSE_CMD build --no-cache
echo "[DialogueForge] Starting fresh …"
$COMPOSE_CMD up -d
echo "[DialogueForge] Clean reset complete."
