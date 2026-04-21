# System Architecture

## Overview

```
ServiceM8 (external SaaS)
    │
    │  REST API (every 15 min via edit_date filter)
    │  OR webhook (instant, via Cloudflare Tunnel)
    ↓
n8n (automation engine)
    │  running on port 5678
    │  self-hosted in Docker
    ↓
PostgreSQL (internal database)
    │  running on port 5432
    │  source of truth for dashboard state
    ↓
FastAPI (backend API)
    │  running on port 8000
    │  handles auth, reads, writes, change logging
    ↓
Next.js (dashboard frontend)
    running on port 3000
    staff-facing UI
```

## Data Flow: Sync (ServiceM8 → Database)

```
n8n polls ServiceM8 /job.json?$filter=edit_date gt 'last_sync'
    → for each changed job, fetch /jobmaterial.json?$filter=job_uuid eq '...'
    → UPSERT into work_orders (on conflict job_uuid)
    → UPSERT into work_order_items (on conflict item_uuid)
    → apply display_name mapping logic
    → write to change_log (source: 'sync')
    → update last_sync timestamp
```

## Data Flow: Manual Override (Staff → Database)

```
Staff edits fields on dashboard
    → click Save
    → Next.js calls PATCH /dashboard/{job_uuid}/override
    → FastAPI validates JWT
    → FastAPI fetches current overrides
    → FastAPI writes changed fields to change_log (source: 'manual')
    → FastAPI upserts work_order_overrides
    → returns success
    → dashboard refreshes row
```

## Data Flow: Dashboard Read

```
Next.js loads dashboard
    → GET /dashboard?status=Work+Order
    → FastAPI validates JWT
    → FastAPI queries dashboard_view
    → dashboard_view joins work_orders + work_order_items + work_order_overrides
    → COALESCE applies override fallback
    → returns array of rows
    → Next.js renders table
```

## Override Display Rule

For each displayed field:
- If `work_order_overrides.field_manual` is not null → show manual value
- Otherwise → show null (blank on dashboard, staff can fill in)

ServiceM8 values for manual fields (stage, finish, glass type etc) are NOT shown as fallback — these fields are internal only. Staff enter them fresh from site knowledge.

## Module Map (future)

```
M01 Data Sync          → n8n: ServiceM8 → PostgreSQL
M02 Dashboard          → This system (current build)
M03 Email Intake       → n8n: IMAP → Claude → ServiceM8 job
M04 Lead Scoring       → n8n: daily briefing via Telegram
M05 Quoting Calculator → Web form → pricing engine → estimate email
M06 Quote Tracking     → Web-hosted quote with tracking pixels
M07 Call Capture       → Whisper transcription → Claude summary → ServiceM8 note
```

## Infrastructure

- **Dev:** Windows laptop, Docker Desktop, localhost
- **Prod:** Mac Mini, Docker, Cloudflare Tunnel (for webhooks)
- **Migration path:** Same docker-compose.yml, same folder structure, different .env values
