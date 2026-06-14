"""
One-time migration: reads tagger/data/products_tagged.xlsx and loads all
products into fashion.db.  Safe to re-run — existing rows are skipped.

Usage:
    python3 migrate.py
"""

import sqlite3
import os
from collections import Counter

import openpyxl

XLSX_PATH = os.path.join(os.path.dirname(__file__), "../tagger/data/products_tagged.xlsx")
DB_PATH   = os.path.join(os.path.dirname(__file__), "fashion.db")
SHEET     = "Products"

TEXT_COLS = ["id", "brand", "name", "category", "currency",
             "price_tier", "colors", "description", "product_url",
             "scraped_at", "image_url"]

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

_KW_COL_DEFS  = "\n".join(f"  {k:<22} REAL DEFAULT 0.0," for k in KEYWORDS)
CREATE_TABLE  = f"""
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
{_KW_COL_DEFS}
  _placeholder           INTEGER DEFAULT 0
)
"""

ALL_COLS    = ["id", "brand", "name", "category", "price", "currency",
               "price_tier", "colors", "description", "product_url",
               "scraped_at", "image_url"] + KEYWORDS
INSERT_SQL  = (
    f"INSERT OR IGNORE INTO products ({', '.join(ALL_COLS)}) "
    f"VALUES ({', '.join(['?'] * len(ALL_COLS))})"
)


def _str(val) -> str:
    return str(val).strip() if val is not None else ""


def _price(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _float(val) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def main():
    print(f"[Migrate] Reading {XLSX_PATH}...")
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET]

    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    data_rows = rows[1:]
    print(f"[Migrate] Found {len(data_rows)} products")

    # warn about any missing keyword columns
    missing_kw = [k for k in KEYWORDS if k not in headers]
    for k in missing_kw:
        print(f'[WARN] Column "{k}" not found in xlsx — defaulting to 0.0')

    col_idx = {h: i for i, h in enumerate(headers)}

    def get(row, col, default=None):
        i = col_idx.get(col)
        return row[i] if i is not None and i < len(row) else default

    print(f"[Migrate] Inserting into {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE)
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
        ] + [_float(get(row, k)) for k in KEYWORDS]

        cur = conn.execute(INSERT_SQL, values)
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1

    conn.commit()

    print(f"[Migrate] {inserted} inserted, {skipped} skipped (already existed)")

    # ── summary stats ──────────────────────────────────────────────────────
    brands = Counter(
        _str(get(row, "brand")) for row in data_rows if get(row, "brand")
    )
    tiers = Counter(
        _str(get(row, "price_tier")) for row in data_rows if get(row, "price_tier")
    )

    # keywords with any score > 0.5 across all rows
    kw_hit = set()
    for row in data_rows:
        for k in KEYWORDS:
            if _float(get(row, k)) > 0.5:
                kw_hit.add(k)

    brands_str = ", ".join(f"{b}({c})" for b, c in brands.most_common(5))
    tiers_str  = " ".join(f"{t}({c})" for t, c in sorted(tiers.items()))

    print()
    print("─" * 41)
    print("Migration complete")
    print("─" * 41)
    print(f"Products inserted:  {inserted:>6}")
    print(f"Products skipped:   {skipped:>6}")
    print(f"Brands:             {brands_str}")
    print(f"Price tiers:        {tiers_str}")
    print(f"Keywords with any score > 0.5: {len(kw_hit)} / {len(KEYWORDS)}")
    print("─" * 41)

    conn.close()
    wb.close()


if __name__ == "__main__":
    main()
