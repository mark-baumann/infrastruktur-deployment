import os
import time
import streamlit as st
import requests
import yaml

SERVICES_YAML_URL = (
    "https://raw.githubusercontent.com/mark-baumann/"
    "infrastruktur-deployment/master/config/services.yaml"
)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
CACHE_TTL = 60  # seconds

st.set_page_config(
    page_title="Status Dashboard — markb.de",
    page_icon="🟢",
    layout="wide",
)

st.title("Status Dashboard — markb.de")
st.caption("Alle Services auf einen Blick · Refresh alle 60s")


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


def status_badge(run: dict) -> str:
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
        return "✅ Success"
    if conclusion == "failure":
        return "❌ Failed"
    if conclusion == "cancelled":
        return "🚫 Cancelled"
    return f"❓ {status}/{conclusion}"


with st.spinner("Lade Services …"):
    try:
        services = load_services()
    except Exception as exc:
        st.error(f"Fehler beim Laden von services.yaml: {exc}")
        st.stop()

rows = []
for svc in services:
    repo = svc.get("repo", "")
    run = get_latest_run(repo) if repo else {"status": "no_repo", "conclusion": None, "created_at": None, "html_url": None}
    domain = svc.get("domain", "")
    created = run.get("created_at", "") or ""
    if created:
        created = created.replace("T", " ").replace("Z", " UTC")
    url = run.get("html_url") or ""
    rows.append({
        "Service": svc.get("name", repo),
        "Status": status_badge(run),
        "Letzter Deploy": created,
        "Domain": f"https://{domain}" if domain else "",
        "Run-URL": url,
    })

col_cfg = {
    "Service": st.column_config.TextColumn("Service", width="medium"),
    "Status": st.column_config.TextColumn("Status", width="small"),
    "Letzter Deploy": st.column_config.TextColumn("Letzter Deploy", width="medium"),
    "Domain": st.column_config.LinkColumn("Domain", width="medium"),
    "Run-URL": st.column_config.LinkColumn("GitHub Run", width="medium"),
}

st.dataframe(rows, column_config=col_cfg, use_container_width=True, hide_index=True)

success_count = sum(1 for r in rows if "✅" in r["Status"])
deploy_count = sum(1 for r in rows if "🔄" in r["Status"])
fail_count = sum(1 for r in rows if "❌" in r["Status"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt", len(rows))
c2.metric("✅ OK", success_count)
c3.metric("🔄 Deploying", deploy_count)
c4.metric("❌ Fehler", fail_count)

st.caption(f"Zuletzt geladen: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

time.sleep(CACHE_TTL)
st.rerun()
