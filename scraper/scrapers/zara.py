import asyncio
import json
import random
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from scrapers.filters import should_keep


# Zara geo-redirects /en/en/ to the local market. The generic l1039/l1040 codes
# resolve to Bags in Spain (the detected market). Use the explicit /es/en/ paths
# for the clothing-collection landing pages instead.
CATEGORIES = [
    {
        "name": "Woman > Clothing",
        "url": "https://www.zara.com/es/en/woman-collections-l2158.html",
    },
    {
        "name": "Man > Clothing",
        "url": "https://www.zara.com/es/en/man-collection-l622.html",
    },
]

_PRODUCTS_RE = re.compile(r"/category/\d+/products", re.I)


def _rand_delay(lo: float = 0.5, hi: float = 2.0) -> float:
    return random.uniform(lo, hi)


def _build_image_url(xmedia_item: dict) -> str:
    delivery = (xmedia_item.get("extraInfo") or {}).get("deliveryUrl") or ""
    if delivery:
        return delivery
    path = xmedia_item.get("path", "")
    ts = xmedia_item.get("timestamp", "")
    name = xmedia_item.get("name", "")
    if path and name:
        return f"https://static.zara.net{path}/{name}.jpg?ts={ts}"
    return ""


def _normalize(raw: dict, category: str) -> dict:
    pid = str(raw.get("id") or raw.get("reference") or "")
    name = raw.get("name") or ""

    # Price: Zara stores in cents (4995 → 49.95)
    price_raw = raw.get("price")
    if isinstance(price_raw, (int, float)) and price_raw > 1000:
        price = round(price_raw / 100, 2)
    elif isinstance(price_raw, dict):
        v = price_raw.get("value") or price_raw.get("amount") or 0
        price = round(v / 100, 2) if v > 1000 else v
    else:
        price = price_raw

    currency = "EUR"

    # Colors and images live under detail.colors[].{name, xmedia}
    colors: list[str] = []
    image_urls: list[str] = []
    detail = raw.get("detail") or {}
    for col in detail.get("colors") or []:
        col_name = col.get("name") or ""
        if col_name:
            colors.append(col_name)
        for xm in col.get("xmedia") or []:
            url = _build_image_url(xm)
            if url:
                image_urls.append(url)

    # Fallback images from top-level xmedia
    if not image_urls:
        for xm in raw.get("xmedia") or []:
            url = _build_image_url(xm)
            if url:
                image_urls.append(url)

    # Product URL via SEO slug
    seo = raw.get("seo") or {}
    seo_keyword = seo.get("keyword") or seo.get("seoProductId") or pid
    product_url = f"https://www.zara.com/en/en/{seo_keyword}-p{pid}.html"

    description = raw.get("description") or ""

    return {
        "id": pid,
        "brand": "Zara",
        "name": name,
        "category": category,
        "price": price,
        "currency": currency,
        "colors": colors,
        "description": description,
        "image_urls": image_urls[:5],
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


async def scrape(mode: str, save_callback, gender: str | None = None, limit: int | None = None) -> tuple[list[dict], dict]:
    if limit is None:
        limit = 10 if mode == "test" else None
    all_products: list[dict] = []
    errors: list[str] = []
    total_filtered = 0

    _gender_tokens = {"men": {"man"}, "women": {"woman"}}
    active_cats = [
        c for c in CATEGORIES
        if gender is None
        or bool(_gender_tokens.get(gender, set()) & set(c["name"].lower().split()))
    ]

    async with async_playwright() as pw:
        browser, context = await _make_browser_context(pw)
        page = await context.new_page()

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
                if not _PRODUCTS_RE.search(response.url):
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
                    print(f"[Zara] {cat['name']} — attempt {attempt}")
                    await page.goto(cat["url"], wait_until="load", timeout=35_000)
                    await asyncio.sleep(_rand_delay(2.0, 3.5))
                    # Scroll to trigger pagination / lazy loads
                    for _ in range(4):
                        await page.keyboard.press("End")
                        await asyncio.sleep(_rand_delay(0.8, 1.5))
                    success = True
                    break
                except Exception as exc:
                    print(f"[Zara] {cat['name']} attempt {attempt} failed: {exc}")
                    await asyncio.sleep(2)

            page.remove_listener("response", handle_response)

            if not success:
                msg = f"Zara | {cat['name']} — failed after 2 retries"
                print(f"[Zara] ERROR: {msg}")
                errors.append(msg)
                continue

            # Parse API blobs
            for blob in api_blobs:
                for group in blob.get("productGroups") or []:
                    for element in group.get("elements") or []:
                        for comp in element.get("commercialComponents") or []:
                            if comp.get("type") != "Product":
                                continue
                            p = _normalize(comp, cat["name"])
                            if p["id"] and p["id"] not in seen_ids:
                                seen_ids.add(p["id"])
                                if should_keep(p, "Zara"):
                                    cat_products.append(p)
                                    if limit and len(cat_products) >= limit:
                                        break
                                else:
                                    cat_filtered += 1
                        if limit and len(cat_products) >= limit:
                            break
                    if limit and len(cat_products) >= limit:
                        break
                if limit and len(cat_products) >= limit:
                    break

            # DOM fallback when API interception yielded nothing
            if not cat_products:
                print(f"[Zara] {cat['name']} — no API data, trying DOM fallback")
                items = await page.query_selector_all("li[class*='product']")
                for item in items:
                    if limit and len(cat_products) >= limit:
                        break
                    try:
                        pid_attr = await item.get_attribute("data-productid") or ""
                        name_el = await item.query_selector("[class*='product-grid-product-info__name']")
                        name = (await name_el.inner_text()).strip() if name_el else ""
                        price_el = await item.query_selector("[class*='price__amount']")
                        price_text = (await price_el.inner_text()).strip() if price_el else "0"
                        price_num = float(re.sub(r"[^\d.]", "", price_text) or 0)
                        link_el = await item.query_selector("a[href]")
                        href = await link_el.get_attribute("href") if link_el else ""
                        product_url = href if href.startswith("http") else f"https://www.zara.com{href}"
                        img_el = await item.query_selector("img")
                        img_src = await img_el.get_attribute("src") if img_el else ""
                        pid = pid_attr or href.split("-p")[-1].split(".html")[0]
                        if pid and pid not in seen_ids:
                            seen_ids.add(pid)
                            p = {
                                "id": pid,
                                "brand": "Zara",
                                "name": name,
                                "category": cat["name"],
                                "price": price_num,
                                "currency": "EUR",
                                "colors": [],
                                "description": "",
                                "image_urls": [img_src] if img_src else [],
                                "product_url": product_url,
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            }
                            if should_keep(p, "Zara"):
                                cat_products.append(p)
                            else:
                                cat_filtered += 1
                    except Exception:
                        pass

            total_filtered += cat_filtered
            print(
                f"[Zara] {cat['name']} — kept {len(cat_products)}, filtered {cat_filtered}"
            )
            all_products.extend(cat_products)
            await save_callback(all_products)
            await asyncio.sleep(_rand_delay())

        await browser.close()

    summary = {
        "brand": "Zara",
        "categories": [c["name"] for c in active_cats],
        "total_products": len(all_products),
        "total_filtered": total_filtered,
        "errors": errors,
    }
    return all_products, summary
