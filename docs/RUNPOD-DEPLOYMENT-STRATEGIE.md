# 🎮 Hybrid-Deployment-Strategie: Raspberry Pi + RunPod

**Status:** Vorschlag / Grundlage für Umsetzung
**Kontext:** Der Raspberry Pi (`pi-runner`) hat keine GPU. Alle Dienste, die
Training, Fine-Tuning oder GPU-gebundene Inferenz brauchen, ziehen auf
[RunPod](https://runpod.io) um. Alles andere bleibt auf dem Pi.

---

## 1. Ausgangslage

Aktuell laufen **alle 14 Dienste** aus `config/services.yaml` als Docker-Container
auf dem Pi (`docker-compose.yml`), gebaut als ARM64-Images via `build-deploy.yml`
und über den self-hosted Runner (`[self-hosted, markb]`) deployed. Cloudflare
Tunnel exponiert sie unter `*.markb.de`.

Problem: Ein Raspberry Pi hat keine GPU. Repos wie **ART** (GRPO + LoRA
Fine-Tuning), **agenten-verstaerkungslernen** (DQN/Policy-Gradient-Training mit
W&B), **nanoGPT** (Transformer-Training) oder **ocr_recognition_nn**
(CNN-Training) laufen dort nur im Trainer-Modus mit `device=cpu` — das ist für
echtes Training unbrauchbar bis unmöglich.

## 2. Architekturprinzip: Zwei-Tier-Modell

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  TIER 1 — Raspberry Pi       │        │  TIER 2 — RunPod              │
│  „Edge / Serving"           │        │  „GPU Compute"                │
│  immer an, günstig, ARM64   │        │  on-demand, GPU, x86_64+CUDA  │
├─────────────────────────────┤        ├──────────────────────────────┤
│ • Streamlit-Dashboards      │  API   │ • Training / Fine-Tuning      │
│ • Reine LLM-API-Orchestrat. │◄──────►│ • GPU-Inferenz (lokale Modelle)│
│ • n8n, Cloudflare Tunnel    │  calls │ • Batch-Jobs (RL, LoRA, CNN)  │
│ • GitHub Actions Runner     │        │ • RunPod Serverless / Pods    │
└─────────────────────────────┘        └──────────────────────────────┘
```

Der Pi bleibt die **einzige dauerhaft öffentlich erreichbare Fläche**
(Cloudflare Tunnel, `markb.de`-Domains, bestehende Runner-Fleet). RunPod wird
ausschließlich als **GPU-Backend** angebunden — entweder von einem
Pi-Streamlit-Frontend per HTTPS aufgerufen, oder für eigenständige
Trainingsläufe, die keine dauerhafte Erreichbarkeit brauchen.

## 3. Entscheidungsmatrix: Pi oder RunPod?

| Kriterium | → Pi | → RunPod |
|---|---|---|
| Nutzt nur externe LLM-APIs (OpenAI etc.) | ✅ | |
| Klassisches ML auf kleinen Daten (TF-IDF, Decision Trees, kleine MLPs) | ✅ | |
| Reine Orchestrierung / Dashboard / UI | ✅ | |
| Lokales Modelltraining oder Fine-Tuning | | ✅ |
| Lokale Inferenz mit Modellen >~1 GB / CNN-Batches | | ✅ |
| Braucht CUDA / PyTorch mit GPU-Beschleunigung | | ✅ |
| Muss 24/7 laufen, aber ist idle-lastig | ✅ (oder RunPod Serverless mit Scale-to-Zero) | |
| Läuft nur gelegentlich / batch-artig | | ✅ (Serverless oder On-Demand-Pod) |

## 4. Repo-Zuordnung (Ist-Stand + Empfehlung)

| Repo | Port (aktuell) | GPU-Bedarf | Ziel | Begründung |
|---|---|---|---|---|
| vergleichs-ki | 8501 | keiner | **Pi** | Dokumentenvergleich via API |
| finanz-assistent | 8502 | keiner | **Pi** | RAG über OpenAI-API |
| handels-agenten | 8503 | keiner | **Pi** | Multi-Agent-Orchestrierung, LLM-API |
| ki-lernplattform | 8505 | keiner | **Pi** | Streamlit-Hub, reine UI |
| spam-klassifikation | 8510 | keiner | **Pi** | TF-IDF/Naive Bayes, trivial klein |
| anonymisierungs-pipeline | 8511 | gering | **Pi** | NER auf kleinen Batches ausreichend |
| rag-agent-langgraph (dokumenten-agent) | 8512 | keiner | **Pi** | Embeddings via API, kein lokales Modell |
| taegliche-aktienanalyse | 8513 | keiner | **Pi** | Decision-Tree-Bias, klassisches ML |
| ebay-scraping-agent | 8514 | keiner | **Pi** | Browser-Automation, CPU-/RAM-bound |
| browser-nutzung | 8515 | keiner | **Pi**¹ | Playwright/Chromium ist RAM-hungrig, nicht GPU |
| open-manus | 8516 | optional | **Pi**¹ | Solange nur API-Modelle genutzt werden |
| agenten-verstaerkungslernen | 8517 | **ja** | **RunPod** | DQN/Policy-Gradient-Training braucht GPU |
| ocr_recognition_nn | 8518 | **ja** (Training) | **Hybrid** | Training auf RunPod, Demo-Inferenz mit fertigem Modell auf Pi |
| ART | 8519 | **ja** | **RunPod** | GRPO + LoRA Fine-Tuning — zwingend GPU |
| nanoGPT | — (kein Service) | **ja** | **RunPod** | Transformer-Training, klassischer GPU-Job |
| pytorch-lernen | — | teils | **RunPod**¹ | Transfer-Learning-Kapitel brauchen GPU, Rest optional |
| handschrifterkennung-mnist | — | gering | **Pi/RunPod optional** | MNIST ist klein genug für CPU, GPU nur „nice to have" |
| hermes-agent | — | optional | **Pi**¹ | Agent-Framework, solange kein lokales Modell gehostet wird |
| n8n | — | keiner | **Pi** | Workflow-Engine, klassischer Dauerbetrieb |

¹ Beobachten: Falls diese Dienste später auf lokal gehostete Modelle
(Ollama, vLLM, lokale Vision-Modelle) umgestellt werden, wandern sie in die
RunPod-Spalte.

**Faustregel:** *Trainiert oder fine-tuned es etwas, oder lädt es ein Modell in
GPU-Speicher zur Inferenz? → RunPod. Ruft es nur eine API auf oder rechnet es
mit einem winzigen Modell auf CPU? → Pi.*

## 5. RunPod-Betriebsmodi

RunPod bietet zwei Muster — die Wahl hängt vom Nutzungsmuster ab, nicht vom
Repo an sich:

### 5.1 Serverless Endpoints (Standard-Empfehlung)
- Skaliert bei Inaktivität auf **0 Worker** → keine Kosten, wenn nichts läuft.
- Passt für: **ART** (Inferenz nach Fine-Tuning), **ocr_recognition_nn**
  (Inferenz-Endpoint), alles, was von einem Pi-Streamlit-Frontend aus
  „on demand" angestoßen wird.
- Muster: Streamlit-UI bleibt auf dem Pi (billig, immer an), ruft bei Bedarf
  den RunPod-Serverless-Endpoint per HTTPS auf. Nur der GPU-Teil kostet Geld,
  und nur während der Job läuft.

### 5.2 On-Demand Pods (für lange Trainingsläufe)
- Persistenter Container, explizit gestartet und wieder terminiert.
- Passt für: **agenten-verstaerkungslernen**, **nanoGPT**, **ART**-Training
  (mehrstündige GRPO/LoRA-Läufe), **ocr_recognition_nn**-Training.
- Wird per CI/CD oder manuell via `runpodctl` / RunPod-API gestartet, führt den
  Trainingsjob aus, lädt Artefakte (Checkpoints/Modelle) in Object Storage
  hoch und terminiert sich danach selbst — kein Dauerbetrieb.

**Default: Serverless.** Nur explizit auf Pods wechseln, wenn ein Job länger
als eine Serverless-Cold-Start-Grenze braucht oder Zustand über mehrere
Requests halten muss (z. B. ein laufendes Training).

## 6. Netzwerk & Domains

Der bestehende Cloudflare Tunnel auf dem Pi bleibt **unverändert** für
Pi-native Dienste. Für RunPod gibt es zwei Optionen, je nach Fall:

- **Fall A — Backend-Aufruf (Standardfall):** RunPod-Endpoint wird nur
  server-seitig vom Pi-Dienst aus aufgerufen (RunPod-URL + `RUNPOD_API_KEY` im
  Header). Kein öffentlicher DNS-Eintrag nötig, kein Cloudflare-Tunnel-Zweig
  nötig — der Pi bleibt die einzige öffentliche Fläche.
- **Fall B — Eigenständiger Dienst auf RunPod:** Falls ein Dienst komplett auf
  RunPod läuft (z. B. eine GPU-Streamlit-Demo), einen zweiten `cloudflared`
  Connector **innerhalb des RunPod-Containers** als Sidecar starten, registriert
  auf denselben Cloudflare-Account, neuer Hostname (z. B. `art-agent.markb.de`
  über Tunnel-Connector B statt A). So bleibt die Zero-Trust-/Domain-Struktur
  einheitlich, unabhängig davon, wo der Container physisch läuft.

Empfehlung: **Fall A ist der Regelfall.** Fall B nur, wenn ein GPU-Dienst
wirklich dauerhaft und eigenständig erreichbar sein muss.

## 7. CI/CD-Erweiterung

Der bestehende reusable Workflow (`build-deploy.yml`) kennt nur den Pi als
Ziel. Vorschlag zur Erweiterung (noch nicht umgesetzt, siehe Migrationsplan):

- **Neues Feld in `services.yaml`:** `target: pi | runpod-serverless | runpod-pod`
- **Neues Dockerfile-Template:** `Dockerfile.gpu.template`, Basis-Image
  `nvidia/cuda:12.x-runtime` oder `runpod/pytorch`, gebaut für `linux/amd64`
  statt `linux/arm64`.
- **Getrenntes Image-Tagging:** `ghcr.io/mark-baumann/<repo>:latest-arm64`
  (Pi) vs. `ghcr.io/mark-baumann/<repo>:latest-cuda` (RunPod) — ein Image pro
  Zielarchitektur, kein gemeinsames Multi-Arch-Manifest, weil die GPU-Variante
  zusätzliche CUDA-Layer hat.
- **Deploy-Job-Dispatch:**
  - `target: pi` → wie bisher, `runs-on: [self-hosted, markb]`, `docker
    compose pull/up`.
  - `target: runpod-serverless` → `runs-on: ubuntu-latest` (GitHub-hosted
    reicht, kein Zugriff auf den Pi nötig), Call an die RunPod REST/GraphQL-API
    zum Aktualisieren des Endpoint-Images (`RUNPOD_API_KEY` Secret).
  - `target: runpod-pod` → `runs-on: ubuntu-latest`, `runpodctl` oder REST-API:
    alten Pod stoppen, neuen mit aktuellem Image-Tag starten, Job ausführen,
    Pod terminieren.

## 8. Secrets & Konfiguration

Ergänzung zu `.env.template`:

```bash
# RunPod API (Console → Settings → API Keys)
RUNPOD_API_KEY=

# Pro GPU-Dienst ein Endpoint-Identifier
RUNPOD_ENDPOINT_ID_ART=
RUNPOD_ENDPOINT_ID_OCR=
RUNPOD_ENDPOINT_ID_RL=
```

Als GitHub Actions Secrets auf Repo- bzw. Org-Ebene hinterlegen (`secrets:
inherit` funktioniert bereits im reusable Workflow).

## 9. Kostensteuerung

- **Serverless als Default**, `min workers = 0` — keine Kosten im Leerlauf.
- **Community Cloud** statt Secure Cloud für unterbrechbare Trainingsjobs
  (günstiger, Unterbrechung tolerierbar bei Checkpointing).
- **Network Volumes** für Modell-Checkpoints statt Container-Storage, damit
  ein terminierter Pod keine Trainingsergebnisse verliert.
- **Timeouts konsequent setzen**: Serverless-Idle-Timeout niedrig halten,
  Pods nie ohne explizites Terminate-Kommando am Ende eines CI-Jobs laufen
  lassen (sonst läuft die Kostenuhr weiter, wenn ein Job hängen bleibt).
- Monatliches Budget-Alert in der RunPod-Console einrichten.

## 10. Observability

- `scripts/health-check.sh` bleibt für Pi-Dienste zuständig.
- Neues Skript `scripts/runpod-health-check.sh`: fragt den RunPod-API-Status
  der Serverless-Endpoints ab (Worker-Status, letzte Job-Latenz, Fehlerquote).
- Trainingsjobs auf Pods loggen nach W&B (bereits im Stack für
  `agenten-verstaerkungslernen` vorgesehen) — als einheitlicher Ort für
  Trainingsmetriken, unabhängig vom Compute-Standort.

## 11. Migrationsplan

| Phase | Inhalt |
|---|---|
| **0** | Ist-Zustand (alles auf dem Pi) — heutiger Stand |
| **1** | RunPod-Account/API-Key einrichten, `Dockerfile.gpu.template` bauen, Secrets hinterlegen |
| **2** | Pilot: **ART-Agent** als RunPod-Serverless-Endpoint migrieren (klarster GPU-Fall) |
| **3** | Reusable Workflow um `target`-Dispatch erweitern, `services.yaml` um `target`-Feld ergänzen |
| **4** | Restliche GPU-Kandidaten migrieren: `agenten-verstaerkungslernen`, `ocr_recognition_nn`, `nanoGPT`-Trainingsjobs |
| **5** | Pi-seitige GPU-Fallback-Codepfade (falls vorhanden, `device=cpu`) entfernen, Kosten- und Health-Monitoring für RunPod final einrichten |

## 12. Rollback-Strategie

- Pi-Seite: unverändert, bestehender `IMAGE_TAG`-Rollback-Mechanismus bleibt
  gültig.
- RunPod-Serverless: Endpoint auf vorherigen Image-Tag zurücksetzen (Images
  bleiben in GHCR versioniert, gleiches Schema wie beim Pi).
- RunPod-Pod-Jobs: da sie pro Lauf frisch gestartet werden, ist „Rollback"
  gleichbedeutend mit „Job mit altem Image-Tag erneut starten" — kein
  persistenter Zustand, der zurückgerollt werden müsste.

## 13. Offene Punkte

- Für `browser-nutzung` / `open-manus` / `hermes-agent` beobachten, ob sie auf
  lokal gehostete Modelle umgestellt werden — dann Neubewertung Pi → RunPod.
- Klären, ob `ocr_recognition_nn`-Inferenz nach dem Training klein genug ist,
  um exportierte Gewichte direkt auf dem Pi laufen zu lassen (dann kein
  dauerhafter RunPod-Serverless-Endpoint nötig, nur Trainings-Pods).
- Prüfen, ob ein gemeinsames RunPod Network Volume für alle GPU-Dienste
  ausreicht oder pro Dienst getrennt werden sollte (Isolation vs. Einfachheit).
