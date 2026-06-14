from fastapi import APIRouter, HTTPException
from app.models import RecommendationsResponse, Product
from app.db import get_db

router = APIRouter()


@router.get("/recommendations/{session_id}/{person_id}", response_model=RecommendationsResponse)
def get_recommendations(session_id: str, person_id: int):
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT r.rank, r.score, r.mode,
                   p.id AS product_id, p.brand, p.name, p.category,
                   p.price, p.currency, p.price_tier,
                   p.product_url, p.image_url
            FROM recommendations r
            JOIN products p ON r.product_id = p.id
            WHERE r.person_id = ?
            ORDER BY r.rank ASC
            LIMIT 10
            """,
            (person_id,),
        ).fetchall()
    finally:
        db.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No recommendations found")

    mode = rows[0]["mode"] if rows else "diverse"
    products = [
        Product(
            product_id=r["product_id"],
            brand=r["brand"] or "",
            name=r["name"] or "",
            category=r["category"] or "",
            price=r["price"] or 0.0,
            currency=r["currency"] or "",
            price_tier=r["price_tier"] or "",
            similarity_score=r["score"],
            product_url=r["product_url"] or "",
            image_url=r["image_url"] or "",
            matched_keywords={},
            rank=r["rank"],
        )
        for r in rows
    ]

    print(f"[GET  /api/recommendations] {session_id} → {len(products)} products")
    return RecommendationsResponse(
        session_id=session_id,
        person_id=person_id,
        products=products,
        ranking_mode=mode,
    )
