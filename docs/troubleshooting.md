# Troubleshooting Log

## Issue 1: `create_user.py` — password authentication failed

**Symptom:**
```
Could not connect to the database: connection to server at "localhost" (::1), port 5432 failed:
FATAL: password authentication failed for user "rgadmin"
```

**Root causes (multiple):**

1. **IPv6 vs IPv4** — On Windows, `localhost` resolves to `::1` (IPv6). Docker port-forwards on IPv4, so the connection never matched the `trust` rule in `pg_hba.conf` for `127.0.0.1`. Fix: use `127.0.0.1` explicitly in the connection string.

2. **scram-sha-256 / md5 hash mismatch** — PostgreSQL 16 stores passwords as `scram-sha-256` by default. The `pg_hba.conf` catch-all rule (`host all all all scram-sha-256`) requires scram auth from the Docker bridge IP, but changing it to `md5` still failed because the stored password hash was scram-sha-256 — you can't verify a scram hash with md5 auth.

3. **Trailing spaces in `.env`** — `type .env` revealed lines like `POSTGRES_USER=rgadmin ` with trailing spaces. `python-dotenv` reads these as part of the value, so psycopg2 was connecting as `"rgadmin "` (with a space).

**Resolution:**
Since the DB is development-only and not exposed externally, set `POSTGRES_HOST_AUTH_METHOD=trust` in `docker-compose.yml`. This bypasses password auth for all connections. Also run `docker compose down -v && docker compose up -d` to wipe and reinitialise the volume so the new config takes effect.

For creating staff accounts, bypass `create_user.py` entirely and insert directly via psql inside Docker:

```bash
# 1. Generate bcrypt hash locally
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"

# 2. Insert via psql inside the container
docker compose exec db psql -U rgadmin -d royalglass -c \
  "INSERT INTO users (name, email, password_hash, role) \
   VALUES ('Name', 'email@example.com', 'HASH_HERE', 'admin') \
   ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, role = EXCLUDED.role;"
```

`create_user.py` was also updated to read `DB_HOST` from the environment (defaulting to `127.0.0.1`), so it can be run from inside the backend container in the future:
```bash
docker compose exec backend python create_user.py
```

---

## Issue 2: Migration not applied after volume reset

**Symptom:** `\dt` returned no relations after `docker compose down -v && docker compose up -d`.

**Cause:** `docker compose down -v` wipes the `pgdata` volume, so the schema is lost and must be re-applied manually.

**Resolution:** Apply migrations after every volume reset:
```bash
# PowerShell (< redirection not supported)
Get-Content db/migrations/001_initial_schema.sql | docker compose exec -T db psql -U rgadmin -d royalglass
```

---

## Issue 3: Backend crash on startup — ImportError

**Symptom:**
```
ImportError: cannot import name 'auth' from 'app.routers'
```

**Cause:** `main.py` imported `from app.routers import auth, dashboard, items` but the actual files are named `router_auth.py`, `router_dashboard.py`, `router_items.py`.

**Resolution:** Fixed the import in `main.py`:
```python
from app.routers import router_auth as auth, router_dashboard as dashboard, router_items as items
```

---

## Key Commands Reference

```bash
# Wipe DB and reinitialise (destroys all data)
docker compose down -v && docker compose up -d

# Apply migration (PowerShell)
Get-Content db/migrations/001_initial_schema.sql | docker compose exec -T db psql -U rgadmin -d royalglass

# Connect to DB directly
docker compose exec db psql -U rgadmin -d royalglass

# Tail backend logs
docker compose logs -f backend

# Rebuild backend after dependency changes
docker compose up -d --build backend
```
