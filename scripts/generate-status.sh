#!/usr/bin/env bash
# generate-status.sh — Docker-Status-JSON für das Status-Dashboard erzeugen
#
# Cron-Job auf dem Pi (alle 5 Minuten):
#   */5 * * * * /opt/data/stack/scripts/generate-status.sh
#
# Ausgabe: /opt/data/docker-status.json
# Format:  { "service-name": { "running": true|false, "status": "Up 2 hours" }, … }

set -euo pipefail

COMPOSE_FILE="/opt/data/stack/docker-compose.yml"
OUTPUT="/opt/data/docker-status.json"
TMP="$(mktemp)"

docker compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null \
  | python3 - <<'PY'
import sys, json

result = {}
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        c = json.loads(line)
    except json.JSONDecodeError:
        continue
    service = c.get("Service", "")
    if not service:
        continue
    result[service] = {
        "running": c.get("State", "") == "running",
        "status":  c.get("Status", ""),
    }

print(json.dumps(result, indent=2))
PY
> "$TMP"

if [ -s "$TMP" ]; then
    mv "$TMP" "$OUTPUT"
else
    echo '{}' > "$OUTPUT"
    rm -f "$TMP"
fi
