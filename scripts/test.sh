#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

COMPOSE_CMD="docker compose"
if ! docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
fi

echo "[DialogueForge] Running backend tests …"
$COMPOSE_CMD run --rm --no-deps backend python -m pytest tests/ -v "$@"
