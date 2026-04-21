# Database Rules

## Core Principle

PostgreSQL is the source of truth for all internal state. ServiceM8 is the source of truth for synced operational data. Never bypass the database — all reads and writes go through the FastAPI backend.

## Table Rules

**work_orders and work_order_items:**
- Synced from ServiceM8 by n8n
- The sync uses UPSERT on job_uuid / item_uuid
- `edit_date` drives incremental sync — only pull records changed since last sync
- `active = 0` means hidden from dashboard, not deleted

**work_order_overrides:**
- NEVER touched by the sync workflow
- Only written by the API when staff save manual fields
- One row per work order (UNIQUE on job_uuid)
- Use INSERT ... ON CONFLICT DO UPDATE (upsert pattern)

**change_log:**
- Append-only — never DELETE or UPDATE rows here
- One row per field change, not per record change
- `change_source` is always either `'sync'` or `'manual'`

**users:**
- Passwords stored as bcrypt hashes — never plaintext
- `active = FALSE` disables login without deleting the account

## Column Naming

- UUIDs from ServiceM8: `job_uuid`, `item_uuid`, `client_uuid`, `material_uuid`
- Our internal IDs: `id` (SERIAL, never exposed to frontend)
- Timestamps: `created_at`, `synced_at`, `updated_at`, `changed_at`, `edit_date`
- Manual fields always suffixed `_manual`: `stage_manual`, `finish_manual`, etc.

## Sync Key Rule

The sync identifies records by UUID, not by `id`. Always use `job_uuid` and `item_uuid` as the lookup key in sync operations.

```sql
-- Correct upsert pattern for sync
INSERT INTO work_orders (job_uuid, job_number, ...)
VALUES (:job_uuid, :job_number, ...)
ON CONFLICT (job_uuid) DO UPDATE
    SET job_number = EXCLUDED.job_number,
        synced_at = NOW()
WHERE work_orders.edit_date < EXCLUDED.edit_date;
```

The `WHERE edit_date <` clause prevents overwriting newer data with older data if a sync runs out of order.

## dashboard_view

The main dashboard query. Always query this view for dashboard reads — do not join the tables manually in the API.

```sql
SELECT * FROM dashboard_view
WHERE status = 'Work Order'   -- default filter
ORDER BY job_number, sort_order;
```

The view handles the join and the COALESCE override fallback logic.

## Indexes

These indexes exist — use them by filtering on these columns:
- `work_orders`: status, active, edit_date, client_uuid
- `work_order_items`: job_uuid, active, category, edit_date, display_name_auto
- `change_log`: record_uuid, table_name, changed_at, change_source
- `users`: email

## Migrations

Migration files live in `db/migrations/`. Naming: `NNN_description.sql` (e.g. `002_add_location_column.sql`). Each migration uses `IF NOT EXISTS` so it is safe to re-run. Never edit an existing migration file — add a new one.
