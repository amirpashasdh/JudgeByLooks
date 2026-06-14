import json
import os
import sqlite3
import sys

import numpy as np

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)
if STYLE_KEYWORDS_DIR not in sys.path:
    sys.path.insert(0, STYLE_KEYWORDS_DIR)

from match import KEYWORDS  # canonical 320-keyword list


def _gender_compat(product_gender: str, person_gender: str) -> bool:
    pg = (product_gender or "unisex").lower()
    if pg == "unisex" or person_gender in ("unisex", "", None):
        return True
    return pg == person_gender


def get_extended(
    person_id: int,
    session_id: str,
    db: sqlite3.Connection,
) -> list[dict]:
    from app.db import KEYWORDS_DB_PATH

    # ── Load person ───────────────────────────────────────────────────────
    kconn = sqlite3.connect(KEYWORDS_DB_PATH)
    kconn.row_factory = sqlite3.Row
    row = kconn.execute(
        "SELECT * FROM person_analysis WHERE id = ?", (person_id,)
    ).fetchone()
    kconn.close()
    if row is None:
        raise LookupError(f"person_id={person_id} not found")

    person = dict(row)

    # Extract gender — stored as column (if present) or from raw_response JSON
    person_gender = (person.get("gender") or "").lower()
    if not person_gender:
        raw = person.get("raw_response") or person.get("brief_json") or ""
        if raw:
            try:
                person_gender = json.loads(raw).get("gender", "unisex")
            except Exception:
                person_gender = "unisex"
        else:
            person_gender = "unisex"

    person_vec = np.array([float(person.get(k) or 0.0) for k in KEYWORDS], dtype=np.float32)

    # ── Load products (gender pre-filtered in SQL when possible) ─────────
    if person_gender not in ("unisex", "", None):
        rows = db.execute(
            "SELECT * FROM products WHERE gender = ? OR gender = 'unisex' OR gender IS NULL OR gender = ''",
            (person_gender,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM products").fetchall()

    products = [dict(r) for r in rows]

    if not products:
        return []

    # ── Vectorized cosine similarity ──────────────────────────────────────
    mat = np.array(
        [[float(p.get(k) or 0.0) for k in KEYWORDS] for p in products],
        dtype=np.float32,
    )

    p_norm = np.linalg.norm(person_vec)
    if p_norm == 0:
        p_norm = 1.0
    pv = person_vec / p_norm

    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat_n = mat / norms

    scores = mat_n @ pv  # (N,) cosine similarity

    # ── Sort + category diversity (max 6 per category) ───────────────────
    order = np.argsort(-scores)
    category_counts: dict[str, int] = {}
    diverse: list[tuple[float, dict, np.ndarray]] = []

    for idx in order:
        p = products[idx]
        cat = p.get("category") or "unknown"
        if category_counts.get(cat, 0) >= 6:
            continue
        category_counts[cat] = category_counts.get(cat, 0) + 1
        diverse.append((float(scores[idx]), p, mat[idx]))
        if len(diverse) >= 50:
            break

    # ── Build response ────────────────────────────────────────────────────
    results = []
    for rank, (score, p, p_vec_arr) in enumerate(diverse, 1):
        contrib = (person_vec * p_vec_arr).tolist()
        top5_idx = sorted(range(len(KEYWORDS)), key=lambda i: -contrib[i])[:5]
        top5 = {KEYWORDS[i]: round(contrib[i], 5) for i in top5_idx if contrib[i] > 0}

        results.append({
            "product_id":       p.get("id") or "",
            "brand":            p.get("brand") or "",
            "name":             p.get("name") or "",
            "category":         p.get("category") or "",
            "price":            p.get("price") or 0.0,
            "currency":         p.get("currency") or "",
            "price_tier":       p.get("price_tier") or "",
            "similarity_score": round(score, 4),
            "product_url":      p.get("product_url") or "",
            "image_url":        p.get("image_url") or "",
            "matched_keywords": top5,
            "rank":             rank,
        })

    return results
