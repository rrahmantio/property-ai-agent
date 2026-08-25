# HOZ Property AI — Content Agent (V1, Phases 1–4)

Automated Threads content agent for HOZ Property: researches current Jakarta
property/lifestyle topics, drafts 3–4 Threads text-chain options a day,
emails them for approval, and publishes only what you click "POST THIS" on.

Built through **Phase 4** (content generation → email approval → Threads
publishing). Phase 5 (Typeform → Google Sheet lead database) and Phase 6
(analytics) are intentionally not built yet — the `leads` table in
`storage.py` is a schema stub so adding them later won't need a migration.

## How it fits together

There are two separate running pieces, because a GitHub Actions cron job
only runs on a schedule — it can't sit and wait for you to click a link in
an email.

1. **`daily_job.py`** — runs once a day (via GitHub Actions, 09:00 WIB).
   Does the research → concepts → scoring → chain-writing → quality-check →
   email steps. Saves each option to SQLite with status `proposed`.
2. **`approval_app.py`** — a small always-on Flask app. This is what the
   email's `VIEW / POST THIS` and `REGENERATE` links point at. When you
   click POST THIS, it publishes that chain to Threads and marks it
   `published`. **This needs to be deployed somewhere that stays up**
   (Render, Fly.io, Railway, a cheap VPS — anywhere with a public URL).
   GitHub Actions itself cannot host it.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your real values, never commit this file
python -c "import storage; storage.init_db()"
```

Required values in `.env` (see `.env.example` for the full list):
- `ANTHROPIC_API_KEY` — your Claude API key
- `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` — Threads (Meta Graph API) creds
- `EMAIL_USER` / `EMAIL_PASSWORD` / `EMAIL_TO` — SMTP creds for the approval email
  (Gmail: use an [app password](https://myaccount.google.com/apppasswords), not your login password)
- `APPROVAL_SECRET` — random string, used as a defense-in-depth secret for the approval app
- `APPROVAL_BASE_URL` — the public URL where you deploy `approval_app.py`
- `TYPEFORM_URL` — already set to your form by default

## Running locally

```bash
# terminal 1: the always-on approval webhook
python approval_app.py

# terminal 2: run one content-generation cycle manually
python daily_job.py
```

Open the approval email, click "VIEW / POST THIS" on whichever option you
like — it publishes straight to Threads.

## Deploying the approval webhook

Any host that keeps a Python process alive and gives you a public HTTPS URL
works. Quick options:
- **Render** (free tier): "New Web Service" → point at this repo → start
  command `gunicorn approval_app:app` → copy the resulting URL into
  `APPROVAL_BASE_URL`.
- **Fly.io** / **Railway**: similar — deploy, get a public URL, set the env var.

Once deployed, set `APPROVAL_BASE_URL` both in your deployment's own env
vars (so `config.py` there matches) and as a GitHub Actions secret (so the
daily email is built with the right links).

## Automating the daily run (GitHub Actions)

`.github/workflows/daily-content.yml` runs `daily_job.py` at 02:00 UTC
(09:00 WIB) every day. Add these as **repository secrets**
(Settings → Secrets and variables → Actions):

```
ANTHROPIC_API_KEY
THREADS_ACCESS_TOKEN
THREADS_USER_ID
TYPEFORM_URL
EMAIL_USER
EMAIL_PASSWORD
EMAIL_TO
APPROVAL_SECRET
APPROVAL_BASE_URL
```

Note on storage: GitHub Actions runners are ephemeral, so `data/hoz_agent.db`
doesn't naturally persist between runs. The workflow caches it as a stopgap,
but for anything you rely on long-term, point `DB_PATH` (via env var) at a
persistent volume on wherever `approval_app.py` is deployed, and have
`daily_job.py` run there too (e.g. as a cron job on the same host) instead
of on GitHub's runners. That also simplifies things to one running place
instead of two.

## Content rules baked into the prompts (`content_generation.py`, `research.py`)

- Concepts are generated (6–8) and scored *before* any full post is written.
- Scoring rubric: hook 20%, audience relevance 20%, useful insight 20%,
  originality 15%, Jakarta relevance 10%, demand potential 15%.
- Research prioritises official/government sources → official company
  announcements → reputable Indonesian media → reputable property sources.
  No invented statistics, prices, timelines, or distances — unsupported
  claims are dropped or clearly framed as opinion.
- Recent history is passed into concept generation so topics/hooks aren't
  repeated.
- Every chain ends with the CTA ("Rumah seperti apa yang kalian cari?") and
  the Typeform link — aimed at capturing property *demand*, not just
  pushing existing listings.
- A quality pass rejects generic, salesy, obviously-AI, repetitive,
  unsupported, clickbait, overly formal, emoji-stuffed, or unnecessarily
  political/controversial drafts.

## What's NOT built yet (by design — see the spec's build order)

- **Phase 5**: wiring the Typeform webhook into the `leads` table /
  Google Sheet.
- **Phase 6**: analytics connecting content → engagement → leads →
  transactions.

The `leads` table already exists in `storage.py` so Phase 5 is additive,
not a rework.

## Secrets hygiene

- Nothing sensitive is hard-coded anywhere in this repo.
- The Threads access token is only read from `config.py` (env var) and is
  explicitly stripped out of any error message before it's raised/logged
  (`threads_client.py`).
- `.env` is for local use only — never commit it. Use GitHub Actions
  secrets / your host's env var settings for anything deployed.
