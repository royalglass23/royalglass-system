-- =============================================================
-- Royal Glass Work Order Dashboard
-- Migration: 001_initial_schema.sql
-- Stage 2: Database Schema
-- Created: April 2026
-- =============================================================

-- Enable UUID extension (needed for UUID type operations)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- TABLE: work_orders
-- One row per ServiceM8 job.
-- ServiceM8 is the source of truth for all synced columns.
-- =============================================================
CREATE TABLE IF NOT EXISTS work_orders (
    id              SERIAL PRIMARY KEY,
    job_uuid        UUID        UNIQUE NOT NULL,         -- ServiceM8 job UUID, primary sync key
    job_number      VARCHAR(50),                         -- e.g. Q250070, P240914
    status          VARCHAR(50),                         -- Quote / Work Order / Invoice / Completed
    client_uuid     UUID,                                -- ServiceM8 company UUID
    client_name     VARCHAR(255),                        -- Client display name
    job_date        DATE,                                -- Job creation date
    job_address     TEXT,                                -- Site address
    total_amount    NUMERIC(10,2),                       -- Total job value
    category        VARCHAR(10),                         -- A / B / C / D / E
    queue_name      VARCHAR(100),                        -- ServiceM8 queue label
    active          SMALLINT    DEFAULT 1,               -- 1 = active, 0 = archived
    edit_date       TIMESTAMP,                           -- ServiceM8 last modified, used for incremental sync
    synced_at       TIMESTAMP   DEFAULT NOW(),           -- When we last pulled this from ServiceM8
    created_at      TIMESTAMP   DEFAULT NOW()            -- When we first inserted this row
);

-- Indexes for common dashboard queries
CREATE INDEX IF NOT EXISTS idx_work_orders_status    ON work_orders (status);
CREATE INDEX IF NOT EXISTS idx_work_orders_active    ON work_orders (active);
CREATE INDEX IF NOT EXISTS idx_work_orders_edit_date ON work_orders (edit_date);
CREATE INDEX IF NOT EXISTS idx_work_orders_client    ON work_orders (client_uuid);


-- =============================================================
-- TABLE: work_order_items
-- One row per line item (ServiceM8 jobmaterial).
-- This is the core of the dashboard — one row per panel/product.
-- =============================================================
CREATE TABLE IF NOT EXISTS work_order_items (
    id                  SERIAL PRIMARY KEY,
    item_uuid           UUID        UNIQUE NOT NULL,                     -- ServiceM8 jobmaterial UUID
    job_uuid            UUID        NOT NULL
                            REFERENCES work_orders(job_uuid)
                            ON DELETE CASCADE,                           -- If job deleted, items go too
    material_uuid       UUID,                                            -- ServiceM8 product/material UUID
    name_raw            TEXT,                                            -- Exact name from ServiceM8 (never overwritten)
    description_raw     TEXT,                                            -- Full spec block from ServiceM8 (never overwritten)
    display_name        VARCHAR(255),                                    -- Clean short name shown on dashboard
    display_name_auto   BOOLEAN     DEFAULT TRUE,                        -- TRUE = auto-mapped, FALSE = needs manual review
    category            VARCHAR(50),                                     -- Mapped category from name mapping reference
    quantity            NUMERIC(10,4),                                   -- Quantity from ServiceM8
    unit_price          NUMERIC(10,2),                                   -- Price per unit
    total_price         NUMERIC(10,2),                                   -- Tax-inclusive displayed amount
    sort_order          INTEGER     DEFAULT 0,                           -- Display order within work order
    active              SMALLINT    DEFAULT 1,                           -- 1 = shown on dashboard, 0 = hidden
    edit_date           TIMESTAMP,                                       -- ServiceM8 last modified
    synced_at           TIMESTAMP   DEFAULT NOW(),
    created_at          TIMESTAMP   DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_items_job_uuid   ON work_order_items (job_uuid);
CREATE INDEX IF NOT EXISTS idx_items_active     ON work_order_items (active);
CREATE INDEX IF NOT EXISTS idx_items_category   ON work_order_items (category);
CREATE INDEX IF NOT EXISTS idx_items_edit_date  ON work_order_items (edit_date);
CREATE INDEX IF NOT EXISTS idx_items_review     ON work_order_items (display_name_auto) WHERE display_name_auto = FALSE;


-- =============================================================
-- TABLE: work_order_overrides
-- Manual fields entered by staff on the dashboard.
-- One row per work order (created on first save, upserted after).
-- Display rule: show manual value if present, else ServiceM8 value.
-- =============================================================
CREATE TABLE IF NOT EXISTS work_order_overrides (
    id                  SERIAL PRIMARY KEY,
    job_uuid            UUID        UNIQUE NOT NULL
                            REFERENCES work_orders(job_uuid)
                            ON DELETE CASCADE,
    stage_manual        VARCHAR(100),                                    -- Stage 1 / Stage 2 / Stage 3 / Stage 4 / Completed
    site_ready_manual   VARCHAR(50),                                     -- Yes / No / TBC
    finish_manual       VARCHAR(100),                                    -- Chrome / Brushed Nickel / Matt Black / Gunmetal / etc.
    glass_type_manual   VARCHAR(100),                                    -- Clear Toughened / Low Iron / Reeded / Laminated / etc.
    hardware_manual     VARCHAR(255),                                    -- Hardware notes
    challenges_manual   TEXT,                                            -- Site challenges or installation issues
    owner_manual        VARCHAR(100),                                    -- Assigned staff name
    comment_manual      TEXT,                                            -- General internal comment visible to staff
    updated_at          TIMESTAMP   DEFAULT NOW(),
    updated_by          VARCHAR(100)                                     -- Staff name or user email who last saved
);

-- Index for fast lookup by job
CREATE INDEX IF NOT EXISTS idx_overrides_job_uuid ON work_order_overrides (job_uuid);


-- =============================================================
-- TABLE: change_log
-- Audit trail for all changes — both sync updates and manual overrides.
-- Never deleted. Grows over time as the historical record.
-- =============================================================
CREATE TABLE IF NOT EXISTS change_log (
    id              SERIAL PRIMARY KEY,
    table_name      VARCHAR(50)     NOT NULL,            -- work_orders / work_order_items / work_order_overrides
    record_uuid     UUID            NOT NULL,            -- job_uuid or item_uuid that changed
    field_name      VARCHAR(100)    NOT NULL,            -- Column that changed
    old_value       TEXT,                                -- Previous value (cast to text)
    new_value       TEXT,                                -- New value (cast to text)
    change_source   VARCHAR(50),                         -- 'sync' = came from ServiceM8, 'manual' = staff entered
    changed_by      VARCHAR(100),                        -- Staff name or 'system' for sync
    changed_at      TIMESTAMP       DEFAULT NOW()
);

-- Indexes for querying history by record or time
CREATE INDEX IF NOT EXISTS idx_log_record    ON change_log (record_uuid);
CREATE INDEX IF NOT EXISTS idx_log_table     ON change_log (table_name);
CREATE INDEX IF NOT EXISTS idx_log_time      ON change_log (changed_at);
CREATE INDEX IF NOT EXISTS idx_log_source    ON change_log (change_source);


-- =============================================================
-- TABLE: users
-- Dashboard login accounts for staff.
-- Passwords stored as bcrypt hashes — never plaintext.
-- =============================================================
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,            -- Display name e.g. Roxy Huang
    email           VARCHAR(255)    UNIQUE NOT NULL,     -- Login email
    password_hash   VARCHAR(255)    NOT NULL,            -- bcrypt hash
    role            VARCHAR(50)     DEFAULT 'staff',     -- 'staff' or 'admin'
    active          BOOLEAN         DEFAULT TRUE,        -- FALSE = account disabled
    created_at      TIMESTAMP       DEFAULT NOW(),
    last_login      TIMESTAMP                            -- Updated on each successful login
);

-- Index for login lookup
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);


-- =============================================================
-- VIEW: dashboard_view
-- The main query the dashboard uses.
-- Merges work_orders + work_order_items + work_order_overrides.
-- Applies display rule: manual value if present, else ServiceM8 value.
-- Only shows active work orders with active items.
-- =============================================================
CREATE OR REPLACE VIEW dashboard_view AS
SELECT
    -- Work order fields
    wo.job_uuid,
    wo.job_number,
    wo.client_name,
    wo.status,
    wo.job_address,
    wo.total_amount,
    wo.category         AS job_category,

    -- Item fields
    woi.item_uuid,
    woi.display_name,
    woi.display_name_auto,
    woi.category        AS item_category,
    woi.quantity,
    woi.total_price,
    woi.sort_order,
    woi.name_raw,

    -- Manual override fields (with fallback logic)
    COALESCE(ov.stage_manual,      NULL)    AS stage,
    COALESCE(ov.site_ready_manual, NULL)    AS site_ready,
    COALESCE(ov.finish_manual,     NULL)    AS finish,
    COALESCE(ov.glass_type_manual, NULL)    AS glass_type,
    COALESCE(ov.hardware_manual,   NULL)    AS hardware,
    COALESCE(ov.challenges_manual, NULL)    AS challenges,
    COALESCE(ov.owner_manual,      NULL)    AS owner,
    COALESCE(ov.comment_manual,    NULL)    AS comment,

    -- Metadata
    wo.edit_date        AS job_last_updated,
    woi.edit_date       AS item_last_updated,
    ov.updated_at       AS override_last_updated

FROM work_order_items woi
INNER JOIN work_orders wo
    ON woi.job_uuid = wo.job_uuid
LEFT JOIN work_order_overrides ov
    ON wo.job_uuid = ov.job_uuid

-- Only show active jobs and active items
WHERE wo.active = 1
  AND woi.active = 1
  AND wo.status = 'Work Order'               -- Default: Work Orders only (can be filtered in query)

ORDER BY
    wo.job_number,
    woi.sort_order;


-- =============================================================
-- COMMENT DOCUMENTATION
-- Documents each table purpose inline in PostgreSQL
-- =============================================================
COMMENT ON TABLE work_orders           IS 'One row per ServiceM8 job. Synced from ServiceM8 every 15 minutes via n8n.';
COMMENT ON TABLE work_order_items      IS 'One row per line item (jobmaterial). Core of the dashboard. Synced from ServiceM8.';
COMMENT ON TABLE work_order_overrides  IS 'Manual fields entered by staff on the dashboard. Never overwritten by sync.';
COMMENT ON TABLE change_log            IS 'Audit trail for all data changes. Append-only. Never deleted.';
COMMENT ON TABLE users                 IS 'Dashboard staff accounts. Passwords stored as bcrypt hashes.';
COMMENT ON VIEW  dashboard_view        IS 'Main dashboard query. Merges jobs + items + overrides. Active Work Orders only by default.';

