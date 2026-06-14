#!/usr/bin/env python3
"""
Fashion product tagging pipeline.
Usage: python tagger/tag.py
"""

import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import anthropic
import httpx
import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

# ── path setup ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from cache import Cache
from dedup import dedup, KEYWORDS

# ── logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)
# httpx is very chatty at DEBUG; keep it quiet
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────
ZARA_JSON = ROOT / "scraper/data/zara_raw.json"
ADIDAS_JSON = ROOT / "scraper/data/adidas_raw.json"
DATA_DIR = Path(__file__).parent / "data"
CACHE_DIR = DATA_DIR / "cache"
XLSX_RAW = DATA_DIR / "products.xlsx"
XLSX_TAGGED = DATA_DIR / "products_tagged.xlsx"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CONCURRENCY = 5
POST_CALL_DELAY = 0.5   # seconds

# Pricing (per 1M tokens, USD) — Sonnet 4 / Haiku 4.5
_PRICES = {
    "claude-sonnet-4-20250514":   {"in": 3.00,  "out": 15.00},
    "claude-haiku-4-5-20251001":  {"in": 0.80,  "out": 4.00},
}

# ── keyword columns ──────────────────────────────────────────────────────────
KEYWORD_GROUPS = {
    "Aesthetic":     ["minimalist", "maximalist", "classic", "avant_garde",
                      "streetwear", "bohemian", "preppy", "romantic", "edgy",
                      "quiet_luxury", "coastal", "dark_academia", "sporty"],
    "Mood":          ["playful", "serious", "rebellious", "elegant", "laid_back",
                      "bold", "understated", "whimsical", "polished", "raw"],
    "Color palette": ["neutral", "monochrome", "earth_tones", "pastel",
                      "bold_colors", "black_forward", "white_forward",
                      "jewel_tones", "multicolor"],
    "Formality":     ["loungewear", "casual", "smart_casual", "business_casual",
                      "formal", "black_tie"],
    "Cultural":      ["parisian", "scandinavian", "italian_luxury",
                      "japanese_minimalist", "american_prep", "british_heritage",
                      "nyc_streetwear", "californian"],
    "Silhouette":    ["fitted", "oversized", "structured", "flowy", "layered",
                      "cropped", "voluminous"],
    "Occasion":      ["everyday", "workwear", "going_out", "travel", "outdoor",
                      "sport", "beach", "occasion"],
    "Values":        ["sustainable", "investment_piece", "trend_driven",
                      "heritage_craft", "luxury_status", "budget_conscious",
                      "logo_forward", "logo_free", "size_inclusive",
                      "gender_neutral", "performance_tech"],
    "Pattern":       ["floral_print", "striped_pattern", "checked_pattern",
                      "animal_print", "solid_color", "abstract_print"],
    "Material":      ["denim_fabric", "linen_fabric", "velvet_fabric", "satin_fabric",
                      "leather_fabric", "knitwear_fabric"],
    "Length":        ["mini_length", "midi_length", "maxi_length"],
    "Detail":        ["ruffled", "belted", "crochet_detail", "embroidered_detail",
                      "pleated_detail"],
}

BASE_COLS = [
    "id", "brand", "name", "category", "price", "currency", "price_tier",
    "colors", "description", "product_url", "scraped_at", "image_url",
]

ALL_COLS = BASE_COLS + KEYWORDS

SYSTEM_PROMPT = """
You are a fashion product tagger. Given a product image and basic info,
return ONLY a JSON object of style keyword scores for keywords that
genuinely apply. Omit keywords with score 0 — do not include them.
Scores range from 0.1 (weakly applies) to 1.0 (defining characteristic).
Most products match 8–15 keywords. No preamble, no markdown, no keys
with 0 values. Valid JSON only.
""".strip()

# ── German→English color map ─────────────────────────────────────────────────
_DE_EN = {
    "braun": "Brown", "schwarz": "Black", "weiß": "White", "weiss": "White",
    "blau": "Blue", "rot": "Red", "grün": "Green", "gruen": "Green",
    "grau": "Gray", "beige": "Beige", "lila": "Purple", "rosa": "Pink",
    "gelb": "Yellow", "orange": "Orange", "mint": "Mint",
}

_PRODUCT_ID_RE = re.compile(r"^[A-Z0-9]{5,8}$")


def _extract_color_from_url(image_url: str) -> str | None:
    """Pull a color word from an Adidas image filename."""
    filename = image_url.rstrip("/").split("/")[-1].split(".")[0]
    parts = filename.split("_")
    for part in parts:
        if not part:
            continue
        if _PRODUCT_ID_RE.match(part):
            continue
        lower = part.lower()
        if lower in _DE_EN:
            return _DE_EN[lower]
        if part[0].isupper() and not part.isupper():
            return part
    return None


def _clean_adidas_colors(product: dict) -> list[str]:
    colors = product.get("colors") or []
    if not colors or all(_PRODUCT_ID_RE.match(str(c)) for c in colors):
        image_urls = product.get("image_urls") or []
        if image_urls:
            color = _extract_color_from_url(image_urls[0])
            return [color] if color else ["Unknown"]
        return ["Unknown"]
    return colors


def _price_tier(price) -> str:
    if price is None:
        return "unknown"
    if price < 30:
        return "budget"
    if price <= 80:
        return "mid"
    if price <= 200:
        return "premium"
    return "luxury"


# ── Step 1 — Load and clean ──────────────────────────────────────────────────
def load_products() -> list[dict]:
    zara = json.loads(ZARA_JSON.read_text(encoding="utf-8"))
    adidas = json.loads(ADIDAS_JSON.read_text(encoding="utf-8"))

    log.info("[Load] Zara: %d products", len(zara))
    log.info("[Load] Adidas: %d products", len(adidas))

    combined = []
    for p in zara:
        p["price_tier"] = _price_tier(p.get("price"))
        combined.append(p)

    for p in adidas:
        p["colors"] = _clean_adidas_colors(p)
        p["price_tier"] = _price_tier(p.get("price"))
        combined.append(p)

    log.info("[Load] Combined: %d products", len(combined))
    return combined


# ── Step 2 — Build products.xlsx ─────────────────────────────────────────────
def build_xlsx(products: list[dict]) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products"

    # Build header
    header = BASE_COLS[:]
    for group, kws in KEYWORD_GROUPS.items():
        header.extend(kws)

    ws.append(header)

    # Header comments (group labels) on keyword columns
    from openpyxl.comments import Comment
    kw_start_col = len(BASE_COLS) + 1
    col = kw_start_col
    for group, kws in KEYWORD_GROUPS.items():
        cell = ws.cell(row=1, column=col)
        comment = Comment(f"Dimension: {group}", "tagger")
        comment.width = 120
        comment.height = 40
        cell.comment = comment
        col += len(kws)

    # Style header row
    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font

    # Data rows
    for p in products:
        colors_str = " / ".join(str(c) for c in (p.get("colors") or []))
        image_url = ""
        if p.get("image_urls"):
            image_url = p["image_urls"][0]
        row = [
            p.get("id", ""),
            p.get("brand", ""),
            p.get("name", ""),
            p.get("category", ""),
            p.get("price"),
            p.get("currency", ""),
            p.get("price_tier", ""),
            colors_str,
            p.get("description", ""),
            p.get("product_url", ""),
            p.get("scraped_at", ""),
            image_url,
        ]
        # keyword columns start as empty (None → 0.0 after tagging)
        for _ in KEYWORDS:
            row.append(None)
        ws.append(row)

    # Freeze top row
    ws.freeze_panes = "A2"

    # Auto-size columns (cap at 60 chars wide)
    for col_idx, _ in enumerate(header, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(header[col_idx - 1]))
        for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            val = str(row[0].value or "")
            max_len = max(max_len, min(len(val), 60))
        ws.column_dimensions[col_letter].width = max_len + 2

    wb.save(str(XLSX_RAW))
    log.info(
        "[Sheet] products.xlsx created — %d rows, %d columns",
        ws.max_row - 1,
        len(header),
    )
    return wb


# ── Step 3 — Tag via Claude API ──────────────────────────────────────────────
def _route_model(product: dict) -> tuple[str, str]:
    sport_terms = {
        "running", "training", "sport", "performance", "gym",
        "workout", "football", "cycling", "outdoor", "hiking",
    }
    cat = (product.get("category") or "").lower()
    if any(t in cat for t in sport_terms):
        return "claude-haiku-4-5-20251001", "haiku"
    return "claude-sonnet-4-20250514", "sonnet"


def _user_message(product: dict) -> str:
    colors = " / ".join(str(c) for c in (product.get("colors") or []))
    kw_list = ", ".join(KEYWORDS)
    return (
        f"Product: {product.get('name', '')}\n"
        f"Brand: {product.get('brand', '')}\n"
        f"Category: {product.get('category', '')}\n"
        f"Price tier: {product.get('price_tier', '')}\n"
        f"Colors: {colors}\n\n"
        f"Valid keywords — return only those that apply with score 0.1–1.0:\n"
        f"{kw_list}"
    )


async def _download_image(
    client: httpx.AsyncClient, url: str
) -> tuple[str, str] | None:
    """Return (base64_data, media_type) or None on failure."""
    if not url:
        return None
    try:
        r = await client.get(url, timeout=5.0, follow_redirects=True)
        r.raise_for_status()
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if ct not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            # Infer from URL extension
            ext = url.split("?")[0].split(".")[-1].lower()
            ct = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp",
            }.get(ext, "image/jpeg")
        return base64.standard_b64encode(r.content).decode(), ct
    except Exception:
        return None


def _parse_scores(text: str) -> dict | None:
    text = text.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return {k: float(v) for k, v in data.items() if k in set(KEYWORDS)}
    except Exception:
        return None


def _expand_scores(sparse: dict) -> dict:
    """Fill all 72 keywords; missing ones get 0.0."""
    return {k: sparse.get(k, 0.0) for k in KEYWORDS}


async def _tag_one(
    semaphore: asyncio.Semaphore,
    client_ai: anthropic.AsyncAnthropic,
    http_client: httpx.AsyncClient,
    cache: Cache,
    product: dict,
    stats: dict,
) -> dict:
    pid = str(product.get("id", ""))
    name = product.get("name", "")

    # Cache hit
    cached = cache.get(pid)
    if cached is not None:
        log.debug("[CACHE] %r → skipped", name)
        stats["from_cache"] += 1
        return _expand_scores(cached)

    async with semaphore:
        model_id, model_short = _route_model(product)
        log.debug("[ROUTE] %r → %s", name, model_short)

        # Image
        img_data = None
        image_url = (product.get("image_urls") or [""])[0]
        if image_url:
            img_data = await _download_image(http_client, image_url)
        if img_data is None and image_url:
            log.debug("[NO IMAGE] %r → text only", name)

        # Build message content
        content: list = []
        if img_data:
            b64, media_type = img_data
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            })
        content.append({"type": "text", "text": _user_message(product)})

        t0 = time.monotonic()
        try:
            response = await client_ai.messages.create(
                model=model_id,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
        except Exception as exc:
            log.warning("[FAIL] %r → API error: %s", name, exc)
            stats["failed"] += 1
            stats["api_calls"] += 1
            await asyncio.sleep(POST_CALL_DELAY)
            return _expand_scores({})

        elapsed = time.monotonic() - t0

        raw_text = response.content[0].text if response.content else ""
        parsed = _parse_scores(raw_text)

        if parsed is None:
            log.warning("[FAIL] %r → parse error, zeros written", name)
            stats["failed"] += 1
            stats["api_calls"] += 1
            stats["model_counts"][model_short] = (
                stats["model_counts"].get(model_short, 0) + 1
            )
            await asyncio.sleep(POST_CALL_DELAY)
            return _expand_scores({})

        # Token accounting
        usage = response.usage
        in_tok = getattr(usage, "input_tokens", 0)
        out_tok = getattr(usage, "output_tokens", 0)
        stats["input_tokens"] += in_tok
        stats["output_tokens"] += out_tok
        prices = _PRICES.get(model_id, {"in": 3.0, "out": 15.0})
        stats["cost_usd"] += (in_tok / 1_000_000 * prices["in"]) + (
            out_tok / 1_000_000 * prices["out"]
        )

        stats["tagged"] += 1
        stats["api_calls"] += 1
        stats["model_counts"][model_short] = (
            stats["model_counts"].get(model_short, 0) + 1
        )

        n_keywords = sum(1 for v in parsed.values() if v > 0)
        log.info(
            "[%s] %s %r → tagged %.1fs | %d keywords",
            model_short, product.get("brand", ""), name, elapsed, n_keywords,
        )

        cache.set(pid, parsed)
        await asyncio.sleep(POST_CALL_DELAY)
        return _expand_scores(parsed)


async def tag_all(
    products: list[dict], cache: Cache
) -> tuple[list[dict], dict]:
    stats = {
        "tagged": 0,
        "from_cache": 0,
        "failed": 0,
        "api_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "model_counts": {},
    }

    semaphore = asyncio.Semaphore(CONCURRENCY)
    client_ai = anthropic.AsyncAnthropic()

    async with httpx.AsyncClient() as http_client:
        tasks = [
            _tag_one(semaphore, client_ai, http_client, cache, p, stats)
            for p in products
        ]
        score_dicts = await asyncio.gather(*tasks)

    # Merge scores back into products
    tagged = []
    for p, scores in zip(products, score_dicts):
        row = dict(p)
        row.update(scores)
        tagged.append(row)

    return tagged, stats


# ── Step 4 — Write products_tagged.xlsx ─────────────────────────────────────
_FILL_YELLOW = PatternFill("solid", fgColor="FFF9C4")
_FILL_ORANGE = PatternFill("solid", fgColor="FFE0B2")
_FILL_GREEN  = PatternFill("solid", fgColor="C8E6C9")


def _kw_fill(val: float) -> PatternFill | None:
    if val >= 0.8:
        return _FILL_GREEN
    if val >= 0.5:
        return _FILL_ORANGE
    if val >= 0.1:
        return _FILL_YELLOW
    return None


def save_tagged_xlsx(
    products_tagged: list[dict],
    products_removed: list[dict],
) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products"

    header = BASE_COLS + KEYWORDS
    ws.append(header)

    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font

    kw_start = len(BASE_COLS) + 1  # 1-based

    for p in products_tagged:
        colors_str = " / ".join(str(c) for c in (p.get("colors") or []))
        image_url = (p.get("image_urls") or [""])[0] if p.get("image_urls") else p.get("image_url", "")
        row_vals = [
            p.get("id", ""),
            p.get("brand", ""),
            p.get("name", ""),
            p.get("category", ""),
            p.get("price"),
            p.get("currency", ""),
            p.get("price_tier", ""),
            colors_str,
            p.get("description", ""),
            p.get("product_url", ""),
            p.get("scraped_at", ""),
            image_url,
        ]
        for kw in KEYWORDS:
            row_vals.append(round(float(p.get(kw, 0.0)), 3))

        ws.append(row_vals)
        data_row = ws.max_row
        for kw_idx, kw in enumerate(KEYWORDS):
            col = kw_start + kw_idx
            val = float(p.get(kw, 0.0))
            fill = _kw_fill(val)
            if fill:
                ws.cell(row=data_row, column=col).fill = fill

    ws.freeze_panes = "A2"
    for col_idx in range(1, len(header) + 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = max(
            len(str(header[col_idx - 1])) + 2, 8
        )

    # "Removed Duplicates" sheet
    ws2 = wb.create_sheet("Removed Duplicates")
    ws2.append(["id", "brand", "name", "similar_to", "similarity_score"])
    for cell in ws2[1]:
        cell.font = header_font
    for p in products_removed:
        ws2.append([
            p.get("id", ""),
            p.get("brand", ""),
            p.get("name", ""),
            p.get("similar_to", ""),
            p.get("similarity_score", ""),
        ])
    for col_idx in range(1, 6):
        ws2.column_dimensions[get_column_letter(col_idx)].width = 30

    wb.save(str(XLSX_TAGGED))
    log.info("[Save] products_tagged.xlsx — %d rows", len(products_tagged))


# ── Step 5 — Summary ─────────────────────────────────────────────────────────
def print_summary(
    products: list[dict],
    tagged_products: list[dict],
    removed: list[dict],
    stats: dict,
) -> None:
    total = len(products)
    final = len(tagged_products)
    n_removed = len(removed)

    # Top 10 keywords by number of products with score > 0.5
    kw_counts = {}
    for p in tagged_products:
        for kw in KEYWORDS:
            if float(p.get(kw, 0.0)) > 0.5:
                kw_counts[kw] = kw_counts.get(kw, 0) + 1
    top10 = sorted(kw_counts.items(), key=lambda x: -x[1])[:10]

    sonnet_count = stats["model_counts"].get("sonnet", 0)
    haiku_count  = stats["model_counts"].get("haiku", 0)

    sep = "─" * 45
    print(f"\n{sep}")
    print("  Tagging complete")
    print(sep)
    print(f"  {'Total products loaded:':<30} {total:>6}")
    print(f"  {'Tagged via API:':<30} {stats['tagged']:>6}")
    print(f"  {'Loaded from cache:':<30} {stats['from_cache']:>6}")
    print(f"  {'Failed (zeros written):':<30} {stats['failed']:>6}")
    print(sep)
    print(f"  {'Duplicates removed:':<30} {n_removed:>6}")
    print(f"  {'Final catalog size:':<30} {final:>6}")
    print(sep)
    print("  Model breakdown:")
    print(f"    {'claude-sonnet:':<26} {sonnet_count:>6}")
    print(f"    {'claude-haiku:':<26} {haiku_count:>6}")
    print(sep)
    print("  Token usage:")
    print(f"    {'Input tokens:':<26} {stats['input_tokens']:>10,}")
    print(f"    {'Output tokens:':<26} {stats['output_tokens']:>10,}")
    print(f"  {'Estimated cost:':<30} ${stats['cost_usd']:>7.2f}")
    print(sep)
    print("  Top 10 keywords (score > 0.5):")
    for rank, (kw, cnt) in enumerate(top10, 1):
        print(f"   {rank:>2}. {kw:<20} {cnt:>4} products")
    print(sep)


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    cache = Cache(str(CACHE_DIR))

    # Step 1
    products = load_products()

    # Step 2
    build_xlsx(products)

    # Step 3
    tagged_products, stats = asyncio.run(tag_all(products, cache))

    # Step 4
    kept, removed = dedup(tagged_products)
    save_tagged_xlsx(kept, removed)

    # Step 5
    print_summary(products, kept, removed, stats)


if __name__ == "__main__":
    main()
