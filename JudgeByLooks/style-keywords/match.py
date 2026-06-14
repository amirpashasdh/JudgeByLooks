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
    "minimalist", "maximalist", "classic", "avant_garde", "streetwear",
    "bohemian", "preppy", "romantic", "edgy", "quiet_luxury", "coastal",
    "dark_academia", "sporty",
    "clean_girl", "ballet_aesthetic", "coquette_style", "tomboy_chic",
    "androgynous_look", "soft_glamour", "indie_style", "coastal_grandmother",
    "dopamine_dressing", "quiet_opulence", "power_dressing", "artsy_downtown",
    "retro_seventies", "retro_nineties", "y2k_inspired", "futuristic_style",
    "boho_luxe", "mob_wife_glam", "stealth_wealth", "avant_minimalist",
    "playful", "serious", "rebellious", "elegant", "laid_back", "bold",
    "understated", "whimsical", "polished", "raw",
    "dramatic", "ethereal", "sensual", "nostalgic", "futuristic_mood",
    "neutral", "monochrome", "earth_tones", "pastel", "bold_colors",
    "black_forward", "white_forward", "jewel_tones", "multicolor",
    "neon_accent", "pastel_rainbow", "gradient_dye", "burnout_print", "ikat_pattern",
    "burgundy_wine", "camel_tan", "cobalt_blue", "forest_green", "blush_pink",
    "cream_ivory", "olive_khaki", "rust_orange",
    "stone_grey", "dusty_mauve", "warm_taupe", "slate_blue", "powder_blue",
    "mint_green", "lilac_purple", "sage_green", "mustard_yellow", "coral_pink",
    "teal_green", "charcoal_grey", "navy_blue", "silver_tone", "golden_yellow",
    "deep_purple", "hot_pink", "champagne_gold", "midnight_blue", "chocolate_brown",
    "nude_pink", "jade_green", "indigo_blue", "fuchsia_pink", "lavender_haze",
    "amber_gold", "smoky_grey", "copper_bronze", "pearl_white", "burnt_sienna",
    "loungewear", "casual", "smart_casual", "business_casual", "formal", "black_tie",
    "parisian", "scandinavian", "italian_luxury", "japanese_minimalist",
    "american_prep", "british_heritage", "nyc_streetwear", "californian",
    "korean_minimal", "french_riviera", "milan_chic", "mediterranean_style",
    "australian_surf", "east_london", "tokyo_street", "brooklyn_cool",
    "porto_casual", "rio_beach",
    "fitted", "oversized", "structured", "flowy", "layered", "cropped", "voluminous",
    "wide_leg", "slim_cut", "high_waist", "tailored_cut", "balloon_sleeve",
    "a_line", "shift_silhouette", "bodycon", "empire_waist", "pencil_cut",
    "column_silhouette", "cape_silhouette", "mermaid_cut", "trapeze_cut", "boxy_cut",
    "v_neck", "turtleneck", "crewneck", "off_shoulder", "halter_neck", "boat_neck",
    "square_neck", "cowl_neck", "mock_neck", "one_shoulder", "scoop_neck",
    "sweetheart_neckline",
    "long_sleeve", "short_sleeve", "sleeveless", "three_quarter_sleeve",
    "raglan_sleeve", "dolman_sleeve", "cap_sleeve", "flutter_sleeve",
    "cold_shoulder", "dropped_shoulder",
    "everyday", "workwear", "going_out", "travel", "outdoor", "sport", "beach", "occasion",
    "date_night", "cocktail", "brunch", "festival_wear", "office_ready", "transitional",
    "gym_wear", "yoga_wear", "running_wear", "swim_wear", "resort_wear",
    "evening_wear", "wedding_guest", "party_wear", "work_from_home", "ski_wear",
    "activewear_set", "capsule_piece", "night_out", "formal_occasion",
    "sustainable", "investment_piece", "trend_driven", "heritage_craft",
    "luxury_status", "budget_conscious", "logo_forward",
    "size_inclusive", "gender_neutral", "performance_tech",
    "wardrobe_staple", "statement_piece", "limited_edition", "handmade_detail",
    "capsule_wardrobe",
    "floral_print", "striped_pattern", "checked_pattern", "animal_print",
    "solid_color", "abstract_print",
    "paisley_print", "baroque_print", "tie_dye", "ombre_effect", "polka_dot",
    "camouflage", "tropical_print", "fairisle_knit", "argyle_pattern", "colour_block",
    "acid_wash", "graphic_print", "logo_repeat", "leopard_spot", "zebra_stripe",
    "toile_print", "damask_print", "windowpane_check",
    "denim_fabric", "linen_fabric", "velvet_fabric", "satin_fabric",
    "leather_fabric", "knitwear_fabric",
    "silk_fabric", "cotton_fabric", "modal_fabric", "lyocell_fabric", "viscose_fabric",
    "wool_fabric", "cashmere_fabric", "suede_fabric", "nylon_fabric", "jersey_fabric",
    "crepe_fabric", "brocade_fabric", "corduroy_fabric", "organza_fabric", "chiffon_fabric",
    "poplin_fabric", "flannel_fabric", "fleece_fabric", "recycled_fabric", "stretch_fabric",
    "sheer_fabric", "mesh_detail", "ribbed_texture", "quilted_detail",
    "faux_fur_trim", "distressed_finish", "woven_texture", "technical_fabric",
    "jacquard_weave", "burnout_effect", "metallic_sheen", "glitter_detail",
    "sequin_embellishment", "beaded_detail", "laser_cut", "perforated_detail",
    "frayed_edge", "brushed_finish",
    "mini_length", "midi_length", "maxi_length",
    "ruffled", "belted", "crochet_detail", "embroidered_detail", "pleated_detail",
    "wrap_style", "cutout_detail", "asymmetric_hem", "tie_waist", "puff_sleeve",
    "button_front", "double_breasted", "single_breasted", "zip_front", "cargo_pockets",
    "patch_pocket", "chest_pocket", "notch_lapel", "mandarin_collar", "shawl_collar",
    "gathered_bodice", "smocked_detail", "pintuck_detail", "shirred_detail",
    "drawstring_waist", "elastic_waist", "corset_detail", "gathered_waist",
    "raw_edge_hem", "fringe_trim", "lace_trim", "contrast_stitch", "open_back",
    "gold_hardware", "silver_hardware", "chain_trim", "buckle_detail",
    "stud_embellishment",
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
