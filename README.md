# 🏗️ Infrastruktur-Deployment

**Deterministische Deployment-Pipeline für alle 14 Streamlit-Dienste + Cloudflare-Tunnel.**

Dieses Repo macht deine Infrastruktur reproduzierbar — kein manuelles Gefrickel mehr.

---

## 📦 Enthaltene Dienste

| Port | Dienst | Repo |
|------|--------|------|
| 8501 | Vergleich-Agenten | vergleichs-ki |
| 8502 | Finanz-Agenten | finanz-assistent |
| 8503 | Handels-Agenten | handels-agenten |
| 8505 | KI-Lernplattform | ki-lernplattform |
| 8510 | Spam-Klassifikation | spam-klassifikation |
| 8511 | Anonymisierung | anonymisierungs-pipeline |
| 8512 | Dokumenten-Agent | rag-agent-langgraph |
| 8513 | Aktienanalyse | taegliche-aktienanalyse |
| 8514 | eBay-Agent | ebay-scraping-agent |
| 8515 | Browser-Nutzung | browser-nutzung |
| 8516 | Open-Manus | open-manus |
| 8517 | Verstärkungslernen | agenten-verstaerkungslernen |
| 8518 | Nano-GPT | nanoGPT |
| 8519 | ART-Agent | ART |

---

## 🚀 Schnellstart

```bash
# 1. Alle Repos klonen
./scripts/clone-all.sh

# 2. Alle Dienste starten
./scripts/start-all.sh

# 3. Tunnel einrichten
./scripts/tunnel-setup.sh

# 4. Health-Check
./scripts/health-check.sh
```

---

## 📁 Struktur

```
config/
  services.yaml       # Alle 14 Dienste deklarativ
  tunnel.yaml         # Cloudflare-Tunnel-Konfiguration
scripts/
  clone-all.sh        # Klont alle 20 Repos
  start-all.sh        # Startet alle 14 Dienste
  stop-all.sh         # Stoppt alle Dienste
  health-check.sh     # Prüft alle Ports + Tunnel
  tunnel-setup.sh     # Erstellt/erneuert Cloudflare-Tunnel
  watchdog.sh         # Autostart-Watchdog (alle 5 Min)
services/
  docker-compose.yml  # Optional: Docker-basiertes Deployment
```

---

## 🛠️ Tech-Stack

`Bash` `Python` `Streamlit` `Cloudflare` `systemd` `Docker`

---

## 👤 Autor

Mark Baumann — [markb.de](https://markb.de)
