#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# health-check.sh — Prüft alle 14 Ports + Tunnel
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/../config/services.yaml"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

failures=0
total=0

echo "═══════════════════════════════════════════"
echo "  🩺 Health-Check — $(date '+%H:%M:%S')"
echo "═══════════════════════════════════════════"

# Ports aus YAML lesen
python3 -c "
import yaml
with open('$CONFIG') as f:
    data = yaml.safe_load(f)
for s in data['services']:
    print(f\"{s['port']}|{s['name']}|{s['domain']}\")
" | while IFS='|' read -r port name domain; do
  total=$((total + 1))
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" --max-time 3 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    echo -e "  ${GREEN}✅${NC} $name (Port $port)"
  else
    echo -e "  ${RED}❌${NC} $name (Port $port) — HTTP $code"
    failures=$((failures + 1))
  fi
done

echo "───────────────────────────────────────────"
echo "  Tunnel: $(ps aux | grep 'cloudflared tunnel' | grep -v grep | wc -l) Prozesse"
echo "═══════════════════════════════════════════"
