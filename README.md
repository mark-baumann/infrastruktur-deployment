# 🏗️ Infrastruktur-Deployment

**Deterministische Docker-Deployment-Pipeline für alle 13 Streamlit-Dienste + Cloudflare-Tunnel.**

Kein manuelles Gefrickel mehr. Push auf `main` → automatischer Build + Deploy auf den Raspberry Pi.

---

## 🚀 Schnellstart

```bash
# 1. Stack klonen
git clone https://github.com/mark-baumann/infrastruktur-deployment.git /opt/stack

# 2. Secrets setzen
cp .env.template .env
# → TUNNEL_TOKEN, GITHUB_TOKEN eintragen
chmod 600 .env

# 3. Alle Dienste starten
docker compose up -d

# 4. Health Check
docker compose ps
```

---

## 📦 Architektur

```
GitHub Push (main)
  → GitHub Actions (build-deploy.yml)
    → docker build + push → ghcr.io (ARM64)
    → Self-hosted Runner (pi)
      → docker compose pull + up -d
        → cloudflared Tunnel → markb.de
```

---

## 🔄 Rollback

```bash
# Auf bestimmten Commit zurücksetzen
IMAGE_TAG=<sha> docker compose up -d <service>
```

---

## 📁 Struktur

```
config/
  services.yaml         # Alle 13 Dienste deklarativ
  tunnel.yaml           # Cloudflare-Tunnel-Konfiguration
scripts/
  start-all.sh          # Startet alle Dienste
  stop-all.sh           # Stoppt alle Dienste
  health-check.sh       # Prüft alle Ports + Tunnel
  tunnel-setup.sh       # Erstellt/erneuert Cloudflare-Tunnel
  watchdog.sh           # Autostart-Watchdog
cloudflared/
  config.yml            # Ingress-Regeln (Referenz)
Dockerfile.template     # Standard-Dockerfile für alle Apps
docker-compose.yml      # 13 Dienste + cloudflared
.env.template           # Vorlage für Secrets
```

---

## 🛠️ Reusable Workflow

Jedes App-Repo ruft den Workflow mit 5 Zeilen auf:

```yaml
jobs:
  deploy:
    uses: mark-baumann/infrastruktur-deployment/.github/workflows/build-deploy.yml@main
    with:
      service_name: ebay-agent
      port: 8514
    secrets: inherit
```

---

## 👤 Autor

Mark Baumann — [markb.de](https://markb.de)
