#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ensure-dns.sh — fehlende DNS-CNAMEs für exponierte Dienste anlegen
# ═══════════════════════════════════════════════════════════════
# Nicht-destruktiv: löscht/überschreibt keine bestehenden Records.
# Legt nur CNAMEs an, die für Domains aus config/services.yaml
# (inkl. extra_domains) noch fehlen und zeigt sie auf den Tunnel.
#
# Nutzung: CF_API_TOKEN=xxx ./ensure-dns.sh
#          CF_API_TOKEN=xxx ./ensure-dns.sh --dry-run
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$REPO_ROOT/config/services.yaml"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

DRY_RUN="${1:-}"
if [ "$DRY_RUN" = "--dry-run" ]; then DRY_RUN=1; else DRY_RUN=0; fi

eval $(python3 -c "
import yaml
with open('$CONFIG') as f:
    d = yaml.safe_load(f)
cf = d.get('cloudflare', {})
print(f'ZONE_ID={cf.get(\"zone_id\", \"\")}')
print(f'ACCOUNT_ID={cf.get(\"account_id\", \"\")}')
print(f'TUNNEL_NAME={cf.get(\"tunnel_name\", \"\")}')
")

if [ -z "$ZONE_ID" ] || [ -z "$ACCOUNT_ID" ] || [ -z "$TUNNEL_NAME" ]; then
  log "❌ zone_id, account_id oder tunnel_name fehlt in config/services.yaml"
  exit 1
fi

CF_TOKEN="${CF_API_TOKEN:-}"
if [ -z "$CF_TOKEN" ]; then
  log "❌ CF_API_TOKEN nicht gesetzt. Exportiere: export CF_API_TOKEN=xxx"
  exit 1
fi

API="https://api.cloudflare.com/client/v4"

# ── Tunnel-ID anhand des Namens ermitteln ──
TUNNEL_ID=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "$API/accounts/$ACCOUNT_ID/cfd_tunnel?name=$TUNNEL_NAME" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); r=d.get('result',[]); print(r[0]['id'] if r else '')")

if [ -z "$TUNNEL_ID" ]; then
  log "❌ Kein Tunnel mit Namen '$TUNNEL_NAME' gefunden."
  exit 1
fi
log "✅ Tunnel-ID: $TUNNEL_ID"

# ── Ziel-Domains aus services.yaml (inkl. extra_domains) ──
TARGET_DOMAINS=$(python3 -c "
import yaml
with open('$CONFIG') as f:
    d = yaml.safe_load(f)
domains = []
for svc in d.get('services', []):
    if not svc.get('expose', True):
        continue
    if not svc.get('domain'):
        continue
    domains.append(svc['domain'])
    domains.extend(svc.get('extra_domains', []))
print('\n'.join(domains))
")

# ── Bestehende DNS-Records laden (nur CNAME/A, sonst blockiert z.B. ──
# ── ein MX/TXT/NS-Record auf der Apex-Domain fälschlich die Anlage) ──
EXISTING=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "$API/zones/$ZONE_ID/dns_records?per_page=100" | \
  python3 -c "import json,sys; [print(r['name']) for r in json.load(sys.stdin)['result'] if r['type'] in ('CNAME', 'A')]")

while IFS= read -r domain; do
  [ -z "$domain" ] && continue
  if echo "$EXISTING" | grep -qx "$domain"; then
    log "OK  bereits vorhanden: $domain"
    continue
  fi

  if [ "$DRY_RUN" = "1" ]; then
    log "🟡 würde anlegen: $domain -> $TUNNEL_ID.cfargotunnel.com"
    continue
  fi

  RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $CF_TOKEN" \
    -H "Content-Type: application/json" \
    "$API/zones/$ZONE_ID/dns_records" \
    -d "{\"type\":\"CNAME\",\"name\":\"$domain\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true}")

  OK=$(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('success'))")
  if [ "$OK" = "True" ]; then
    log "✅ angelegt: $domain"
  else
    log "❌ Fehler bei $domain: $(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('errors'))")"
  fi
done <<< "$TARGET_DOMAINS"

log "✅ DNS-Abgleich abgeschlossen"
