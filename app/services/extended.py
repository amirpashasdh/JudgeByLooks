import math
import sqlite3

KEYWORDS = [
    "minimalist", "maximalist", "classic", "avant_garde", "streetwear",
    "bohemian", "preppy", "romantic", "edgy", "quiet_luxury", "coastal",
    "dark_academia", "sporty", "playful", "serious", "rebellious",
    "elegant", "laid_back", "bold", "understated", "whimsical",
    "polished", "raw", "neutral", "monochrome", "earth_tones", "pastel",
    "bold_colors", "black_forward", "white_forward", "jewel_tones",
    "multicolor", "loungewear", "casual", "smart_casual",
    "business_casual", "formal", "black_tie", "parisian", "scandinavian",
    "italian_luxury", "japanese_minimalist", "american_prep",
    "british_heritage", "nyc_streetwear", "californian", "fitted",
    "oversized", "structured", "flowy", "layered", "cropped",
    "voluminous", "everyday", "workwear", "going_out", "travel",
    "outdoor", "sport", "beach", "occasion", "sustainable",
    "investment_piece", "trend_driven", "heritage_craft", "luxury_status",
    "budget_conscious", "logo_forward", "logo_free", "size_inclusive",
    "gender_neutral", "performance_tech",
]

DIMENSION_WEIGHTS = {
    "aesthetic":  0.30,
    "mood":       0.15,
    "color":      0.20,
    "formality":  0.10,
    "cultural":   0.08,
    "silhouette": 0.12,
    "occasion":   0.03,
    "values":     0.02,
}

KEYWORD_DIMENSIONS = {
    "minimalist": "aesthetic", "maximalist": "aesthetic",
    "classic": "aesthetic", "avant_garde": "aesthetic",
    "streetwear": "aesthetic", "bohemian": "aesthetic",
    "preppy": "aesthetic", "romantic": "aesthetic",
    "edgy": "aesthetic", "quiet_luxury": "aesthetic",
    "coastal": "aesthetic", "dark_academia": "aesthetic",
    "sporty": "aesthetic",
    "playful": "mood", "serious": "mood", "rebellious": "mood",
    "elegant": "mood", "laid_back": "mood", "bold": "mood",
    "understated": "mood", "whimsical": "mood",
    "polished": "mood", "raw": "mood",
    "neutral": "color", "monochrome": "color",
    "earth_tones": "color", "pastel": "color",
    "bold_colors": "color", "black_forward": "color",
    "white_forward": "color", "jewel_tones": "color",
    "multicolor": "color",
    "loungewear": "formality", "casual": "formality",
    "smart_casual": "formality", "business_casual": "formality",
    "formal": "formality", "black_tie": "formality",
    "parisian": "cultural", "scandinavian": "cultural",
    "italian_luxury": "cultural", "japanese_minimalist": "cultural",
    "american_prep": "cultural", "british_heritage": "cultural",
    "nyc_streetwear": "cultural", "californian": "cultural",
    "fitted": "silhouette", "oversized": "silhouette",
    "structured": "silhouette", "flowy": "silhouette",
    "layered": "silhouette", "cropped": "silhouette",
    "voluminous": "silhouette",
    "everyday": "occasion", "workwear": "occasion",
    "going_out": "occasion", "travel": "occasion",
    "outdoor": "occasion", "sport": "occasion",
    "beach": "occasion", "occasion": "occasion",
    "sustainable": "values", "investment_piece": "values",
    "trend_driven": "values", "heritage_craft": "values",
    "luxury_status": "values", "budget_conscious": "values",
    "logo_forward": "values", "logo_free": "values",
    "size_inclusive": "values", "gender_neutral": "values",
    "performance_tech": "values",
}

# precompute per-keyword weight = dimension weight / count of keywords in dimension
_dim_counts: dict[str, int] = {}
for kw in KEYWORDS:
    dim = KEYWORD_DIMENSIONS.get(kw, "values")
    _dim_counts[dim] = _dim_counts.get(dim, 0) + 1

KEYWORD_WEIGHTS: dict[str, float] = {}
for kw in KEYWORDS:
    dim = KEYWORD_DIMENSIONS.get(kw, "values")
    KEYWORD_WEIGHTS[kw] = DIMENSION_WEIGHTS.get(dim, 0.0) / _dim_counts[dim]


def _weighted_cosine(person_vec: list[float], product_vec: list[float]) -> float:
    weights = [KEYWORD_WEIGHTS[k] for k in KEYWORDS]
    dot = sum(w * a * b for w, a, b in zip(weights, person_vec, product_vec))
    na = math.sqrt(sum(w * a * a for w, a in zip(weights, person_vec)))
    nb = math.sqrt(sum(w * b * b for w, b in zip(weights, product_vec)))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _row_to_vec(row: dict) -> list[float]:
    return [float(row.get(k) or 0.0) for k in KEYWORDS]


def get_extended(
    person_id: int,
    session_id: str,
    db: sqlite3.Connection,
) -> list[dict]:
    from app.db import KEYWORDS_DB_PATH

    # load person vector
    kconn = sqlite3.connect(KEYWORDS_DB_PATH)
    kconn.row_factory = sqlite3.Row
    row = kconn.execute(
        "SELECT * FROM person_analysis WHERE id = ?", (person_id,)
    ).fetchone()
    kconn.close()
    if row is None:
        raise LookupError(f"person_id={person_id} not found")
    person_vec = _row_to_vec(dict(row))

    # load products
    products = [
        dict(r) for r in db.execute("SELECT * FROM products").fetchall()
    ]

    # score all products
    scored = sorted(
        [(_weighted_cosine(person_vec, _row_to_vec(p)), p) for p in products],
        key=lambda x: -x[0],
    )

    # category diversity: max 6 per category
    category_counts: dict[str, int] = {}
    diverse: list[tuple[float, dict]] = []
    for score, p in scored:
        cat = p.get("category") or "unknown"
        if category_counts.get(cat, 0) >= 6:
            continue
        category_counts[cat] = category_counts.get(cat, 0) + 1
        diverse.append((score, p))
        if len(diverse) >= 50:
            break

    results = []
    for rank, (score, p) in enumerate(diverse, 1):
        p_vec = _row_to_vec(p)
        weights = [KEYWORD_WEIGHTS[k] for k in KEYWORDS]
        contributions = {
            k: round(person_vec[i] * p_vec[i] * weights[i], 5)
            for i, k in enumerate(KEYWORDS)
        }
        top5 = dict(
            sorted(contributions.items(), key=lambda x: -x[1])[:5]
        )
        results.append({
            "product_id": p.get("id") or "",
            "brand": p.get("brand") or "",
            "name": p.get("name") or "",
            "category": p.get("category") or "",
            "price": p.get("price") or 0.0,
            "currency": p.get("currency") or "",
            "price_tier": p.get("price_tier") or "",
            "similarity_score": round(score, 4),
            "product_url": p.get("product_url") or "",
            "image_url": p.get("image_url") or "",
            "matched_keywords": top5,
            "rank": rank,
        })

    return results
