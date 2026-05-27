#!/bin/bash
# Flip VITE_UI_BACKEND_MODE across every env file in one shot.
# Usage:  ./scripts/set-backend-mode.sh real|emulated
#
# Touches:
#   ./.env                              (gitignored — local docker-compose env)
#   ./.env.local                        (gitignored — local override)
#   ./.env.deploy                       (tracked — deploy.sh fallback)
#   ./ui_engine/towa-app/.env           (gitignored — `npm run dev` env)
#
# A file is skipped silently if it doesn't exist. Per-domain overrides
# (VITE_UI_AUTH_BACKEND etc.) are left alone — they only take effect when
# master is 'emulated', and throw at startup when master is 'real'.

set -e

MODE="${1:-}"
if [ "$MODE" != "real" ] && [ "$MODE" != "emulated" ]; then
  echo "usage: $0 real|emulated" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

FILES=(
  ".env"
  ".env.local"
  ".env.deploy"
  "ui_engine/towa-app/.env"
)

VAR="VITE_UI_BACKEND_MODE"
LINE="${VAR}=${MODE}"

for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "skip  $f (missing)"
    continue
  fi
  if grep -q "^${VAR}=" "$f"; then
    # macOS/BSD sed needs '' after -i; portable approach: tmp file
    awk -v var="$VAR" -v line="$LINE" '
      $0 ~ "^"var"=" { print line; next }
      { print }
    ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
    echo "set   $f -> $LINE"
  else
    printf '\n%s\n' "$LINE" >> "$f"
    echo "add   $f -> $LINE"
  fi
done

echo ""

# When master=real, any per-domain '=emulated' line is a startup-throw timebomb.
# Warn explicitly so the operator notices before the next dev/server restart.
if [ "$MODE" = "real" ]; then
  warned=0
  for f in "${FILES[@]}"; do
    if [ -f "$f" ] && grep -qE '^VITE_UI_(AUTH|AI|FILES)_BACKEND=emulated' "$f"; then
      if [ "$warned" -eq 0 ]; then
        echo "WARNING: master=real, but found per-domain 'emulated' override(s) that will throw at startup:"
        warned=1
      fi
      grep -nE '^VITE_UI_(AUTH|AI|FILES)_BACKEND=emulated' "$f" | sed "s|^|  $f:|"
    fi
  done
  if [ "$warned" -eq 1 ]; then
    echo "  → Comment them out or change to 'real' before restarting."
  fi
fi

echo "done. Restart dev server / 'docker compose up -d --build ui-engine' to pick up the change."
