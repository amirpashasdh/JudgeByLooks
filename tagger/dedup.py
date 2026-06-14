"""Post-tagging cosine-similarity deduplication."""

import logging

import numpy as np

logger = logging.getLogger(__name__)

KEYWORDS = [
    # Aesthetic
    "minimalist", "maximalist", "classic", "avant_garde", "streetwear",
    "bohemian", "preppy", "romantic", "edgy", "quiet_luxury", "coastal",
    "dark_academia", "sporty",
    # Mood
    "playful", "serious", "rebellious", "elegant", "laid_back", "bold",
    "understated", "whimsical", "polished", "raw",
    # Color palette
    "neutral", "monochrome", "earth_tones", "pastel", "bold_colors",
    "black_forward", "white_forward", "jewel_tones", "multicolor",
    # Formality
    "loungewear", "casual", "smart_casual", "business_casual", "formal", "black_tie",
    # Cultural
    "parisian", "scandinavian", "italian_luxury", "japanese_minimalist",
    "american_prep", "british_heritage", "nyc_streetwear", "californian",
    # Silhouette
    "fitted", "oversized", "structured", "flowy", "layered", "cropped", "voluminous",
    # Occasion
    "everyday", "workwear", "going_out", "travel", "outdoor", "sport", "beach", "occasion",
    # Values
    "sustainable", "investment_piece", "trend_driven", "heritage_craft",
    "luxury_status", "budget_conscious", "logo_forward", "logo_free",
    "size_inclusive", "gender_neutral", "performance_tech",
    # ── Product attributes (discriminating) ──────────────────────────────
    # Pattern
    "floral_print", "striped_pattern", "checked_pattern", "animal_print",
    "solid_color", "abstract_print",
    # Material
    "denim_fabric", "linen_fabric", "velvet_fabric", "satin_fabric",
    "leather_fabric", "knitwear_fabric",
    # Length / proportion
    "mini_length", "midi_length", "maxi_length",
    # Key design detail
    "ruffled", "belted", "crochet_detail", "embroidered_detail", "pleated_detail",
]


def _score_vector(product: dict) -> np.ndarray:
    return np.array([float(product.get(k, 0.0)) for k in KEYWORDS], dtype=np.float32)


def _informativeness(product: dict) -> int:
    """Count of keywords with score > 0.5."""
    return sum(1 for k in KEYWORDS if float(product.get(k, 0.0)) > 0.5)


def dedup(
    products: list[dict], threshold: float = 0.92
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
