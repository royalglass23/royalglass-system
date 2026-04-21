# Royal Glass Work Order Dashboard

Internal dashboard for Royal Glass staff to view and annotate glazing jobs pulled from ServiceM8.

## Stack

| Service | Purpose | Port |
|---|---|---|
| PostgreSQL 16 | Primary data store | 5432 |
| FastAPI | REST API + JWT auth | 8000 |
| n8n | ServiceM8 sync automation | 5678 |
| Next.js | Staff dashboard UI | 3000 (not yet built) |

## Quick Start

**Requirements:** Docker Desktop, Python 3.12 (local), `.env` file in repo root.

```bash
# Start all services
docker compose up -d

# Check everything is running
docker compose ps
```

**Swagger UI:** http://localhost:8000/docs  
**n8n UI:** http://localhost:5678  
**Health check:** http://localhost:8000/health

## First-Time Setup

### 1. Apply the database schema

```powershell
Get-Content db/migrations/001_initial_schema.sql | docker compose exec -T db psql -U rgadmin -d royalglass
```

### 2. Create a staff account

```bash
docker compose exec backend python app/seed_user.py
```

Or use the interactive script (run from repo root, requires Docker running):

```bash
docker compose exec backend python create_user.py
```

> **Note:** `create_user.py` cannot be run directly from Windows due to a Docker networking issue (see `docs/troubleshooting.md`). Always run it from inside the backend container.

### 3. Test the login

Go to http://localhost:8000/docs → `POST /auth/login` → enter your credentials → copy the `access_token` → click **Authorize** → paste the token → test `GET /dashboard`.

## Common Commands

```powershell
# Rebuild backend after adding/changing Python dependencies
docker compose up -d --build backend

# Tail backend logs
docker compose logs -f backend

# Apply a new migration
Get-Content db/migrations/002_your_migration.sql | docker compose exec -T db psql -U rgadmin -d royalglass

# Connect to the database directly
docker compose exec db psql -U rgadmin -d royalglass

# Full reset — wipes ALL data (use only when needed)
docker compose down -v
docker compose up -d
# Then re-apply migrations and re-seed users
```

## Environment Variables

`.env` is gitignored. Required variables:

```
POSTGRES_DB=royalglass
POSTGRES_USER=rgadmin
POSTGRES_PASSWORD=yourpassword
JWT_SECRET=your-secret-key
APP_ENV=development
SM8_API_KEY=your-servicem8-key
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=yourpassword
```

## Project Structure

```
backend/
  app/
    main.py              — FastAPI app, CORS, router registration
    config.py            — Settings from .env
    database.py          — SQLAlchemy engine + get_db()
    auth.py              — JWT + bcrypt password helpers
    seed_user.py         — Seed admin user (run inside container)
    routers/
      router_auth.py     — POST /auth/login
      router_dashboard.py — GET /dashboard, PATCH /dashboard/{job_uuid}/override
      router_items.py    — PATCH /items/{item_uuid}/display-name, GET /items/review
  create_user.py         — Interactive account creation (run inside container)
  Dockerfile
  requirements.txt
db/
  migrations/
    001_initial_schema.sql
docs/
  docs_architecture.md
  troubleshooting.md
docker-compose.yml
```

## Docs

- [Architecture](docs/docs_architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
