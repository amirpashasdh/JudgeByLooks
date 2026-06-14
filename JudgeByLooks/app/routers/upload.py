import os
import time
import tempfile
from fastapi import APIRouter, UploadFile, File, Query, HTTPException

from app.models import UploadResponse
from app.services.session import generate_session_id
from app.services import analysis as analysis_svc
from app.services import matching as matching_svc

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTS  = {".jpg", ".jpeg", ".png", ".webp"}


@router.post("/upload", response_model=UploadResponse)
async def upload_photo(
    photo: UploadFile = File(...),
    taxonomy_mode: str         = Query(default="both",      description="keywords | archetypes | both"),
    price_tier_strategy: str   = Query(default="match",     description="match | above | below | mixed | ignore"),
    tier_shift: int            = Query(default=0,           description="tiers to shift for above/below strategy"),
    retrieval_mode: str        = Query(default="gap_based", description="similarity | gap_based"),
    silhouette_adjustment: bool = Query(default=True,       description="include silhouette reasoning in recommendations"),
    gender: str                = Query(default="auto",      description="male | female | unisex | auto (inferred from photo)"),
):
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

        result = analysis_svc.run_analysis(tmp_path, session_id, taxonomy_mode=taxonomy_mode)
        person_id  = result["person_id"]
        brief      = result["brief"]
        run_folder = result["run_folder"]

        # resolve gender: use override if provided, else take from brief
        resolved_gender = gender if gender != "auto" else brief.get("gender", "unisex")

        params = {
            "session_id":            session_id,
            "taxonomy_mode":         taxonomy_mode,
            "price_tier_strategy":   price_tier_strategy,
            "tier_shift":            tier_shift,
            "retrieval_mode":        retrieval_mode,
            "silhouette_adjustment": silhouette_adjustment,
            "gender":                resolved_gender,
        }
        matching_svc.run_matching(person_id, run_folder, brief=brief, params=params)

        keywords_filtered = {k: v for k, v in brief.get("style_scores", {}).get("keywords", {}).items() if v > 0.3}

        elapsed = time.time() - t0
        conf = brief.get("overall_confidence", 0.0)
        print(f"[POST /api/upload] {session_id} → person_id={person_id} conf={conf:.2f} mode={retrieval_mode} ({elapsed:.1f}s)")

        return UploadResponse(
            session_id=session_id,
            person_id=person_id,
            run_folder=run_folder,
            keywords=keywords_filtered,
        )
    except Exception as exc:
        print(f"[ERROR] /api/upload: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
