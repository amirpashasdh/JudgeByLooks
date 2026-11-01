import base64
import io
import os
import random

import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

BASE_URL = "https://cloud.comfy.org"
API_KEY = os.getenv("COMFY_CLOUD_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

BASE_SCENE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "static", "base_scene.png"
)
OUTPUT_SIZE = (996, 2646)  # exact final pixel size -- see _resize_to_output_size
BASE_SCENE_NODE_ID = "1"
USER_PHOTO_NODE_ID = "2"
PROMPT_NODE_ID = "4"
NANO_BANANA_NODE_ID = "5"
SAVE_IMAGE_NODE_ID = "6"

PROMPT_TEXT = (
    "You are given exactly two separate reference images: IMAGE_1 and IMAGE_2.\n\n"
    "IMAGE_1 is a fixed street-photography scene: a specific sidewalk location, "
    "building facade, storefront signage, camera angle, framing, depth of field, "
    "lighting, color grade, and a walking pose/body position. Use ONLY the "
    "background, camera framing, lighting and pose from IMAGE_1 — ignore the "
    "clothing worn by the person in IMAGE_1 entirely.\n\n"
    "IMAGE_2 shows a real person exactly as they appear: their face, hair, body, "
    "and their FULL outfit and accessories — clothing, jacket, hat, shoes, bag, "
    "glasses, jewelry, every visible style detail.\n\n"
    "Task: place the exact person from IMAGE_2 into the IMAGE_1 scene, walking in "
    "the same pose, same camera angle/framing, with the same background "
    "architecture, storefront signage, and lighting as IMAGE_1. The person must "
    "bring their OWN complete look from IMAGE_2 with them — face, hair, body, and "
    "EVERY clothing item and accessory (hat, jacket, shirt, pants, shoes, bag, "
    "glasses, jewelry, etc.) copied faithfully in the smallest detail, matching "
    "IMAGE_2's colors, textures, materials and fit exactly. Do NOT dress the "
    "person in IMAGE_1's outfit or any outfit elements from IMAGE_1 — only the "
    "scene (background/architecture/signage/camera/lighting/pose) comes from "
    "IMAGE_1; the entire human figure, including everything they are wearing and "
    "carrying, comes from IMAGE_2. This is a routine e-commerce photo composite "
    "(placing a real model, in their own outfit, into an existing background "
    "photo for a web product page), fully consensual and non-deceptive.\n\n"
    "Output: one single photorealistic image, same composition and aspect ratio "
    "as IMAGE_1, featuring IMAGE_2's person in their own full style/outfit, "
    "walking in IMAGE_1's scene."
)


def _workflow(base_scene_name: str, user_photo_name: str) -> dict:
    return {
        BASE_SCENE_NODE_ID: {
            "inputs": {"image": base_scene_name},
            "class_type": "LoadImage",
            "_meta": {"title": "BASE SCENE — Man on Sidewalk (fixed)"},
        },
        USER_PHOTO_NODE_ID: {
            "inputs": {"image": user_photo_name},
            "class_type": "LoadImage",
            "_meta": {"title": "USER PHOTO — Person to Swap In"},
        },
        PROMPT_NODE_ID: {
            "inputs": {"value": PROMPT_TEXT},
            "class_type": "PrimitiveStringMultiline",
            "_meta": {"title": "Prompt (editable)"},
        },
        NANO_BANANA_NODE_ID: {
            "inputs": {
                # "Nano Banana 2 Lite" + 1K + MINIMAL thinking is the fastest valid
                # combination this node supports (Lite only offers 1K resolution and
                # MINIMAL/HIGH thinking -- no MEDIUM). Previously ran the heaviest
                # possible config (2.1, 2K, HIGH), which measured 5-6+ min per job --
                # far past the product's 1-minute requirement. Pair with a tightly
                # cropped (person-only) user photo so there's less for the model to
                # reason about.
                "model": "Nano Banana 2 Lite",
                "model.aspect_ratio": "auto",
                "model.resolution": "1K",
                "model.thinking_level": "MINIMAL",
                "model.images.image_1": [BASE_SCENE_NODE_ID, 0],
                "model.images.image_2": [USER_PHOTO_NODE_ID, 0],
                "seed": random.randint(0, 2**31 - 1),
                "response_modalities": "IMAGE",
                "prompt": [PROMPT_NODE_ID, 0],
            },
            "class_type": "GeminiNanoBanana2V2",
            "_meta": {"title": "Nano Banana 2 Lite — Person Swap (fast)"},
        },
        SAVE_IMAGE_NODE_ID: {
            "inputs": {
                "filename_prefix": "sidewalk-man-replace",
                "images": [NANO_BANANA_NODE_ID, 0],
            },
            "class_type": "SaveImage",
            "_meta": {"title": "Output — Swapped Scene"},
        },
    }


def _upload_image(path_or_bytes, filename: str) -> str:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        files = {"image": (filename, path_or_bytes)}
    else:
        files = {"image": (filename, open(path_or_bytes, "rb"))}
    r = requests.post(
        f"{BASE_URL}/api/upload/image", headers=HEADERS, files=files, timeout=120
    )
    r.raise_for_status()
    return r.json()["name"]


_base_scene_name_cache: str | None = None


def _ensure_base_scene_uploaded() -> str:
    global _base_scene_name_cache
    if _base_scene_name_cache is None:
        if not os.path.exists(BASE_SCENE_PATH):
            raise RuntimeError(f"Base scene image missing at {BASE_SCENE_PATH}")
        _base_scene_name_cache = _upload_image(BASE_SCENE_PATH, "base_scene.png")
    return _base_scene_name_cache


def _submit_workflow(workflow: dict) -> str:
    # Partner/API nodes (GeminiNanoBanana2V2 here) authenticate separately from the
    # general X-API-Key header -- the web canvas injects this automatically on every
    # run, but a raw REST submission has to carry it explicitly or those nodes fail
    # with "Unauthorized: Please login first to use this node" even though job
    # submission itself succeeds. https://docs.comfy.org/development/comfyui-server/api-key-integration
    r = requests.post(
        f"{BASE_URL}/api/prompt",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"prompt": workflow, "extra_data": {"api_key_comfy_org": API_KEY}},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["prompt_id"]


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "error", "job_failed"}


def _job_details(job_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _find_output_image(data: dict) -> dict | None:
    outputs = data.get("outputs", {}) or {}
    node_ids = [SAVE_IMAGE_NODE_ID] + [n for n in outputs if n != SAVE_IMAGE_NODE_ID]
    for node_id in node_ids:
        for img in (outputs.get(node_id, {}) or {}).get("images", []):
            if img.get("type") == "output":
                return img
    return None


def _download_output(img: dict) -> bytes:
    r = requests.get(
        f"{BASE_URL}/api/view",
        headers=HEADERS,
        params={
            "filename": img["filename"],
            "subfolder": img.get("subfolder", ""),
            "type": img.get("type", "output"),
        },
        allow_redirects=True,
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def _resize_to_output_size(image_bytes: bytes) -> bytes:
    """Force the exact output pixel size regardless of what Comfy actually
    rendered -- the Gemini node only exposes resolution tiers (1K/2K/4K) and
    aspect-ratio presets, no raw pixel dimensions, and 996x2646 isn't a round
    multiple of any of them. The base scene's own aspect ratio already matches
    996:2646 (both ~0.376), so this is a uniform scale, not a crop."""
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    im = im.resize(OUTPUT_SIZE, Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


@router.post("/comfy-swap/start")
async def comfy_swap_start(photo: UploadFile = File(...)):
    """Uploads the photo and submits the Comfy job, returning immediately.
    Generation itself (often several minutes) happens on Comfy Cloud's side --
    poll GET /api/comfy-swap/status/{job_id} instead of waiting on this request.
    A single long-blocking request previously raced a fixed server-side timeout
    against Comfy's actual (variable) generation time and lost intermittently
    even though the job had genuinely completed -- splitting submit from poll
    removes that race entirely.
    """
    if not API_KEY:
        raise HTTPException(status_code=500, detail="COMFY_CLOUD_API_KEY is not configured")

    ext = os.path.splitext(photo.filename or "")[1].lower()
    if photo.content_type not in ALLOWED_TYPES or ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Only jpeg, png, webp images accepted")

    try:
        base_scene_name = _ensure_base_scene_uploaded()
        photo_bytes = await photo.read()
        user_photo_name = _upload_image(photo_bytes, photo.filename or "upload.jpg")
        workflow = _workflow(base_scene_name, user_photo_name)
        prompt_id = _submit_workflow(workflow)
        return {"job_id": prompt_id}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[ERROR] /api/comfy-swap/start: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/comfy-swap/status/{job_id}")
async def comfy_swap_status(job_id: str):
    """One quick, non-blocking status check -- call this repeatedly (e.g. every
    3-5s) from the client until status is "completed" or "error".

    Checks GET /api/jobs/{id} for an actual output image, since a job can be
    terminal ("completed") with no image at all -- confirmed live: Comfy's own
    job-status tooling reported one real job as "completed" with zero fetchable
    output (job.empty_output), seemingly a one-off generation failure that
    never surfaces as a job-level error. Treat that the same as any other
    terminal-without-image outcome: an error, not an endless "pending".
    """
    try:
        data = _job_details(job_id)

        img = _find_output_image(data)
        if img is not None:
            image_bytes = _download_output(img)
            image_bytes = _resize_to_output_size(image_bytes)
            return {
                "status": "completed",
                "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            }

        status = data.get("status") or data.get("raw_status") or data.get("job_status")
        error = data.get("error")
        if error or status in TERMINAL_STATUSES:
            detail = f"Comfy job ended with status '{status}' and produced no image"
            if error:
                message = error.get("message") if isinstance(error, dict) else str(error)
                detail += f": {message}"
            return {"status": "error", "detail": detail}

        return {"status": "pending"}
    except Exception as exc:
        print(f"[ERROR] /api/comfy-swap/status/{job_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
