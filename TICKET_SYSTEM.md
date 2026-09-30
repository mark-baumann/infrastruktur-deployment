# 🏢 Ticket-System — Hermes Agent CTO

## Status
- **Hermes API-Server:** ❌ Existiert nicht — Diagnose AUG-671 (2026-09-24, Pi-Runner): kein Listener auf Port 8642, kein Cron, kein systemd-Service
- **Paperclip:** ✅ Erreichbar; Ticket-Erstellung durch externe Prozesse ist 🔴 GESPERRT (Sicherheitsvorschrift unten, siehe AUG-671)
- **GitHub:** ✅ Deployments laufen über GitHub Actions (Self-Hosted-Runner auf dem Pi)

## Blocker
1. 🔴 **SICHERHEIT — KEIN Board-Token für externe Prozesse:** Der CTO-Paperclip-Token wurde 2026-09-23 in Commit `536469c` öffentlich geleakt (Root Cause AUG-671) und ist bis zur Rotation als kompromittiert zu behandeln. **Nie wieder** Paperclip-Tokens an externe Prozesse (Hermes-Scripts, Cronjobs) vergeben oder in diesem Repo speichern (`queue/` ist seit AUG-671 in `.gitignore`).
   → Rotation erfolgt **ausschließlich** durch den User per Board-Auth (`/api/board-api-keys` ist nicht agent-navigierbar, siehe AUG-671). Bis dahin erzeugt kein Prozess Paperclip-Tickets im Namen des CTO.

## ⚠️ Root Cause AUG-573–584 / AUG-595 / AUG-600 / AUG-609–612 / AUG-620
Aufgabe #2 unten wies Hermes Agent an, einen **festen Portbereich (8501-8519)**
zu scannen und Service-Namen selbst zuzuordnen, statt `config/services.yaml`
zu lesen. Das führte zu Fehlalarmen für nicht existierende/auskommentierte
Ports und sogar zu falsch benannten realen Services (z.B. Port 8502 als
"finanz-assistent" statt Bewerbungsagent). `scripts/health-check.sh` und
`.github/workflows/healthcheck-autoheal.yml` machen es korrekt: Ports/Namen
aus `config/services.yaml` bzw. dem daraus generierten `cloudflared/config.yml`
lesen, nie hardcoden. Aufgabe #2 wurde entsprechend korrigiert — falls Hermes
Agent weiterhin nach dem alten festen Portbereich alarmiert, muss der
zuständige Owner die tatsächliche Monitoring-Logik/Instruktionen des Hermes
Agent (außerhalb dieses Repos) auf dieselbe Quelle umstellen.

## Aufgaben-Liste (Wird zu Paperclip-Tickets)

### Kategorie 1: Monitoring & Health (24/7)
| # | Aufgabe | Frequenz | Zuständig |
|---|---------|----------|-----------|
| 1 | Disk-Space-Check (`df -h`) | Alle 6h | Hermes Agent |
| 2 | Service-Health-Check (Ports & Namen aus `config/services.yaml` lesen — **nicht** hardcoden, siehe `scripts/health-check.sh`) | Alle 15min | Hermes Agent |
| 3 | Cloudflare-Tunnel-Status | Stündlich | Hermes Agent |
| 4 | n8n-Workflow-Health | Stündlich | Hermes Agent |
| 5 | GitHub-Repo-Health (uncommitted changes) | Täglich | Hermes Agent |

### Kategorie 2: Content & Updates
| # | Aufgabe | Frequenz | Zuständig |
|---|---------|----------|-----------|
| 6 | Tägliche KI-Aktienanalyse | 11:00 Uhr | Cronjob (läuft) |
| 7 | Bachelorarbeit-Fortschritt loggen | Täglich | Hermes Agent |
| 8 | README.md aktualisieren (mark-baumann-profile) | Bei Änderung | Hermes Agent |
| 9 | Neue GitHub-Repos scannen & dokumentieren | Täglich | Hermes Agent |
| 10 | Backup-Check (n8n Workflows) | Täglich | Hermes Agent |

### Kategorie 3: Entwicklung & Deployment
| # | Aufgabe | Frequenz | Zuständig |
|---|---------|----------|-----------|
| 11 | Code-Review für offene PRs | Bei neuem PR | GitHub Engineer |
| 12 | Tests laufen lassen (alle Repos) | Täglich | Hermes Agent |
| 13 | Dependency-Updates (uv.lock, requirements) | Wöchentlich | Hermes Agent |
| 14 | Streamlit-Apps auf Fehler prüfen | Alle 2h | Hermes Agent |
| 15 | Neue Features in vergleichs-ki/vergütungs-agent | Auf Anfrage | Hermes Agent |

### Kategorie 4: Sicherheit & Wartung
| # | Aufgabe | Frequenz | Zuständig |
|---|---------|----------|-----------|
| 16 | API-Key-Rotation prüfen | Monatlich | Hermes Agent |
| 17 | Log-Rotation & Cleanup | Wöchentlich | Hermes Agent |
| 18 | SSL-Zertifikate prüfen | Täglich | Hermes Agent |
| 19 | .env-Dateien auf Leaks prüfen | Täglich | Hermes Agent |
| 20 | Backup-Verifizierung | Wöchentlich | Hermes Agent |

## Ticket-Vorlage (für Paperclip)

```
Titel: [SYSTEM] {Aufgabe} — {Status}
Beschreibung:
- Aufgabe: {Beschreibung}
- Frequenz: {Häufigkeit}
- Letzte Ausführung: {Timestamp}
- Nächste Ausführung: {Timestamp}
- Zuständig: {Rolle}
- Priorität: {P0|P1|P2}
```

## Nächste Schritte
1. [ ] ⛔ GESPERRT (AUG-671): ~~Paperclip Token mit Board-Access erstellen~~ — externe Prozesse erhalten aus Sicherheitsgründen keinen Paperclip-Zugriff mehr; Tickets laufen über den zuständigen Paperclip-Agenten
2. [x] GitHub-Auth für Deployments läuft über GitHub Actions + Self-Hosted-Runner
3. [ ] ⛔ GESPERRT (AUG-671): ~~Hermes Agent: Tickets in Paperclip anlegen~~ — bis zur Token-Rotation und Freigabe durch den User ruht die externe Ticketerstellung; Monitoring läuft über `scripts/health-check.sh` + `.github/workflows/healthcheck-autoheal.yml`
