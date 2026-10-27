import os
import sqlite3
import tempfile
import time

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services import analysis as analysis_svc
from app.services import matching as matching_svc
from app.services.session import generate_session_id

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

RECOMMENDATION_COUNT = 6

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)
FASHION_DB = os.path.join(STYLE_KEYWORDS_DIR, "fashion.db")


def _style_reading(keywords: dict) -> str:
    top = sorted(
        ((k, v) for k, v in keywords.items() if v and v > 0.3),
        key=lambda kv: -kv[1],
    )[:4]
    if not top:
        return "We couldn't get a confident read on your style from this photo."
    labels = [k.replace("_", " ") for k, _ in top]
    if len(labels) == 1:
        joined = labels[0]
    else:
        joined = ", ".join(labels[:-1]) + f" and {labels[-1]}"
    return f"Your style reads as {joined}."


def _fallback_description(row: sqlite3.Row) -> str:
    # The scraped catalog has no real product descriptions (empty for every row) —
    # synthesize a short one so cards aren't blank until real copy is backfilled.
    parts = [p for p in (row["brand"], row["category"]) if p]
    price = row["price"]
    currency = row["currency"] or ""
    if price:
        parts.append(f"{currency}{price:g}")
    return " · ".join(parts)


def _descriptions_for(product_ids: list[str]) -> dict[str, str]:
    if not product_ids:
        return {}
    conn = sqlite3.connect(FASHION_DB)
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in product_ids)
    rows = conn.execute(
        f"SELECT id, brand, category, price, currency, description FROM products WHERE id IN ({placeholders})",
        product_ids,
    ).fetchall()
    conn.close()
    return {r["id"]: (r["description"] or _fallback_description(r)) for r in rows}


@router.post("/style-check")
async def style_check(photo: UploadFile = File(...)):
    t0 = time.time()

    ext = os.path.splitext(photo.filename or "")[1].lower()
    if photo.content_type not in ALLOWED_TYPES or ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Only jpeg, png, webp images accepted")

    session_id = generate_session_id()
    tmp_path = None

    try:
        suffix = ext or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await photo.read())
            tmp_path = tmp.name

        result = analysis_svc.run_analysis(tmp_path, session_id, taxonomy_mode="both")
        person_id = result["person_id"]
        brief = result["brief"]
        run_folder = result["run_folder"]
        keywords = result["keywords"]

        params = {
            "session_id": session_id,
            "taxonomy_mode": "both",
            "price_tier_strategy": "match",
            "tier_shift": 0,
            "retrieval_mode": "gap_based",
            "silhouette_adjustment": True,
            "gender": brief.get("gender", "unisex"),
        }
        matches = matching_svc.run_matching(person_id, run_folder, brief=brief, params=params)
        top_matches = matches[:RECOMMENDATION_COUNT]

        descriptions = _descriptions_for([m["product_id"] for m in top_matches])

        recommendations = [
            {
                "product_id": m["product_id"],
                "brand": m["brand"],
                "name": m["name"],
                "description": descriptions.get(m["product_id"], ""),
                "image_url": m["image_url"],
                "product_url": m["product_url"],
                "price": m["price"],
                "currency": m["currency"],
            }
            for m in top_matches
        ]

        elapsed = time.time() - t0
        print(f"[POST /api/style-check] {session_id} -> {len(recommendations)} items ({elapsed:.1f}s)")

        return {
            "session_id": session_id,
            "person_id": person_id,
            "style_reading": _style_reading(keywords),
            "recommendations": recommendations,
        }
    except Exception as exc:
        print(f"[ERROR] /api/style-check: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
