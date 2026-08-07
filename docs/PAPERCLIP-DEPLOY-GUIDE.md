# Paperclip / Claude Code Agent — Deploy Guide

> Letzte Aktualisierung: 2026-08-07 (AUG-17)

Paperclip-Agenten deployen wie normale Entwickler: PR öffnen → CI grün → Auto-Merge → Deploy auf Pi. Kein direkter Pi-Zugriff nötig.

---

## 1. GitHub App einrichten (einmalig, manuell)

**GitHub App erstellen** unter https://github.com/settings/apps/new:

| Feld | Wert |
|---|---|
| Name | `markb-claude-code-agent` |
| Homepage URL | `https://github.com/mark-baumann` |
| Webhook | deaktiviert |

**Permissions (Repository):**
| Permission | Level |
|---|---|
| Contents | Read & Write |
| Pull requests | Read & Write |
| Workflows | Read & Write |
| Metadata | Read (Pflicht) |

**Nach der Erstellung:**
1. App-ID notieren (steht oben auf der App-Seite)
2. Private Key generieren (Button "Generate a private key") → `.pem`-Datei speichern
3. App auf alle App-Repos installieren: App-Seite → "Install App" → mark-baumann → Repos auswählen

---

## 2. GitHub Secrets hinterlegen

Pro App-Repo (oder als Organization Secret falls vorhanden):

```
Settings → Secrets and variables → Actions → New repository secret
```

| Secret-Name | Wert |
|---|---|
| `CLAUDE_CODE_APP_ID` | Numerische App-ID (z.B. `12345`) |
| `CLAUDE_CODE_APP_PRIVATE_KEY` | Inhalt der `.pem`-Datei (komplett, inklusive Header/Footer) |

---

## 3. Branch Protection Rules aktivieren

Pro App-Repo unter `Settings → Branches → Add branch protection rule`:

| Einstellung | Wert |
|---|---|
| Branch name pattern | `main` |
| Require a pull request before merging | ✅ aktivieren |
| Require status checks to pass | ✅ aktivieren |
| Required status checks | `build`, `deploy` |
| Require branches to be up to date | ✅ aktivieren |
| Allow auto-merge | ✅ aktivieren |
| Do not allow bypassing the above settings | ❌ (lassen, damit du als Admin noch direkt pushen kannst) |

> **Hinweis zu Check-Namen:** Wenn der App-Repo-Workflow (z.B. `deploy.yml`) den Job einfach `deploy` nennt und `uses: infrastruktur-deployment/.../build-deploy.yml`, erscheinen die reusable-workflow Jobs als `deploy / build` und `deploy / deploy`. Passe die Required Status Checks entsprechend an, nachdem der erste CI-Lauf durchgelaufen ist.

---

## 4. App-Repo Workflow für Auto-Merge

Jedes App-Repo braucht eine `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      service_name:
        required: true
        type: string
      port:
        required: true
        type: string

jobs:
  deploy:
    uses: mark-baumann/infrastruktur-deployment/.github/workflows/build-deploy.yml@master
    with:
      service_name: ${{ inputs.service_name || 'spam-klassifikation' }}
      port: ${{ inputs.port || '8510' }}
    secrets: inherit
```

**Auto-Merge aktivieren** (pro Repo, einmalig):
```bash
# Via GitHub API (Paperclip-Agent kann das ausführen)
curl -X PATCH \
  -H "Authorization: Bearer <GITHUB_TOKEN>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/mark-baumann/<repo> \
  -d '{"allow_auto_merge": true}'
```

---

## 5. Wie Paperclip-Agent einen Deploy triggert

### Option A: PR-Flow (Standard, empfohlen)

```python
# Pseudo-Code — Paperclip Agent Workflow

# 1. Feature-Branch erstellen
git checkout -b agent/fix-spam-model

# 2. Änderungen committen
git commit -m "fix: Modell-Parameter anpassen"

# 3. PR öffnen via GitHub API
POST /repos/mark-baumann/spam-klassifikation/pulls
{
  "title": "fix: Modell-Parameter anpassen",
  "head": "agent/fix-spam-model",
  "base": "main",
  "body": "Automatisch erstellt von Paperclip Agent (AUG-XX)"
}

# 4. Auto-Merge aktivieren auf dem PR
PUT /repos/mark-baumann/spam-klassifikation/pulls/<number>/merge
# (wird automatisch ausgeführt sobald CI grün)

# → CI läuft → Build → Deploy auf Pi → Health Check → Auto-Merge
```

### Option B: On-demand Deploy (ohne Code-Änderung)

```bash
# Direkter workflow_dispatch — triggert Deploy des aktuellen main-Stands
curl -X POST \
  -H "Authorization: Bearer <GITHUB_APP_TOKEN>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/mark-baumann/spam-klassifikation/actions/workflows/deploy.yml/dispatches \
  -d '{
    "ref": "main",
    "inputs": {
      "service_name": "spam-klassifikation",
      "port": "8510"
    }
  }'
```

### GitHub App Token generieren (für Agent-Aufrufe)

```python
import jwt, time, requests

def get_installation_token(app_id: str, private_key: str, installation_id: str) -> str:
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
    jwt_token = jwt.encode(payload, private_key, algorithm="RS256")

    resp = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        },
    )
    return resp.json()["token"]
```

---

## 6. Vollständiger Agent-Flow (Referenz)

```
Paperclip Task → Claude Code Agent
  ├─ liest App-Repo Code
  ├─ macht Code-Änderung
  ├─ git commit + PR öffnen (NICHT direkt auf main pushen)
  │   └─ verwendet CLAUDE_CODE_APP_ID + CLAUDE_CODE_APP_PRIVATE_KEY
  ├─ GitHub CI läuft automatisch (build-deploy.yml):
  │   ├─ build-job: Docker Build → ghcr.io
  │   └─ deploy-job: Pi pull + up + Health Check
  ├─ Auto-Merge (wenn alle Checks grün)
  └─ Deploy auf Pi — fertig, kein SSH nötig
```

---

## 7. Checkliste — Einmalige Einrichtung

- [ ] GitHub App `markb-claude-code-agent` erstellt
- [ ] App-Private-Key als `CLAUDE_CODE_APP_PRIVATE_KEY` Secret hinterlegt (pro Repo oder als Org Secret)
- [ ] `CLAUDE_CODE_APP_ID` Secret hinterlegt
- [ ] Branch Protection Rules auf `main` aktiviert (require PR + status checks)
- [ ] Auto-Merge auf Repository-Ebene aktiviert
- [ ] `workflow_dispatch` in App-Repo `deploy.yml` vorhanden ✅ (via `build-deploy.yml`)
- [ ] Erster Agent-Test-PR erfolgreich durchgelaufen
