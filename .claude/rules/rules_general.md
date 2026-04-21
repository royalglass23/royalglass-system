# General Rules

## Environment

- Development: Windows laptop (D:\royalglass\), Docker Desktop
- Production: Mac Mini (same Docker stack, different env vars)
- Never hardcode paths — use relative paths or environment variables
- The `.env` file is never committed to Git

## Docker

All services run in Docker. Do not try to run FastAPI or PostgreSQL directly on Windows outside of Docker during development.

```bash
# Rebuild only the backend (fastest after Python code changes)
docker compose up -d --build backend

# View logs for a specific service
docker compose logs -f backend
docker compose logs -f db

# Restart a single service without rebuild
docker compose restart backend

# Full reset (wipes database volume — use only when needed)
docker compose down -v && docker compose up -d
```

Container names:
- `royalglass-db-1` — PostgreSQL
- `royalglass-backend-1` — FastAPI
- `royalglass-n8n-1` — n8n

## Git Workflow

```bash
# Never commit these files
.env
__pycache__/
*.pyc
.next/
node_modules/
n8n/data/

# Commit message format
git commit -m "stage X: short description of what changed"
```

## Security Rules

- JWT_SECRET must stay in `.env` — never hardcode it
- Passwords are always bcrypt hashed before storage
- API endpoints always validate the JWT before processing
- CORS is restricted to localhost:3000 and royalglass.co.nz
- Never log passwords, tokens, or the ServiceM8 API key

## Code Style

- Python: follow PEP 8, 4-space indentation
- SQL: uppercase keywords, lowercase table/column names
- JavaScript/TypeScript: 2-space indentation
- Comments explain WHY, not WHAT — the code shows what, comments show why

## What Not to Do

- Do not query ServiceM8 directly from the frontend — always go through the API
- Do not write directly to `work_order_overrides` from the sync workflow
- Do not delete rows from `change_log`
- Do not store plaintext passwords anywhere
- Do not expose internal `id` columns to the frontend — use UUIDs
- Do not put business logic in `main.py`

## Stage Progress

When asked what stage we are on or what to build next, check the Current Build Stage section in CLAUDE.md. Do not assume a stage is complete unless it is marked ✅.
