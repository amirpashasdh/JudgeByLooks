import json
import os
import sqlite3
import tempfile
import time

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.services import analysis as analysis_svc
from app.services import matching as matching_svc
from app.services.session import generate_session_id

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

RECOMMENDATION_COUNT = 10
KEYWORD_TAG_COUNT = 8
SENTENCE_KEYWORD_COUNT = 4

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)
FASHION_DB = os.path.join(STYLE_KEYWORDS_DIR, "fashion.db")

# Bridges /style-read -> /style-recommendations: the brief/run_folder a person_id
# needs for matching, stashed in-process between the two calls. Single-use by
# design (popped on read) -- a second /style-recommendations call for the same
# person_id means either a genuine double-call or the process restarted and lost
# it, and both should 404 rather than silently matching against nothing.
_pending_briefs: dict[int, dict] = {}


def _top_keyword_tags(keywords: dict, limit: int) -> list[str]:
    top = sorted(
        ((k, v) for k, v in keywords.items() if v and v > 0.3),
        key=lambda kv: -kv[1],
    )[:limit]
    return [k.replace("_", " ") for k, _ in top]


def _join_labels(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f" and {labels[-1]}"


def _style_reading(tags: list[str]) -> str:
    primary = tags[:SENTENCE_KEYWORD_COUNT]
    if not primary:
        return "We couldn't get a confident read on your style from this photo."

    secondary = tags[SENTENCE_KEYWORD_COUNT : SENTENCE_KEYWORD_COUNT * 2]
    sentence = f"Your style reads as {_join_labels(primary)}."
    if secondary:
        sentence += f" It also carries notes of {_join_labels(secondary)}."
    return sentence


def _descriptions_for(product_ids: list[str]) -> dict[str, str]:
    # The scraped catalog has no real product descriptions (empty for every row) --
    # return "" rather than synthesizing a brand/category breadcrumb; the frontend
    # omits the description line when it's empty.
    if not product_ids:
        return {}
    conn = sqlite3.connect(FASHION_DB)
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in product_ids)
    rows = conn.execute(
        f"SELECT id, description FROM products WHERE id IN ({placeholders})",
        product_ids,
    ).fetchall()
    conn.close()
    return {r["id"]: (r["description"] or "") for r in rows}


@router.post("/style-read")
async def style_read(photo: UploadFile = File(...)):
    """Stage 1 of 2: Claude analysis only. Returns the style reading + keywords
    immediately so the frontend can show them without waiting on matching too.
    Call /api/style-recommendations next with the returned person_id."""
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
        keywords = result["keywords"]

        _pending_briefs[person_id] = {
            "brief": brief,
            "run_folder": result["run_folder"],
            "session_id": session_id,
        }

        tags = _top_keyword_tags(keywords, limit=KEYWORD_TAG_COUNT)
        # Prefer Claude's own written interpretation of the outfit over the
        # templated keyword sentence -- only fall back to the template if the
        # model didn't produce one (e.g. the low-confidence fallback brief).
        style_reading = brief.get("interpretation") or _style_reading(tags)

        elapsed = time.time() - t0
        print(f"[POST /api/style-read] {session_id} person_id={person_id} ({elapsed:.1f}s)")

        return {
            "session_id": session_id,
            "person_id": person_id,
            "style_reading": style_reading,
            "keywords": tags,
            # Full raw analysis JSON -- the frontend uses this purely as decorative
            # background texture, not for display/reading.
            "raw_brief": json.dumps(brief, indent=2),
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[ERROR] /api/style-read: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


class StyleRecommendationsRequest(BaseModel):
    person_id: int


@router.post("/style-recommendations")
async def style_recommendations(body: StyleRecommendationsRequest):
    """Stage 2 of 2: matching only, keyed by the person_id from /api/style-read.
    person_id is single-use -- a second call with the same one 404s, since the
    pending brief it needs has already been consumed (or the process restarted
    and lost it)."""
    t0 = time.time()

    pending = _pending_briefs.pop(body.person_id, None)
    if pending is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No pending analysis for person_id={body.person_id} -- "
                "either already used, or the backend restarted since /api/style-read. "
                "Re-run /api/style-read."
            ),
        )

    try:
        brief = pending["brief"]
        run_folder = pending["run_folder"]

        params = {
            "session_id": pending["session_id"],
            "taxonomy_mode": "both",
            "price_tier_strategy": "match",
            "tier_shift": 0,
            "retrieval_mode": "gap_based",
            "silhouette_adjustment": True,
            "gender": brief.get("gender", "unisex"),
        }
        matches = matching_svc.run_matching(body.person_id, run_folder, brief=brief, params=params)
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
        print(f"[POST /api/style-recommendations] person_id={body.person_id} -> {len(recommendations)} items ({elapsed:.1f}s)")

        return {
            "person_id": body.person_id,
            "recommendations": recommendations,
        }
    except Exception as exc:
        print(f"[ERROR] /api/style-recommendations: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
