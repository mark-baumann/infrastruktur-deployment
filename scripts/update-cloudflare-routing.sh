#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# update-cloudflare-routing.sh — Ingress des Tunnels aus services.yaml
# ═══════════════════════════════════════════════════════════════
# Konsolidiert die hartkodierte Ingress-Liste des alten
# fix-cloudflare-routing.yml: Die Regeln werden jetzt deterministisch
# aus config/services.yaml erzeugt (gleiche Service-Key-Logik wie
# scripts/render_configs.py). Kein Tunnel wird neu erstellt — nur die
# bestehende Tunnel-Konfiguration wird aktualisiert.
#
# Nutzung: CF_API_TOKEN=xxx ./update-cloudflare-routing.sh
#          CF_API_TOKEN=xxx ./update-cloudflare-routing.sh --dry-run
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$REPO_ROOT/config/services.yaml"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

DRY_RUN="${1:-}"
if [ "$DRY_RUN" = "--dry-run" ]; then DRY_RUN=1; else DRY_RUN=0; fi

# ── Konfiguration aus YAML lesen ──
eval $(python3 -c "
import yaml, sys
with open('$CONFIG') as f:
    d = yaml.safe_load(f)
cf = d.get('cloudflare', {})
print(f'CF_ACCOUNT_ID={cf.get(\"account_id\", \"\")}')
print(f'CF_TUNNEL_NAME={cf.get(\"tunnel_name\", \"\")}')
")

if [ -z "$CF_ACCOUNT_ID" ] || [ -z "$CF_TUNNEL_NAME" ]; then
  log "❌ account_id oder tunnel_name fehlt in config/services.yaml"
  exit 1
fi

CF_TOKEN="${CF_API_TOKEN:-}"
if [ -z "$CF_TOKEN" ]; then
  log "❌ CF_API_TOKEN nicht gesetzt. Exportiere: export CF_API_TOKEN=xxx"
  exit 1
fi

API="https://api.cloudflare.com/client/v4"
log "Account: $CF_ACCOUNT_ID | Tunnel: $CF_TUNNEL_NAME"

# ── 1. Tunnel-ID anhand des Namens ermitteln (kein Neu-Erstellen) ──
TUNNEL_ID=$(curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "$API/accounts/$CF_ACCOUNT_ID/cfd_tunnel?name=$CF_TUNNEL_NAME" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); r=d.get('result',[]); print(r[0]['id'] if r else '')")

if [ -z "$TUNNEL_ID" ]; then
  log "❌ Kein Tunnel mit Namen '$CF_TUNNEL_NAME' gefunden. Bitte zuerst tunnel-setup.sh ausführen."
  exit 1
fi
log "✅ Tunnel-ID: $TUNNEL_ID"

# ── 2. Ingress-Regeln aus services.yaml erzeugen (Service-Key wie render_configs.py) ──
INGRESS_JSON=$(python3 -c "
import json, re, sys
from pathlib import Path
import yaml

def service_key(svc):
    if svc.get('service_name'):
        return svc['service_name']
    domain = svc.get('domain')
    if domain:
        return domain.replace('.markb.de', '')
    def slugify(name):
        s = name.lower().replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')
        s = re.sub(r'[^a-z0-9-]', '-', s)
        s = re.sub(r'-+', '-', s).strip('-')
        return s
    return slugify(svc['name'])

def ingress_host(svc):
    return svc.get('ingress_host') or service_key(svc)

with open('$CONFIG') as f:
    d = yaml.safe_load(f)

rules = []
for svc in d.get('services', []):
    if not svc.get('expose', True):
        continue
    if not svc.get('domain') or not svc.get('port'):
        continue
    for domain in [svc['domain']] + list(svc.get('extra_domains', [])):
        rules.append({'hostname': domain, 'service': 'http://{}:{}'.format(ingress_host(svc), svc['port'])})
rules.append({'service': 'http_status:404'})
print(json.dumps(rules))
")
log "Ingress-Regeln abgeleitet aus config/services.yaml:"
echo "$INGRESS_JSON" | python3 -m json.tool
echo "$INGRESS_JSON" > /tmp/cf-ingress.json

if [ "$DRY_RUN" = "1" ]; then
  log "🟡 Dry-Run — keine Änderungen übertragen."
  exit 0
fi

# ── 3. Tunnel-Konfiguration aktualisieren ──
log "🔀 Aktualisiere Tunnel-Ingress..."
RESPONSE=$(curl -s -X PUT \
  -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" \
  "$API/accounts/$CF_ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/configurations" \
  -d "{\"config\":{\"ingress\":$(cat /tmp/cf-ingress.json)}}")

echo "$RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if d.get('success'):
    print('✅ Cloudflare Ingress erfolgreich aktualisiert.')
else:
    print('❌ Fehler:', json.dumps(d.get('errors', d), indent=2, ensure_ascii=False))
    sys.exit(1)
"
