"""
main.py — Beispiel-Hauptloop für einen Headless-Service.

Kopiere dieses Muster in dein App-Repo (app/main.py).
"""

import logging
import time

from heartbeat import write_heartbeat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 60  # Sekunden — muss < 300s (Health-Check-Timeout) sein


def main() -> None:
    log.info("Headless-Service gestartet")
    last_heartbeat = 0.0

    while True:
        now = time.time()

        # Heartbeat mindestens alle 60s schreiben
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            write_heartbeat()
            last_heartbeat = now

        # Eigentliche Arbeit hier
        log.info("Verarbeite Daten...")
        time.sleep(10)


if __name__ == "__main__":
    main()
