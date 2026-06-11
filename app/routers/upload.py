import os
import time
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models import UploadResponse
from app.services.session import generate_session_id
from app.services import analysis as analysis_svc
from app.services import matching as matching_svc

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@router.post("/upload", response_model=UploadResponse)
async def upload_photo(photo: UploadFile = File(...)):
    t0 = time.time()

    ext = os.path.splitext(photo.filename or "")[1].lower()
    if photo.content_type not in ALLOWED_TYPES or ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Only jpeg, png, webp images accepted")

    session_id = generate_session_id()

    try:
        suffix = ext or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await photo.read())
            tmp_path = tmp.name

        result = analysis_svc.run_analysis(tmp_path, session_id)
        person_id = result["person_id"]
        keywords_full = result["keywords"]
        run_folder = result["run_folder"]

        matching_svc.run_matching(person_id, run_folder)

        keywords_filtered = {k: v for k, v in keywords_full.items() if v > 0.3}

        elapsed = time.time() - t0
        print(f"[POST /api/upload] {session_id} → person_id={person_id} ({elapsed:.1f}s)")

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
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
