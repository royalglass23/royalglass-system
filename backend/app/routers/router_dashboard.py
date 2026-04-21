"""
routers/dashboard.py
Main dashboard endpoints.

GET  /dashboard
     Returns work order line items from dashboard_view.
     Supports filters: status, stage, site_ready, category, search.

PATCH /dashboard/{job_uuid}/override
     Saves manual fields for a work order.
     Creates a new override row or updates the existing one (upsert).
     Logs every changed field to change_log.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.auth import get_current_user


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ── Response models ───────────────────────────────────────────────────────────

class DashboardRow(BaseModel):
    # Work order fields
    job_uuid: str
    job_number: Optional[str]
    client_name: Optional[str]
    status: Optional[str]
    job_address: Optional[str]
    total_amount: Optional[float]
    job_category: Optional[str]

    # Item fields
    item_uuid: str
    display_name: Optional[str]
    display_name_auto: Optional[bool]
    item_category: Optional[str]
    quantity: Optional[float]
    total_price: Optional[float]
    sort_order: Optional[int]
    name_raw: Optional[str]

    # Manual override fields
    stage: Optional[str]
    site_ready: Optional[str]
    finish: Optional[str]
    glass_type: Optional[str]
    hardware: Optional[str]
    challenges: Optional[str]
    owner: Optional[str]
    comment: Optional[str]

    # Timestamps
    job_last_updated: Optional[datetime]
    item_last_updated: Optional[datetime]
    override_last_updated: Optional[datetime]

    class Config:
        from_attributes = True


class OverrideRequest(BaseModel):
    stage_manual: Optional[str] = None
    site_ready_manual: Optional[str] = None
    finish_manual: Optional[str] = None
    glass_type_manual: Optional[str] = None
    hardware_manual: Optional[str] = None
    challenges_manual: Optional[str] = None
    owner_manual: Optional[str] = None
    comment_manual: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DashboardRow])
def get_dashboard(
    status: Optional[str] = Query(default="Work Order", description="Job status filter"),
    stage: Optional[str] = Query(default=None),
    site_ready: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, description="Search client name or job number"),
    limit: int = Query(default=500, le=1000),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Returns all work order line items from dashboard_view.

    The dashboard_view already:
    - Joins work_orders + work_order_items + work_order_overrides
    - Applies override fallback logic
    - Filters to active records only

    This endpoint adds optional runtime filters on top.
    """
    # Build the query dynamically based on which filters are provided
    # We query the view directly and add WHERE clauses as needed
    conditions = []
    params = {"limit": limit, "offset": offset}

    # Status filter — default is Work Order but can be overridden
    if status:
        conditions.append("status = :status")
        params["status"] = status

    # Stage filter on the override field
    if stage:
        conditions.append("stage = :stage")
        params["stage"] = stage

    # Site ready filter
    if site_ready:
        conditions.append("site_ready = :site_ready")
        params["site_ready"] = site_ready

    # Category filter (item category)
    if category:
        conditions.append("item_category = :category")
        params["category"] = category

    # Search across client name and job number
    if search:
        conditions.append(
            "(client_name ILIKE :search OR job_number ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = text(f"""
        SELECT *
        FROM dashboard_view
        {where_clause}
        ORDER BY job_number, sort_order
        LIMIT :limit OFFSET :offset
    """)

    rows = db.execute(sql, params).mappings().all()
    return [dict(row) for row in rows]


@router.patch("/{job_uuid}/override")
def save_override(
    job_uuid: str,
    body: OverrideRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Save manual fields for a work order.

    Uses an upsert: creates the override row if it does not exist,
    updates it if it does. Only non-null fields in the request body are saved.
    Every changed field is written to change_log.
    """
    # Fetch current overrides to detect what actually changed
    existing = db.execute(
        text("SELECT * FROM work_order_overrides WHERE job_uuid = :job_uuid"),
        {"job_uuid": job_uuid}
    ).mappings().fetchone()

    # Fields we are allowed to update
    override_fields = [
        "stage_manual", "site_ready_manual", "finish_manual",
        "glass_type_manual", "hardware_manual", "challenges_manual",
        "owner_manual", "comment_manual",
    ]

    # Only process fields that were actually sent in the request
    updates = body.model_dump(exclude_none=True)

    if not updates:
        return {"message": "No fields to update."}

    # Log each changed field to change_log
    for field, new_val in updates.items():
        old_val = str(existing[field]) if existing and existing.get(field) is not None else None
        new_str = str(new_val) if new_val is not None else None

        if old_val != new_str:
            db.execute(text("""
                INSERT INTO change_log
                    (table_name, record_uuid, field_name, old_value, new_value, change_source, changed_by)
                VALUES
                    ('work_order_overrides', :uuid, :field, :old, :new, 'manual', :who)
            """), {
                "uuid": job_uuid,
                "field": field,
                "old": old_val,
                "new": new_str,
                "who": user["email"],
            })

    if existing:
        # Update existing override row
        set_clauses = ", ".join([f"{f} = :{f}" for f in updates.keys()])
        db.execute(
            text(f"""
                UPDATE work_order_overrides
                SET {set_clauses}, updated_at = NOW(), updated_by = :updated_by
                WHERE job_uuid = :job_uuid
            """),
            {**updates, "job_uuid": job_uuid, "updated_by": user["email"]}
        )
    else:
        # Insert new override row
        fields = list(updates.keys())
        cols = ", ".join(fields + ["job_uuid", "updated_by"])
        vals = ", ".join([f":{f}" for f in fields] + [":job_uuid", ":updated_by"])
        db.execute(
            text(f"INSERT INTO work_order_overrides ({cols}) VALUES ({vals})"),
            {**updates, "job_uuid": job_uuid, "updated_by": user["email"]}
        )

    db.commit()
    return {"message": "Override saved.", "job_uuid": job_uuid}
