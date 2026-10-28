#!/usr/bin/env python3
"""
Liest config/services.yaml und generiert:
  - docker-compose.yml             (alle deploybaren Services)
  - cloudflared/config.yml         (nur Services mit expose: true)
  - examples/deploy-workflows/*.yml (Beispiel-Workflows pro Repo)

Verwendung:
  python scripts/render_configs.py
  python scripts/render_configs.py --dry-run
  python scripts/render_configs.py --generate-workflows
"""

import json
import re
import sys
import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Fehler: pyyaml fehlt. Bitte: pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
SERVICES_YAML = REPO_ROOT / "config" / "services.yaml"

AUTO_HEADER = (
    "# AUTO-GENERATED — nicht manuell bearbeiten\n"
    "# Quelle: config/services.yaml  |  Generator: scripts/render_configs.py\n"
)


def slugify(name: str) -> str:
    """Anzeigenamen → docker-compose-konformer Key (Umlaute, Sonderzeichen)."""
    s = name.lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def service_key(svc: dict) -> str:
    """Gibt den docker-compose Service-Key zurück."""
    if "service_name" in svc:
        return svc["service_name"]
    domain = svc.get("domain")
    if domain:
        return domain.replace(".markb.de", "")
    return slugify(svc["name"])


def load_services() -> tuple[list[dict], dict, dict]:
    with open(SERVICES_YAML) as f:
        data = yaml.safe_load(f)
    services = []
    for svc in data.get("services", []):
        svc.setdefault("type", "ui")
        svc.setdefault("expose", svc.get("type") == "ui")
        svc.setdefault("healthcheck", "http" if svc.get("type") == "ui" else "heartbeat_file")
        services.append(svc)
    return services, data.get("cloudflare", {}), data.get("paths", {})


# ── docker-compose.yml ───────────────────────────────────────────────────────

def render_docker_compose(services: list[dict]) -> str:
    lines = [AUTO_HEADER, "services:"]
    needs_internal = False
    named_volumes = []

    for svc in services:
        stype = svc.get("type", "ui")
        hc = svc.get("healthcheck", "http")
        key = service_key(svc)
        repo = svc.get("repo")
        port = svc.get("port")

        # Nicht-exponierte UI-Services überspringen (z.B. OCR während RunPod-Klärung)
        if stype == "ui" and not svc.get("expose", True):
            continue

        # Externe Dienste laufen nicht in Docker (z.B. systemd-Dienst auf dem Pi).
        # Sie brauchen nur eine Ingress-Regel, keinen Compose-Service — und damit
        # auch kein 'image'/'repo'. Ziel ist 'ingress_host' (meist das Gateway
        # des edge-Netzes), siehe render_cloudflared().
        if svc.get("external"):
            continue

        if "image" in svc:
            image = svc["image"]
        elif repo:
            image = f"ghcr.io/mark-baumann/{repo.lower()}:${{IMAGE_TAG:-latest}}"
        else:
            raise ValueError(f"Service '{svc['name']}' benötigt 'image' oder 'repo'")
        lines.append(f"\n  {key}:")
        build = svc.get("build")
        if build:
            # Lokal gebautes Image (z.B. Patch auf ein Upstream-Image); 'image' ist dann der lokale Tag
            lines.append(f"    build:")
            lines.append(f"      context: {build['context']}")
            if build.get("args"):
                lines.append(f"      args:")
                for arg_key, arg_val in build["args"].items():
                    lines.append(f"        {arg_key}: {arg_val}")
        lines.append(f"    image: {image}")
        if svc.get("container_name"):
            lines.append(f"    container_name: {svc['container_name']}")
        if svc.get("user"):
            lines.append(f"    user: {json.dumps(str(svc['user']))}")
        lines.append(f"    restart: unless-stopped")
        if svc.get("command"):
            lines.append(f"    command: {json.dumps(svc['command'])}")
        if svc.get("env_file", True):
            lines.append(f"    env_file: .env")
        # Zusätzliche Variablen aus services.yaml (Werte dürfen ${VAR} aus der .env referenzieren)
        extra_env = svc.get("environment", {})
        if port or extra_env:
            lines.append(f"    environment:")
            if port:
                lines.append(f"      - PORT={port}")
            for env_key, env_val in extra_env.items():
                lines.append(f"      - {env_key}={env_val}")

        volumes = svc.get("volumes", [])
        if volumes:
            lines.append(f"    volumes:")
            for vol in volumes:
                lines.append(f"      - {vol}")
                # Quelle ohne Pfad-Präfix = benanntes Volume → Top-Level deklarieren
                source = vol.split(":")[0]
                if not source.startswith(("/", ".", "~")) and source not in named_volumes:
                    named_volumes.append(source)

        if stype == "ui" and port:
            lines.append(f"    networks: [edge]")
            if hc == "http_ping":
                lines.append(f"    healthcheck:")
                hc_path = svc.get("healthcheck_path", "/")
                lines.append(
                    f"      test: [\"CMD-SHELL\","
                    f" \"curl -f http://localhost:{port}{hc_path} || exit 1\"]"
                )
                lines.append(f"      interval: 30s")
                lines.append(f"      timeout: 10s")
                lines.append(f"      retries: 3")
                lines.append(f"      start_period: 30s")
            else:
                hc_url = f"http://localhost:{port}/_stcore/health"
                lines.append(f"    healthcheck:")
                lines.append(
                    f"      test: [\"CMD\", \"python\", \"-c\","
                    f" \"import urllib.request;urllib.request.urlopen('{hc_url}')\"]"
                )
                lines.append(f"      interval: 30s")
                lines.append(f"      timeout: 5s")
                lines.append(f"      retries: 3")
        elif stype in ("headless", "cron"):
            network = svc.get("network", "internal")
            if network == "internal":
                needs_internal = True
            lines.append(f"    networks: [{network}]")
            if hc == "heartbeat_file":
                lines.append(f"    healthcheck:")
                lines.append(
                    f"      test: [\"CMD\", \"bash\", \"-c\","
                    f" \"FILE=/tmp/{key}-heartbeat.txt &&"
                    f" [ -f $$FILE ] &&"
                    f" [ $(( $(date +%s) - $(stat -c %Y $$FILE) )) -le 300 ]\"]"
                )
                lines.append(f"      interval: 60s")
                lines.append(f"      timeout: 5s")
                lines.append(f"      retries: 3")
            # hc == "none": kein healthcheck-Block generieren

    lines.extend([
        "",
        "  cloudflared:",
        "    image: cloudflare/cloudflared:latest",
        "    restart: unless-stopped",
        "    command: tunnel --no-autoupdate run",
        "    environment:",
        "      TUNNEL_TOKEN: ${TUNNEL_TOKEN}",
        "    networks: [edge]",
        "",
        "networks:",
        "  edge:",
        "    driver: bridge",
    ])

    if needs_internal:
        lines.extend([
            "  internal:",
            "    driver: bridge",
        ])

    if named_volumes:
        lines.extend(["", "volumes:"])
        for vol in named_volumes:
            lines.append(f"  {vol}:")

    return "\n".join(lines) + "\n"


# ── cloudflared/config.yml ───────────────────────────────────────────────────

def render_cloudflared(services: list[dict]) -> str:
    lines = [AUTO_HEADER, "ingress:"]
    for svc in services:
        if not svc.get("expose", True):
            continue
        if not svc.get("domain") or not svc.get("port"):
            continue
        key = service_key(svc)
        host = svc.get("ingress_host") or key
        all_domains = [svc["domain"]] + list(svc.get("extra_domains", []))
        for domain in all_domains:
            lines.append(f"  - hostname: {domain}")
            lines.append(f"    service: http://{host}:{svc['port']}")
    lines.append("  - service: http_status:404")
    return "\n".join(lines) + "\n"


# ── Example deploy workflows ─────────────────────────────────────────────────

def render_deploy_workflow(svc: dict) -> str:
    """Generiert eine deploy.yml für ein App-Repo, inkl. healthcheck_type."""
    key = service_key(svc)
    port = svc.get("port")
    app_file = svc.get("app_file")
    hc = svc.get("healthcheck", "http")

    with_lines = [f"        service_name: {key}"]
    if port:
        with_lines.append(f'        port: "{port}"')
    if app_file:
        with_lines.append(f"        app_file: {app_file}")
    with_lines.append(f"        healthcheck_type: {hc}")

    with_block = "\n".join(with_lines)
    return (
        f"# .github/workflows/deploy.yml — generiert für: {svc['name']}\n"
        f"# Kopiere diese Datei in: {svc['repo']}/.github/workflows/deploy.yml\n\n"
        f"name: Deploy\n\n"
        f"on:\n"
        f"  push:\n"
        f"    branches: [main, master]\n"
        f"  workflow_dispatch:\n\n"
        f"jobs:\n"
        f"  deploy:\n"
        f"    uses: mark-baumann/infrastruktur-deployment/.github/workflows/build-deploy.yml@master\n"
        f"    with:\n"
        f"{with_block}\n"
        f"    secrets: inherit\n"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Render configs from services.yaml")
    parser.add_argument("--dry-run", action="store_true", help="stdout statt Dateien")
    parser.add_argument(
        "--generate-workflows",
        action="store_true",
        help="Beispiel-Deploy-Workflows in examples/deploy-workflows/ generieren",
    )
    args = parser.parse_args()

    services, _cf, _paths = load_services()
    compose_content = render_docker_compose(services)
    cloudflared_content = render_cloudflared(services)

    exposed_count = sum(1 for s in services if s.get("expose", True) and s.get("type") == "ui")
    headless_count = sum(1 for s in services if s.get("type") in ("headless", "cron"))

    if args.dry_run:
        print("=== docker-compose.yml ===")
        print(compose_content)
        print("=== cloudflared/config.yml ===")
        print(cloudflared_content)
    else:
        (REPO_ROOT / "docker-compose.yml").write_text(compose_content)
        print(f"  docker-compose.yml geschrieben ({exposed_count} UI + {headless_count} headless)")

        (REPO_ROOT / "cloudflared" / "config.yml").write_text(cloudflared_content)
        print(f"  cloudflared/config.yml geschrieben ({exposed_count} ingress rules)")

    if args.generate_workflows:
        examples_dir = REPO_ROOT / "examples" / "deploy-workflows"
        for svc in services:
            if not svc.get("repo"):
                continue
            wf = render_deploy_workflow(svc)
            fname = f"{svc['repo']}.yml"
            if args.dry_run:
                print(f"=== examples/deploy-workflows/{fname} ===")
                print(wf)
            else:
                examples_dir.mkdir(parents=True, exist_ok=True)
                (examples_dir / fname).write_text(wf)
                print(f"  examples/deploy-workflows/{fname} geschrieben")

    print(f"\n📊 {len(services)} Services:")
    for svc in services:
        icon = "🖥️ " if svc.get("type") == "ui" else "⚙️ "
        tag = "🌐" if svc.get("expose") else "🔒"
        print(f"  {icon}{tag} {svc['name']:<28} healthcheck={svc.get('healthcheck')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
