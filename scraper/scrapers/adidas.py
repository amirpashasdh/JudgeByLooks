import asyncio
import json
import random
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from scrapers.filters import should_keep


CATEGORIES = [
    {
        "name": "Men Shoes",
        "url_path": "herren-schuhe",
        "taxonomy_slug": "schuhe",   # matches plp-app/api/taxonomy/{slug}
        "gender": "men",
    },
    {
        "name": "Women Shoes",
        "url_path": "damen-schuhe",
        "taxonomy_slug": "damen-schuhe",
        "gender": "women",
    },
]

_TAXONOMY_RE = re.compile(r"plp-app/api/taxonomy/", re.I)


def _rand_delay(lo: float = 0.5, hi: float = 2.0) -> float:
    return random.uniform(lo, hi)


def _normalize(raw: dict, category: str) -> dict:
    pid = str(raw.get("id") or "")
    name = raw.get("title") or raw.get("name") or ""

    # Price: priceData.prices[0].value
    price: float | None = None
    currency = "EUR"
    price_data = raw.get("priceData") or {}
    prices = price_data.get("prices") or []
    if prices:
        price = prices[0].get("value")

    # Colors: colourVariations is a list of article IDs (not color names)
    # Use category + subtitle as color context since color names aren't in list API
    colour_vars = raw.get("colourVariations") or []
    colors = colour_vars  # article IDs; caller can resolve if needed

    # Images
    image_urls = []
    for key in ("image", "hoverImage"):
        val = raw.get(key)
        if val and isinstance(val, str):
            image_urls.append(val)

    product_url = raw.get("url") or f"https://www.adidas.de/{pid}.html"
    description = raw.get("subTitle") or raw.get("description") or ""

    return {
        "id": pid,
        "brand": "Adidas",
        "name": name,
        "category": category,
        "price": price,
        "currency": currency,
        "colors": colors,
        "description": description,
        "image_urls": image_urls,
        "product_url": product_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


async def _make_browser_context(pw):
    browser = await pw.chromium.launch(
        channel="chrome",
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
    )
    await Stealth().apply_stealth_async(context)
    return browser, context


async def _scrape_dom_products(page, category: str, limit: int | None) -> list[dict]:
    """DOM fallback when the taxonomy API didn't fire."""
    products: list[dict] = []
    seen: set[str] = set()

    articles = await page.query_selector_all("article")
    for art in articles:
        if limit and len(products) >= limit:
            break
        try:
            link_el = await art.query_selector("a[href]")
            href = (await link_el.get_attribute("href")) if link_el else ""
            product_url = href if (href or "").startswith("http") else f"https://www.adidas.de{href}"

            pid_match = re.search(r"/([A-Z0-9]{5,8})\.html", href or "")
            pid = pid_match.group(1) if pid_match else href.split("/")[-1].split(".")[0]

            name_el = await art.query_selector("p, h2, h3, [data-auto-id*='title']")
            name = (await name_el.inner_text()).strip() if name_el else ""

            img_el = await art.query_selector("img")
            img_src = (await img_el.get_attribute("src")) if img_el else ""

            price_el = await art.query_selector("[class*='price'], [data-auto-id*='price']")
            price_text = (await price_el.inner_text()).strip() if price_el else ""
            price_match = re.search(r"[\d,.]+", price_text.replace(",", ""))
            price_num: float | None = float(price_match.group()) if price_match else None

            if pid and pid not in seen:
                seen.add(pid)
                products.append({
                    "id": pid,
                    "brand": "Adidas",
                    "name": name,
                    "category": category,
                    "price": price_num,
                    "currency": "EUR",
                    "colors": [],
                    "description": "",
                    "image_urls": [img_src] if img_src else [],
                    "product_url": product_url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            pass

    return products


async def scrape(mode: str, save_callback, gender: str | None = None, limit: int | None = None) -> tuple[list[dict], dict]:
    if limit is None:
        limit = 10 if mode == "test" else None
    all_products: list[dict] = []
    errors: list[str] = []
    total_filtered = 0

    active_cats = [
        c for c in CATEGORIES
        if gender is None or gender.lower() in c["name"].lower()
    ]

    async with async_playwright() as pw:
        browser, context = await _make_browser_context(pw)
        page = await context.new_page()

        # Warm up: load homepage first so Kasada challenge passes
        print("[Adidas] Warming up on homepage…")
        try:
            await page.goto("https://www.adidas.de/", wait_until="load", timeout=30_000)
            await asyncio.sleep(_rand_delay(2.0, 3.0))
        except Exception as exc:
            print(f"[Adidas] Homepage warm-up error (continuing): {exc}")

        for cat in active_cats:
            if limit and len(all_products) >= limit:
                break

            cat_products: list[dict] = []
            cat_filtered = 0
            api_blobs: list[dict] = []
            seen_ids: set[str] = set()

            async def handle_response(response):
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                if not _TAXONOMY_RE.search(response.url):
                    return
                try:
                    body = await response.json()
                    api_blobs.append(body)
                except Exception:
                    pass

            page.on("response", handle_response)

            success = False
            for attempt in range(1, 3):
                try:
                    print(f"[Adidas] {cat['name']} — attempt {attempt}")
                    cat_url = f"https://www.adidas.de/{cat['url_path']}"
                    await page.goto(cat_url, wait_until="load", timeout=40_000)
                    await asyncio.sleep(_rand_delay(2.0, 4.0))
                    success = True
                    break
                except Exception as exc:
                    print(f"[Adidas] {cat['name']} attempt {attempt} failed: {exc}")
                    await asyncio.sleep(2)

            if not success:
                msg = f"Adidas | {cat['name']} — failed after 2 retries"
                print(f"[Adidas] ERROR: {msg}")
                errors.append(msg)
                page.remove_listener("response", handle_response)
                continue

            # Scroll to load lazy products
            prev_count = 0
            max_scrolls = 2 if mode == "test" else 20
            for _ in range(max_scrolls):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(_rand_delay(1.0, 2.0))
                articles = await page.query_selector_all("article")
                current = len(articles)
                if limit and current >= limit:
                    break
                if current == prev_count and _ >= 2:
                    break
                prev_count = current

            page.remove_listener("response", handle_response)

            # Parse taxonomy API responses
            for blob in api_blobs:
                for raw in blob.get("products") or []:
                    p = _normalize(raw, cat["name"])
                    if p["id"] and p["id"] not in seen_ids:
                        seen_ids.add(p["id"])
                        if should_keep(p, "Adidas"):
                            cat_products.append(p)
                            if limit and len(cat_products) >= limit:
                                break
                        else:
                            cat_filtered += 1
                if limit and len(cat_products) >= limit:
                    break

            # DOM fallback
            if not cat_products and not cat_filtered:
                print(f"[Adidas] {cat['name']} — no taxonomy API data, trying DOM fallback")
                raw_dom = await _scrape_dom_products(page, cat["name"], None)
                for p in raw_dom:
                    if limit and len(cat_products) >= limit:
                        break
                    if should_keep(p, "Adidas"):
                        cat_products.append(p)
                    else:
                        cat_filtered += 1

            total_filtered += cat_filtered
            print(
                f"[Adidas] {cat['name']} — kept {len(cat_products)}, filtered {cat_filtered}"
            )
            all_products.extend(cat_products)
            await save_callback(all_products)
            await asyncio.sleep(_rand_delay())

        await browser.close()

    summary = {
        "brand": "Adidas",
        "categories": [c["name"] for c in active_cats],
        "total_products": len(all_products),
        "total_filtered": total_filtered,
        "errors": errors,
    }
    return all_products, summary
