#!/bin/bash
# Server auto-deploy: bootstrap .env on first run, pull THIS worktree's tracking branch,
# rebuild its compose stack if changed. Each environment is its own worktree on its own
# branch (prod worktree -> production, staging -> pre-production); the stack is selected by
# COMPOSE_PROJECT_NAME in that worktree's .env (docker compose reads it automatically).
# Usage: `*/5 * * * * cd /home/jy/TOWA-prod && ./deploy.sh >> deploy.log 2>&1` (one cron per env).

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# Deploy whatever branch this worktree is checked out on — no forced branch switch.
BRANCH=$(git rev-parse --abbrev-ref HEAD)

STUCK_MARKER=".deploy-stuck-at-sha"
NEEDS_BUILD=0

if [ ! -f .env ]; then
  cp .env.deploy .env
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] .env initialized from .env.deploy"
  NEEDS_BUILD=1
fi

git fetch origin "$BRANCH" --quiet

LOCAL=$(git rev-parse "$BRANCH" 2>/dev/null || echo "none")
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" != "$REMOTE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $BRANCH updated: $LOCAL -> $REMOTE"
  git pull origin "$BRANCH"
  NEEDS_BUILD=1
  # New code arrived — clear any stuck-build marker so we retry.
  rm -f "$STUCK_MARKER"
fi

POST_PULL_SHA=$(git rev-parse HEAD)

EXPECTED_SERVICES=$(printf "db\nmodel-engine\nservice-engine\nui-engine\n")
RUNNING_SERVICES=$(docker compose ps --status running --services 2>/dev/null | sort)
if [ "$RUNNING_SERVICES" != "$EXPECTED_SERVICES" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] some services are not running, will rebuild"
  NEEDS_BUILD=1
fi

if [ "$NEEDS_BUILD" -eq 0 ]; then
  exit 0
fi

# Guard against rebuild-loop: if we already attempted a build at this exact SHA and
# the result is still broken, don't burn CPU rebuilding every 5min. Surface the failing
# logs and exit non-zero so the cron log shows clearly what to investigate.
if [ -f "$STUCK_MARKER" ] && [ "$(cat "$STUCK_MARKER")" = "$POST_PULL_SHA" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] SKIP rebuild — already attempted at $POST_PULL_SHA and services still down."
  echo "  Inspect with: docker compose logs --tail 50 ui-engine service-engine model-engine"
  echo "  Common cause: VITE_UI_*_BACKEND in .env conflicting with VITE_UI_BACKEND_MODE master switch."
  echo "  After fixing .env (or pushing a fix to main), remove $STUCK_MARKER to allow retry:"
  echo "    rm $REPO_DIR/$STUCK_MARKER"
  exit 1
fi

docker compose up -d --build

# Give services a moment to either come up or crash, then verify.
sleep 10
POST_BUILD_RUNNING=$(docker compose ps --status running --services 2>/dev/null | sort)
if [ "$POST_BUILD_RUNNING" != "$EXPECTED_SERVICES" ]; then
  echo "$POST_PULL_SHA" > "$STUCK_MARKER"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] build done but not all services are running. Marker written."
  echo "  Expected: $(echo "$EXPECTED_SERVICES" | tr '\n' ' ')"
  echo "  Running:  $(echo "$POST_BUILD_RUNNING" | tr '\n' ' ')"
  for svc in db service-engine model-engine ui-engine; do
    if ! echo "$POST_BUILD_RUNNING" | grep -qx "$svc"; then
      echo "--- $svc logs (last 20 lines) ---"
      docker compose logs --tail 20 "$svc" 2>&1 | sed 's/^/  /'
    fi
  done
  exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] deploy done"
