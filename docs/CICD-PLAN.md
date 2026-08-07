# CI/CD Pipeline — Vollständiges Konzept (AUG-11)

> Status: **FINALISIERT** — Bereit zur Implementierung
> Stand: 2026-08-07
> Entscheidungen: Alle offenen Fragen vom Nutzer beantwortet (2026-08-07)

## Entschiedene Konfiguration

| Frage | Entscheidung |
|---|---|
| OCR-Agent | Vorerst ausgelassen — RunPod-Strategie ausstehend |
| RunPod-Services | Vorerst kein Cloudflare-Tunnel — RunPod-Strategie ausstehend |
| render-configs.sh Sprache | **Python + pyyaml** |
| Claude Code Token | **GitHub App** (einmal einrichten, gilt für alle Repos) |
| Auto-Merge | **GitHub Branch Protection Rules** (nativ, kostenlos) |

---

## 1. Ist-Analyse — Was bereits funktioniert

| Komponente | Status |
|---|---|
| Reusable Workflow `build-deploy.yml` | ✅ Existiert, funktioniert für alle UI-Services |
| ARM64-Build → ghcr.io | ✅ Konfiguriert |
| Self-hosted Runner auf Pi | ✅ Aktiv |
| `docker compose pull + up -d` | ✅ Deterministisch |
| Cloudflare Tunnel (cloudflared) | ✅ Läuft |
| `services.yaml` als Deklarationsdatei | ✅ Existiert — aber unvollständig |
| `cloudflared/config.yml` | ⚠️ Manuell gepflegt — Drift-Risiko |
| `docker-compose.yml` | ⚠️ Manuell gepflegt — OCR-Agent fehlt bereits |
| Headless-Service-Support | ❌ Nicht vorhanden |
| Paperclip/Claude Code Integration | ❌ Nicht definiert |
| Zentrales Status-Dashboard | ❌ Nicht vorhanden |

---

## 2. Kernproblem: Manuelle Pflege führt zu Drift

Aktuell müssen bei einem neuen Service **drei Dateien** manuell synchron gehalten werden:
- `config/services.yaml`
- `cloudflared/config.yml`
- `docker-compose.yml`

Beweis: `ocr_recognition_nn` steht in `services.yaml` (Port 8518), fehlt aber in `docker-compose.yml`.

**Lösung: `services.yaml` wird die einzige Quelle der Wahrheit — alle anderen Dateien werden daraus generiert.**

---

## 3. services.yaml — Schema-Erweiterung

Das bestehende Schema wird um drei Felder erweitert:

```yaml
services:
  # UI-Service mit Cloudflare-Ingress (Status quo)
  - name: Spam-Klassifikation
    port: 8510
    repo: spam-klassifikation
    app_file: app/app.py
    domain: spam-klassifikation.markb.de
    type: ui              # NEU: ui | headless | cron
    expose: true          # NEU: bekommt Cloudflare-Hostname
    healthcheck: http     # NEU: http | heartbeat_file | ping_url

  # Headless-Service ohne Cloudflare-Ingress (NEU)
  - name: Daten-Feed-Worker
    port: null
    repo: daten-feed-worker
    app_file: null
    domain: null
    type: headless
    expose: false
    healthcheck: heartbeat_file   # schreibt /tmp/heartbeat.txt

  # Cron-Job (NEU)
  - name: Täglicher-Report
    port: null
    repo: daily-report-agent
    app_file: null
    domain: null
    type: cron
    expose: false
    healthcheck: ping_url   # healthchecks.io oder ähnlich
```

**Bestehende Services bekommen `type: ui`, `expose: true`, `healthcheck: http` als Defaults.**
Keine bestehende Funktionalität bricht.

---

## 4. Code-Generierung aus services.yaml

Ein neues Script `scripts/render_configs.py` (Python + pyyaml, entschieden) liest `services.yaml` und generiert:

### 4a. cloudflared/config.yml (auto-generiert)
```
Nur Services mit expose: true → ingress entry
Services mit expose: false → kein Eintrag
```

### 4b. docker-compose.yml (auto-generiert)
```
type: ui     → port-mapping + HTTP healthcheck + network: edge
type: headless → restart: unless-stopped, kein Port, kein Ingress, network: internal
type: cron   → restart: unless-stopped, kein Port, keine healthcheck via HTTP
```

**Trigger:** Das Script läuft als erster Step des `build-deploy.yml` Workflows, wenn Änderungen an `config/services.yaml` gepusht werden. Alternativ als eigenständiger Workflow `render-configs.yml` in diesem Repo.

---

## 5. Vollständiger CI/CD Flow (deterministisch)

```
┌─────────────────────────────────────────────────────────────┐
│                    DEVELOPER / AGENT                        │
│                                                             │
│  1. Code-Änderung in App-Repo                               │
│     git commit + push → main                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              GITHUB ACTIONS (GitHub-hosted runner)          │
│                                                             │
│  2. App-Repo Workflow (.github/workflows/deploy.yml):       │
│     uses: infrastruktur-deployment/.../build-deploy.yml     │
│                                                             │
│  3. build-job (ubuntu-latest):                              │
│     - docker buildx build --platform linux/arm64            │
│     - push → ghcr.io/mark-baumann/<repo>:latest+<sha>       │
│     - cache: GHA cache                                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              GITHUB ACTIONS (self-hosted runner auf Pi)     │
│                                                             │
│  4. deploy-job (runs-on: [self-hosted, markb]):             │
│     - cd /opt/data/stack                                    │
│     - docker compose pull <service>                         │
│     - docker compose up -d --no-deps <service>              │
│     - docker image prune -f                                 │
│                                                             │
│  5. healthcheck-job:                                        │
│     - type: ui       → curl localhost:<port>/_stcore/health │
│     - type: headless → check /tmp/<service>-heartbeat.txt   │
│     - type: cron     → check healthchecks.io ping status    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    RASPBERRY PI                             │
│                                                             │
│  6. Docker Compose Stack:                                   │
│     - UI-Services: Port + cloudflared network               │
│     - Headless: restart: unless-stopped, internal network   │
│     - cloudflared: Tunnel zu markb.de                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  CLOUDFLARE                                 │
│                                                             │
│  7. Tunnel-Ingress (auto-generiert aus services.yaml):      │
│     *.markb.de → jeweiliger Container                       │
│     Nur Services mit expose: true                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Infrastruktur-Repo als Steuerzentrale

Wenn `services.yaml` geändert wird (neuer Service, neues expose-Flag), läuft ein separater Workflow:

```
Push zu infrastruktur-deployment/config/services.yaml
  → Workflow: render-configs.yml
    → scripts/render-configs.sh
      → docker-compose.yml (neu generiert)
      → cloudflared/config.yml (neu generiert)
    → git commit + push der generierten Dateien
    → deploy-job:
        docker compose up -d (Diff → nur neue/geänderte Services hochfahren)
        cloudflared tunnel ingress update (oder tunnel neu starten)
```

**Neue Service hinzufügen = 1 Eintrag in `services.yaml`, alles andere ist automatisch.**

---

## 7. Paperclip / Claude Code Integration

Claude Code verhält sich wie ein weiterer Entwickler — kein Sonderweg:

```
Paperclip Task → Claude Code Agent
  → liest App-Repo
  → macht Code-Änderung
  → git commit + PR öffnen (NICHT direkt auf main pushen)
  → GitHub CI läuft (build-deploy.yml)
  → Auto-Merge NUR wenn:
      a) Alle Checks grün
      b) Build erfolgreich
      c) Health Check nach Deploy grün
  → Deployment auf Pi automatisch
```

**Token-Scoping (entschieden: GitHub App):**
- Eine **GitHub App** für alle Repos einrichten — einmal registrieren, dann als Installation auf alle App-Repos geben
- Scope: `contents: write` + `pull_requests: write` (installation-scoped, nicht user-scoped)
- Claude Code bekommt die Installation-Token über GitHub Actions `secrets: inherit`
- **Nicht** deinen persönlichen Token — ein fehlerhafter Agent-Lauf kann sonst alle Repos beschreiben

**On-Demand Trigger aus Paperclip:**
- Statt SSH auf den Pi: `repository_dispatch` oder `workflow_dispatch` an den Workflow
- Paperclip-Agent kann via GitHub API einen Deploy triggern ohne direkten Pi-Zugriff
- Beispiel: `POST /repos/mark-baumann/spam-klassifikation/actions/workflows/deploy.yml/dispatches`

---

## 8. N8n — Wann sinnvoll, wann nicht

**N8n ist optional, nicht notwendig für die deterministische Pipeline.**

Die Frage war: Macht N8n die Pipeline besser?

| Szenario | N8n notwendig? | Alternative |
|---|---|---|
| Push → Build → Deploy | ❌ Nein | GitHub Actions (bereits vorhanden) |
| On-demand Deploy aus Paperclip | ❌ Nein | `workflow_dispatch` via GitHub API |
| Multi-Repo-Orchestrierung | ⚠️ Optional | GitHub Actions Workflow-Call |
| Externe Trigger (Slack, Webhook) | ✅ Sinnvoll | N8n als Glue-Layer |
| Komplexe Konditionslogik vor Deploy | ✅ Sinnvoll | N8n als Entscheidungs-Router |
| Benachrichtigungen bei Failure | ⚠️ Optional | GitHub Actions Notify-Step |

**Empfehlung:** N8n erst einführen, wenn GitHub Actions an seine Grenzen stößt (z.B. komplexe Multi-Repo-Koordination, externe Webhook-Integration). Bis dahin: die bestehende GitHub Actions Pipeline ist determinstischer und einfacher zu debuggen.

---

## 9. Zentrales Status-Dashboard

Ein neuer Service in der gleichen Pipeline:

```yaml
# services.yaml Eintrag
- name: Status-Dashboard
  port: 8520
  repo: status-dashboard
  app_file: app/app.py
  domain: status.markb.de
  type: ui
  expose: true
  healthcheck: http
```

Der Service liest:
- `config/services.yaml` → Liste aller Services
- GitHub API → letzter Workflow-Run-Status pro Repo
- `docker compose ps` (via SSH oder lokaler Cronjob) → Container-Status

Zeigt: Welcher Service läuft / deployt / fehlgeschlagen / nicht exposed.

---

## 10. Secrets-Management — Unveränderlich

| Secret | Wo | Wer sieht es |
|---|---|---|
| `TUNNEL_TOKEN` | Pi: `/opt/data/.env` | Nur Pi-Prozesse |
| `GITHUB_TOKEN` | GitHub Actions Secrets | Nur GitHub Actions |
| `ANTHROPIC_API_KEY` | GitHub Actions Secrets + Pi `.env` | Nur berechtigte Services |
| Claude Code PAT | GitHub Actions Secret (per Repo) | Nur Claude Code |
| cloudflare API-Token | GitHub Actions Secret | Nur `render-configs.yml` |

**Regel:** Kein Secret kommt je in ein Git-Repo. `.env` ist in `.gitignore`. Claude Code/Paperclip committed nur Code, nie Secrets.

---

## 11. Umsetzungsreihenfolge (Implementierungsplan — finalisiert)

> Alle Entscheidungen getroffen. Bereit für Implementierungs-Issues.
> RunPod-Thema (OCR, ART, Verstärkungslernen) wird in separatem Issue behandelt sobald RunPod-Strategie klar ist.

### Phase 1 — Schema-Erweiterung + Auto-Generierung (Woche 1)
1. `config/services.yaml` um `type`, `expose`, `healthcheck` erweitern (bestehende Services = Defaults: `type: ui`, `expose: true`, `healthcheck: http`)
2. `scripts/render_configs.py` schreiben (Python + pyyaml) — liest `services.yaml`, schreibt `docker-compose.yml` + `cloudflared/config.yml`
3. Workflow `render-configs.yml` in diesem Repo schreiben — triggered auf Änderungen an `config/services.yaml`
4. `docker-compose.yml` und `cloudflared/config.yml` mit `# AUTO-GENERATED — nicht manuell bearbeiten` Header versehen

### Phase 2 — Headless-Service-Support (Woche 1-2)
5. `build-deploy.yml` um optionalen Input `healthcheck_type: http | heartbeat_file | none` erweitern
6. Health-Check-Logic für `heartbeat_file` implementieren (prüft `/tmp/<service>-heartbeat.txt` Timestamp)
7. Ersten Headless-Service als Testcase durch die Pipeline schicken

### Phase 3 — Paperclip / Claude Code Integration (Woche 2)
8. **GitHub App** erstellen und auf alle App-Repos installieren
9. App-Private-Key als GitHub Actions Secret hinterlegen (`CLAUDE_CODE_APP_PRIVATE_KEY`, `CLAUDE_CODE_APP_ID`)
10. **GitHub Branch Protection Rules** in App-Repos aktivieren: require status checks, auto-merge enabled
11. `workflow_dispatch` Trigger in `build-deploy.yml` ergänzen für On-demand-Deploys aus Paperclip

### Phase 4 — Status-Dashboard (Woche 3)
12. `status-dashboard` Repo anlegen (Streamlit, liest GitHub API + services.yaml)
13. Service in `services.yaml` eintragen (Port 8520, domain `status.markb.de`)
14. Durch Pipeline deployen

### Später (RunPod-Strategie ausstehend)
- OCR-Agent (`ocr_recognition_nn`) Deployment klären
- ART + Verstärkungslernen Cloudflare-Anbindung entscheiden
- Ggf. separater Cloudflare-Tunnel für RunPod-Services

---

## 12. Entschiedene offene Fragen

| Frage | Antwort |
|---|---|
| OCR-Agent Ziel | Vorerst ausgelassen — RunPod-Entscheidung ausstehend |
| RunPod-Services Tunnel | Vorerst kein Tunnel — RunPod-Entscheidung ausstehend |
| render-configs Sprache | Python + pyyaml |
| Token-Strategie | GitHub App (eine App für alle Repos) |
| Auto-Merge | GitHub Branch Protection Rules |
