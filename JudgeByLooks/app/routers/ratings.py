from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.models import RatingRequest, RatingResponse
from app.db import get_db

router = APIRouter()


def _save_rating(db, req: RatingRequest) -> RatingResponse:
    if not (1 <= req.contextual_fit <= 5 and 1 <= req.general_taste <= 5):
        raise ValueError("Ratings must be between 1 and 5")

    existing = db.execute(
        "SELECT id FROM ratings WHERE session_id = ? AND product_id = ?",
        (req.session_id, req.product_id),
    ).fetchone()
    if existing:
        return RatingResponse(success=True, message="already rated")

    db.execute(
        """INSERT INTO ratings (session_id, person_id, product_id, contextual_fit, general_taste, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (req.session_id, req.person_id, req.product_id,
         req.contextual_fit, req.general_taste,
         datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return RatingResponse(success=True, message="saved")


@router.post("/ratings", response_model=RatingResponse)
def post_rating(req: RatingRequest):
    if not (1 <= req.contextual_fit <= 5 and 1 <= req.general_taste <= 5):
        raise HTTPException(status_code=400, detail="Ratings must be between 1 and 5")

    db = get_db()
    try:
        result = _save_rating(db, req)
        print(f"[POST /api/ratings] {req.session_id} → {result.message}")
        return result
    finally:
        db.close()


@router.post("/ratings/batch")
def post_ratings_batch(reqs: list[RatingRequest]):
    if len(reqs) > 10:
        reqs = reqs[:10]

    db = get_db()
    success_count = already_rated = errors = 0
    results = []

    for req in reqs:
        try:
            r = _save_rating(db, req)
            if r.message == "already rated":
                already_rated += 1
            else:
                success_count += 1
            results.append(r)
        except Exception as exc:
            errors += 1
            results.append(RatingResponse(success=False, message=str(exc)))

    db.close()
    print(f"[POST /api/ratings/batch] {reqs[0].session_id if reqs else ''} → {success_count + already_rated}/{len(reqs)} saved")
    return {
        "success_count": success_count,
        "already_rated": already_rated,
        "errors": errors,
        "results": results,
    }
