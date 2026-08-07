import json
import os
import time

import requests
import streamlit as st
import yaml

SERVICES_YAML_URL = (
    "https://raw.githubusercontent.com/mark-baumann/"
    "infrastruktur-deployment/master/config/services.yaml"
)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
DOCKER_STATUS_FILE = "/data/docker-status.json"
CACHE_TTL = 60  # seconds

st.set_page_config(
    page_title="Status Dashboard — markb.de",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Status Dashboard — markb.de")
st.caption("Alle Services auf einen Blick")


@st.cache_data(ttl=CACHE_TTL)
def load_services() -> list[dict]:
    resp = requests.get(SERVICES_YAML_URL, timeout=10)
    resp.raise_for_status()
    data = yaml.safe_load(resp.text)
    return data.get("services", [])


@st.cache_data(ttl=CACHE_TTL)
def get_latest_run(repo: str) -> dict:
    url = f"https://api.github.com/repos/mark-baumann/{repo}/actions/runs?per_page=1"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return {"status": "no_repo", "conclusion": None, "created_at": None, "html_url": None}
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
        if not runs:
            return {"status": "no_runs", "conclusion": None, "created_at": None, "html_url": None}
        run = runs[0]
        return {
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"),
            "html_url": run.get("html_url"),
        }
    except Exception as exc:
        return {"status": "error", "conclusion": str(exc), "created_at": None, "html_url": None}


@st.cache_data(ttl=30)
def load_docker_status() -> tuple[dict, float | None]:
    if os.path.exists(DOCKER_STATUS_FILE):
        try:
            with open(DOCKER_STATUS_FILE) as f:
                return json.load(f), os.path.getmtime(DOCKER_STATUS_FILE)
        except Exception:
            pass
    return {}, None


def _find_docker_info(svc: dict, docker_data: dict) -> dict:
    name = svc.get("name", "")
    repo = svc.get("repo", "")
    candidates = [
        name.lower()
        .replace(" ", "-")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss"),
        repo.replace("_", "-"),
    ]
    for key in candidates:
        if key in docker_data:
            return docker_data[key]
    return {}


def ci_badge(run: dict) -> str:
    conclusion = run.get("conclusion")
    status = run.get("status")
    if status == "in_progress":
        return "🔄 Deploying"
    if status == "queued":
        return "⏳ Queued"
    if status == "no_repo":
        return "⬜ Kein Repo"
    if status == "no_runs":
        return "⬜ Noch kein Run"
    if status == "error":
        return "⚠️ API-Fehler"
    if conclusion == "success":
        return "✅ OK"
    if conclusion == "failure":
        return "❌ Fehler"
    if conclusion == "cancelled":
        return "🚫 Abgebrochen"
    return f"❓ {status}/{conclusion}"


def row_status(ci: str, docker_running) -> str:
    if "🔄" in ci or "⏳" in ci:
        return "🟡"
    if "❌" in ci or docker_running is False:
        return "🔴"
    if "✅" in ci and docker_running:
        return "🟢"
    return "⚪"


with st.spinner("Lade Services …"):
    try:
        services = load_services()
    except Exception as exc:
        st.error(f"Fehler beim Laden von services.yaml: {exc}")
        st.stop()

docker_data, docker_mtime = load_docker_status()

if docker_mtime is not None:
    age_min = (time.time() - docker_mtime) / 60
    if age_min > 10:
        st.warning(
            f"⚠️ Docker-Status veraltet ({age_min:.0f} Min). "
            "Bitte `scripts/generate-status.sh` als Cron-Job auf dem Pi einrichten."
        )
elif not docker_data:
    st.info(
        "ℹ️ Keine Docker-Statusdaten verfügbar. "
        "Cron-Job `scripts/generate-status.sh` auf dem Pi einrichten."
    )

rows = []
for svc in services:
    repo = svc.get("repo", "")
    domain = svc.get("domain", "")
    run = (
        get_latest_run(repo)
        if repo
        else {"status": "no_repo", "conclusion": None, "created_at": None, "html_url": None}
    )
    created = run.get("created_at", "") or ""
    if created:
        created = created.replace("T", " ").replace("Z", " UTC")

    docker_info = _find_docker_info(svc, docker_data)
    docker_running = docker_info.get("running") if docker_info else None
    ci = ci_badge(run)

    rows.append(
        {
            "": row_status(ci, docker_running),
            "Service": svc.get("name", repo),
            "GitHub CI": ci,
            "Docker": "✅" if docker_running else ("❌" if docker_running is False else "–"),
            "Letzter Deploy": created,
            "Domain": f"https://{domain}" if domain else "",
            "Run-URL": run.get("html_url") or "",
        }
    )

col_cfg = {
    "": st.column_config.TextColumn("", width="small"),
    "Service": st.column_config.TextColumn("Service", width="medium"),
    "GitHub CI": st.column_config.TextColumn("GitHub CI", width="small"),
    "Docker": st.column_config.TextColumn("Docker", width="small"),
    "Letzter Deploy": st.column_config.TextColumn("Letzter Deploy", width="medium"),
    "Domain": st.column_config.LinkColumn("Domain", width="medium"),
    "Run-URL": st.column_config.LinkColumn("GitHub Run", width="medium"),
}

st.dataframe(rows, column_config=col_cfg, use_container_width=True, hide_index=True)

green = sum(1 for r in rows if r[""] == "🟢")
yellow = sum(1 for r in rows if r[""] == "🟡")
red = sum(1 for r in rows if r[""] == "🔴")

st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt", len(rows))
c2.metric("🟢 Aktiv", green)
c3.metric("🟡 Deploying", yellow)
c4.metric("🔴 Fehler", red)

st.caption(f"Zuletzt geladen: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

time.sleep(CACHE_TTL)
st.rerun()
