"""Mississauga Library Swim & Skate Family Activity Pass watcher.

Polls the BiblioCommons availability API and pushes a Discord message when a
copy becomes available at any branch (or only BRANCHES, if set).

Env:
  DISCORD_WEBHOOK_URL  Discord webhook (required to send; otherwise prints only)
  BRANCHES             optional, comma-separated branch names/codes to watch,
                       e.g. "Meadowvale,CHU,Erin Meadows"
  RECORD_ID            optional, defaults to S220C769335
  STATE_FILE           optional, defaults to state.json next to this script
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RECORD_ID = os.environ.get("RECORD_ID", "S220C769335")
API_URL = f"https://gateway.bibliocommons.com/v2/libraries/mississauga/availability/{RECORD_ID}"
RECORD_URL = f"https://mississauga.bibliocommons.com/v2/record/{RECORD_ID}"
STATE_FILE = Path(os.environ.get("STATE_FILE", Path(__file__).with_name("state.json")))
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
BRANCHES = {b.strip().lower() for b in os.environ.get("BRANCHES", "").split(",") if b.strip()}


def fetch_items():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    items = []
    for group in data.get("items", []):
        for it in group.get("items", []):
            avail = it.get("availability") or {}
            branch = it.get("branch") or {}
            items.append({
                "id": it.get("itemId"),
                "branch": branch.get("name") or it.get("branchName") or "?",
                "code": branch.get("code") or "",
                "status_type": avail.get("statusType") or avail.get("status") or "",
                "library_status": avail.get("libraryStatus") or "",
                "due": it.get("dueDate"),
            })
    return items


def watched(item):
    return not BRANCHES or item["branch"].lower() in BRANCHES or item["code"].lower() in BRANCHES


def is_available(item):
    return item["status_type"].upper() == "AVAILABLE"


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"available": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def send_discord(content):
    if not WEBHOOK:
        print("DISCORD_WEBHOOK_URL not set, skip sending")
        return
    body = json.dumps({"content": content[:1900]}).encode()
    req = urllib.request.Request(WEBHOOK, data=body, headers={"Content-Type": "application/json", "User-Agent": "swim-skate-pass-watcher"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("Discord:", resp.status)


def main():
    items = [it for it in fetch_items() if watched(it)]
    if not items:
        print("No items matched (check BRANCHES)")
        return 1

    available = sorted(it["id"] for it in items if is_available(it))
    state = load_state()
    newly = [it for it in items if it["id"] in set(available) - set(state.get("available", []))]

    for it in sorted(items, key=lambda x: x["branch"]):
        print(f'{it["branch"]:<34} {it["status_type"]:<12} {it["library_status"]:<14} {it["due"] or ""}')

    if "--test" in sys.argv:
        send_discord(f"Swim & Skate pass watcher test: {len(available)}/{len(items)} available now\n{RECORD_URL}")

    if newly:
        lines = [f'- **{it["branch"]}** ({it["library_status"] or "Available"})' for it in sorted(newly, key=lambda x: x["branch"])]
        in_transit = [it["branch"] for it in items if it["library_status"].lower() == "in transit"]
        msg = "🏊⛸️ **Swim & Skate Family Activity Pass 有货了！**\n" + "\n".join(lines)
        if in_transit:
            msg += "\n在途: " + ", ".join(in_transit)
        msg += f"\n{RECORD_URL}"
        send_discord(msg)

    # Only rewrite on change so the workflow doesn't commit every run
    if available != state.get("available"):
        state["available"] = available
        state["changed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_state(state)
    print(f"available {len(available)}/{len(items)}, newly {len(newly)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
