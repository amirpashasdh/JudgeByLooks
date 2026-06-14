#!/usr/bin/env python3
"""
Rule-based fashion product tagger — free, instant, no API calls.

Scores each of the 72 style keywords against product name, description,
category, brand, price, and color using pattern matching.
Output format is identical to tag.py (products_tagged.xlsx).
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
from dedup import dedup, KEYWORDS

ZARA_JSON   = ROOT / "scraper/data/zara_raw.json"
ADIDAS_JSON = ROOT / "scraper/data/adidas_raw.json"
DATA_DIR    = Path(__file__).parent / "data"
XLSX_OUT    = DATA_DIR / "products_tagged.xlsx"

BASE_COLS = [
    "id", "brand", "name", "category", "price", "currency", "price_tier",
    "colors", "description", "product_url", "scraped_at", "image_url",
]
ALL_COLS = BASE_COLS + KEYWORDS

# ── helpers ──────────────────────────────────────────────────────────────────

def _haystack(p: dict) -> str:
    """Single lowercase search string: name + description + category."""
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
    """Return confidence score based on keyword presence."""
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


# ── per-keyword scoring rules ─────────────────────────────────────────────────

def _tag(product: dict) -> dict:
    h    = _haystack(product)
    col  = _colors_str(product)
    brand = (product.get("brand") or "").lower()
    price = product.get("price")
    cat  = (product.get("category") or "").lower()
    tier = _price_tier(price)
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

    s("quiet_luxury", _score(h,
        ["cashmere", "silk", "merino", "tailored", "wool blend", "camel coat"],
        ["structured", "refined", "understated", "premium"]))
    if is_zara and tier in ("premium", "luxury"):
        s("quiet_luxury", max(scores.get("quiet_luxury", 0), 0.5))

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

    s("italian_luxury", _score(h,
        ["italian", "milan", "linen italian", "cashmere italian"],
        ["luxe", "premium", "artisan"]))
    if is_zara and tier == "luxury":
        s("italian_luxury", max(scores.get("italian_luxury", 0), 0.4))

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

    s("investment_piece", 0.0)
    if tier == "luxury":
        s("investment_piece", 0.85)
    elif tier == "premium" and _has(h, "cashmere", "silk", "leather", "wool", "coat"):
        s("investment_piece", 0.7)

    s("trend_driven", 0.0)
    if is_zara:
        s("trend_driven", 0.7)
    elif _has(h, "trending", "new arrival", "season", "limited edition"):
        s("trend_driven", 0.6)

    s("heritage_craft", _score(h,
        ["handmade", "hand-stitched", "artisan", "craft", "heritage",
         "hand-woven", "hand-embroidered"],
        ["traditional", "vintage", "archive"]))

    s("luxury_status", 0.0)
    if tier == "luxury":
        s("luxury_status", 0.8)
    elif tier == "premium":
        s("luxury_status", 0.4)

    s("budget_conscious", 0.0)
    if tier == "budget":
        s("budget_conscious", 0.85)
    elif tier == "mid":
        s("budget_conscious", 0.4)

    s("logo_forward", _score(h,
        ["logo", "branded", "slogan", "graphic print brand",
         "embossed logo", "label"],
        ["print logo", "brand print"]))
    if is_adidas and _has(h, "logo", "trefoil", "3-stripe", "three stripe"):
        s("logo_forward", 0.85)

    # Default: most products are logo-free
    if scores.get("logo_forward", 0) < 0.3:
        s("logo_free", 0.7)

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

    # ── Product attributes — Pattern ──────────────────────────────────────
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

    # solid_color: high confidence when name has no pattern indicator
    _has_pattern = any(scores.get(k, 0) > 0.3 for k in [
        "floral_print", "striped_pattern", "checked_pattern",
        "animal_print", "abstract_print", "multicolor"
    ])
    if not _has_pattern:
        s("solid_color", 0.75)

    # ── Product attributes — Material ─────────────────────────────────────
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

    # ── Product attributes — Length ───────────────────────────────────────
    s("mini_length", _score(h,
        ["mini", "micro", "short dress", "short skirt"],
        ["above knee", "thigh"]))

    s("midi_length", _score(h,
        ["midi", "mid-length", "calf-length", "below knee"],
        ["mid length", "tea length"]))

    s("maxi_length", _score(h,
        ["maxi", "full length", "floor length", "long dress", "long skirt"],
        ["ankle length", "sweeping"]))

    # ── Product attributes — Key design detail ────────────────────────────
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
    """Add price_tier, image_url, and keyword scores to a product dict."""
    p = dict(product)
    p["price_tier"] = _price_tier(p.get("price"))
    imgs = p.get("image_urls") or []
    p["image_url"] = imgs[0] if imgs else ""
    cols = p.get("colors") or []
    p["colors"] = ", ".join(str(c) for c in cols) if isinstance(cols, list) else str(cols)

    scores = _tag(p)
    for kw in KEYWORDS:
        p[kw] = scores.get(kw, 0.0)
    return p


def write_xlsx(products: list[dict], path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    kw_fill     = PatternFill("solid", fgColor="2E75B6")
    header_font = Font(bold=True, color="FFFFFF")

    for ci, col in enumerate(ALL_COLS, 1):
        cell = ws.cell(row=1, column=ci, value=col)
        cell.font = header_font
        cell.fill = kw_fill if col in KEYWORDS else header_fill

    for ri, p in enumerate(products, 2):
        for ci, col in enumerate(ALL_COLS, 1):
            ws.cell(row=ri, column=ci, value=p.get(col, ""))

    # Column widths
    for ci, col in enumerate(ALL_COLS, 1):
        width = 8 if col in KEYWORDS else max(12, min(len(col) + 4, 40))
        ws.column_dimensions[get_column_letter(ci)].width = width

    ws.freeze_panes = "A2"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main():
    print("\n── Rule-based tagger ─────────────────────────────────────────")
    products_raw = load_products()
    if not products_raw:
        print("No products found. Run the scraper first.")
        return

    print(f"\nTagging {len(products_raw):,} products...")
    tagged = [enrich(p) for p in products_raw]
    print(f"Tagged {len(tagged):,} products")

    print("\nDeduplicating...")
    kept, dupes = dedup(tagged)
    print(f"Kept {len(kept):,} unique products, removed {len(dupes):,} duplicates")

    print(f"\nWriting {XLSX_OUT}...")
    write_xlsx(kept, XLSX_OUT)

    # Quick stats
    kw_hits = {kw: sum(1 for p in kept if p.get(kw, 0) > 0) for kw in KEYWORDS}
    top = sorted(kw_hits.items(), key=lambda x: -x[1])[:10]
    print("\nTop 10 keywords by coverage:")
    for kw, count in top:
        print(f"  {kw:25} {count:6,} products ({count/len(kept)*100:.1f}%)")

    print(f"\n✓ Done — {XLSX_OUT}")


if __name__ == "__main__":
    main()
