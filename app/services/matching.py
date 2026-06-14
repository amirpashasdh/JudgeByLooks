import os
import sys
import json
import sqlite3
from datetime import datetime

STYLE_KEYWORDS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "style-keywords")
)
FASHION_DB = os.path.join(STYLE_KEYWORDS_DIR, "fashion.db")
KEYWORDS_DB = os.path.join(STYLE_KEYWORDS_DIR, "keywords.db")


def _ensure_path():
    if STYLE_KEYWORDS_DIR not in sys.path:
        sys.path.insert(0, STYLE_KEYWORDS_DIR)


def run_matching(person_id: int, run_folder: str) -> list[dict]:
    _ensure_path()

    from match import (
        KEYWORDS, cosine, row_to_vec, diverse_top, top_keywords
    )

    # load person vector from keywords.db
    conn = sqlite3.connect(KEYWORDS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM person_analysis WHERE id = ?", (person_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(f"person_analysis id={person_id} not found")
    person = dict(row)
    person_vec = row_to_vec(person)

    # load products from fashion.db
    conn = sqlite3.connect(FASHION_DB)
    conn.row_factory = sqlite3.Row
    products = [dict(r) for r in conn.execute("SELECT * FROM products").fetchall()]
    conn.close()

    if not products:
        return []

    ranked = sorted(
        [(cosine(person_vec, row_to_vec(p)), p) for p in products],
        key=lambda x: -x[0],
    )
    results = diverse_top(ranked, 10)

    recs = []
    for i, (score, p) in enumerate(results):
        kws = top_keywords(row_to_vec(p), 5)
        recs.append({
            "rank": i + 1,
            "score": round(score, 4),
            "product_id": p.get("id"),
            "brand": p.get("brand") or "",
            "name": p.get("name") or "",
            "category": p.get("category") or "",
            "price": p.get("price") or 0.0,
            "currency": p.get("currency") or "",
            "price_tier": p.get("price_tier") or "",
            "product_url": p.get("product_url") or "",
            "image_url": p.get("image_url") or "",
            "top_keywords": kws,
        })

    # save to recommendations table in fashion.db
    now = datetime.now().isoformat()
    conn = sqlite3.connect(FASHION_DB)
    conn.execute("DELETE FROM recommendations WHERE person_id = ?", (person_id,))
    for r in recs:
        conn.execute(
            """INSERT INTO recommendations
               (session_id, person_id, product_id, rank, score, mode, created_at)
               VALUES (?, ?, ?, ?, ?, 'diverse', ?)""",
            ("", person_id, r["product_id"], r["rank"], r["score"], now),
        )
    conn.commit()
    conn.close()

    return recs
