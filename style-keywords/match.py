"""
match.py — Recommend products for a person based on style vector similarity.

Usage:
    python3 match.py                         # latest person analysis → top 10
    python3 match.py --person 2              # specific person_analysis row id
    python3 match.py --top 20                # return top 20
    python3 match.py --no-diverse            # pure cosine rank, no diversity filter
    python3 match.py --out results/my_run    # custom output folder
"""

import argparse
import json
import math
import os
import sqlite3
from datetime import datetime

KEYWORDS_DB = os.path.join(os.path.dirname(__file__), "keywords.db")
FASHION_DB  = os.path.join(os.path.dirname(__file__), "fashion.db")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

KEYWORDS = [
    "minimalist", "maximalist", "classic", "avant_garde", "streetwear", "bohemian",
    "preppy", "romantic", "edgy", "quiet_luxury", "coastal", "dark_academia", "sporty",
    "playful", "serious", "rebellious", "elegant", "laid_back", "bold", "understated",
    "whimsical", "polished", "raw",
    "neutral", "monochrome", "earth_tones", "pastel", "bold_colors", "black_forward",
    "white_forward", "jewel_tones", "multicolor",
    "loungewear", "casual", "smart_casual", "business_casual", "formal", "black_tie",
    "parisian", "scandinavian", "italian_luxury", "japanese_minimalist",
    "american_prep", "british_heritage", "nyc_streetwear", "californian",
    "fitted", "oversized", "structured", "flowy", "layered", "cropped", "voluminous",
    "everyday", "workwear", "going_out", "travel", "outdoor", "sport", "beach", "occasion",
    "sustainable", "investment_piece", "trend_driven", "heritage_craft",
    "luxury_status", "budget_conscious", "logo_forward", "logo_free",
    "size_inclusive", "gender_neutral", "performance_tech",
    "floral_print", "striped_pattern", "checked_pattern", "animal_print",
    "solid_color", "abstract_print",
    "denim_fabric", "linen_fabric", "velvet_fabric", "satin_fabric",
    "leather_fabric", "knitwear_fabric",
    "mini_length", "midi_length", "maxi_length",
    "ruffled", "belted", "crochet_detail", "embroidered_detail", "pleated_detail",
]


# ── vector math ───────────────────────────────────────────────────────────────

def cosine(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def row_to_vec(row: dict) -> list[float]:
    return [float(row.get(k) or 0.0) for k in KEYWORDS]


# ── data loading ──────────────────────────────────────────────────────────────

def load_person(person_id: int | None) -> dict:
    conn = sqlite3.connect(KEYWORDS_DB)
    conn.row_factory = sqlite3.Row
    if person_id is None:
        row = conn.execute(
            "SELECT * FROM person_analysis ORDER BY id DESC LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM person_analysis WHERE id = ?", (person_id,)
        ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(
            f"No person analysis found (id={person_id}). "
            "Run: python3 main.py --image photo.jpg"
        )
    return dict(row)


def load_products() -> list[dict]:
    conn = sqlite3.connect(FASHION_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── diverse selection ─────────────────────────────────────────────────────────

def diverse_top(
    ranked: list[tuple[float, dict]],
    top_n: int,
    diversity_threshold: float = 0.90,
) -> list[tuple[float, dict]]:
    """
    Greedy diverse selection: add next candidate only if its vector is not
    too similar to any already-selected product (avoids 10 identical items).
    """
    selected = []
    for score, product in ranked:
        if len(selected) >= top_n:
            break
        vec = row_to_vec(product)
        too_similar = any(
            cosine(vec, row_to_vec(s)) > diversity_threshold
            for _, s in selected
        )
        if not too_similar:
            selected.append((score, product))
    return selected


# ── output ────────────────────────────────────────────────────────────────────

def next_run_dir(base: str) -> str:
    os.makedirs(base, exist_ok=True)
    existing = [
        d for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d)) and d.startswith("run_")
    ]
    n = len(existing) + 1
    run_dir = os.path.join(base, f"run_{n:03d}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def top_keywords(vec: list[float], n: int = 3) -> list[str]:
    scored = sorted(zip(KEYWORDS, vec), key=lambda x: -x[1])
    return [k for k, v in scored[:n] if v > 0]


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Style-based product recommender")
    parser.add_argument("--person",     type=int,  default=None, help="person_analysis row id (default: latest)")
    parser.add_argument("--top",        type=int,  default=10,   help="Number of recommendations (default: 10)")
    parser.add_argument("--no-diverse", action="store_true",     help="Disable diversity filter")
    parser.add_argument("--out",        default=None,            help="Output folder (default: results/run_NNN)")
    args = parser.parse_args()

    # ── load ──────────────────────────────────────────────────────────────────
    print(f"[Match] Loading person #{args.person or 'latest'} vector...")
    person = load_person(args.person)
    person_vec = row_to_vec(person)

    print(f"[Match] Loading {FASHION_DB.split('/')[-1]} products...")
    products = load_products()
    if not products:
        print("[Match] No products in fashion.db. Run: python3 migrate.py")
        return

    print(f"[Match] Found {len(products)} products")

    # ── score ─────────────────────────────────────────────────────────────────
    mode = "diverse" if not args.no_diverse else "ranked"
    print(f"[Match] Computing similarity ({mode} mode)...")
    ranked = sorted(
        [(cosine(person_vec, row_to_vec(p)), p) for p in products],
        key=lambda x: -x[0],
    )

    if not args.no_diverse:
        results = diverse_top(ranked, args.top)
    else:
        results = ranked[:args.top]

    # ── print ─────────────────────────────────────────────────────────────────
    print(f"[Match] Top {len(results)} selected:")
    for i, (score, p) in enumerate(results, 1):
        kws = top_keywords(row_to_vec(p))
        name = (p.get("name") or "")[:40]
        print(f"  #{i:<3} {score:.2f}  {p.get('brand',''):<8}  \"{name}\"  [{', '.join(kws)}]")

    # ── save ──────────────────────────────────────────────────────────────────
    out_dir = args.out if args.out else next_run_dir(RESULTS_DIR)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "recommendations.json")

    payload = {
        "generated_at": datetime.now().isoformat(),
        "person": {
            "id": person["id"],
            "image_path": person.get("image_path"),
            "analysed_at": person.get("analysed_at"),
            "top_keywords": top_keywords(person_vec, 6),
        },
        "mode": mode,
        "recommendations": [
            {
                "rank": i + 1,
                "score": round(score, 4),
                "id": p.get("id"),
                "brand": p.get("brand"),
                "name": p.get("name"),
                "category": p.get("category"),
                "price": p.get("price"),
                "currency": p.get("currency"),
                "price_tier": p.get("price_tier"),
                "product_url": p.get("product_url"),
                "image_url": p.get("image_url"),
                "top_keywords": top_keywords(row_to_vec(p)),
            }
            for i, (score, p) in enumerate(results)
        ],
    }

    with open(out_file, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"[Match] Saved {out_file}")


if __name__ == "__main__":
    main()
