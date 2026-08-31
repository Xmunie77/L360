# Learning 360° (l360)

Internal room-booking + billing tool for Learning 360° Foundation (Malta).
Standalone app, own database schema, own deploy — see `l360/DEPLOY.md`.

## Local dev

```bash
# Backend (defaults to a local SQLite DB — no Postgres needed)
pip install -r requirements.txt
python -m l360.seed                      # 5 rooms, 12 educators, 1 admin, price list
uvicorn l360.api:app --reload             # http://localhost:8000
python -m pytest l360/tests/

# Frontend (proxies /api and /health to :8000)
cd l360/web && npm ci && npm run dev      # http://localhost:5173
npm test
```

Dev admin login: `admin@example.com` / `l360-admin-dev`.
Dev educator logins: `educator1@example.com` .. `educator12@example.com` / `l360-dev`.

## Layout

```
l360/
  api.py              app assembly only: middleware, monitoring, SPA serving
  routers/            the actual routes, one module per area (auth, directory,
                      clients, educators, settings, billing, bookings,
                      payments, finance, public) — split 31/08/2026
  deps.py             shared FastAPI dependencies (require_user/admin) + helpers
  auth.py             password hashing + signed session cookie
  config.py           env config, fail-loud guard on Postgres with dev secrets
  db.py               engine/session, init_db() (SQLite dev only)
  models.py           SQLAlchemy 2.0 models
  schemas.py          Pydantic request/response models
  onboarding.py       client onboarding questionnaire: token link, invite email,
                      submission → client record + consent/signature record
  import_form_responses.py  one-off loader for the legacy Google Form responses
                      CSV (run with the data supplied at run time — never a
                      committed file; see its docstring)
  privacy.py          /privacy notice (DRAFT pending legal review)
  invoice_pdf.py      client invoice PDFs (fpdf2), letterhead from Admin → Invoicing
  jobs.py             T-24h reminders + daily digest — runs as the Fly `jobs` process
  seed.py             idempotent dev seed data
  migrations/         Alembic (l360 schema), gated — never run on boot
  tests/              pytest
  design/             Learning 360° brand tokens + UX spec (read-only reference)
  web/                Vite + React + TS SPA, styled from design/tokens.css
```

Status: Phase 1 (foundation) complete. Booking engine, notifications, billing +
Revolut reconciliation, and statements are built in later phases — see the
project plan for the full build order.

## Client onboarding

Adding a client (admin → Clients → "Add a client") needs only the guardian's
basic details — the full onboarding questionnaire (the in-app replacement for
the old Google "Client Onboarding Form": both guardians, learner details,
allergies, fee undertakings, policies, typed signatures) is **emailed to the
guardian automatically** on creation. The guardian opens `/?onboarding=<token>`
with no account (the unguessable token is the auth), and their submission
fills in the client record and stores the point-in-time consent/signature
record on `onboarding_forms`. Admins can re-send the link, open it themselves,
or type the details straight into the client detail page. Requires the SMTP
Fly secrets to be set for the email to actually send (see DEPLOY.md) —
without them the invite only logs to stdout.
