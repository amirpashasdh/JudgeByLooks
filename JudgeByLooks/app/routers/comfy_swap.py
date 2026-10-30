import os
import random
import time

import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

BASE_URL = "https://cloud.comfy.org"
API_KEY = os.getenv("COMFY_CLOUD_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

BASE_SCENE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "static", "base_scene.png"
)
BASE_SCENE_NODE_ID = "1"
USER_PHOTO_NODE_ID = "2"
PROMPT_NODE_ID = "4"
NANO_BANANA_NODE_ID = "5"
SAVE_IMAGE_NODE_ID = "6"
JOB_TIMEOUT_S = 180
POLL_JOB_S = 3

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
                "model": "Gemini Nano Banana 2.1",
                "model.aspect_ratio": "auto",
                "model.resolution": "2K",
                "model.thinking_level": "HIGH",
                "model.images.image_1": [BASE_SCENE_NODE_ID, 0],
                "model.images.image_2": [USER_PHOTO_NODE_ID, 0],
                "seed": random.randint(0, 2**31 - 1),
                "response_modalities": "IMAGE",
                "prompt": [PROMPT_NODE_ID, 0],
            },
            "class_type": "GeminiNanoBanana2V2",
            "_meta": {"title": "Nano Banana 2.1 — Person Swap"},
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
    r = requests.post(
        f"{BASE_URL}/api/prompt",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"prompt": workflow},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["prompt_id"]


def _wait_for_job(prompt_id: str) -> str:
    deadline = time.time() + JOB_TIMEOUT_S
    while time.time() < deadline:
        r = requests.get(
            f"{BASE_URL}/api/job/{prompt_id}/status", headers=HEADERS, timeout=30
        )
        r.raise_for_status()
        status = r.json().get("status")
        if status in ("completed", "failed", "cancelled"):
            return status
        time.sleep(POLL_JOB_S)
    return "timeout"


def _job_output_image(prompt_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/api/jobs/{prompt_id}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    outputs = data.get("outputs", {}) or {}
    node_ids = [SAVE_IMAGE_NODE_ID] + [n for n in outputs if n != SAVE_IMAGE_NODE_ID]
    for node_id in node_ids:
        for img in (outputs.get(node_id, {}) or {}).get("images", []):
            if img.get("type") == "output":
                return img
    raise RuntimeError("Job completed but produced no output image")


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


@router.post("/comfy-swap")
async def comfy_swap(photo: UploadFile = File(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="COMFY_CLOUD_API_KEY is not configured")

    ext = os.path.splitext(photo.filename or "")[1].lower()
    if photo.content_type not in ALLOWED_TYPES or ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Only jpeg, png, webp images accepted")

    t0 = time.time()
    try:
        base_scene_name = _ensure_base_scene_uploaded()

        photo_bytes = await photo.read()
        user_photo_name = _upload_image(photo_bytes, photo.filename or "upload.jpg")

        workflow = _workflow(base_scene_name, user_photo_name)
        prompt_id = _submit_workflow(workflow)

        status = _wait_for_job(prompt_id)
        if status != "completed":
            raise HTTPException(
                status_code=502,
                detail=f"Comfy job ended with status '{status}' (prompt_id={prompt_id})",
            )

        img = _job_output_image(prompt_id)
        image_bytes = _download_output(img)

        elapsed = time.time() - t0
        print(f"[POST /api/comfy-swap] prompt_id={prompt_id} -> {len(image_bytes)} bytes ({elapsed:.1f}s)")

        return Response(content=image_bytes, media_type="image/png")
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[ERROR] /api/comfy-swap: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
