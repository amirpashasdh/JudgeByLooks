import os
import sys
import json
import sqlite3
from datetime import datetime

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)
FASHION_DB  = os.path.join(STYLE_KEYWORDS_DIR, "fashion.db")
KEYWORDS_DB = os.path.join(STYLE_KEYWORDS_DIR, "keywords.db")

TIER_ORDER = ["budget", "mid", "premium", "luxury"]


def _ensure_path():
    if STYLE_KEYWORDS_DIR not in sys.path:
        sys.path.insert(0, STYLE_KEYWORDS_DIR)


def _gender_match(product: dict, person_gender: str) -> bool:
    pg = (product.get("gender") or "unisex").lower()
    if pg == "unisex" or person_gender in ("unisex", "", None):
        return True
    return pg == person_gender


def _tier_targets(inferred_tier: str, strategy: str = "match") -> list[str]:
    if strategy == "ignore" or inferred_tier not in TIER_ORDER:
        return TIER_ORDER[:]
    idx = TIER_ORDER.index(inferred_tier)
    if strategy == "match":
        return [inferred_tier]
    if strategy == "mixed":
        return [TIER_ORDER[idx]] + ([TIER_ORDER[idx + 1]] if idx + 1 < len(TIER_ORDER) else [])
    return TIER_ORDER[:]


def _profile_cosine(rec_keywords: dict, product: dict, all_keywords: list) -> float:
    """Cosine similarity between a recommendation keyword profile and a product vector."""
    pv = [float(rec_keywords.get(k, 0.0)) for k in all_keywords]
    qv = [float(product.get(k) or 0.0) for k in all_keywords]
    dot = sum(a * b for a, b in zip(pv, qv))
    na  = sum(a * a for a in pv) ** 0.5
    nb  = sum(b * b for b in qv) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def run_matching(
    person_id: int,
    run_folder: str,
    brief: dict = None,
    params: dict = None,
) -> list[dict]:
    _ensure_path()
    if params is None:
        params = {}

    from match import KEYWORDS

    # ── Load person ───────────────────────────────────────────────────────
    conn = sqlite3.connect(KEYWORDS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM person_analysis WHERE id = ?", (person_id,)).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(f"person_analysis id={person_id} not found")

    # ── Load products ─────────────────────────────────────────────────────
    conn = sqlite3.connect(FASHION_DB)
    conn.row_factory = sqlite3.Row
    products = [dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
    conn.close()

    if not products:
        return []

    # ── Filters ───────────────────────────────────────────────────────────
    person_gender  = (brief or {}).get("gender", "unisex")
    inferred_tier  = (brief or {}).get("price_tier", {}).get("inferred_tier", "mid")
    tier_targets   = _tier_targets(inferred_tier, params.get("price_tier_strategy", "match"))

    def _eligible(p: dict, relax_tier: bool = False) -> bool:
        if not _gender_match(p, person_gender):
            return False
        if not relax_tier and p.get("price_tier") not in tier_targets:
            return False
        return True

    eligible = [p for p in products if _eligible(p)]

    # ── Per-recommendation best-product lookup ────────────────────────────
    recommendations = (brief or {}).get("recommendations", [])

    final = []
    used_ids: set = set()

    # map analyzer slots to product item_types
    SLOT_TO_ITEM_TYPES = {
        "top":       {"top"},
        "bottom":    {"trousers", "jeans", "skirt"},
        "dress":     {"dress"},
        "jacket":    {"jacket", "outerwear"},
        "shoes":     {"shoes"},
        "accessory": {"accessory"},
        "other":     {"other", "top", "trousers", "jeans", "dress", "jacket", "outerwear", "accessory", "shoes"},
    }

    for rec in recommendations:
        if len(final) >= 10:
            break

        rec_keywords = rec.get("keywords", {})
        slot         = rec.get("slot", "other")
        reasoning    = rec.get("reasoning", "")

        allowed_types = SLOT_TO_ITEM_TYPES.get(slot, {slot})

        # score eligible products of the right item_type
        pool = eligible if eligible else products
        scored = []
        for p in pool:
            if p.get("id") in used_ids:
                continue
            if (p.get("item_type") or "other").lower() not in allowed_types:
                continue
            score = _profile_cosine(rec_keywords, p, KEYWORDS)
            scored.append((score, p))

        if not scored:
            continue

        scored.sort(key=lambda x: -x[0])
        best_score, best_product = scored[0]

        # skip if no meaningful match at all
        if best_score < 0.01:
            continue

        final.append({
            "rank":         len(final) + 1,
            "score":        round(best_score, 4),
            "product_id":   best_product.get("id"),
            "brand":        best_product.get("brand") or "",
            "name":         best_product.get("name") or "",
            "category":     best_product.get("category") or "",
            "price":        best_product.get("price") or 0.0,
            "currency":     best_product.get("currency") or "",
            "price_tier":   best_product.get("price_tier") or "",
            "product_url":  best_product.get("product_url") or "",
            "image_url":    best_product.get("image_url") or "",
            "slot":         slot,
            "slot_reasoning": reasoning,
            "retrieval_mode": "analyzer_led",
        })
        used_ids.add(best_product.get("id"))

    # ── Persist ───────────────────────────────────────────────────────────
    now        = datetime.now().isoformat()
    session_id = params.get("session_id", "")
    conn = sqlite3.connect(FASHION_DB)
    conn.execute("DELETE FROM recommendations WHERE person_id = ?", (person_id,))
    for r in final:
        conn.execute(
            """INSERT INTO recommendations
               (session_id, person_id, product_id, rank, score, mode, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, person_id, r["product_id"], r["rank"], r["score"], "analyzer_led", now),
        )
    conn.commit()
    conn.close()

    try:
        from storage import log_experiment
        log_experiment(person_id, session_id, {**params, "retrieval_mode": "analyzer_led"},
                       [r["product_id"] for r in final])
    except Exception:
        pass

    return final
