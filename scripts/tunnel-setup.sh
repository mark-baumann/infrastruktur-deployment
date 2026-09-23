#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# tunnel-setup.sh — Cloudflare-Tunnel deterministisch einrichten
# ═══════════════════════════════════════════════════════════════
# Nutzung: CF_API_TOKEN=xxx ./tunnel-setup.sh
# Ohne Token: interaktiver Login
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/../config/services.yaml"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Konfiguration aus YAML lesen ──
eval $(python3 -c "
import yaml
with open('$CONFIG') as f:
    d = yaml.safe_load(f)
cf = d['cloudflare']
paths = d['paths']
print(f'ZONE_ID={cf[\"zone_id\"]}')
print(f'ACCOUNT_ID={cf[\"account_id\"]}')
print(f'TUNNEL_NAME={cf[\"tunnel_name\"]}')
print(f'TOKEN_FILE={paths[\"token_file\"]}')
print(f'CLOUDFLARED={paths[\"cloudflared_bin\"]}')
for s in d['services']:
    if s.get('port'):
        # Service-Key Logik (konsistent mit render_configs.py)
        key = s.get('service_name')
        if not key:
            domain = s.get('domain')
            key = domain.replace('.markb.de', '') if domain else s['name'].lower().replace(' ', '-')
        # Userspace-Ziel-Host (z.B. localhost) überschreibt den Docker-Hostnamen
        host = s.get('ingress_host') or key
        print(f'SERVICE_{s[\"port\"]}={s[\"domain\"]}|{s[\"port\"]}|{host}')
")

CF_TOKEN="${CF_API_TOKEN:-}"
if [ -z "$CF_TOKEN" ]; then
  log "❌ CF_API_TOKEN nicht gesetzt. Exportiere: export CF_API_TOKEN=xxx"
  exit 1
fi

API="https://api.cloudflare.com/client/v4"

# ── 1. Alten Tunnel löschen ──
log "🔍 Suche alte Tunnel..."
OLD_TUNNELS=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "$API/accounts/$ACCOUNT_ID/cfd_tunnel?name=$TUNNEL_NAME" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(r['id']) for r in d.get('result',[])]")

for tid in $OLD_TUNNELS; do
  log "🗑️  Lösche Tunnel $tid..."
  curl -s -X DELETE -H "Authorization: Bearer $CF_TOKEN" \
    "$API/accounts/$ACCOUNT_ID/cfd_tunnel/$tid" > /dev/null
done

# ── 2. Neuen Tunnel erstellen ──
log "🆕 Erstelle Tunnel '$TUNNEL_NAME'..."
RESP=$(curl -s -X POST -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" \
  "$API/accounts/$ACCOUNT_ID/cfd_tunnel" \
  -d "{\"name\":\"$TUNNEL_NAME\",\"config_src\":\"cloudflare\"}")

TUNNEL_ID=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['id'])")
TUNNEL_TOKEN=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['token'])")

echo "$TUNNEL_TOKEN" > "$TOKEN_FILE"
log "✅ Tunnel erstellt: $TUNNEL_ID"
log "   Token gespeichert: $TOKEN_FILE"

# ── 3. DNS-Einträge setzen ──
log "🌐 DNS-Einträge..."

# Alte CNAMEs löschen
EXISTING=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "$API/zones/$ZONE_ID/dns_records?type=CNAME&per_page=100" | \
  python3 -c "import json,sys; [print(r['id'], r['name']) for r in json.load(sys.stdin)['result']]")

while read -r rid rname; do
  curl -s -X DELETE -H "Authorization: Bearer $CF_TOKEN" \
    "$API/zones/$ZONE_ID/dns_records/$rid" > /dev/null
  log "   🗑️  $rname"
done <<< "$EXISTING"

# Neue CNAMEs für alle Dienste
for var in $(env | grep '^SERVICE_' | cut -d= -f1); do
  val="${!var}"
  domain="${val%%|*}"
  rest="${val#*|}"
  port="${rest%%|*}"
  curl -s -X POST -H "Authorization: Bearer $CF_TOKEN" \
    -H "Content-Type: application/json" \
    "$API/zones/$ZONE_ID/dns_records" \
    -d "{\"type\":\"CNAME\",\"name\":\"$domain\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true}" > /dev/null
  log "   ✅ $domain → Port $port"
done

# ── 4. Ingress konfigurieren ──
log "🔀 Ingress..."

INGRESS_RULES=""
for var in $(env | grep '^SERVICE_' | cut -d= -f1); do
  val="${!var}"
  domain="${val%%|*}"
  rest="${val#*|}"
  port="${rest%%|*}"
  key="${rest##*|}"
  INGRESS_RULES+="{\"hostname\":\"$domain\",\"service\":\"http://$key:$port\"},"
done
INGRESS_RULES+="{\"service\":\"http_status:404\"}"

curl -s -X PUT -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" \
  "$API/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" \
  -d "{\"config\":{\"ingress\":[$INGRESS_RULES]}}" > /dev/null
log "   ✅ Ingress gesetzt"

# ── 5. Tunnel starten ──
log "🚀 Starte Tunnel..."
pkill -f cloudflared 2>/dev/null || true
sleep 2
nohup "$CLOUDFLARED" tunnel --no-autoupdate run --token "$TUNNEL_TOKEN" \
  >> /tmp/cloudflared.log 2>&1 &
log "   PID $!"

log "✅ Tunnel-Setup abgeschlossen"
