#!/usr/bin/env python3
"""The board's own notifications, as plain text for a note.

Reads the board rather than any system source: an inbox of what several
sessions have announced, gathered in one tile.
"""

import json
import os
import urllib.error
import urllib.request

API = os.environ.get("STARK_HUD_API", "http://127.0.0.1:8000/api/v1")

try:
    with urllib.request.urlopen(f"{API}/board/items", timeout=5) as response:
        items = json.load(response)
except (urllib.error.HTTPError, OSError):
    items = []

lines = [
    f"{i['payload'].get('source') or '—'}: {i['payload']['message']}"
    for i in items
    if i["payload"]["kind"] == "notification"
]
print("notificações\n\n" + ("\n".join(lines) if lines else "(nenhuma)"))
