"""Mississauga Library Swim & Skate Family Activity Pass watcher.

Polls the BiblioCommons availability API and pushes Discord messages when a
copy becomes available at a branch, and again when it's gone (with how long it
stayed available).

Usage:
  python check_pass.py              check once
  python check_pass.py --loop 20700 keep polling every 10-30s for N seconds
  python check_pass.py --test       also send a test message

Env:
  DISCORD_WEBHOOK_URL  Discord webhook (required to send; otherwise prints only)
  BRANCHES             optional, comma-separated branch names/codes to watch,
                       e.g. "Meadowvale,CHU,Erin Meadows"
  RECORD_ID            optional, defaults to S220C769335
  STATE_FILE           optional, defaults to state.json next to this script
  COMMIT_STATE         "1" to git commit + push state.json whenever it changes
  MIN_DELAY/MAX_DELAY  optional loop interval bounds in seconds (default 10/30)
"""

import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/Toronto")
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=-5))

RECORD_ID = os.environ.get("RECORD_ID", "S220C769335")
API_URL = f"https://gateway.bibliocommons.com/v2/libraries/mississauga/availability/{RECORD_ID}"
RECORD_URL = f"https://mississauga.bibliocommons.com/v2/record/{RECORD_ID}"
STATE_FILE = Path(os.environ.get("STATE_FILE", Path(__file__).with_name("state.json")))
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
BRANCHES = {b.strip().lower() for b in os.environ.get("BRANCHES", "").split(",") if b.strip()}
COMMIT_STATE = os.environ.get("COMMIT_STATE") == "1"
MIN_DELAY = float(os.environ.get("MIN_DELAY", 10))
MAX_DELAY = float(os.environ.get("MAX_DELAY", 30))


def now():
    return datetime.now(timezone.utc)


def local_hm(dt):
    return dt.astimezone(LOCAL_TZ).strftime("%m-%d %H:%M:%S")


def fmt_duration(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}小时{m}分{s}秒"
    if m:
        return f"{m}分{s}秒"
    return f"{s}秒"


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
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        state = {}
    avail = state.get("available")
    state["available"] = avail if isinstance(avail, dict) else {}
    return state


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if COMMIT_STATE:
        try:
            subprocess.run(["git", "add", str(STATE_FILE)], check=True)
            subprocess.run(["git", "commit", "-q", "-m", "Update pass state"], check=True)
            subprocess.run(["git", "pull", "-q", "--rebase"], check=True)
            subprocess.run(["git", "push", "-q"], check=True)
        except subprocess.CalledProcessError as e:
            print("git commit/push failed:", e, flush=True)


def send_discord(content):
    if not WEBHOOK:
        print("DISCORD_WEBHOOK_URL not set, skip sending:", content.replace("\n", " | "), flush=True)
        return
    body = json.dumps({"content": content[:1900]}).encode()
    req = urllib.request.Request(WEBHOOK, data=body, headers={"Content-Type": "application/json", "User-Agent": "swim-skate-pass-watcher"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print("Discord:", resp.status, flush=True)
                return
        except Exception as e:
            print("Discord send failed:", e, flush=True)
            time.sleep(2 + attempt * 3)


def check_once(state, verbose=False):
    items = [it for it in fetch_items() if watched(it)]
    if not items:
        print("No items matched (check BRANCHES)", flush=True)
        return

    t = now()
    current = {it["id"]: it for it in items if is_available(it)}
    prev = state["available"]
    changed = False

    if verbose:
        for it in sorted(items, key=lambda x: x["branch"]):
            print(f'{it["branch"]:<34} {it["status_type"]:<12} {it["library_status"]:<14} {it["due"] or ""}', flush=True)

    appeared = [current[i] for i in current if i not in prev]
    if appeared:
        names = sorted(it["branch"] for it in appeared)
        lines = [f"- **{n}**" for n in names]
        others = sorted(it["branch"] for i, it in current.items() if i in prev)
        msg = "🏊⛸️ **Swim & Skate pass 可以借了！** 去这里：\n" + "\n".join(lines)
        if others:
            msg += "\n其他仍可借: " + ", ".join(others)
        msg += f"\n发现时间 {local_hm(t)}\n{RECORD_URL}"
        send_discord(msg)
        for it in appeared:
            prev[it["id"]] = {"branch": it["branch"], "since": t.isoformat(timespec="seconds")}
        changed = True

    gone = [i for i in prev if i not in current]
    for i in gone:
        info = prev.pop(i)
        since = info.get("since")
        if since:
            start = datetime.fromisoformat(since)
            dur = fmt_duration((t - start).total_seconds())
            msg = (f"❌ **{info['branch']}** 的 Swim & Skate pass 没了，"
                   f"可借状态持续了约 **{dur}**（{local_hm(start)} → {local_hm(t)}）")
        else:
            msg = f"❌ **{info['branch']}** 的 Swim & Skate pass 没了（开始时间未知）"
        send_discord(msg)
        changed = True

    if changed:
        state["changed_at"] = t.isoformat(timespec="seconds")
        save_state(state)
    print(f"{local_hm(t)} available {len(current)}/{len(items)} +{len(appeared)} -{len(gone)}", flush=True)


def main():
    state = load_state()
    if "--test" in sys.argv:
        send_discord(f"Swim & Skate pass watcher test ✅ 当前可借 {len(state['available'])} 份\n{RECORD_URL}")
        return 0

    if "--loop" not in sys.argv:
        check_once(state, verbose=True)
        return 0

    duration = float(sys.argv[sys.argv.index("--loop") + 1])
    deadline = time.monotonic() + duration
    first = True
    while time.monotonic() < deadline:
        try:
            check_once(state, verbose=first)
            first = False
        except Exception as e:
            print(f"{local_hm(now())} check failed: {e}", flush=True)
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    return 0


if __name__ == "__main__":
    sys.exit(main())
