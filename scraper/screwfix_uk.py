"""Screwfix.com (GBP, UK's largest trade supplier) — no product sitemap is
published, but the 599 category sitemaps embed ~20 product URLs each, and
every product page carries clean schema.org ld+json with GBP price.

Pipeline: category sitemap -> product URLs -> product page ld+json.
"""
import re
from common import get, sitemap_urls, ldjson_products, offer_from_ld, sane_price, valid_ean, first_str, write_jsonl, pmap

BASE = "https://www.screwfix.com"
OUT = "data/latest/screwfix_uk.jsonl"
PROD_RE = re.compile(r'^/p/[^"]+/[^"]+$')


def fetch_url_list(limit=None):
    # category sitemaps live in the main sitemap index
    idx = get(f"{BASE}/sitemap-en-gb.xml")
    cat_files = [u for u in sitemap_urls(idx) if "/c/" in u or u.endswith("/cat830034")]
    urls = []
    seen = set()
    for f in cat_files:
        try:
            xml = get(f)
        except Exception:
            continue
        page = get(BASE + f) if not f.startswith("http") else get(f)
        # category pages embed product URLs as itemList JSON-LD
        pus = re.findall(r'"url":"(/p/[^"]+/[^"]+)"', page)
        for pu in pus:
            if PROD_RE.match(pu) and pu not in seen:
                seen.add(pu)
                urls.append(BASE + pu)
                if limit and len(urls) >= limit:
                    return urls
    return urls


def handle(u, html):
    rows = []
    for p in ldjson_products(html):
        off = p.get("offers") or {}
        if isinstance(off, list):
            off = off[0] if off and isinstance(off[0], dict) else {}
        amt = off.get("price")
        if not amt:
            continue
        price = sane_price(amt)
        if not price:
            continue
        avail = str(off.get("availability") or "")
        sku = u.rstrip("/").rsplit("/", 1)[-1].upper()
        rows.append({
            "chain": "screwfix_uk",
            "country": "uk",
            "currency": off.get("priceCurrency", "GBP"),
            "sku": sku,
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")),
            "name": p.get("name"),
            "url": u,
            "price": price,
            "in_stock": ("InStock" in avail) if avail else None,
            "image": first_str(p.get("image")),
        })
        break
    return rows


def scrape(limit=None):
    def work(u):
        try:
            return handle(u, get(u))
        except Exception as e:
            print(f"  ! {u}: {e}")
            return []
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("screwfix_uk: %d products -> %s" % (len(rows), OUT))
