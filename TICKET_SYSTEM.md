# 🏢 Ticket-System — Hermes Agent CTO

## Status
- **Hermes API-Server:** ✅ Läuft (Port 8642)
- **Paperclip:** ✅ Erreichbar, aber 🔴 Token hat keinen Board-Access
- **GitHub:** ❌ Nicht authentifiziert (Engineer muss sich kümmern)

## Blocker
1. **Paperclip Token Scope:** `/api/companies` gibt 403 "Board access required"
   → GitHub Engineer muss in Paperclip einen Token mit Board-Write-Rechten erstellen
2. **GitHub Auth:** `gh auth status` zeigt keine Anmeldung
   → GitHub Engineer muss `gh auth login` ausführen

## Aufgaben-Liste (Wird zu Paperclip-Tickets)

### Kategorie 1: Monitoring & Health (24/7)
| # | Aufgabe | Frequenz | Zuständig |
|---|---------|----------|-----------|
| 1 | Disk-Space-Check (`df -h`) | Alle 6h | Hermes Agent |
| 2 | Service-Health-Check (Ports 8501-8519) | Alle 15min | Hermes Agent |
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
1. [ ] GitHub Engineer: Paperclip Token mit Board-Access erstellen
2. [ ] GitHub Engineer: `gh auth login` ausführen
3. [ ] Hermes Agent: Erstes Ticket "System-Setup abgeschlossen" erstellen
4. [ ] Hermes Agent: Alle 20 Aufgaben als Tickets in Paperclip anlegen
5. [ ] Hermes Agent: Cronjobs für Monitoring einrichten
