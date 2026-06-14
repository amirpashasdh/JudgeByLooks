#!/usr/bin/env python3
"""
Fashion product scraper — Zara & Adidas
Usage:
    python scraper/scrape.py                              # test mode, 10 items/brand
    python scraper/scrape.py --mode full                  # all products
    python scraper/scrape.py --limit 100                  # exactly 100 kept items/brand
    python scraper/scrape.py --brand zara                 # Zara only
    python scraper/scrape.py --brand zara --gender men    # Zara men only
    python scraper/scrape.py --brand zara --gender men --limit 50
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)

# Allow running as `python scraper/scrape.py` from repo root
sys.path.insert(0, str(Path(__file__).parent))

from scrapers import zara, adidas

DATA_DIR = Path(__file__).parent / "data"


def _save_json(path: Path, products: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


async def run(mode: str, brand: str | None, gender: str | None, limit: int | None) -> None:
    brand_label = f"brand={brand}" if brand else "all brands"
    gender_label = f", gender={gender}" if gender else ""
    limit_label  = f", limit={limit}" if limit is not None else ""
    print(f"\n{'='*60}")
    print(f"  Fashion Scraper  |  mode={mode}  |  {brand_label}{gender_label}{limit_label}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    zara_path = DATA_DIR / "zara_raw.json"
    adidas_path = DATA_DIR / "adidas_raw.json"

    summaries = []
    run_zara   = brand in (None, "zara")
    run_adidas = brand in (None, "adidas")

    # ── Zara ──────────────────────────────────────────────────────
    if run_zara:
        print("[Zara] Starting scrape…")

        async def save_zara(products):
            _save_json(zara_path, products)
            print(f"[Zara] Saved {len(products)} products → {zara_path}")

        zara_products, zara_summary = await zara.scrape(mode, save_zara, gender=gender, limit=limit)
        summaries.append(zara_summary)

    # ── Adidas ────────────────────────────────────────────────────
    if run_adidas:
        print("\n[Adidas] Starting scrape…")

        async def save_adidas(products):
            _save_json(adidas_path, products)
            print(f"[Adidas] Saved {len(products)} products → {adidas_path}")

        adidas_products, adidas_summary = await adidas.scrape(mode, save_adidas, gender=gender, limit=limit)
        summaries.append(adidas_summary)

    # ── Final summary ─────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for s in summaries:
        print(f"\n  Brand     : {s['brand']}")
        print(f"  Categories: {', '.join(s['categories'])}")
        print(f"  Kept      : {s['total_products']}")
        print(f"  Filtered  : {s.get('total_filtered', 0)}")
        if s["errors"]:
            print(f"  Errors    :")
            for e in s["errors"]:
                print(f"    - {e}")
        else:
            print(f"  Errors    : none")
    print(f"\n{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fashion product scraper (Zara & Adidas)")
    parser.add_argument(
        "--mode",
        choices=["test", "full"],
        default="test",
        help="test=10 kept products per brand, full=all products (default: test)",
    )
    parser.add_argument(
        "--brand",
        choices=["zara", "adidas"],
        default=None,
        help="scrape one brand only (default: both)",
    )
    parser.add_argument(
        "--gender",
        choices=["men", "women"],
        default=None,
        help="scrape one gender only (default: both)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="max kept products per brand (overrides mode default; e.g. --limit 100)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.mode, args.brand, args.gender, args.limit))


if __name__ == "__main__":
    main()
