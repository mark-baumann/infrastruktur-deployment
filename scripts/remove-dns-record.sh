#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# remove-dns-record.sh — einen DNS-Record aus Cloudflare löschen
# ═══════════════════════════════════════════════════════════════
# Destruktiv: löst einen einzelnen DNS-Record (CNAME/A) für eine Domain.
# Nutzung: CF_API_TOKEN=xxx ./remove-dns-record.sh <domain>
#          CF_API_TOKEN=xxx ./remove-dns-record.sh <domain> --dry-run
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$REPO_ROOT/config/services.yaml"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

DRY_RUN=0
case "${2:-}" in
  --dry-run) DRY_RUN=1 ;;
esac

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  log "❌ Keine Domain übergeben. Nutzung: $0 <domain>"
  exit 1
fi

eval $(python3 -c "
import yaml
with open('$CONFIG') as f:
    d = yaml.safe_load(f)
cf = d.get('cloudflare', {})
print(f'ZONE_ID={cf.get(\"zone_id\", \"\")}')
")

if [ -z "$ZONE_ID" ]; then
  log "❌ zone_id fehlt in config/services.yaml"
  exit 1
fi

CF_TOKEN="${CF_API_TOKEN:-}"
if [ -z "$CF_TOKEN" ]; then
  log "❌ CF_API_TOKEN nicht gesetzt. Exportiere: export CF_API_TOKEN=xxx"
  exit 1
fi

API="https://api.cloudflare.com/client/v4"

RECORDS=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "$API/zones/$ZONE_ID/dns_records?name=$DOMAIN&per_page=100" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); [print('%s\t%s' % (r['id'], r['type'])) for r in d.get('result',[])]")

if [ -z "$RECORDS" ]; then
  log "ℹ️  Kein DNS-Record für $DOMAIN gefunden."
  exit 0
fi

log "Gefundene Records für $DOMAIN:"
echo "$RECORDS" | sed 's/^/  /'

if [ "$DRY_RUN" = "1" ]; then
  log "🟡 Dry-Run — würde löschen:"
  echo "$RECORDS" | awk -F'\t' '{print "  "$2" "$1}' >&2
  exit 0
fi

echo "$RECORDS" | while IFS=$'\t' read -r ID TYPE; do
  [ -z "$ID" ] && continue
  RESPONSE=$(curl -s -X DELETE -H "Authorization: Bearer $CF_TOKEN" \
    "$API/zones/$ZONE_ID/dns_records/$ID")
  OK=$(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('success'))")
  if [ "$OK" = "True" ]; then
    log "✅ gelöscht: $TYPE-Record $ID ($DOMAIN)"
  else
    log "❌ Fehler beim Löschen von $ID: $(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('errors'))")"
  fi
done

log "✅ DNS-Löschabgleich abgeschlossen"
