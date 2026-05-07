#!/bin/bash
# Server auto-deploy: bootstrap .env on first run, pull main, rebuild if changed.
# Usage: cron entry like `*/5 * * * * /path/to/TOWA/deploy.sh >> /path/to/TOWA/deploy.log 2>&1`

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

NEEDS_BUILD=0

if [ ! -f .env ]; then
  cp .env.deploy .env
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] .env initialized from .env.deploy"
  NEEDS_BUILD=1
fi

git fetch origin main --quiet

LOCAL=$(git rev-parse main 2>/dev/null || echo "none")
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] main updated: $LOCAL -> $REMOTE"
  CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
  if [ "$CURRENT_BRANCH" != "main" ]; then
    git checkout main
  fi
  git pull origin main
  NEEDS_BUILD=1
fi

EXPECTED_SERVICES=$(printf "db\nmodel-engine\nservice-engine\nui-engine\n")
RUNNING_SERVICES=$(docker compose ps --status running --services 2>/dev/null | sort)
if [ "$RUNNING_SERVICES" != "$EXPECTED_SERVICES" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] some services are not running, will rebuild"
  NEEDS_BUILD=1
fi

if [ "$NEEDS_BUILD" -eq 0 ]; then
  exit 0
fi

docker compose up -d --build

echo "[$(date '+%Y-%m-%d %H:%M:%S')] deploy done"
