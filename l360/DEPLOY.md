# Deploying Learning 360° (l360)

A fully separate standalone app living in this repo purely for convenience —
its own Fly app, its own Neon Postgres project/schema, its own GitHub Actions
workflows. It shares nothing at runtime with kitchentable or the retail/POS
system.

- **Backend:** FastAPI + SQLAlchemy + Neon Postgres, gated Alembic migrations
  (schema `l360`).
- **Frontend:** React (Vite + TypeScript), built at `l360/web` → `l360/web/dist`.
- **Fly app:** `rubicon-l360` (region `fra`, matches Neon's recommended EU region).

```
l360/
  *.py                    FastAPI package (api.py, models.py, config.py, db.py, ...)
  migrations/              Alembic (l360 schema), gated — never on boot
  web/                     Vite + React + TS SPA
  Dockerfile               two-stage: Node builds the SPA → Python serves it + the API
  fly.toml                 Fly app `rubicon-l360` (fra)
  requirements.txt         backend deps (starting point; may be extended)
.github/workflows/
  l360-deploy.yml          auto-deploy to Fly on push to main touching l360/**
                             (secret: FLY_API_TOKEN_L360)
  l360-migrate.yml         gated Alembic run (secret: DATABASE_URL_L360)
```

## Local dev

```bash
# Backend (defaults to a local SQLite DB — no Postgres needed)
pip install -r l360/requirements.txt
uvicorn l360.api:app --reload                     # http://localhost:8000
python -m pytest l360/tests/

# Frontend (proxies /api and /health to :8000)
cd l360/web && npm ci && npm run dev               # http://localhost:5173
npm test                                            # vitest
```

On Postgres the app **refuses to boot** with a dev-default `L360_SESSION_SECRET`
(see `l360/config.py: assert_secure_config`).

## Deploy (browser + GitHub Actions — no local tooling)

Two repo secrets and two Fly secrets. Order matters: the Fly app + deploy
token must exist **before** the first push, or the deploy job goes red.

**1 — Neon (browser).** neon.tech → New Project "l360" (or "learning-360"),
region EU (Frankfurt). Copy the **direct / unpooled** connection string (host
*without* `-pooler`), ensure it ends `?sslmode=require`. Call it `<NEON_URL>`.
This must be a project separate from kitchentable's — l360 owns its own
database, not just a separate schema in the same project.

**2 — Fly app + runtime secrets.** Create app `rubicon-l360` (region `fra`).
Either in the Fly dashboard, or CLI:
```
fly apps create rubicon-l360
fly secrets set -a rubicon-l360 \
  DATABASE_URL='<NEON_URL>' \
  L360_SESSION_SECRET='<64 hex chars, e.g. `openssl rand -hex 32`>'
```
Then create a **deploy token** (Fly dashboard → Tokens, or
`fly tokens create deploy -a rubicon-l360`).

**3 — GitHub repo secrets** (this repo → Settings → Secrets and variables →
Actions), add two:
- `FLY_API_TOKEN_L360` = the Fly deploy token from step 2.
- `DATABASE_URL_L360` = the same `<NEON_URL>` (used only by the migrate
  workflow). Named distinctly from kitchentable's `FLY_API_TOKEN` /
  `DATABASE_URL` secrets since these are separate Fly apps and separate Neon
  databases sharing one repo's secret store.

**4 — Push to main** (touching `l360/**`). The push triggers
`l360-deploy.yml`, which builds the image on Fly's remote builder — using
`--config l360/fly.toml --dockerfile l360/Dockerfile` since l360's config
lives in a subdirectory alongside kitchentable's root-level config — and
deploys. (The app boots healthy before the DB is migrated — API routes that
touch the DB error until step 5.)

**5 — Migrate.** GitHub → Actions → "Migrate — Alembic (l360 DB)" → Run
workflow → command=`upgrade`, revision=`head`. Creates the `l360` schema +
tables in Neon.

**6 — Verify.** Open `https://rubicon-l360.fly.dev`, confirm `/health`
returns `{"status":"ok"}`, then sign in and confirm the booking flow works.

From then on, any push to `main` that touches `l360/**` auto-deploys.

## Optional integrations (the app runs fine without these — they degrade gracefully)

**Email.** Without `SMTP_HOST` set, every notification (booking confirmations,
T-24h reminders, invoice-issued emails) just logs to stdout instead of
sending — safe, but nobody actually gets emailed. Set as Fly secrets once
you have an SMTP provider: `SMTP_HOST`, `SMTP_PORT` (default 587),
`SMTP_USER`, `SMTP_PASSWORD`, `L360_EMAIL_FROM`.

**Revolut Business (payment reconciliation).** Without `REVOLUT_API_TOKEN`
set, the admin "Sync payments" button returns a clear 409 rather than
crashing. Set `REVOLUT_API_TOKEN` (and `REVOLUT_API_BASE` if it differs from
the default) once you have API access. ⚠️ `l360/payments/revolut.py`'s
request/response handling is best-effort — written without a live token to
verify against — so test it against a real Revolut sandbox/account before
relying on it; a shape mismatch there fails obviously (no transactions
import) rather than silently, but it still needs that check before go-live.

**Scheduled reminders & digest.** T-24h reminder emails and each educator's
daily digest are NOT started automatically inside the web process — the
Dockerfile runs 2 uvicorn workers, and an in-process scheduler per worker
would double-fire every job (harmless given the notification dedupe, but
wasteful). Run them as a separate Fly process instead:
```toml
# add to l360/fly.toml
[processes]
  app = "sh -c \"python -c 'from l360.db import init_db; init_db()' && uvicorn l360.api:app --host 0.0.0.0 --port 8000 --workers 2\""
  jobs = "python -m l360.jobs"
```
then `fly scale count app=1 jobs=1 -a rubicon-l360`. Not yet wired up —
booking confirmation/change/cancel emails (the synchronous ones) work
without this; only the T-24h reminder and daily digest need it.
