import sqlite3
import json
from datetime import datetime

DB_PATH = "keywords.db"

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

_KW_COLUMNS = ", ".join(f"{k} REAL DEFAULT 0.0" for k in KEYWORDS)
_CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS person_analysis (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path          TEXT NOT NULL,
    analysed_at         TEXT NOT NULL,
    raw_response        TEXT NOT NULL,
    taxonomy_mode       TEXT NOT NULL DEFAULT 'both',
    current_outfit      TEXT,
    coloring            TEXT,
    context             TEXT,
    price_tier_brief    TEXT,
    overall_confidence  REAL DEFAULT 0.0,
    low_confidence_fallback INTEGER DEFAULT 0,
    recommendations     TEXT,
    gender              TEXT DEFAULT 'unisex',
    {_KW_COLUMNS}
)
"""

_CREATE_EXPERIMENT_LOG = """
CREATE TABLE IF NOT EXISTS experiment_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id               INTEGER NOT NULL,
    session_id              TEXT NOT NULL,
    logged_at               TEXT NOT NULL,
    taxonomy_mode           TEXT,
    price_tier_strategy     TEXT,
    tier_shift              INTEGER DEFAULT 0,
    silhouette_adjustment   INTEGER DEFAULT 0,
    retrieval_mode          TEXT,
    products_surfaced       TEXT,
    FOREIGN KEY (person_id) REFERENCES person_analysis(id)
)
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(person_analysis)")}
    if cols and "image_path" not in cols:
        conn.execute("DROP TABLE person_analysis")
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_EXPERIMENT_LOG)
    # add new columns to existing tables if upgrading from fashion-ai schema
    existing = {row[1] for row in conn.execute("PRAGMA table_info(person_analysis)")}
    for col_def in [
        ("taxonomy_mode", "TEXT NOT NULL DEFAULT 'both'"),
        ("current_outfit", "TEXT"),
        ("coloring", "TEXT"),
        ("context", "TEXT"),
        ("price_tier_brief", "TEXT"),
        ("overall_confidence", "REAL DEFAULT 0.0"),
        ("low_confidence_fallback", "INTEGER DEFAULT 0"),
        ("recommendations", "TEXT"),
        ("gender", "TEXT DEFAULT 'unisex'"),
    ]:
        if col_def[0] not in existing:
            conn.execute(f"ALTER TABLE person_analysis ADD COLUMN {col_def[0]} {col_def[1]}")
    conn.commit()
    conn.close()


def save_analysis(image_path: str, raw_response: str, brief: dict, taxonomy_mode: str = "both") -> int:
    """Insert one row. brief is the full stylist brief dict."""
    style_scores = brief.get("style_scores", {})
    kw_scores = style_scores.get("keywords", {})
    full_kw = {k: float(kw_scores.get(k, 0.0)) for k in KEYWORDS}
    analysed_at = datetime.now().isoformat()

    cols = [
        "image_path", "analysed_at", "raw_response", "taxonomy_mode",
        "current_outfit", "coloring", "context", "price_tier_brief",
        "overall_confidence", "low_confidence_fallback", "recommendations",
        "gender",
    ] + KEYWORDS

    values = [
        image_path,
        analysed_at,
        raw_response,
        taxonomy_mode,
        json.dumps(brief.get("current_outfit", [])),
        json.dumps(brief.get("coloring", {})),
        json.dumps(brief.get("context", {})),
        json.dumps(brief.get("price_tier", {})),
        float(brief.get("overall_confidence", 0.0)),
        1 if brief.get("low_confidence_fallback", False) else 0,
        json.dumps(brief.get("recommendations", [])),
        brief.get("gender", "unisex") or "unisex",
    ] + [full_kw[k] for k in KEYWORDS]

    placeholders = ", ".join(["?"] * len(cols))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        f"INSERT INTO person_analysis ({', '.join(cols)}) VALUES ({placeholders})",
        values,
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def log_experiment(person_id: int, session_id: str, params: dict, product_ids: list) -> None:
    """Record experimental parameters and surfaced products for one recommendation pass."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO experiment_log
           (person_id, session_id, logged_at, taxonomy_mode, price_tier_strategy,
            tier_shift, silhouette_adjustment, retrieval_mode, products_surfaced)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            person_id,
            session_id,
            datetime.now().isoformat(),
            params.get("taxonomy_mode", "both"),
            params.get("price_tier_strategy", "match"),
            int(params.get("tier_shift", 0)),
            1 if params.get("silhouette_adjustment", False) else 0,
            params.get("retrieval_mode", "gap_based"),
            json.dumps(product_ids),
        ),
    )
    conn.commit()
    conn.close()


def get_recent(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(person_analysis)")}
    if not cols:
        conn.close()
        return []
    rows = conn.execute(
        "SELECT id, image_path, analysed_at, raw_response, overall_confidence FROM person_analysis ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        try:
            brief = json.loads(r[3])
            kw = brief.get("style_scores", {}).get("keywords", {})
            top_kw = sorted(kw.items(), key=lambda x: -x[1])[:5]
            arch = brief.get("style_scores", {}).get("archetypes", {})
            top_arch = sorted(arch.items(), key=lambda x: -x[1])[:3]
        except (json.JSONDecodeError, TypeError, AttributeError):
            top_kw = []
            top_arch = []
        results.append({
            "id": r[0],
            "image_path": r[1],
            "analysed_at": r[2],
            "overall_confidence": r[4],
            "top_keywords": top_kw,
            "top_archetypes": top_arch,
        })
    return results
