#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# start-all.sh — Startet alle 14 Dienste deterministisch
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/../config/services.yaml"
BASE="/opt/data"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# YAML parsen (ohne externe Tools)
parse_yaml() {
  python3 -c "
import yaml, sys
with open('$CONFIG') as f:
    data = yaml.safe_load(f)
for s in data['services']:
    print(f\"{s['port']}|{s['repo']}|{s['app_file']}|{s['name']}\")
"
}

log "🚀 Starte alle Dienste..."

while IFS='|' read -r port repo app_file name; do
  REPO_DIR="$BASE/$repo"
  VENV="$REPO_DIR/.venv"
  APP_PATH="$REPO_DIR/$app_file"

  if [ ! -d "$REPO_DIR" ]; then
    log "❌ $name: Repo nicht gefunden — $REPO_DIR"
    continue
  fi

  if [ ! -f "$APP_PATH" ]; then
    log "❌ $name: App nicht gefunden — $APP_PATH"
    continue
  fi

  # Prüfen ob schon läuft
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" --max-time 2 | grep -q 200; then
    log "✅ $name (Port $port) — läuft bereits"
    continue
  fi

  log "⚠️  $name (Port $port) — starte..."
  pkill -f "streamlit run.*$port" 2>/dev/null || true
  sleep 1

  cd "$REPO_DIR"
  source "$VENV/bin/activate"
  nohup streamlit run "$app_file" --server.port "$port" --server.headless true \
    >> "/tmp/$repo.log" 2>&1 &
  log "   PID $! gestartet"
done < <(parse_yaml)

log "✅ Alle Dienste gestartet"
