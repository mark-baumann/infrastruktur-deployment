#!/usr/bin/env python3
"""
CTO Hermes Agent — Ticket Queue Manager
Wenn Paperclip nicht erreichbar: Tickets in lokale Queue schreiben.
Wenn Paperclip erreichbar: Queue abarbeiten.
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

QUEUE_DIR = Path("/opt/data/infrastruktur-deployment/queue")
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

PAPERCLIP_BASE = "https://paperclip-prph.srv1741927.hstgr.cloud"
API_KEY = os.environ.get("PAPERCLIP_API_KEY", "")

def add_to_queue(title: str, body: str, priority: str = "P1", category: str = "system"):
    """Fügt ein Ticket zur Queue hinzu."""
    ticket = {
        "id": f"LOCAL-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.urandom(4).hex()}",
        "title": title,
        "body": body,
        "priority": priority,
        "category": category,
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "paperclip_id": None
    }
    filepath = QUEUE_DIR / f"{ticket['id']}.json"
    with open(filepath, 'w') as f:
        json.dump(ticket, f, indent=2)
    print(f"📋 Ticket in Queue: {ticket['id']} — {title}")
    return ticket

def list_queue():
    """Listet alle offenen Tickets in der Queue."""
    tickets = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        with open(f) as fp:
            tickets.append(json.load(fp))
    return tickets

def flush_queue():
    """Versucht alle Queued-Tickets nach Paperclip zu schieben."""
    import urllib.request
    import urllib.error

    if not API_KEY:
        print("❌ Kein API_KEY — kann nicht flushen")
        return 0

    flushed = 0
    for f in sorted(QUEUE_DIR.glob("*.json")):
        with open(f) as fp:
            ticket = json.load(fp)

        if ticket.get("status") == "queued":
            payload = json.dumps({
                "title": ticket["title"],
                "body": ticket["body"],
                "priority": ticket.get("priority", "P1"),
                "labels": ["auto", ticket.get("category", "system")]
            }).encode()

            req = urllib.request.Request(
                f"{PAPERCLIP_BASE}/api/issues",
                data=payload,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )

            try:
                with urllib.request.urlopen(req) as resp:
                    result = json.loads(resp.read().decode())
                    ticket["status"] = "synced"
                    ticket["paperclip_id"] = result.get("id")
                    with open(f, 'w') as fpw:
                        json.dump(ticket, fpw, indent=2)
                    print(f"✅ Synced: {ticket['id']} → Paperclip {result.get('id')}")
                    flushed += 1
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    print(f"🔴 Paperclip noch nicht bereit (403) — Queue bleibt bestehen")
                    return flushed
                print(f"⚠️ HTTP {e.code} für {ticket['id']}")
            except Exception as e:
                print(f"⚠️ Fehler: {e}")

    return flushed

def main():
    if len(sys.argv) < 2:
        print("Usage: python ticket_queue.py add 'Titel' 'Body' [priority] [category]")
        print("       python ticket_queue.py list")
        print("       python ticket_queue.py flush")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) >= 4:
        add_to_queue(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv)>4 else "P1", sys.argv[5] if len(sys.argv)>5 else "system")
    elif cmd == "list":
        for t in list_queue():
            print(f"[{t['status']}] {t['id']}: {t['title']} ({t['priority']})")
    elif cmd == "flush":
        n = flush_queue()
        print(f"🔄 {n} Tickets geflusht")
    else:
        print("Unbekannter Befehl")
        sys.exit(1)

if __name__ == "__main__":
    main()
