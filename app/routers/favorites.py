from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.models import FavoritesRequest, FavoritesResponse
from app.db import get_db

router = APIRouter()


@router.post("/favorites", response_model=FavoritesResponse)
def post_favorites(req: FavoritesRequest):
    if len(req.product_ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 favorites allowed")

    db = get_db()
    try:
        db.execute(
            "DELETE FROM favorites WHERE session_id = ?", (req.session_id,)
        )
        now = datetime.now(timezone.utc).isoformat()
        for pid in req.product_ids:
            db.execute(
                """INSERT OR IGNORE INTO favorites (session_id, person_id, product_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                (req.session_id, req.person_id, pid, now),
            )
        db.commit()
    finally:
        db.close()

    saved = len(req.product_ids)
    print(f"[POST /api/favorites] {req.session_id} → {saved} saved")
    return FavoritesResponse(success=True, saved=saved, message="favorites saved")
