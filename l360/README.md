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
  api.py              FastAPI app: auth, admin CRUD, read-only lists, SPA serving
  auth.py             password hashing + signed session cookie
  config.py           env config, fail-loud guard on Postgres with dev secrets
  db.py               engine/session, init_db() (SQLite dev only)
  models.py           SQLAlchemy 2.0 models
  schemas.py          Pydantic request/response models
  seed.py             idempotent dev seed data
  migrations/         Alembic (l360 schema), gated — never run on boot
  tests/              pytest
  design/             Learning 360° brand tokens + UX spec (read-only reference)
  web/                Vite + React + TS SPA, styled from design/tokens.css
```

Status: Phase 1 (foundation) complete. Booking engine, notifications, billing +
Revolut reconciliation, and statements are built in later phases — see the
project plan for the full build order.
