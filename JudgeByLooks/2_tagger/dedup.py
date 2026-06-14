"""Post-tagging cosine-similarity deduplication."""

import logging

import numpy as np

logger = logging.getLogger(__name__)

KEYWORDS = [
    # ── Aesthetic — broad (13) ────────────────────────────────────────────────
    "minimalist", "maximalist", "classic", "avant_garde", "streetwear",
    "bohemian", "preppy", "romantic", "edgy", "quiet_luxury", "coastal",
    "dark_academia", "sporty",
    # ── Aesthetic — sub-genres (20) ───────────────────────────────────────────
    "clean_girl", "ballet_aesthetic", "coquette_style", "tomboy_chic",
    "androgynous_look", "soft_glamour", "indie_style", "coastal_grandmother",
    "dopamine_dressing", "quiet_opulence", "power_dressing", "artsy_downtown",
    "retro_seventies", "retro_nineties", "y2k_inspired", "futuristic_style",
    "boho_luxe", "mob_wife_glam", "stealth_wealth", "avant_minimalist",
    # ── Mood (15) ─────────────────────────────────────────────────────────────
    "playful", "serious", "rebellious", "elegant", "laid_back", "bold",
    "understated", "whimsical", "polished", "raw",
    "dramatic", "ethereal", "sensual", "nostalgic", "futuristic_mood",
    # ── Color — palette (14) ──────────────────────────────────────────────────
    "neutral", "monochrome", "earth_tones", "pastel", "bold_colors",
    "black_forward", "white_forward", "jewel_tones", "multicolor",
    "neon_accent", "pastel_rainbow", "gradient_dye", "burnout_print", "ikat_pattern",
    # ── Color — specifics (38) ────────────────────────────────────────────────
    "burgundy_wine", "camel_tan", "cobalt_blue", "forest_green", "blush_pink",
    "cream_ivory", "olive_khaki", "rust_orange",
    "stone_grey", "dusty_mauve", "warm_taupe", "slate_blue", "powder_blue",
    "mint_green", "lilac_purple", "sage_green", "mustard_yellow", "coral_pink",
    "teal_green", "charcoal_grey", "navy_blue", "silver_tone", "golden_yellow",
    "deep_purple", "hot_pink", "champagne_gold", "midnight_blue", "chocolate_brown",
    "nude_pink", "jade_green", "indigo_blue", "fuchsia_pink", "lavender_haze",
    "amber_gold", "smoky_grey", "copper_bronze", "pearl_white", "burnt_sienna",
    # ── Formality (6) ─────────────────────────────────────────────────────────
    "loungewear", "casual", "smart_casual", "business_casual", "formal", "black_tie",
    # ── Cultural (18) ─────────────────────────────────────────────────────────
    "parisian", "scandinavian", "italian_luxury", "japanese_minimalist",
    "american_prep", "british_heritage", "nyc_streetwear", "californian",
    "korean_minimal", "french_riviera", "milan_chic", "mediterranean_style",
    "australian_surf", "east_london", "tokyo_street", "brooklyn_cool",
    "porto_casual", "rio_beach",
    # ── Silhouette — core (7) ─────────────────────────────────────────────────
    "fitted", "oversized", "structured", "flowy", "layered", "cropped", "voluminous",
    # ── Silhouette — cut (15) ─────────────────────────────────────────────────
    "wide_leg", "slim_cut", "high_waist", "tailored_cut", "balloon_sleeve",
    "a_line", "shift_silhouette", "bodycon", "empire_waist", "pencil_cut",
    "column_silhouette", "cape_silhouette", "mermaid_cut", "trapeze_cut", "boxy_cut",
    # ── Neckline (12) ─────────────────────────────────────────────────────────
    "v_neck", "turtleneck", "crewneck", "off_shoulder", "halter_neck", "boat_neck",
    "square_neck", "cowl_neck", "mock_neck", "one_shoulder", "scoop_neck",
    "sweetheart_neckline",
    # ── Sleeve (10) ───────────────────────────────────────────────────────────
    "long_sleeve", "short_sleeve", "sleeveless", "three_quarter_sleeve",
    "raglan_sleeve", "dolman_sleeve", "cap_sleeve", "flutter_sleeve",
    "cold_shoulder", "dropped_shoulder",
    # ── Occasion — broad (8) ──────────────────────────────────────────────────
    "everyday", "workwear", "going_out", "travel", "outdoor", "sport", "beach", "occasion",
    # ── Occasion — nuance (20) ────────────────────────────────────────────────
    "date_night", "cocktail", "brunch", "festival_wear", "office_ready", "transitional",
    "gym_wear", "yoga_wear", "running_wear", "swim_wear", "resort_wear",
    "evening_wear", "wedding_guest", "party_wear", "work_from_home", "ski_wear",
    "activewear_set", "capsule_piece", "night_out", "formal_occasion",
    # ── Values (15) ───────────────────────────────────────────────────────────
    "sustainable", "investment_piece", "trend_driven", "heritage_craft",
    "luxury_status", "budget_conscious", "logo_forward",
    "size_inclusive", "gender_neutral", "performance_tech",
    "wardrobe_staple", "statement_piece", "limited_edition", "handmade_detail",
    "capsule_wardrobe",
    # ── Pattern (24) ──────────────────────────────────────────────────────────
    "floral_print", "striped_pattern", "checked_pattern", "animal_print",
    "solid_color", "abstract_print",
    "paisley_print", "baroque_print", "tie_dye", "ombre_effect", "polka_dot",
    "camouflage", "tropical_print", "fairisle_knit", "argyle_pattern", "colour_block",
    "acid_wash", "graphic_print", "logo_repeat", "leopard_spot", "zebra_stripe",
    "toile_print", "damask_print", "windowpane_check",
    # ── Fabric — material (26) ────────────────────────────────────────────────
    "denim_fabric", "linen_fabric", "velvet_fabric", "satin_fabric",
    "leather_fabric", "knitwear_fabric",
    "silk_fabric", "cotton_fabric", "modal_fabric", "lyocell_fabric", "viscose_fabric",
    "wool_fabric", "cashmere_fabric", "suede_fabric", "nylon_fabric", "jersey_fabric",
    "crepe_fabric", "brocade_fabric", "corduroy_fabric", "organza_fabric", "chiffon_fabric",
    "poplin_fabric", "flannel_fabric", "fleece_fabric", "recycled_fabric", "stretch_fabric",
    # ── Fabric — texture (18) ─────────────────────────────────────────────────
    "sheer_fabric", "mesh_detail", "ribbed_texture", "quilted_detail",
    "faux_fur_trim", "distressed_finish", "woven_texture", "technical_fabric",
    "jacquard_weave", "burnout_effect", "metallic_sheen", "glitter_detail",
    "sequin_embellishment", "beaded_detail", "laser_cut", "perforated_detail",
    "frayed_edge", "brushed_finish",
    # ── Length (3) ────────────────────────────────────────────────────────────
    "mini_length", "midi_length", "maxi_length",
    # ── Construction & detail (38) ────────────────────────────────────────────
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


def _score_vector(product: dict) -> np.ndarray:
    return np.array([float(product.get(k, 0.0)) for k in KEYWORDS], dtype=np.float32)


def _informativeness(product: dict) -> int:
    """Count of keywords with score > 0.5."""
    return sum(1 for k in KEYWORDS if float(product.get(k, 0.0)) > 0.5)


def dedup(
    products: list[dict], threshold: float = 0.98
) -> tuple[list[dict], list[dict]]:
    """
    Return (kept, removed).
    removed entries have extra fields: similar_to, similarity_score.
    """
    if not products:
        return [], []

    vecs = np.stack([_score_vector(p) for p in products])

    # Normalise rows; zero-vectors stay zero
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vecs_n = vecs / norms

    sim = vecs_n @ vecs_n.T  # (N, N) cosine matrix

    removed_idx: set[int] = set()

    for i in range(len(products)):
        if i in removed_idx:
            continue
        for j in range(i + 1, len(products)):
            if j in removed_idx:
                continue
            # Skip exact-same product ID (identical rows from two scrapers)
            if products[i].get("id") == products[j].get("id") and products[i].get("id"):
                removed_idx.add(j)
                continue
            if sim[i, j] > threshold:
                info_i = _informativeness(products[i])
                info_j = _informativeness(products[j])
                # Remove the less informative one; ties go to j (higher index)
                loser = j if info_i >= info_j else i
                winner = i if loser == j else j
                removed_idx.add(loser)
                logger.info(
                    '[DEDUP] Removed "%s" — similar to "%s" (sim=%.2f, brand=%s)',
                    products[loser]["name"],
                    products[winner]["name"],
                    float(sim[i, j]),
                    products[loser]["brand"],
                )
                products[loser]["similar_to"] = products[winner]["name"]
                products[loser]["similarity_score"] = round(float(sim[i, j]), 4)

    kept = [p for idx, p in enumerate(products) if idx not in removed_idx]
    removed = [p for idx, p in enumerate(products) if idx in removed_idx]
    return kept, removed
