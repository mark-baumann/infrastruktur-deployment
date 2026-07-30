#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# stop-all.sh — Stoppt alle 14 Dienste
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/../config/services.yaml"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "🛑 Stoppe alle Dienste..."

python3 -c "
import yaml
with open('$CONFIG') as f:
    data = yaml.safe_load(f)
for s in data['services']:
    print(s['port'])
" | while read -r port; do
  pkill -f "streamlit run.*$port" 2>/dev/null && log "   Port $port gestoppt" || log "   Port $port — lief nicht"
done

log "✅ Alle Dienste gestoppt"
