"""
heartbeat.py — Heartbeat-Helper für Headless-Services.

Importieren und im Hauptloop aufrufen. Der CI Health Check in build-deploy.yml
prüft ob /tmp/<SERVICE_NAME>-heartbeat.txt in den letzten 5 Minuten aktualisiert wurde.

Beispiel:
    from heartbeat import write_heartbeat

    while True:
        write_heartbeat()
        do_work()
        time.sleep(60)
"""

import os
import time
from pathlib import Path


def write_heartbeat() -> None:
    """Schreibt /tmp/<SERVICE_NAME>-heartbeat.txt mit aktuellem Timestamp."""
    service_name = os.environ.get("SERVICE_NAME", "headless-service")
    path = Path(f"/tmp/{service_name}-heartbeat.txt")
    path.write_text(f"{time.time():.0f}\n")
