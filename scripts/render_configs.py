#!/usr/bin/env python3
"""
Reads config/services.yaml and generates:
  - docker-compose.yml      (all services with expose != false)
  - cloudflared/config.yml  (only services with expose: true)

Services with expose: false are excluded from both outputs.
"""

import os
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_YAML = os.path.join(REPO_ROOT, "config", "services.yaml")
DOCKER_COMPOSE_OUT = os.path.join(REPO_ROOT, "docker-compose.yml")
CLOUDFLARED_OUT = os.path.join(REPO_ROOT, "cloudflared", "config.yml")

AUTO_HEADER = (
    "# AUTO-GENERATED — nicht manuell bearbeiten\n"
    "# Quelle: config/services.yaml  |  Generator: scripts/render_configs.py\n"
)


def container_name(svc):
    """Derive Docker service name; uses explicit service_name field if present."""
    if "service_name" in svc:
        return svc["service_name"]
    return svc["domain"].replace(".markb.de", "")


def render_docker_compose(services):
    lines = [AUTO_HEADER, "services:"]

    for svc in services:
        if not svc.get("expose", True):
            continue

        svc_type = svc.get("type", "ui")
        hc_type = svc.get("healthcheck", "http")
        name = container_name(svc)
        repo = svc["repo"]
        port = svc["port"]

        lines.append(f"\n  {name}:")
        lines.append(f"    image: ghcr.io/mark-baumann/{repo}:${{IMAGE_TAG:-latest}}")
        lines.append(f"    restart: unless-stopped")
        lines.append(f"    env_file: .env")
        lines.append(f"    networks: [edge]")

        if svc_type == "ui" and hc_type == "http":
            hc_url = f"http://localhost:{port}/_stcore/health"
            lines.append(f"    healthcheck:")
            lines.append(
                f"      test: [\"CMD\", \"python\", \"-c\","
                f" \"import urllib.request;urllib.request.urlopen('{hc_url}')\"]"
            )
            lines.append(f"      interval: 30s")
            lines.append(f"      timeout: 5s")
            lines.append(f"      retries: 3")

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

    return "\n".join(lines) + "\n"


def render_cloudflared(services):
    lines = [AUTO_HEADER, "ingress:"]

    for svc in services:
        if not svc.get("expose", True):
            continue
        name = container_name(svc)
        lines.append(f"  - hostname: {svc['domain']}")
        lines.append(f"    service: http://{name}:{svc['port']}")

    lines.append("  - service: http_status:404")

    return "\n".join(lines) + "\n"


def main():
    with open(SERVICES_YAML) as f:
        data = yaml.safe_load(f)

    services = data["services"]

    compose_content = render_docker_compose(services)
    with open(DOCKER_COMPOSE_OUT, "w") as f:
        f.write(compose_content)
    print(f"  docker-compose.yml written ({sum(1 for s in services if s.get('expose', True))} services)")

    cloudflared_content = render_cloudflared(services)
    with open(CLOUDFLARED_OUT, "w") as f:
        f.write(cloudflared_content)
    exposed = sum(1 for s in services if s.get("expose", True))
    print(f"  cloudflared/config.yml written ({exposed} ingress rules)")


if __name__ == "__main__":
    main()
