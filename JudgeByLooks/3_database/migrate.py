"""
One-time migration: reads 2_tagger/data/products_tagged.xlsx and loads all
products into style-keywords/fashion.db.  Safe to re-run — existing rows are skipped.

Usage:
    cd JudgeByLooks && python3 3_database/migrate.py
"""

import sqlite3
import os
from collections import Counter

import openpyxl

XLSX_PATH = os.path.join(os.path.dirname(__file__), "../2_tagger/data/products_tagged.xlsx")
DB_PATH   = os.path.join(os.path.dirname(__file__), "../style-keywords/fashion.db")
SHEET     = "Products"

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

LAYER1_COLS = ["gender", "item_type", "color_family", "silhouette_attr", "fabric_attr", "formality_attr"]

ARCHETYPE_IDS = [
    "minimalist", "streetwear", "goth", "dark_academia", "preppy", "bohemian",
    "classic_business", "athleisure", "romantic_feminine", "grunge", "cottagecore",
    "y2k_retro", "coastal_resort", "punk_edgy", "old_money_quiet_luxury", "techwear",
    "western_country", "glam_evening", "artsy_eclectic", "scandinavian_minimal",
    "military_utility", "pinup_vintage_50s", "skater_surf",
    "japanese_street_avant_garde", "tropical_vacation", "biker_moto", "normcore",
    "art_deco_glamour", "gorpcore", "balletcore", "office_siren",
    "festival_eclectic", "scholarly_prep_ivy",
]
ARCH_COLS = [f"arch_{a}" for a in ARCHETYPE_IDS]

_KW_COL_DEFS    = "\n".join(f"  {k:<22} REAL DEFAULT 0.0," for k in KEYWORDS)
_L1_COL_DEFS    = "\n".join(f"  {c:<22} TEXT," for c in LAYER1_COLS)
_ARCH_COL_DEFS  = "\n".join(f"  {c:<38} REAL DEFAULT 0.0," for c in ARCH_COLS)

CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS products (
  id                     TEXT PRIMARY KEY,
  brand                  TEXT,
  name                   TEXT,
  category               TEXT,
  price                  REAL,
  currency               TEXT,
  price_tier             TEXT,
  colors                 TEXT,
  description            TEXT,
  product_url            TEXT,
  scraped_at             TEXT,
  image_url              TEXT,
{_L1_COL_DEFS}
{_KW_COL_DEFS}
{_ARCH_COL_DEFS}
  _placeholder           INTEGER DEFAULT 0
)
"""

ALL_COLS = (
    ["id", "brand", "name", "category", "price", "currency",
     "price_tier", "colors", "description", "product_url",
     "scraped_at", "image_url"]
    + LAYER1_COLS
    + KEYWORDS
    + ARCH_COLS
)

INSERT_SQL = (
    f"INSERT OR IGNORE INTO products ({', '.join(ALL_COLS)}) "
    f"VALUES ({', '.join(['?'] * len(ALL_COLS))})"
)


def _str(val) -> str:
    return str(val).strip() if val is not None else ""

def _price(val):
    try:    return float(val)
    except: return None

def _float(val) -> float:
    try:    return float(val) if val is not None else 0.0
    except: return 0.0


def main():
    print(f"[Migrate] Reading {XLSX_PATH}...")
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET]

    rows    = list(ws.iter_rows(values_only=True))
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    data_rows = rows[1:]
    print(f"[Migrate] Found {len(data_rows)} products in xlsx")

    missing_kw   = [k for k in KEYWORDS    if k not in headers]
    missing_l1   = [k for k in LAYER1_COLS if k not in headers]
    missing_arch = [k for k in ARCH_COLS   if k not in headers]
    for k in missing_kw + missing_l1 + missing_arch:
        print(f'[WARN] Column "{k}" not found in xlsx — defaulting to 0/empty')

    col_idx = {h: i for i, h in enumerate(headers)}

    def get(row, col, default=None):
        i = col_idx.get(col)
        return row[i] if i is not None and i < len(row) else default

    print(f"[Migrate] Inserting into {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE)
    conn.commit()

    # add any missing columns if db already exists with old schema
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
    for col in LAYER1_COLS:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col} TEXT")
    for col in ARCH_COLS:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col} REAL DEFAULT 0.0")
    conn.commit()

    inserted = skipped = 0
    for row in data_rows:
        values = [
            _str(get(row, "id")),
            _str(get(row, "brand")),
            _str(get(row, "name")),
            _str(get(row, "category")),
            _price(get(row, "price")),
            _str(get(row, "currency")),
            _str(get(row, "price_tier")),
            _str(get(row, "colors")),
            _str(get(row, "description")),
            _str(get(row, "product_url")),
            _str(get(row, "scraped_at")),
            _str(get(row, "image_url")),
        ] + [_str(get(row, c)) for c in LAYER1_COLS] \
          + [_float(get(row, k)) for k in KEYWORDS] \
          + [_float(get(row, c)) for c in ARCH_COLS]

        cur = conn.execute(INSERT_SQL, values)
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1

    conn.commit()

    # ── summary ────────────────────────────────────────────────────────────────
    brands = Counter(_str(get(r, "brand")) for r in data_rows if get(r, "brand"))
    tiers  = Counter(_str(get(r, "price_tier")) for r in data_rows if get(r, "price_tier"))
    l1_coverage = {c: sum(1 for r in data_rows if _str(get(r, c))) for c in LAYER1_COLS}
    arch_hits = {a: sum(1 for r in data_rows if _float(get(r, f"arch_{a}")) > 0) for a in ARCHETYPE_IDS}
    top_arch = sorted(arch_hits.items(), key=lambda x: -x[1])[:5]

    brands_str = ", ".join(f"{b}({c})" for b, c in brands.most_common(5))
    tiers_str  = " ".join(f"{t}({c})" for t, c in sorted(tiers.items()))

    print()
    print("─" * 50)
    print("Migration complete")
    print("─" * 50)
    print(f"Products inserted:  {inserted:>6}")
    print(f"Products skipped:   {skipped:>6}")
    print(f"Brands:             {brands_str}")
    print(f"Price tiers:        {tiers_str}")
    print(f"\nLayer-1 coverage:")
    for c, n in l1_coverage.items():
        print(f"  {c:<22} {n:>6}")
    print(f"\nTop 5 archetypes by coverage:")
    for aid, n in top_arch:
        print(f"  arch_{aid:<30} {n:>6}")
    print("─" * 50)

    conn.close()
    wb.close()


if __name__ == "__main__":
    main()
