"""
routers/items.py
Item-level endpoints.

PATCH /items/{item_uuid}/display-name
      Staff corrects the auto-mapped display name for an item.
      Sets display_name_auto = FALSE so the sync never overwrites it.
      Logs the change to change_log.

GET   /items/review
      Returns all items where display_name_auto = FALSE.
      These are items the sync could not map confidently and need a human to name.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.auth import get_current_user


router = APIRouter(prefix="/items", tags=["Items"])


class DisplayNameRequest(BaseModel):
    display_name: str
    category: Optional[str] = None   # Optionally correct the category too


@router.patch("/{item_uuid}/display-name")
def update_display_name(
    item_uuid: str,
    body: DisplayNameRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Correct the display name for a line item.

    Once a display name is manually set, display_name_auto is set to FALSE.
    This tells the sync to never overwrite this field again — the human
    decision takes priority over the auto-mapping.
    """
    # Confirm item exists
    item = db.execute(
        text("SELECT item_uuid, display_name, category FROM work_order_items WHERE item_uuid = :uuid"),
        {"uuid": item_uuid}
    ).mappings().fetchone()

    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_uuid} not found.")

    old_name = item["display_name"]
    old_category = item["category"]

    # Log display name change
    if old_name != body.display_name:
        db.execute(text("""
            INSERT INTO change_log
                (table_name, record_uuid, field_name, old_value, new_value, change_source, changed_by)
            VALUES
                ('work_order_items', :uuid, 'display_name', :old, :new, 'manual', :who)
        """), {"uuid": item_uuid, "old": old_name, "new": body.display_name, "who": user["email"]})

    # Log category change if provided and different
    if body.category and old_category != body.category:
        db.execute(text("""
            INSERT INTO change_log
                (table_name, record_uuid, field_name, old_value, new_value, change_source, changed_by)
            VALUES
                ('work_order_items', :uuid, 'category', :old, :new, 'manual', :who)
        """), {"uuid": item_uuid, "old": old_category, "new": body.category, "who": user["email"]})

    # Update the item — set display_name_auto = FALSE to protect from future sync overwrites
    update_params = {
        "uuid": item_uuid,
        "display_name": body.display_name,
        "display_name_auto": False,
    }

    if body.category:
        db.execute(text("""
            UPDATE work_order_items
            SET display_name = :display_name,
                display_name_auto = :display_name_auto,
                category = :category
            WHERE item_uuid = :uuid
        """), {**update_params, "category": body.category})
    else:
        db.execute(text("""
            UPDATE work_order_items
            SET display_name = :display_name,
                display_name_auto = :display_name_auto
            WHERE item_uuid = :uuid
        """), update_params)

    db.commit()
    return {"message": "Display name updated.", "item_uuid": item_uuid}


@router.get("/review")
def get_review_queue(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Returns items flagged for manual display name review.
    These are items the auto-mapping could not confidently label.
    Staff can use this list to work through corrections.
    """
    rows = db.execute(text("""
        SELECT
            woi.item_uuid,
            woi.name_raw,
            woi.display_name,
            woi.category,
            wo.job_number,
            wo.client_name,
            wo.job_address
        FROM work_order_items woi
        INNER JOIN work_orders wo ON woi.job_uuid = wo.job_uuid
        WHERE woi.display_name_auto = FALSE
          AND woi.active = 1
        ORDER BY wo.job_number, woi.sort_order
        LIMIT :limit OFFSET :offset
    """), {"limit": limit, "offset": offset}).mappings().all()

    return {
        "count": len(rows),
        "items": [dict(r) for r in rows]
    }
