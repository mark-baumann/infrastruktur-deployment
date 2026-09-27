#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# health-check.sh — Prüft alle HTTP-pruefbaren Services aus config/services.yaml
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

# Services aus der Quelle der Wahrheit lesen. Nur HTTP-pruefbare Eintraege:
# - ohne Port (z.B. WordPress-DB, port: null) ist kein HTTP-Check moeglich
# - healthcheck: none ist bewusst nicht ueberwacht
# Vorher wurden hier None-Ports als "❌ ... HTTP 000" gemeldet (Fehlalarm-Quelle).
mapfile -t HEALTHCHECK_SERVICES < <(python3 -c "
import yaml
with open('$CONFIG') as f:
    data = yaml.safe_load(f)
for s in data.get('services', []):
    if s.get('healthcheck') in (None, 'none'):
        continue
    port = s.get('port')
    if port is None:
        continue
    print(f\"{port}|{s['name']}\")
")

for row in "${HEALTHCHECK_SERVICES[@]}"; do
  IFS='|' read -r port name <<<"$row"
  total=$((total + 1))
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" --max-time 3 2>/dev/null) || true
  [ -n "$code" ] || code=000
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
