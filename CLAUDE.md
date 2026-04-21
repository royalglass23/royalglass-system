# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Royal Glass work order dashboard. Staff view and annotate glazing jobs pulled from **ServiceM8** (field service SaaS). The stack is:

- **PostgreSQL 16** — primary data store
- **FastAPI backend** (`backend/`) — REST API, JWT auth, raw SQL via SQLAlchemy
- **n8n** — automation engine that syncs data from ServiceM8 into the database
- **Next.js frontend** (`frontend/`) — not yet built

## Commands

All services run via Docker Compose from the repo root:

```bash
docker compose up -d          # start all services (db, backend, n8n)
docker compose up -d --build  # rebuild backend image after dependency changes
docker compose down           # stop all services
docker compose logs -f backend  # tail backend logs
docker compose ps             # check service health
```

The backend uses `--reload`, so code changes in `backend/app/` apply immediately without a restart.

**Swagger UI** (development only): http://localhost:8000/docs  
**n8n UI**: http://localhost:5678  
**Health check**: http://localhost:8000/health

**Create a staff account** (run from inside the backend container):
```bash
docker compose exec backend python app/seed_user.py
```

> `create_user.py` cannot be run directly from Windows — Docker port-forwarding prevents password auth from the host. Always run scripts that connect to the DB from inside the backend container.

**Apply a migration** (PowerShell — stdin redirection `<` is not supported):
```powershell
Get-Content db/migrations/001_initial_schema.sql | docker compose exec -T db psql -U rgadmin -d royalglass
```

> After `docker compose down -v`, the schema is wiped. Always re-apply all migrations before using the API.

## Architecture

### Data flow

ServiceM8 → n8n (sync every ~15 min) → PostgreSQL → FastAPI → Next.js frontend

n8n calls the ServiceM8 REST API and upserts rows into `work_orders` and `work_order_items`. Staff can annotate jobs via the dashboard, writing to `work_order_overrides`. These two data sources are never mixed — sync only touches ServiceM8 columns; manual overrides only touch the `_manual` columns.

### Database design

Five tables + one view:

| Table | Purpose |
|---|---|
| `work_orders` | One row per ServiceM8 job. Synced. |
| `work_order_items` | One row per line item (jobmaterial). Synced. |
| `work_order_overrides` | Manual annotations (stage, finish, glass type, etc.). One row per job, created on first staff save. |
| `change_log` | Append-only audit trail for all field changes (both sync and manual). |
| `users` | Dashboard staff accounts (bcrypt passwords, roles: staff/admin). |

**`dashboard_view`** is the main query: joins the three core tables and applies `COALESCE` to surface manual values. The API queries this view directly — no ORM models.

### Backend structure

```
backend/app/
  main.py       — FastAPI app, CORS, router registration, /health, /me
  config.py     — pydantic-settings: reads .env, exposes settings singleton
  database.py   — SQLAlchemy engine + get_db() dependency
  auth.py       — JWT encode/decode, bcrypt helpers, get_current_user() dependency
  routers/
    router_auth.py       — POST /auth/login
    router_dashboard.py  — GET /dashboard, PATCH /dashboard/{job_uuid}/override
    router_items.py      — PATCH /items/{item_uuid}/display-name, GET /items/review
```

All endpoints use raw `text()` SQL against PostgreSQL — no ORM models or Alembic. Every write operation logs to `change_log`.

### Auth pattern

Login returns a JWT (8 h expiry). All protected endpoints use `Depends(get_current_user)`, which decodes the token and re-validates the user is still active in the DB. The token payload carries `sub` (email) and `role`.

### Key rules from the domain

- `work_order_items.display_name_auto = FALSE` means a human has named it — the sync must never overwrite `display_name` for those rows.
- `work_order_overrides` uses upsert: insert on first save, update on subsequent saves.
- `change_log` is append-only — never delete rows from it.
- `active = 0` soft-deletes jobs/items; the view filters these out automatically.

## Migrations

SQL files live in `db/migrations/` and are numbered sequentially (`001_initial_schema.sql`, etc.). There is no migration runner — apply them manually via psql. The migration file is the schema source of truth.

## Environment

`.env` is in `.gitignore`. Required variables:

```
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
JWT_SECRET
APP_ENV (development | production)
SM8_API_KEY
N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD
```

`config.py` builds `database_url` from the Postgres vars. In Docker Compose, `DB_HOST=db` (the service name); the `create_user.py` script connects to `localhost:5432` (host-side).
