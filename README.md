# Swim & Skate pass watcher

Watches the Mississauga Library [Swim & Skate Family Activity Pass](https://mississauga.bibliocommons.com/v2/record/S220C769335)
and pushes to Discord when a copy turns **Available** at any branch.

## Setup

1. Repo → Settings → Secrets and variables → Actions → **Secrets** → `DISCORD_WEBHOOK_URL`
   (Discord channel → Edit Channel → Integrations → Webhooks → Copy Webhook URL).
2. Optional: **Variables** → `BRANCHES`, comma-separated names or codes, e.g. `Meadowvale,CHU,Erin Meadows`.
   Empty = all branches.
3. Actions tab → *Check Swim & Skate pass* → Run workflow (tick *test*) to confirm Discord works.

Runs every 10 minutes via GitHub Actions; `state.json` remembers which copies were already available
so you're only pinged when a new one appears.

## Local

~~~
set DISCORD_WEBHOOK_URL=...
python check_pass.py --test
~~~
