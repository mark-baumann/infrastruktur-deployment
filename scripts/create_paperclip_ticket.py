#!/usr/bin/env python3
"""
Ticket-Erstellung für Paperclip.
Wird von Cronjobs und manuellen Prozessen aufgerufen.

Usage:
    python create_paperclip_ticket.py "Titel" "Beschreibung" [priority]

Benötigt: PAPERCLIP_API_KEY in Umgebung
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

PAPERCLIP_BASE = "https://paperclip-prph.srv1741927.hstgr.cloud"
API_KEY = os.environ.get("PAPERCLIP_API_KEY", "")

def create_ticket(title: str, body: str, priority: str = "P1") -> dict:
    """Erstellt ein Ticket in Paperclip."""
    if not API_KEY:
        print("❌ PAPERCLIP_API_KEY nicht gesetzt")
        sys.exit(1)

    url = f"{PAPERCLIP_BASE}/api/issues"
    payload = json.dumps({
        "title": title,
        "body": body,
        "priority": priority,
        "labels": ["auto", "system"]
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) < 3:
        print("Usage: python create_paperclip_ticket.py 'Titel' 'Beschreibung' [priority]")
        sys.exit(1)

    title = sys.argv[1]
    body = sys.argv[2]
    priority = sys.argv[3] if len(sys.argv) > 3 else "P1"

    print(f"🎫 Erstelle Ticket: {title}")
    result = create_ticket(title, body, priority)
    print(f"✅ Ticket erstellt: {result.get('id', 'N/A')}")
    return result

if __name__ == "__main__":
    main()
