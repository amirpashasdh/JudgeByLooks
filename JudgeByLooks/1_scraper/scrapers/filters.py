"""Shared category-exclusion and price-floor filters for all scrapers."""

import logging
import re

logger = logging.getLogger(__name__)

_ZARA_EXCLUDED = [
    "zara home", "perfume", "fragrance", "zara hair", "hair",
    "makeup", "cosmetic", "beauty", "bag", "backpack", "underwear",
    "lingerie", "bra", "brief", "sock", "hosiery", "gift card",
    "swimwear", "swimsuit", "bikini", "jewel", "jewellery", "jewelry",
    "belt", "kids", "children", "baby", "infant",
]

_ADIDAS_EXCLUDED = [
    "underwear", "brief", "boxer", "swimwear", "swimsuit",
    "accessory", "accessories", "headwear", "cap", "hat", "beanie",
    "sock", "hosiery", "bag", "backpack", "ball", "equipment",
    "football boot", "cleat", "pet", "kids", "junior", "children",
    "youth", "golf", "cycling", "slide", "sandal",
]

# Short terms that are substrings of legitimate product words — match as whole
# words only to avoid false positives (e.g. "ball" inside "handball").
_WORD_BOUNDARY_TERMS = {"ball", "cap", "hat", "pet", "bra", "brief", "golf"}

PRICE_FLOOR = 15.0


def _category_hit(text: str, terms: list[str]) -> str | None:
    """Return the first matching term, or None if no match."""
    lower = text.lower()
    for term in terms:
        if term in _WORD_BOUNDARY_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", lower):
                return term
        else:
            if term in lower:
                return term
    return None


def should_keep(product: dict, brand: str) -> bool:
    """
    Return True if the product passes all filters.
    Logs a DEBUG line for every rejected product.
    """
    name = product.get("name") or ""
    category = product.get("category") or ""
    price = product.get("price")

    terms = _ZARA_EXCLUDED if brand == "Zara" else _ADIDAS_EXCLUDED

    # Check category field first, then fall back to name for extra safety
    hit = _category_hit(category, terms) or _category_hit(name, terms)
    if hit:
        logger.debug("[FILTERED] %s — %r — reason: category(%s)", brand, name, hit)
        return False

    if price is not None and price < PRICE_FLOOR:
        logger.debug(
            "[FILTERED] %s — %r — reason: price_floor(€%.2f)", brand, name, price
        )
        return False

    return True
