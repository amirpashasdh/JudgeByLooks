#!/usr/bin/env python3
"""
Rule-based fashion product tagger — free, instant, no API calls.

Scores each of the 110 style keywords against product name, description,
category, brand, price, and color using pattern matching.

Changes from fashion-ai:
- Price decoupled from style keywords (no price-based boosts on quiet_luxury etc.)
- logo_free dropped (near-constant, dilutes cosine similarity)
- 5 shared Layer-1 attribute columns added per product
- 32-archetype scoring pass added from style_archetypes.json
- gender column added (male/female/unisex extracted from category)
- dedup removed — diversity handled at retrieval time instead
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from dedup import KEYWORDS

ZARA_JSON   = ROOT / "1_scraper/data/zara_raw.json"
ADIDAS_JSON = ROOT / "1_scraper/data/adidas_raw.json"
DATA_DIR    = Path(__file__).parent / "data"
XLSX_OUT    = DATA_DIR / "products_tagged.xlsx"
ARCHETYPES_JSON = ROOT / "style_archetypes.json"

# Layer-1 attribute columns (shared vocabulary with analyzer output)
LAYER1_COLS = [
    "gender",
    "item_type",
    "color_family",
    "silhouette_attr",
    "fabric_attr",
    "formality_attr",
]

# 32 archetype ids (must match style_archetypes.json)
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

BASE_COLS = [
    "id", "brand", "name", "category", "price", "currency", "price_tier",
    "colors", "description", "product_url", "scraped_at", "image_url",
]
ALL_COLS = BASE_COLS + LAYER1_COLS + KEYWORDS + ARCH_COLS

# ── archetype rule sets loaded once ──────────────────────────────────────────

def _load_archetype_rules() -> dict:
    """Return {archetype_id: {"pattern_terms": [...], "color_terms": [...]}}."""
    if not ARCHETYPES_JSON.exists():
        print(f"[WARN] {ARCHETYPES_JSON} not found — archetype scoring disabled")
        return {}
    data = json.loads(ARCHETYPES_JSON.read_text(encoding="utf-8"))
    rules = {}
    for arch in data.get("archetypes", []):
        aid = arch["id"]
        pattern_terms = []
        for p in arch.get("patterns", []):
            pattern_terms.extend(p.lower().replace("-", " ").split())
            if " " in p:
                pattern_terms.append(p.lower())
        for f in arch.get("fabrics", []):
            pattern_terms.append(f.lower())
        for s in arch.get("silhouette", []):
            pattern_terms.extend(s.lower().split())

        color_terms = []
        for c in arch.get("colors", []):
            color_terms.extend(c.lower().replace("/", " ").split())
            if " " in c:
                color_terms.append(c.lower())

        rules[aid] = {
            "pattern_terms": list(set(t for t in pattern_terms if len(t) > 2)),
            "color_terms": list(set(t for t in color_terms if len(t) > 2)),
        }
    return rules

_ARCHETYPE_RULES = _load_archetype_rules()


# ── helpers ──────────────────────────────────────────────────────────────────

def _haystack(p: dict) -> str:
    parts = [
        p.get("name") or "",
        p.get("description") or "",
        p.get("category") or "",
    ]
    return " ".join(parts).lower()

def _colors_str(p: dict) -> str:
    cols = p.get("colors") or []
    if isinstance(cols, list):
        return " ".join(str(c) for c in cols).lower()
    return str(cols).lower()

def _has(text: str, *terms) -> bool:
    return any(t in text for t in terms)

def _score(text: str, strong: list, weak: list = None) -> float:
    if any(t in text for t in strong):
        return 0.85
    if weak and any(t in text for t in weak):
        return 0.5
    return 0.0

def _price_tier(price) -> str:
    if price is None: return "unknown"
    try: price = float(price)
    except: return "unknown"
    if price < 30:   return "budget"
    if price < 80:   return "mid"
    if price < 200:  return "premium"
    return "luxury"


# ── Layer-1 attribute extraction ──────────────────────────────────────────────

_ITEM_TYPE_MAP = [
    ("shoes",     ["shoe", "sneaker", "trainer", "boot", "loafer", "sandal", "heel", "pump", "flat"]),
    ("jacket",    ["jacket", "coat", "parka", "anorak", "trench", "blazer", "puffer", "windbreaker", "overcoat"]),
    ("outerwear", ["overshirt", "gilet", "waistcoat", "vest layer"]),
    ("dress",     ["dress", "gown", "jumpsuit", "playsuit", "romper"]),
    ("top",       ["t-shirt", "tshirt", "shirt", "blouse", "top", "tank", "tee", "polo", "sweatshirt", "hoodie", "sweater", "jumper", "cardigan", "knit"]),
    ("trousers",  ["trouser", "pant", "jogger", "chino", "legging", "short"]),
    ("jeans",     ["jean", "denim"]),
    ("skirt",     ["skirt"]),
    ("accessory", ["bag", "belt", "scarf", "hat", "cap", "glove", "sock", "tie", "jewel", "watch", "necklace", "earring"]),
]

def _extract_gender(category: str) -> str:
    """Extract gender from category string. Returns 'male', 'female', or 'unisex'."""
    cat = (category or "").lower()
    if cat.startswith("woman") or cat.startswith("women"):
        return "female"
    if cat.startswith("man") or cat.startswith("men"):
        return "male"
    return "unisex"


def _extract_item_type(h: str, cat: str) -> str:
    # normalise: remove "bootcut" before checking for "boot" to avoid false shoes match
    text = (h + " " + cat).replace("bootcut", "").replace("boot cut", "")
    for item_type, terms in _ITEM_TYPE_MAP:
        if any(t in text for t in terms):
            return item_type
    return "other"

_COLOR_FAMILY_MAP = [
    ("black",        ["black"]),
    ("white",        ["white", "ivory", "ecru", "off-white", "cream"]),
    ("pastel",       ["pastel", "lilac", "lavender", "mint", "blush", "baby blue", "powder", "soft pink", "pale"]),
    ("jewel_tone",   ["emerald", "sapphire", "ruby", "burgundy", "deep purple", "teal", "wine", "oxblood"]),
    ("bold",         ["neon", "electric", "cobalt", "fuchsia", "hot pink", "bright red", "lime green", "vivid", "scarlet"]),
    ("earth_tone",   ["terracotta", "rust", "burnt orange", "mustard", "olive", "chocolate", "cognac", "brown", "camel", "tan", "sand", "khaki", "beige", "taupe"]),
    ("neutral",      ["grey", "gray", "stone", "nude", "oat"]),
    ("warm_neutral", ["beige", "camel", "ecru", "sand", "cream", "taupe"]),
    ("cool_neutral", ["grey", "gray", "silver", "charcoal"]),
    ("denim_blue",   ["denim", "indigo"]),
    ("navy",         ["navy"]),
    ("multi",        ["multicolor", "multicolour", "color block", "tie dye", "pattern"]),
]

def _extract_color_family(h: str, col: str) -> str:
    text = h + " " + col
    for family, terms in _COLOR_FAMILY_MAP:
        if any(t in text for t in terms):
            return family
    return "neutral"

_SILHOUETTE_MAP = [
    ("fitted",      ["fitted", "slim fit", "skinny", "bodycon", "close-fitting", "form-fitting", "tight"]),
    ("oversized",   ["oversized", "baggy", "boxy", "wide fit", "loose fit", "relaxed fit", "extra large"]),
    ("structured",  ["structured", "tailored", "padded shoulder", "corseted", "crisp"]),
    ("flowy",       ["flowy", "fluid", "draped", "floaty", "billowy", "chiffon"]),
    ("voluminous",  ["puff", "balloon", "full skirt", "flared", "wide leg", "pleated", "tiered", "gathered"]),
    ("cropped",     ["crop", "cropped", "midriff"]),
    ("straight",    ["straight", "regular fit", "classic fit"]),
    ("relaxed",     ["relaxed", "easy fit", "casual fit", "comfort fit"]),
]

def _extract_silhouette(h: str) -> str:
    for sil, terms in _SILHOUETTE_MAP:
        if any(t in h for t in terms):
            return sil
    return "regular"

_FABRIC_MAP = [
    ("denim",     ["denim", "jean", "chambray"]),
    ("leather",   ["leather", "faux leather", "vegan leather", "nappa", "suede"]),
    ("velvet",    ["velvet", "velour"]),
    ("satin",     ["satin", "silk"]),
    ("linen",     ["linen"]),
    ("knit",      ["knit", "knitwear", "jersey", "ribbed", "cable knit", "cashmere", "merino", "wool"]),
    ("cotton",    ["cotton", "poplin", "twill", "oxford cloth", "pique"]),
    ("technical", ["technical", "performance", "moisture-wicking", "quick-dry", "nylon", "polyester", "recycled poly"]),
    ("fleece",    ["fleece", "sherpa"]),
]

def _extract_fabric(h: str) -> str:
    for fabric, terms in _FABRIC_MAP:
        if any(t in h for t in terms):
            return fabric
    return "unknown"

_FORMALITY_MAP = [
    ("black_tie",       ["tuxedo", "black tie", "evening gown", "ball gown", "dinner jacket"]),
    ("formal",          ["formal", "suit", "dress shirt", "evening dress", "gown", "cocktail", "tailored suit"]),
    ("business_casual", ["office", "work", "business", "blazer", "dress trouser", "professional"]),
    ("smart_casual",    ["smart casual", "chino", "overshirt", "polo", "dressy casual"]),
    ("casual",          ["casual", "denim", "t-shirt", "jeans", "hoodie", "sweatshirt", "sneaker", "everyday"]),
    ("loungewear",      ["jogger", "sweatpant", "lounge", "pyjama", "pajama", "tracksuit"]),
]

def _extract_formality(h: str, cat: str) -> str:
    text = h + " " + cat
    for formality, terms in _FORMALITY_MAP:
        if any(t in text for t in terms):
            return formality
    return "casual"


# ── archetype scoring ─────────────────────────────────────────────────────────

def _score_archetypes(h: str, col: str) -> dict:
    """Score all 32 archetypes: 0.75 (both match), 0.40 (one matches), 0 (none)."""
    text = h + " " + col
    results = {}
    for aid in ARCHETYPE_IDS:
        col_name = f"arch_{aid}"
        rules = _ARCHETYPE_RULES.get(aid)
        if not rules:
            results[col_name] = 0.0
            continue
        pattern_hit = any(t in text for t in rules["pattern_terms"])
        color_hit   = any(t in text for t in rules["color_terms"])
        if pattern_hit and color_hit:
            results[col_name] = 0.75
        elif pattern_hit or color_hit:
            results[col_name] = 0.40
        else:
            results[col_name] = 0.0
    return results


# ── per-keyword scoring rules ─────────────────────────────────────────────────

def _tag(product: dict) -> dict:
    h     = _haystack(product)
    col   = _colors_str(product)
    brand = (product.get("brand") or "").lower()
    cat   = (product.get("category") or "").lower()
    is_adidas = brand == "adidas"
    is_zara   = brand == "zara"

    scores: dict[str, float] = {}

    def s(key, val):
        if val > 0:
            scores[key] = round(min(val, 1.0), 2)

    # ── Aesthetic ──────────────────────────────────────────────────────────
    s("minimalist", _score(h,
        ["plain", "simple", "clean-cut", "minimal", "essential", "basic",
         "classic fit", "straight fit"],
        ["classic", "clean", "neat", "understated", "solid"]))

    s("maximalist", _score(h,
        ["embroidered", "embellishment", "sequin", "rhinestone", "beaded",
         "fringe", "ruffle", "ornate", "printed", "patterned"],
        ["print", "pattern", "detail", "decorated", "floral"]))

    s("classic", _score(h,
        ["classic", "timeless", "traditional", "heritage", "regular fit",
         "straight leg", "oxford", "chino", "tailored"],
        ["slim fit", "polo", "stripe", "checked", "structured"]))

    s("avant_garde", _score(h,
        ["asymmetric", "cut-out", "cutout", "deconstructed", "sculptural",
         "architectural", "unconventional", "draped"],
        ["asymmetrical", "unusual", "experimental"]))

    s("streetwear", _score(h,
        ["hoodie", "graphic tee", "streetwear", "jogger", "sweatpant",
         "baggy", "skate", "graffiti", "logo"],
        ["sweatshirt", "cap", "oversized", "sneaker", "trainer"]))
    if is_adidas and _has(h, "hoodie", "sweatshirt", "jogger", "track"):
        s("streetwear", 0.75)

    s("bohemian", _score(h,
        ["boho", "bohemian", "crochet", "embroidered", "ethnic", "paisley",
         "kaftan", "peasant", "macrame", "woven", "folk"],
        ["floral", "flowy", "maxi", "festival", "lace"]))

    s("preppy", _score(h,
        ["polo", "chino", "oxford cloth", "argyle", "madras", "varsity",
         "collegiate", "blazer stripe", "prep"],
        ["stripe", "blazer", "checked", "loafer", "tennis"]))

    s("romantic", _score(h,
        ["lace", "ruffle", "bow", "floral", "feminine", "satin slip",
         "puff sleeve", "smock", "broderie"],
        ["mesh", "delicate", "soft", "flowy", "tiered"]))

    s("edgy", _score(h,
        ["leather", "biker", "moto", "chain", "studded", "punk",
         "distressed", "ripped", "dark wash"],
        ["asymmetric", "graphic", "torn", "destroyed", "black"]))

    # quiet_luxury: text evidence only — no price boost
    s("quiet_luxury", _score(h,
        ["cashmere", "silk", "merino", "tailored", "wool blend", "camel coat"],
        ["structured", "refined", "understated", "premium"]))

    s("coastal", _score(h,
        ["linen", "nautical", "sailor", "stripe navy", "breton", "marine",
         "coastal", "riviera"],
        ["beach", "light", "airy", "stripe", "canvas"]))

    s("dark_academia", _score(h,
        ["tweed", "plaid", "corduroy", "houndstooth", "checked blazer",
         "tartan", "wool plaid", "academic"],
        ["checked", "oxford", "vintage", "dark", "brown"]))

    s("sporty", 0.0)
    if is_adidas:
        s("sporty", 0.9)
    elif _has(h, "sport", "athletic", "activewear", "gym", "workout",
              "running", "training", "fitness", "jersey"):
        s("sporty", 0.8)
    elif _has(h, "track", "polo", "zip", "performance"):
        s("sporty", 0.45)

    # ── Mood ─────────────────────────────────────────────────────────────────
    s("playful", _score(h,
        ["print", "graphic", "colorful", "fun", "cartoon", "novelty",
         "embroidered patch", "polka dot", "tie dye"],
        ["pattern", "floral", "stripe", "bright"]))

    s("serious", _score(h,
        ["tailored", "suit", "formal", "business", "structured", "sharp"],
        ["blazer", "trouser", "monochrome", "pressed"]))

    s("rebellious", _score(h,
        ["ripped", "distressed", "destroyed", "punk", "chain", "studded",
         "graphic slogan", "combat", "biker"],
        ["leather", "dark", "grunge", "torn"]))

    s("elegant", _score(h,
        ["silk", "satin", "velvet", "lace", "evening", "gown", "cocktail",
         "formal dress", "chiffon"],
        ["flowy", "draped", "embellished", "jewel"]))

    s("laid_back", _score(h,
        ["relaxed", "easy fit", "loose fit", "loungewear", "jogger",
         "sweatshirt", "hoodie", "casual", "comfy"],
        ["linen", "cotton", "soft", "wide leg"]))

    s("bold", _score(h,
        ["bold", "statement", "sequin", "neon", "oversized print",
         "graphic", "vibrant", "vivid"],
        ["print", "pattern", "bright", "colorful"]))

    s("understated", _score(h,
        ["plain", "minimal", "subtle", "understated", "simple", "clean"],
        ["neutral", "basic", "solid", "quiet"]))

    s("whimsical", _score(h,
        ["floral print", "embroidered flower", "puff", "bow", "ruffle",
         "fun print", "playful", "novelty"],
        ["floral", "print", "pattern", "cute"]))

    s("polished", _score(h,
        ["tailored", "blazer", "trouser", "shirt crisp", "structured",
         "pressed", "professional"],
        ["slim fit", "clean", "neat", "smart"]))

    s("raw", _score(h,
        ["raw denim", "raw hem", "raw edge", "distressed", "washed",
         "worn", "faded", "unfinished"],
        ["denim", "dark wash", "worn-in"]))

    # ── Color palette ─────────────────────────────────────────────────────────
    all_text = h + " " + col

    s("neutral", _score(all_text,
        ["beige", "camel", "ecru", "ivory", "cream", "sand", "taupe",
         "nude", "off-white", "oat", "khaki"],
        ["grey", "gray", "tan", "stone", "bone"]))

    s("monochrome", _score(all_text,
        ["monochrome", "tonal", "all-black", "all-white", "tone on tone"],
        ["black and white", "black/white"]))

    s("earth_tones", _score(all_text,
        ["terracotta", "rust", "burnt orange", "mustard", "olive",
         "forest green", "chocolate", "cognac"],
        ["brown", "tan", "earthy", "warm"]))

    s("pastel", _score(all_text,
        ["pastel", "lilac", "lavender", "mint", "blush", "baby blue",
         "powder", "soft pink", "light pink"],
        ["pale", "light blue", "dusty"]))

    s("bold_colors", _score(all_text,
        ["electric blue", "neon", "vivid", "cobalt", "scarlet", "fuchsia",
         "hot pink", "bright red", "lime green"],
        ["red", "yellow", "orange", "bright"]))

    if "black" in all_text:
        s("black_forward", 0.9)

    if _has(all_text, "white", "ecru", "ivory", "off-white", "cream"):
        s("white_forward", 0.85)

    s("jewel_tones", _score(all_text,
        ["emerald", "sapphire", "ruby", "burgundy", "deep purple",
         "teal", "forest", "wine", "oxblood"],
        ["deep", "rich", "jewel", "purple", "green"]))

    s("multicolor", _score(all_text,
        ["multicolour", "multicolor", "multi-colour", "tie dye",
         "colour-block", "color block", "patchwork"],
        ["print", "pattern", "stripe", "plaid", "checked", "floral"]))

    # ── Formality ─────────────────────────────────────────────────────────────
    s("loungewear", _score(h,
        ["jogger", "sweatpant", "lounge", "pyjama", "pajama",
         "tracksuit", "fleece", "lounge pants"],
        ["hoodie", "sweatshirt", "cozy", "comfortable"]))

    s("casual", _score(h,
        ["casual", "denim", "t-shirt", "jeans", "hoodie", "sweatshirt",
         "sneaker", "polo shirt", "chino casual"],
        ["everyday", "relaxed", "laid-back", "basic"]))

    s("smart_casual", _score(h,
        ["smart casual", "chino", "polo", "overshirt", "blazer casual",
         "dressy casual"],
        ["smart", "neat", "crisp shirt"]))

    s("business_casual", _score(h,
        ["office", "work", "business", "formal shirt", "dress trouser",
         "blazer", "suit separate"],
        ["professional", "meeting", "structured"]))

    s("formal", _score(h,
        ["formal", "suit", "tuxedo", "dress shirt", "evening dress",
         "gown", "cocktail", "tailored suit"],
        ["black tie", "ceremony", "occasion dress"]))

    s("black_tie", _score(h,
        ["tuxedo", "black tie", "evening gown", "formal gown",
         "dinner jacket", "ball gown"],
        ["evening", "gala", "ceremony formal"]))

    # ── Cultural ──────────────────────────────────────────────────────────────
    s("parisian", _score(h,
        ["breton", "beret", "french", "parisian", "chic",
         "marinière", "striped top"],
        ["stripe", "silk scarf", "tailored", "chic"]))

    s("scandinavian", _score(h,
        ["nordic", "scandinavian", "hygge", "minimal nordic", "clean design"],
        ["minimal", "clean", "simple", "functional"]))

    # italian_luxury: text evidence only — no price boost
    s("italian_luxury", _score(h,
        ["italian", "milan", "linen italian", "cashmere italian"],
        ["luxe", "premium", "artisan"]))

    s("japanese_minimalist", _score(h,
        ["japanese", "wabi", "sabi", "kyoto", "minimal japanese"],
        ["asymmetric", "minimal", "monochrome", "clean cut"]))

    s("american_prep", _score(h,
        ["prep", "ivy league", "collegiate", "varsity", "polo",
         "oxford cloth", "madras", "american"],
        ["chino", "blazer", "stripe", "loafer"]))

    s("british_heritage", _score(h,
        ["tartan", "tweed", "houndstooth", "trench", "checked wool",
         "heritage", "pea coat", "british"],
        ["plaid", "checked", "wool coat", "classic British"]))

    s("nyc_streetwear", _score(h,
        ["streetwear", "graphic tee", "ny", "new york", "skate",
         "graffiti", "basketball"],
        ["hoodie", "oversized", "baggy", "logo"]))
    if is_adidas and _has(h, "hoodie", "cap", "graphic"):
        s("nyc_streetwear", max(scores.get("nyc_streetwear", 0), 0.5))

    s("californian", _score(h,
        ["californian", "surf", "venice", "la style", "west coast"],
        ["linen", "beach", "relaxed", "denim", "casual"]))

    # ── Silhouette ────────────────────────────────────────────────────────────
    s("fitted", _score(h,
        ["fitted", "slim fit", "skinny", "tight", "bodycon",
         "close-fitting", "form-fitting"],
        ["slim", "narrow", "tapered"]))

    s("oversized", _score(h,
        ["oversized", "baggy", "boxy", "wide fit", "loose fit",
         "relaxed fit", "extra large"],
        ["wide", "roomy", "big fit"]))

    s("structured", _score(h,
        ["structured", "tailored", "padded shoulder", "boned", "corseted",
         "stiff", "crisp"],
        ["blazer", "suit", "formal", "sharp"]))

    s("flowy", _score(h,
        ["flowy", "fluid", "draped", "chiffon", "georgette",
         "floaty", "billowy"],
        ["loose", "soft", "silk", "flowing"]))

    s("layered", _score(h,
        ["layer", "layered", "over", "underneath", "multi-layer",
         "sheer over"],
        ["vest", "gilet", "overshirt"]))

    s("cropped", _score(h,
        ["crop", "cropped", "midriff", "belly", "short top"],
        ["boxy short", "cut-off"]))

    s("voluminous", _score(h,
        ["volume", "puff", "balloon", "full skirt", "flared",
         "wide leg", "pleated", "tiered"],
        ["gathered", "ruffle", "maxi skirt"]))

    # ── Occasion ──────────────────────────────────────────────────────────────
    s("everyday", _score(h,
        ["everyday", "daily", "casual", "basic", "essential"],
        ["t-shirt", "jeans", "simple", "easy"]))

    s("workwear", _score(h,
        ["office", "work", "professional", "business", "corporate",
         "meeting", "desk to dinner"],
        ["blazer", "trouser", "formal", "structured"]))

    s("going_out", _score(h,
        ["evening", "night out", "party", "cocktail", "club",
         "sequin", "going out", "date night"],
        ["glam", "dressy", "mini dress", "bodycon"]))

    s("travel", _score(h,
        ["travel", "wrinkle", "crease-resistant", "pack", "lightweight",
         "easy care", "versatile"],
        ["comfortable", "functional", "easy"]))

    s("outdoor", _score(h,
        ["outdoor", "hiking", "windproof", "waterproof", "rain",
         "technical", "trail", "mountain"],
        ["performance", "durable", "functional"]))

    s("sport", 0.0)
    if is_adidas:
        s("sport", 0.95)
    elif _has(h, "sport", "gym", "workout", "training", "running",
              "athletic", "fitness", "activewear"):
        s("sport", 0.85)

    s("beach", _score(h,
        ["beach", "swim", "swimwear", "surf", "holiday", "resort",
         "poolside", "vacation"],
        ["linen", "stripe", "tropical", "sun"]))

    s("occasion", _score(h,
        ["occasion", "wedding", "gala", "ceremony", "evening dress",
         "formal event", "black tie", "prom"],
        ["cocktail", "formal", "special", "celebration"]))

    # ── Values ────────────────────────────────────────────────────────────────
    s("sustainable", _score(h,
        ["organic", "recycled", "sustainable", "eco-friendly",
         "responsible", "join life", "oeko-tex", "tencel", "lyocell"],
        ["natural", "linen", "hemp", "bamboo"]))

    # investment_piece: text evidence only — no price boost
    s("investment_piece", _score(h,
        ["cashmere", "silk", "merino wool", "leather coat", "camel coat",
         "investment", "timeless piece"],
        ["wool coat", "quality", "enduring"]))

    s("trend_driven", 0.0)
    if is_zara:
        s("trend_driven", 0.7)
    elif _has(h, "trending", "new arrival", "season", "limited edition"):
        s("trend_driven", 0.6)

    s("heritage_craft", _score(h,
        ["handmade", "hand-stitched", "artisan", "craft", "heritage",
         "hand-woven", "hand-embroidered"],
        ["traditional", "vintage", "archive"]))

    # luxury_status and budget_conscious: text evidence only — no price boost
    s("luxury_status", _score(h,
        ["cashmere", "silk", "couture", "bespoke", "hand-finished", "italian"],
        ["premium", "refined", "exclusive"]))

    s("budget_conscious", _score(h,
        ["value", "affordable", "budget", "price", "basic essential"],
        ["simple", "everyday basic"]))

    s("logo_forward", _score(h,
        ["logo", "branded", "slogan", "graphic print brand",
         "embossed logo", "label"],
        ["print logo", "brand print"]))
    if is_adidas and _has(h, "logo", "trefoil", "3-stripe", "three stripe"):
        s("logo_forward", 0.85)

    # logo_free dropped — near-constant, dilutes cosine similarity

    s("size_inclusive", _score(h,
        ["plus size", "extended size", "size inclusive", "curve",
         "all sizes", "large sizes"],
        ["plus", "xl", "xxl"]))

    s("gender_neutral", _score(h,
        ["unisex", "gender neutral", "gender-free", "non-binary",
         "genderless"],
        ["gender fluid"]))

    s("performance_tech", _score(h,
        ["performance", "moisture-wicking", "breathable", "quick-dry",
         "compression", "technical", "dri-fit", "climacool", "aeroready"],
        ["stretch", "functional", "active"]))
    if is_adidas:
        s("performance_tech", max(scores.get("performance_tech", 0), 0.65))

    # ── Pattern ───────────────────────────────────────────────────────────
    s("floral_print", _score(h,
        ["floral", "flower", "botanical", "rose print", "daisy"],
        ["bloom", "petal"]))

    s("striped_pattern", _score(h,
        ["stripe", "striped", "breton", "pinstripe", "nautical stripe"],
        ["band", "linear"]))

    s("checked_pattern", _score(h,
        ["check", "checked", "plaid", "tartan", "gingham", "houndstooth",
         "vichy", "windowpane"],
        ["grid", "lattice"]))

    s("animal_print", _score(h,
        ["leopard", "zebra", "snake", "crocodile", "tiger", "animal print",
         "python", "jaguar"],
        ["animal", "wild print"]))

    s("abstract_print", _score(h,
        ["abstract", "geometric print", "tie dye", "marble", "watercolour",
         "patchwork", "motif"],
        ["pattern", "printed"]))

    _has_pattern = any(scores.get(k, 0) > 0.3 for k in [
        "floral_print", "striped_pattern", "checked_pattern",
        "animal_print", "abstract_print", "multicolor"
    ])
    if not _has_pattern:
        s("solid_color", 0.75)

    # ── Material ─────────────────────────────────────────────────────────
    s("denim_fabric", _score(h,
        ["denim", "jean", "chambray"],
        ["washed", "indigo"]))

    s("linen_fabric", _score(h,
        ["linen", "linen blend", "linen-blend"],
        ["natural fibre", "breathable"]))

    s("velvet_fabric", _score(h,
        ["velvet", "crushed velvet", "velour"],
        []))

    s("satin_fabric", _score(h,
        ["satin", "silk satin", "polished"],
        ["slip", "glossy", "shiny"]))

    s("leather_fabric", _score(h,
        ["leather", "faux leather", "vegan leather", "nappa"],
        ["patent", "suede"]))

    s("knitwear_fabric", _score(h,
        ["knit", "knitwear", "jersey", "ribbed", "cable knit", "cashmere",
         "merino", "wool", "jumper", "cardigan", "sweater"],
        ["cosy", "chunky", "fine knit"]))

    # ── Length ───────────────────────────────────────────────────────────
    s("mini_length", _score(h,
        ["mini", "micro", "short dress", "short skirt"],
        ["above knee", "thigh"]))

    s("midi_length", _score(h,
        ["midi", "mid-length", "calf-length", "below knee"],
        ["mid length", "tea length"]))

    s("maxi_length", _score(h,
        ["maxi", "full length", "floor length", "long dress", "long skirt"],
        ["ankle length", "sweeping"]))

    # ── Key design detail ─────────────────────────────────────────────────
    s("ruffled", _score(h,
        ["ruffle", "ruffled", "frill", "frilled", "flounce"],
        ["tiered", "layered hem"]))

    s("belted", _score(h,
        ["belt", "belted", "tied waist", "sash", "obi"],
        ["cinched", "waist tie"]))

    s("crochet_detail", _score(h,
        ["crochet", "crochet trim", "macrame"],
        ["open weave", "hand-crafted"]))

    s("embroidered_detail", _score(h,
        ["embroidered", "embroidery", "embroidered patch", "needlework"],
        ["cross stitch", "stitched"]))

    s("pleated_detail", _score(h,
        ["pleat", "pleated", "accordion", "knife pleat", "box pleat"],
        ["gathered", "smocked"]))

    # ── Color specifics ───────────────────────────────────────────────────
    s("burgundy_wine", _score(h,
        ["burgundy", "wine", "bordeaux", "merlot", "maroon", "oxblood"],
        ["deep red", "dark red"]))

    s("camel_tan", _score(h,
        ["camel", "tan", "toffee", "biscuit", "sand", "ecru beige"],
        ["warm beige", "light brown"]))

    s("cobalt_blue", _score(h,
        ["cobalt", "electric blue", "royal blue", "sapphire", "cerulean"],
        ["bright blue", "vivid blue"]))

    s("forest_green", _score(h,
        ["forest green", "bottle green", "hunter green", "dark green", "pine"],
        ["deep green", "moss green"]))

    s("blush_pink", _score(h,
        ["blush", "rose", "dusty pink", "powder pink", "ballet pink"],
        ["pale pink", "soft pink"]))

    s("cream_ivory", _score(h,
        ["cream", "ivory", "off-white", "ecru", "eggshell", "vanilla"],
        ["off white", "warm white"]))

    s("olive_khaki", _score(h,
        ["olive", "khaki", "army green", "military green", "sage"],
        ["earthy green", "muted green"]))

    s("rust_orange", _score(h,
        ["rust", "burnt orange", "terracotta", "clay", "brick", "copper"],
        ["warm orange", "amber"]))

    # ── Silhouette extras ─────────────────────────────────────────────────
    s("wide_leg", _score(h,
        ["wide leg", "wide-leg", "palazzo", "flared", "flare leg", "bootcut"],
        ["wide cut", "relaxed leg"]))

    s("slim_cut", _score(h,
        ["slim", "skinny", "tapered", "narrow leg", "cigarette"],
        ["slim fit", "tight leg"]))

    s("high_waist", _score(h,
        ["high waist", "high-waist", "high rise", "high-rise", "paperbag waist"],
        ["waist high", "elevated waist"]))

    s("tailored_cut", _score(h,
        ["tailored", "bespoke", "sharp cut", "precision cut", "constructed"],
        ["sharp silhouette", "clean lines"]))

    s("balloon_sleeve", _score(h,
        ["balloon sleeve", "puff sleeve", "bishop sleeve", "lantern sleeve",
         "bubble sleeve"],
        ["voluminous sleeve", "gathered sleeve"]))

    # ── Occasion nuance ───────────────────────────────────────────────────
    s("date_night", _score(h,
        ["date night", "evening out", "night out", "romantic evening"],
        ["evening wear", "going out"]))

    s("cocktail", _score(h,
        ["cocktail", "party dress", "event dress", "celebration", "gala"],
        ["semi-formal", "dressy"]))

    s("brunch", _score(h,
        ["brunch", "weekend brunch", "casual lunch", "garden party"],
        ["daytime social", "relaxed chic"]))

    s("festival_wear", _score(h,
        ["festival", "boho festival", "coachella", "outdoor festival"],
        ["music festival", "summer festival"]))

    s("office_ready", _score(h,
        ["office", "work wear", "professional", "boardroom", "corporate"],
        ["desk to dinner", "9 to 5"]))

    s("transitional", _score(h,
        ["transitional", "layering piece", "between seasons", "spring-autumn",
         "all season"],
        ["versatile", "seasonless"]))

    # ── Texture / fabric detail ───────────────────────────────────────────
    s("sheer_fabric", _score(h,
        ["sheer", "transparent", "see-through", "mesh overlay", "chiffon",
         "organza", "tulle"],
        ["lightweight", "floaty"]))

    s("mesh_detail", _score(h,
        ["mesh", "fishnet", "net fabric", "open knit", "lattice fabric"],
        ["cut-out mesh", "mesh insert"]))

    s("ribbed_texture", _score(h,
        ["ribbed", "rib knit", "ribbed knit", "waffle", "textured knit"],
        ["rib fabric", "stretch rib"]))

    s("quilted_detail", _score(h,
        ["quilted", "padded", "diamond quilt", "channel quilt"],
        ["puffer", "insulated"]))

    s("faux_fur_trim", _score(h,
        ["faux fur", "fake fur", "fluffy trim", "teddy", "shearling"],
        ["fur trim", "fluffy"]))

    s("distressed_finish", _score(h,
        ["distressed", "washed", "faded", "bleached", "worn", "vintage wash",
         "acid wash"],
        ["raw hem", "frayed"]))

    s("woven_texture", _score(h,
        ["woven", "jacquard", "tweed", "boucle", "twill", "herringbone",
         "houndstooth weave"],
        ["textured weave", "structured weave"]))

    s("technical_fabric", _score(h,
        ["technical", "neoprene", "scuba", "nylon", "ripstop", "gore-tex",
         "recycled polyester", "spandex blend"],
        ["performance fabric", "stretch fabric"]))

    # ── Construction detail ───────────────────────────────────────────────
    s("wrap_style", _score(h,
        ["wrap", "wrap dress", "wrap top", "wrap skirt", "sarong", "cross-over"],
        ["crossover", "tied front"]))

    s("cutout_detail", _score(h,
        ["cutout", "cut-out", "keyhole", "open back", "bare shoulder",
         "midriff cutout"],
        ["peekaboo", "exposed"]))

    s("asymmetric_hem", _score(h,
        ["asymmetric", "asymmetrical", "one shoulder", "one sleeve",
         "uneven hem", "diagonal hem"],
        ["off-shoulder asymm", "draped asymm"]))

    s("tie_waist", _score(h,
        ["tie waist", "tie-waist", "self-tie", "sash tie", "drawstring waist",
         "bow waist"],
        ["waist tie", "knotted"]))

    s("puff_sleeve", _score(h,
        ["puff sleeve", "puffy sleeve", "puffed sleeve", "bubble sleeve",
         "gigot sleeve"],
        ["volume sleeve", "gathered sleeve"]))

    # ── Aesthetic sub-genres ──────────────────────────────────────────────
    s("clean_girl", _score(h,
        ["clean girl", "clean aesthetic", "no-makeup makeup", "effortless"],
        ["minimal", "fresh", "natural"]))

    s("ballet_aesthetic", _score(h,
        ["ballet", "ballerina", "tutu", "pointe", "dance wrap"],
        ["wrap skirt", "satin ribbon", "dance"]))

    s("coquette_style", _score(h,
        ["coquette", "bow detail", "ribbon trim", "babydoll", "lolita"],
        ["romantic detail", "feminine bow"]))

    s("tomboy_chic", _score(h,
        ["boyfriend", "tomboy", "gender-free", "relaxed straight"],
        ["oversized fit", "unisex", "straight leg"]))

    s("androgynous_look", _score(h,
        ["androgynous", "gender fluid", "unisex cut", "non-binary"],
        ["gender neutral", "fluid"]))

    s("soft_glamour", _score(h,
        ["soft glamour", "draped", "goddess", "bias cut"],
        ["soft satin", "flowing", "luxe drape"]))

    s("indie_style", _score(h,
        ["indie", "thrift", "vintage-inspired", "retro print"],
        ["indie brand", "alternative"]))

    s("coastal_grandmother", _score(h,
        ["coastal", "linen shirt", "relaxed linen", "nautical stripe"],
        ["beach linen", "navy stripe", "rope detail"]))

    s("dopamine_dressing", _score(h,
        ["colour pop", "vibrant", "neon", "fun colour", "bright hue"],
        ["bold colour", "happy colour"]))

    s("quiet_opulence", _score(h,
        ["cashmere", "merino", "fine wool", "understated luxury", "pure silk"],
        ["premium fabric", "luxe", "refined"]))

    s("power_dressing", _score(h,
        ["power suit", "sharp blazer", "structured blazer", "strong shoulder",
         "authority"],
        ["tailored", "executive", "boardroom"]))

    s("artsy_downtown", _score(h,
        ["artistic", "gallery", "downtown", "art print", "abstract design"],
        ["creative", "expressive"]))

    s("retro_seventies", _score(h,
        ["70s", "seventies", "flared", "bell-bottom", "boho 70", "retro 70"],
        ["vintage 70", "disco", "peasant blouse"]))

    s("retro_nineties", _score(h,
        ["90s", "nineties", "slip dress", "grunge 90", "retro 90"],
        ["vintage 90", "90s inspired"]))

    s("y2k_inspired", _score(h,
        ["y2k", "2000s", "early 2000", "cyber", "rhinestone"],
        ["early aughts", "2000 inspired"]))

    s("futuristic_style", _score(h,
        ["futuristic", "sci-fi", "metallic", "chrome", "space age"],
        ["technical", "architectural"]))

    s("boho_luxe", _score(h,
        ["boho", "bohemian luxe", "embroidered kaftan", "luxury boho"],
        ["free spirit", "artisanal"]))

    s("mob_wife_glam", _score(h,
        ["faux fur", "leopard", "gold chain", "bold animal", "plunging"],
        ["statement fur", "maximalist glam"]))

    s("stealth_wealth", _score(h,
        ["quiet luxury", "understated", "cashmere coat", "cream wool"],
        ["subtle", "luxe minimal"]))

    s("avant_minimalist", _score(h,
        ["deconstructed", "architectural", "asymmetric cut", "avant-garde minimal"],
        ["conceptual", "sculptural"]))

    # ── Mood extras ───────────────────────────────────────────────────────
    s("dramatic", _score(h,
        ["dramatic", "statement", "bold silhouette", "theatrical", "show-stopping"],
        ["striking", "powerful"]))

    s("ethereal", _score(h,
        ["ethereal", "dreamy", "cloud", "angelic", "gossamer", "organza"],
        ["soft", "delicate", "whimsical"]))

    s("sensual", _score(h,
        ["sensual", "body-con", "slit", "plunging", "cutout", "bodysuit"],
        ["revealing", "alluring", "sultry"]))

    s("nostalgic", _score(h,
        ["nostalgic", "vintage", "retro", "throwback", "archive"],
        ["classic revival", "heirloom"]))

    s("futuristic_mood", _score(h,
        ["futuristic", "tech", "chrome", "metallic sheen", "holographic"],
        ["modern", "forward"]))

    # ── Color palette extras ───────────────────────────────────────────────
    s("neon_accent", _score(h + " " + col,
        ["neon", "fluorescent", "electric lime", "acid yellow", "hot neon"],
        ["bright accent", "vivid"]))

    s("pastel_rainbow", _score(h + " " + col,
        ["pastel rainbow", "multicolour pastel", "candy colour", "pastel mix"],
        ["soft rainbow", "colourful pastel"]))

    s("gradient_dye", _score(h + " " + col,
        ["gradient", "ombre wash", "dip dye", "colour fade", "colour wash"],
        ["fade", "wash effect"]))

    s("burnout_print", _score(h,
        ["burnout", "devore", "burn-out velvet", "velvet burnout"],
        []))

    s("ikat_pattern", _score(h,
        ["ikat", "ikat print", "woven ikat"],
        []))

    # ── Color specifics (use both haystack and colors field) ───────────────
    hc = h + " " + col

    s("stone_grey",      _score(hc, ["stone grey","stone gray","stone","pebble","flint"],    ["grey stone","warm grey"]))
    s("dusty_mauve",     _score(hc, ["mauve","dusty rose","dusty pink","antique rose"],      ["muted pink","rose grey"]))
    s("warm_taupe",      _score(hc, ["taupe","warm taupe","greige","mocha beige"],           ["warm beige","taupe"]))
    s("slate_blue",      _score(hc, ["slate","slate blue","slate grey","denim blue"],        ["mid blue","steel blue"]))
    s("powder_blue",     _score(hc, ["powder blue","baby blue","sky blue","pale blue"],      ["light blue","icy blue"]))
    s("mint_green",      _score(hc, ["mint","mint green","seafoam","aquamint"],              ["light green","fresh green"]))
    s("lilac_purple",    _score(hc, ["lilac","pale purple","soft purple","lavender purple"], ["light purple","pastel purple"]))
    s("sage_green",      _score(hc, ["sage","sage green","herbal green","muted green"],      ["soft green","earthy green"]))
    s("mustard_yellow",  _score(hc, ["mustard","ochre","golden ochre","mustard yellow"],     ["yellow ochre","warm yellow"]))
    s("coral_pink",      _score(hc, ["coral","coral pink","warm coral","peach coral"],       ["warm pink","salmon"]))
    s("teal_green",      _score(hc, ["teal","teal green","turquoise","peacock"],             ["blue-green","aqua teal"]))
    s("charcoal_grey",   _score(hc, ["charcoal","dark grey","charcoal grey","anthracite"],   ["deep grey","graphite"]))
    s("navy_blue",       _score(hc, ["navy","navy blue","marine","midnight navy","dark navy"],["deep blue","ink blue"]))
    s("silver_tone",     _score(hc, ["silver","silver grey","metallic silver","argent"],     ["light silver","cool silver"]))
    s("golden_yellow",   _score(hc, ["golden","gold yellow","sunflower","marigold","saffron"],["warm gold","bright yellow"]))
    s("deep_purple",     _score(hc, ["purple","deep purple","violet","plum","aubergine"],    ["dark purple","rich purple"]))
    s("hot_pink",        _score(hc, ["hot pink","fuchsia","magenta","neon pink","shocking pink"],["bright pink","vivid pink"]))
    s("champagne_gold",  _score(hc, ["champagne","ecru gold","pale gold","golden beige"],    ["light gold","warm cream"]))
    s("midnight_blue",   _score(hc, ["midnight blue","deep navy","midnight","ink"],          ["very dark blue","almost black blue"]))
    s("chocolate_brown", _score(hc, ["chocolate","dark brown","espresso","coffee brown"],    ["deep brown","rich brown"]))
    s("nude_pink",       _score(hc, ["nude","skin tone","blush nude","beige pink","nude pink"],["skin","barely there"]))
    s("jade_green",      _score(hc, ["jade","jade green","emerald","hunter","bottle green"], ["rich green","deep green"]))
    s("indigo_blue",     _score(hc, ["indigo","dark indigo","deep indigo"],                  ["deep denim","blue indigo"]))
    s("fuchsia_pink",    _score(hc, ["fuchsia","magenta pink","hot fuchsia","vivid fuchsia"],["bright fuchsia","pink fuchsia"]))
    s("lavender_haze",   _score(hc, ["lavender","lavender haze","pale lavender","soft lavender"],["light lavender","lilac haze"]))
    s("amber_gold",      _score(hc, ["amber","honey","cognac","warm amber","toffee"],        ["golden amber","amber tone"]))
    s("smoky_grey",      _score(hc, ["grey","gray","smoke grey","medium grey","cool grey"],  ["grey tone","smoky"]))
    s("copper_bronze",   _score(hc, ["copper","bronze","metallic copper","warm copper"],     ["copper tone","bronze sheen"]))
    s("pearl_white",     _score(hc, ["pearl","pearlescent","pearl white","opalescent"],      ["shimmery white","pearl tone"]))
    s("burnt_sienna",    _score(hc, ["sienna","burnt sienna","brick red","terracotta red"],  ["warm sienna","red clay"]))

    # ── Cultural extras ───────────────────────────────────────────────────
    s("korean_minimal", _score(h,
        ["korean", "k-style", "korean fashion", "seoul"],
        ["k-pop","korean minimal"]))

    s("french_riviera", _score(h,
        ["riviera","côte d'azur","saint tropez","cannes","nice style"],
        ["french coast","mediterranean chic"]))

    s("milan_chic", _score(h,
        ["milan","milanese","italian chic","made in italy"],
        ["milan fashion","italian elegance"]))

    s("mediterranean_style", _score(h,
        ["mediterranean","greek","aegean","ibiza","santorini"],
        ["island style","sunny style"]))

    s("australian_surf", _score(h,
        ["australian","aussie","surf brand","bondi","beach surf"],
        ["surf culture","ocean wear"]))

    s("east_london", _score(h,
        ["east london","hackney","shoreditch","dalston","brixton"],
        ["london street","urban london"]))

    s("tokyo_street", _score(h,
        ["tokyo","harajuku","shibuya","japanese street","osaka"],
        ["japanese fashion","j-fashion"]))

    s("brooklyn_cool", _score(h,
        ["brooklyn","new york cool","ny downtown","williamsburg"],
        ["ny style","brooklyn vibes"]))

    s("porto_casual", _score(h,
        ["portuguese","porto","lisbon","azulejo","atlantic coast"],
        []))

    s("rio_beach", _score(h,
        ["rio","brazilian","copacabana","ipanema","beach brazil"],
        ["tropical beach","brazil"]))

    # ── Silhouette cut extras ─────────────────────────────────────────────
    s("a_line", _score(h,
        ["a-line","a line dress","a-line skirt","flared hem","princess line"],
        ["flared","swing dress"]))

    s("shift_silhouette", _score(h,
        ["shift dress","shift silhouette","straight shift","boxy dress"],
        ["shift cut","loose shift"]))

    s("bodycon", _score(h,
        ["bodycon","body-con","body con","bandage dress","tight fit",
         "figure-hugging","second skin"],
        ["stretch fit","form fitting"]))

    s("empire_waist", _score(h,
        ["empire waist","empire-waist","high waist empire","babydoll waist"],
        ["raised waist","under-bust"]))

    s("pencil_cut", _score(h,
        ["pencil skirt","pencil dress","pencil cut","column skirt"],
        ["tube skirt","straight skirt"]))

    s("column_silhouette", _score(h,
        ["column dress","column silhouette","straight cut gown","pillar dress"],
        ["straight gown","sleek column"]))

    s("cape_silhouette", _score(h,
        ["cape","capelet","cape sleeve","poncho","cape back"],
        ["cape-style","draped cape"]))

    s("mermaid_cut", _score(h,
        ["mermaid","fishtail","trumpet dress","fit and flare gown"],
        ["mermaid gown","flared bottom"]))

    s("trapeze_cut", _score(h,
        ["trapeze","tent dress","a-line tent","flared from shoulder"],
        ["swing coat","trapeze silhouette"]))

    s("boxy_cut", _score(h,
        ["boxy","box cut","boxy fit","square fit","boxy top"],
        ["boxy shape","square silhouette"]))

    # ── Neckline ──────────────────────────────────────────────────────────
    s("v_neck", _score(h,
        ["v-neck","v neck","v-neckline","deep v","plunge v"],
        ["v shape neck","vneck"]))

    s("turtleneck", _score(h,
        ["turtleneck","polo neck","roll neck","roll-neck","cowl roll"],
        ["high neck","funnel roll"]))

    s("crewneck", _score(h,
        ["crew neck","crewneck","round neck","crew-neck"],
        ["round neckline","classic neck"]))

    s("off_shoulder", _score(h,
        ["off shoulder","off-shoulder","bardot","cold shoulder top","bare shoulder"],
        ["shoulder off","exposed shoulder"]))

    s("halter_neck", _score(h,
        ["halter","halter neck","halter-neck","halter top","halterneck"],
        ["neck tie","neck strap"]))

    s("boat_neck", _score(h,
        ["boat neck","bateau","boat-neck","breton neck","wide neckline"],
        ["wide neck","horizontal neck"]))

    s("square_neck", _score(h,
        ["square neck","square neckline","square-neck"],
        ["box neck","straight neckline"]))

    s("cowl_neck", _score(h,
        ["cowl neck","cowl-neck","drape neck","draped neckline","cascade neck"],
        ["draped neck","cowl drape"]))

    s("mock_neck", _score(h,
        ["mock neck","mock-neck","funnel neck","mock turtleneck","stand collar"],
        ["short turtleneck","funnel top"]))

    s("one_shoulder", _score(h,
        ["one shoulder","one-shoulder","single shoulder","asymmetric shoulder"],
        ["one arm","single strap top"]))

    s("scoop_neck", _score(h,
        ["scoop neck","scoop-neck","u-neck","curved neckline","low scoop"],
        ["wide scoop","u neckline"]))

    s("sweetheart_neckline", _score(h,
        ["sweetheart","sweetheart neckline","heart neckline","sweetheart top"],
        ["heart-shaped neck","sweetheart cut"]))

    # ── Sleeve ────────────────────────────────────────────────────────────
    s("long_sleeve", _score(h,
        ["long sleeve","long-sleeve","full sleeve","full-length sleeve"],
        ["longsleeve","full arm"]))

    s("short_sleeve", _score(h,
        ["short sleeve","short-sleeve","half sleeve","t-shirt sleeve"],
        ["short arm","short-sleeved"]))

    s("sleeveless", _score(h,
        ["sleeveless","without sleeves","no sleeve","tank","vest top","singlet"],
        ["armless","strappy top"]))

    s("three_quarter_sleeve", _score(h,
        ["3/4 sleeve","three quarter sleeve","3/4-sleeve","bracelet sleeve"],
        ["mid-length sleeve","elbow sleeve"]))

    s("raglan_sleeve", _score(h,
        ["raglan","raglan sleeve","baseball sleeve"],
        ["sporty sleeve","two-tone sleeve"]))

    s("dolman_sleeve", _score(h,
        ["dolman","batwing","dolman sleeve","batwing sleeve"],
        ["wide sleeve","drape sleeve"]))

    s("cap_sleeve", _score(h,
        ["cap sleeve","cap-sleeve","flutter cap","tiny sleeve"],
        ["short cap","minimal sleeve"]))

    s("flutter_sleeve", _score(h,
        ["flutter sleeve","flutter-sleeve","butterfly sleeve","frill sleeve"],
        ["ruffle sleeve","soft sleeve"]))

    s("cold_shoulder", _score(h,
        ["cold shoulder","cold-shoulder","cut-out shoulder","open shoulder"],
        ["shoulder cutout","shoulder opening"]))

    s("dropped_shoulder", _score(h,
        ["drop shoulder","dropped shoulder","off-the-shoulder drop","relaxed shoulder"],
        ["low shoulder","wide shoulder"]))

    # ── Occasion extras ───────────────────────────────────────────────────
    s("gym_wear", _score(h,
        ["gym","fitness","workout","training","exercise"],
        ["active","sport wear"]))
    if is_adidas:
        s("gym_wear", max(scores.get("gym_wear", 0), 0.6))

    s("yoga_wear", _score(h,
        ["yoga","pilates","studio","flow","namaste"],
        ["stretch","mindful"]))

    s("running_wear", _score(h,
        ["running","jogging","marathon","run","race day"],
        ["sprint","track"]))
    if is_adidas and _has(h, "running","run","marathon","jogging"):
        s("running_wear", 0.9)

    s("swim_wear", _score(h,
        ["swim","swimwear","bikini","swimsuit","bathing","one-piece swim"],
        ["beach wear","pool"]))

    s("resort_wear", _score(h,
        ["resort","vacation wear","holiday","cruise","beach resort"],
        ["getaway","sun holiday"]))

    s("evening_wear", _score(h,
        ["evening","gala","evening gown","night event","evening dress"],
        ["evening wear","formal event"]))

    s("wedding_guest", _score(h,
        ["wedding","bridal party","garden party","guest dress"],
        ["occasion dress","special event"]))

    s("party_wear", _score(h,
        ["party","celebration","festive","new year","holiday party"],
        ["party dress","fun night"]))

    s("work_from_home", _score(h,
        ["wfh","work from home","home office","comfortable work"],
        ["casual office","relaxed workwear"]))

    s("ski_wear", _score(h,
        ["ski","snowboard","slope","mountain sport","snow sport"],
        ["winter outdoor","apres ski"]))

    s("activewear_set", _score(h,
        ["matching set","co-ord set","two-piece set","co-ord","coordinating set",
         "bike short set","legging set"],
        ["set","co-ord"]))

    s("capsule_piece", _score(h,
        ["capsule","essential","wardrobe staple","everyday essential"],
        ["versatile","basic"]))

    s("night_out", _score(h,
        ["night out","club","bar outfit","going out","nights out"],
        ["evening out","social"]))

    s("formal_occasion", _score(h,
        ["gala","formal occasion","ceremony","red carpet","award"],
        ["special occasion","grand event"]))

    # ── Values extras ─────────────────────────────────────────────────────
    s("wardrobe_staple", _score(h,
        ["wardrobe staple","essential","must-have","everyday hero","timeless"],
        ["classic piece","go-to"]))

    s("statement_piece", _score(h,
        ["statement","hero piece","stand-out","key piece","centrepiece"],
        ["show piece","feature item"]))

    s("limited_edition", _score(h,
        ["limited edition","exclusive","capsule collection","special edition",
         "limited release","collaboration"],
        ["limited","exclusive drop"]))

    s("handmade_detail", _score(h,
        ["handmade","hand-crafted","artisan","hand-finished","hand-knitted",
         "hand-embroidered"],
        ["craft","artisanal"]))

    s("capsule_wardrobe", _score(h,
        ["capsule wardrobe","capsule collection","minimalist wardrobe",
         "versatile wardrobe"],
        ["capsule","minimal wardrobe"]))

    # ── Pattern extras ────────────────────────────────────────────────────
    s("paisley_print", _score(h,
        ["paisley","paisley print","teardrop print","boteh"],
        ["paisley pattern","swirl print"]))

    s("baroque_print", _score(h,
        ["baroque","ornate print","scrollwork","damask baroque","renaissance"],
        ["ornamental","regal print"]))

    s("tie_dye", _score(h,
        ["tie dye","tie-dye","tiedye","tye dye","spiral dye"],
        ["dyed","hand dyed"]))

    s("ombre_effect", _score(h,
        ["ombre","ombré","dip dye","gradient colour","fade effect"],
        ["colour fade","wash effect"]))

    s("polka_dot", _score(h,
        ["polka dot","polka-dot","spotted","dotted","spot print","pois"],
        ["dots","dot pattern"]))

    s("camouflage", _score(h,
        ["camouflage","camo","military print","camo print"],
        ["army pattern","camo style"]))

    s("tropical_print", _score(h,
        ["tropical","palm print","hibiscus","jungle print","bird of paradise"],
        ["tropical flower","island print"]))

    s("fairisle_knit", _score(h,
        ["fair isle","fairisle","nordic pattern","scandinavian knit","snowflake knit"],
        ["ski knit","nordic knit"]))

    s("argyle_pattern", _score(h,
        ["argyle","diamond pattern","diamond knit","golf diamond"],
        ["diamond check","argyle print"]))

    s("colour_block", _score(h,
        ["colour block","color block","colourblock","colorblock","colour-block"],
        ["blocked colour","panel colour"]))

    s("acid_wash", _score(h,
        ["acid wash","acid-wash","bleach wash","destroyed wash"],
        ["washed denim","bleached"]))

    s("graphic_print", _score(h,
        ["graphic","graphic tee","graphic print","printed graphic","illustration"],
        ["artwork","printed design"]))

    s("logo_repeat", _score(h,
        ["all-over logo","logo print","monogram print","logo repeat","allover logo"],
        ["logo pattern","brand print"]))

    s("leopard_spot", _score(h,
        ["leopard","leopard print","leopard spot","cheetah"],
        ["big cat print","feline print"]))

    s("zebra_stripe", _score(h,
        ["zebra","zebra print","zebra stripe"],
        ["zebra pattern","black white stripe"]))

    s("toile_print", _score(h,
        ["toile","toile de jouy","scenic print","pastoral print"],
        []))

    s("damask_print", _score(h,
        ["damask","damask print","brocade pattern","jacquard damask"],
        ["ornate weave","woven pattern"]))

    s("windowpane_check", _score(h,
        ["windowpane","windowpane check","grid check","open check","large check"],
        ["bold check","oversized check"]))

    # ── Fabric material extras ────────────────────────────────────────────
    s("silk_fabric", _score(h,
        ["silk","pure silk","100% silk","mulberry silk","silk blend"],
        ["silky","satin silk"]))

    s("cotton_fabric", _score(h,
        ["cotton","100% cotton","pure cotton","organic cotton","cotton blend"],
        ["cotton fabric","natural cotton"]))

    s("modal_fabric", _score(h,
        ["modal","micromodal","modal blend","modal jersey"],
        ["soft modal","modal fabric"]))

    s("lyocell_fabric", _score(h,
        ["lyocell","tencel","tencel™","lyocell blend"],
        ["sustainable lyocell","eco fabric"]))

    s("viscose_fabric", _score(h,
        ["viscose","rayon","viscose blend","rayon fabric"],
        ["fluid fabric","fluid viscose"]))

    s("wool_fabric", _score(h,
        ["wool","pure wool","wool blend","virgin wool","lambswool"],
        ["woollen","warm wool"]))

    s("cashmere_fabric", _score(h,
        ["cashmere","pure cashmere","cashmere blend","100% cashmere"],
        ["cashmere soft","luxe cashmere"]))

    s("suede_fabric", _score(h,
        ["suede","genuine suede","faux suede","micro suede","suede effect"],
        ["suede finish","suede touch"]))

    s("nylon_fabric", _score(h,
        ["nylon","polyamide","nylon blend","ripstop nylon"],
        ["nylon fabric","wind fabric"]))

    s("jersey_fabric", _score(h,
        ["jersey","jersey fabric","stretch jersey","cotton jersey","modal jersey"],
        ["jersey knit","soft jersey"]))

    s("crepe_fabric", _score(h,
        ["crepe","crêpe","crepe fabric","crepe de chine","crepe georgette"],
        ["crinkle","crepe texture"]))

    s("brocade_fabric", _score(h,
        ["brocade","brocade fabric","jacquard brocade","woven brocade"],
        ["ornate weave","raised weave"]))

    s("corduroy_fabric", _score(h,
        ["corduroy","cord","needlecord","wide cord","baby cord"],
        ["cord fabric","ribbed cord"]))

    s("organza_fabric", _score(h,
        ["organza","silk organza","organza overlay","sheer organza"],
        ["stiff sheer","crisp sheer"]))

    s("chiffon_fabric", _score(h,
        ["chiffon","silk chiffon","chiffon overlay","chiffon blend"],
        ["sheer chiffon","light chiffon"]))

    s("poplin_fabric", _score(h,
        ["poplin","cotton poplin","poplin shirt","poplin fabric"],
        ["crisp cotton","woven shirt fabric"]))

    s("flannel_fabric", _score(h,
        ["flannel","brushed flannel","wool flannel","plaid flannel"],
        ["soft flannel","warm flannel"]))

    s("fleece_fabric", _score(h,
        ["fleece","polar fleece","sherpa","fleece jacket","fleece pullover"],
        ["soft fleece","cosy fleece"]))

    s("recycled_fabric", _score(h,
        ["recycled","econyl","primeblue","repreve","recycled polyester",
         "upcycled","sustainable material"],
        ["eco","recycled fibre"]))

    s("stretch_fabric", _score(h,
        ["stretch","elastane","lycra","spandex","four-way stretch"],
        ["stretch fabric","flexible"]))

    # ── Fabric texture extras ─────────────────────────────────────────────
    s("jacquard_weave", _score(h,
        ["jacquard","jacquard weave","woven jacquard","dobby weave"],
        ["self-pattern","woven motif"]))

    s("burnout_effect", _score(h,
        ["burnout","devore","velvet burnout","burn-out"],
        ["devore velvet","burnout velvet"]))

    s("metallic_sheen", _score(h,
        ["metallic","lamé","foil fabric","metallic sheen","metallic thread"],
        ["shiny fabric","glam fabric"]))

    s("glitter_detail", _score(h,
        ["glitter","glittery","sparkle","glitter print","glitter fabric"],
        ["sparkly","festive glitter"]))

    s("sequin_embellishment", _score(h,
        ["sequin","sequined","paillette","sequin dress","sequin top"],
        ["all-over sequin","disc embellishment"]))

    s("beaded_detail", _score(h,
        ["beaded","beading","beadwork","bead embellishment","bead trim"],
        ["bead detail","glass bead"]))

    s("laser_cut", _score(h,
        ["laser cut","laser-cut","laser cutout","precision cut"],
        ["geometric cutout","cut pattern"]))

    s("perforated_detail", _score(h,
        ["perforated","perforation","punched","laser punched"],
        ["dot holes","punch detail"]))

    s("frayed_edge", _score(h,
        ["frayed","raw edge hem","distressed hem","frayed hem","unfinished hem"],
        ["raw finish","fringe edge"]))

    s("brushed_finish", _score(h,
        ["brushed","brushed finish","peached","soft-touch","suede touch"],
        ["brushed surface","soft finish"]))

    # ── Construction extras ───────────────────────────────────────────────
    s("button_front", _score(h,
        ["button-front","button front","button-up","button through","buttoned"],
        ["button closure","front buttons"]))

    s("double_breasted", _score(h,
        ["double-breasted","double breasted","DB blazer","double button"],
        ["double row button","DB coat"]))

    s("single_breasted", _score(h,
        ["single-breasted","single breasted","single button","one-button"],
        ["single row","SB blazer"]))

    s("zip_front", _score(h,
        ["zip","full zip","front zip","zip-up","zipped front"],
        ["zipper","zip closure"]))

    s("cargo_pockets", _score(h,
        ["cargo","utility pocket","cargo pocket","side cargo","military pocket"],
        ["multi-pocket","functional pocket"]))

    s("patch_pocket", _score(h,
        ["patch pocket","applied pocket","external pocket"],
        ["sewn pocket","pockets"]))

    s("chest_pocket", _score(h,
        ["chest pocket","breast pocket","welt pocket","top pocket"],
        ["upper pocket","front chest"]))

    s("notch_lapel", _score(h,
        ["notch lapel","notched lapel","standard lapel","classic lapel"],
        ["lapel","notch collar"]))

    s("mandarin_collar", _score(h,
        ["mandarin collar","band collar","nehru collar","mao collar","chinese collar"],
        ["stand collar","banded neck"]))

    s("shawl_collar", _score(h,
        ["shawl collar","shawl lapel","rolled collar","wrap collar"],
        ["soft lapel","fold collar"]))

    s("gathered_bodice", _score(h,
        ["gathered bodice","ruched bodice","gathered front","shirred bodice"],
        ["gathered top","ruched front"]))

    s("smocked_detail", _score(h,
        ["smocked","smocking","smock detail","elasticated smock"],
        ["smocked fabric","hand smocking"]))

    s("pintuck_detail", _score(h,
        ["pintuck","pin tuck","pin-tuck","fine tuck"],
        ["tiny pleat","tuck detail"]))

    s("shirred_detail", _score(h,
        ["shirred","shirring","elastic thread","elasticated bodice"],
        ["gathered elastic","elastic ruched"]))

    s("drawstring_waist", _score(h,
        ["drawstring","drawstring waist","draw cord","toggleable waist"],
        ["pull cord","tie cord"]))

    s("elastic_waist", _score(h,
        ["elastic waist","elasticated waist","pull-on","pull on waist","stretch waist"],
        ["elasticated","pull on"]))

    s("corset_detail", _score(h,
        ["corset","corseted","boning","lace-up back","bustier","waist cincher"],
        ["corset-style","structured bodice"]))

    s("gathered_waist", _score(h,
        ["gathered waist","ruched waist","gathered skirt","ruched side"],
        ["ruched waist","gathered hip"]))

    s("raw_edge_hem", _score(h,
        ["raw hem","raw edge","unfinished hem","undone hem"],
        ["rough edge","exposed seam"]))

    s("fringe_trim", _score(h,
        ["fringe","tassel","fringing","fringed hem","tassel trim"],
        ["knotted fringe","western fringe"]))

    s("lace_trim", _score(h,
        ["lace trim","lace detail","lace hem","lace edging","lace border"],
        ["lace insert","delicate lace"]))

    s("contrast_stitch", _score(h,
        ["contrast stitch","contrast stitching","tonal stitch","visible seam"],
        ["topstitch","decorative stitch"]))

    s("open_back", _score(h,
        ["open back","backless","low back","bare back","cut-out back"],
        ["exposed back","back cutout"]))

    s("gold_hardware", _score(h,
        ["gold hardware","gold zip","gold button","gold buckle","gold chain detail"],
        ["gold tone metal","golden clasp"]))

    s("silver_hardware", _score(h,
        ["silver hardware","silver zip","silver button","gunmetal","silver buckle"],
        ["silver tone","chrome hardware"]))

    s("chain_trim", _score(h,
        ["chain","chain trim","chain detail","chain strap","chain belt"],
        ["chain embellishment","metal chain"]))

    s("buckle_detail", _score(h,
        ["buckle","D-ring","belt buckle","strap buckle","metal buckle"],
        ["clasp","fastening"]))

    s("stud_embellishment", _score(h,
        ["stud","studded","rivet","metal stud","pyramid stud"],
        ["rock stud","stud detail"]))

    return scores


# ── pipeline ──────────────────────────────────────────────────────────────────

def load_products() -> list[dict]:
    products = []
    for path in (ZARA_JSON, ADIDAS_JSON):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            products.extend(data)
            print(f"Loaded {len(data):,} products from {path.name}")
    return products


def enrich(product: dict) -> dict:
    """Add price_tier, image_url, Layer-1 attrs, keyword scores, and archetype scores."""
    p = dict(product)
    p["price_tier"] = _price_tier(p.get("price"))
    imgs = p.get("image_urls") or []
    p["image_url"] = imgs[0] if imgs else ""
    raw_cols = p.get("colors") or []
    p["colors"] = ", ".join(str(c) for c in raw_cols) if isinstance(raw_cols, list) else str(raw_cols)

    h   = _haystack(p)
    col = _colors_str(p)
    cat = (p.get("category") or "").lower()

    # Layer-1 attributes
    p["gender"]          = _extract_gender(p.get("category") or "")
    p["item_type"]       = _extract_item_type(h, cat)
    p["color_family"]    = _extract_color_family(h, col)
    p["silhouette_attr"] = _extract_silhouette(h)
    p["fabric_attr"]     = _extract_fabric(h)
    p["formality_attr"]  = _extract_formality(h, cat)

    # 72-keyword scores
    kw_scores = _tag(p)
    for kw in KEYWORDS:
        p[kw] = kw_scores.get(kw, 0.0)

    # 32-archetype scores
    arch_scores = _score_archetypes(h, col)
    for arch_col in ARCH_COLS:
        p[arch_col] = arch_scores.get(arch_col, 0.0)

    return p


def write_xlsx(products: list[dict], path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    kw_fill     = PatternFill("solid", fgColor="2E75B6")
    layer1_fill = PatternFill("solid", fgColor="375623")
    arch_fill   = PatternFill("solid", fgColor="7B2D8B")
    header_font = Font(bold=True, color="FFFFFF")

    for ci, col in enumerate(ALL_COLS, 1):
        cell = ws.cell(row=1, column=ci, value=col)
        cell.font = header_font
        if col in KEYWORDS:
            cell.fill = kw_fill
        elif col in LAYER1_COLS:
            cell.fill = layer1_fill
        elif col in ARCH_COLS:
            cell.fill = arch_fill
        else:
            cell.fill = header_fill

    for ri, p in enumerate(products, 2):
        for ci, col in enumerate(ALL_COLS, 1):
            ws.cell(row=ri, column=ci, value=p.get(col, ""))

    for ci, col in enumerate(ALL_COLS, 1):
        width = 8 if (col in KEYWORDS or col in ARCH_COLS) else max(12, min(len(col) + 4, 40))
        ws.column_dimensions[get_column_letter(ci)].width = width

    ws.freeze_panes = "A2"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main():
    print("\n── Rule-based tagger (JudgeByLooks) ──────────────────────────────────")
    products_raw = load_products()
    if not products_raw:
        print("No products found. Run the scraper first.")
        return

    print(f"\nTagging {len(products_raw):,} products...")
    tagged = [enrich(p) for p in products_raw]
    print(f"Tagged {len(tagged):,} products")

    print(f"\nWriting {XLSX_OUT}...")
    write_xlsx(tagged, XLSX_OUT)

    kw_hits = {kw: sum(1 for p in tagged if p.get(kw, 0) > 0) for kw in KEYWORDS}
    top = sorted(kw_hits.items(), key=lambda x: -x[1])[:10]
    print("\nTop 10 keywords by coverage:")
    for kw, count in top:
        print(f"  {kw:25} {count:6,} products ({count/len(tagged)*100:.1f}%)")

    gender_counts = {}
    for p in tagged:
        g = p.get("gender", "unisex")
        gender_counts[g] = gender_counts.get(g, 0) + 1
    print(f"\nGender split: {gender_counts}")

    arch_hits = {a: sum(1 for p in tagged if p.get(f"arch_{a}", 0) > 0) for a in ARCHETYPE_IDS}
    top_arch = sorted(arch_hits.items(), key=lambda x: -x[1])[:5]
    print("\nTop 5 archetypes by coverage:")
    for aid, count in top_arch:
        print(f"  {aid:30} {count:6,} products ({count/len(tagged)*100:.1f}%)")

    print(f"\n✓ Done — {len(tagged):,} products → {XLSX_OUT}")


if __name__ == "__main__":
    main()
