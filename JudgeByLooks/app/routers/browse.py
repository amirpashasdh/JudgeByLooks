from fastapi import APIRouter, HTTPException
from app.models import BrowseResponse, Product
from app.db import get_db
from app.services.extended import get_extended

router = APIRouter()


@router.get("/browse/{session_id}/{person_id}", response_model=BrowseResponse)
def get_browse(session_id: str, person_id: int):
    db = get_db()
    try:
        items = get_extended(person_id, session_id, db)
    except LookupError:
        raise HTTPException(status_code=404, detail=f"person_id={person_id} not found")
    finally:
        db.close()

    products = [Product(**item) for item in items]
    print(f"[GET  /api/browse] {session_id} → {len(products)} products")
    return BrowseResponse(session_id=session_id, person_id=person_id, products=products)
