# Swim & Skate pass watcher

Watches the Mississauga Library [Swim & Skate Family Activity Pass](https://mississauga.bibliocommons.com/v2/record/S220C769335)
every 10-30 seconds and pushes to Discord:

- when a copy turns **Available** at a branch (which library to go to), and
- when it's gone again, with how long it stayed available.

## Setup

1. Repo → Settings → Secrets and variables → Actions → **Secrets** → `DISCORD_WEBHOOK_URL`
   (Discord channel → Edit Channel → Integrations → Webhooks → Copy Webhook URL).
2. Optional: **Variables** → `BRANCHES`, comma-separated names or codes, e.g. `Meadowvale,CHU,Erin Meadows`.
   Empty = all branches.
3. Actions tab → *Check Swim & Skate pass* → Run workflow (tick *test*) to confirm Discord works.

A single GitHub Actions job polls for ~5h45m; the hourly schedule keeps the next run queued so it takes over
right away. `state.json` stores which copies are available and since when.

## Local

~~~
set DISCORD_WEBHOOK_URL=...
python check_pass.py              # check once
python check_pass.py --loop 3600  # poll every 10-30s for an hour
~~~
