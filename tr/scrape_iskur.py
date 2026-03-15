"""
İŞKUR Meslek Sozlugu Scraper
Scrapes Turkish occupation definitions from İŞKUR (iskur.gov.tr).
Uses Playwright for dynamic page rendering.

Cache strategy: data/raw/iskur/<meslek_kodu>.html per detail page,
data/iskur_meslekler_raw.json for the full index list.

Usage:
    python scrape_iskur.py                        # scrape index + all detail pages
    python scrape_iskur.py --index-only           # only build the occupation list
    python scrape_iskur.py --start 0 --end 10     # scrape first 10 detail pages
    python scrape_iskur.py --force                # re-scrape ignoring cache

NOTE: CSS selectors in parse_iskur_index() are placeholders.  Run
      scrape_iskur.py --index-only once, inspect the saved
      data/raw/iskur/_index.html and update selectors to match the
      actual İŞKUR HTML structure before running detail scraping.
"""
import argparse
import json
import os
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ISKUR_BASE = "https://iskur.gov.tr"
ISKUR_SOZLUK = f"{ISKUR_BASE}/is-arayan/meslek-sozlugu"
RAW_DIR = "data/raw/iskur"
INDEX_FILE = "data/iskur_meslekler_raw.json"


# ---------------------------------------------------------------------------
# Pure parsing helpers (no I/O — testable without Playwright)
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Generate a URL-safe slug from Turkish text.

    Maps Turkish-specific characters (ç,ğ,ı,ö,ş,ü and their uppercase
    equivalents) to ASCII, then collapses non-alphanumeric runs to hyphens.

    Implementation note: str.maketrans cannot handle multi-codepoint characters
    such as İ (U+0130, dotted capital I) because Python's unicode lower() turns
    it into the two-codepoint sequence 'i\u0307' rather than plain 'i'.  We
    therefore pre-replace multi-codepoint problem chars before calling lower().
    """
    # Pre-replace characters whose unicode lower() produces multi-codepoint
    # sequences that confuse str.maketrans:
    #   İ (U+0130, dotted capital I) → lower() gives 'i\u0307' (two chars)
    #   ı (U+0131, dotless small I)  → keep as ASCII 'i' directly
    text = text.replace("İ", "i").replace("ı", "i")

    # Single-codepoint Turkish characters safe for str.maketrans
    tr_map = str.maketrans(
        "çğöşüÇĞÖŞÜâîûÂÎÛ",
        "cgosuCGOSUaiuAIU",
    )
    slug = text.lower().translate(tr_map)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def parse_iskur_index(html: str) -> list:
    """Parse İŞKUR meslek sozlugu index page and return occupation list.

    Returns a list of dicts with keys:
        meslek_adi  — Turkish occupation name
        meslek_kodu — ISCO-08 code string (may be empty if not found)
        url         — Absolute URL to the occupation's detail page
        slug        — URL-safe ASCII slug derived from meslek_adi

    Selector strategy (most-to-least specific):
      1. Looks for elements matching .meslek-item, tr[data-isco], or
         .list-group-item that contain an <a> tag.
      2. For each match tries to read the ISCO code from a .isco element,
         a [data-isco] attribute, or the second <td>.
      3. Falls back to extracting a numeric trailing segment from the href.

    NOTE: These selectors are placeholders.  After manually inspecting the
    live İŞKUR page update this selector string to match the real structure.
    """
    soup = BeautifulSoup(html, "html.parser")
    occupations = []

    # Candidate selectors — update after real HTML inspection.
    candidates = soup.select(
        ".meslek-item, tr[data-isco], .list-group-item, "
        "table.meslek-tablosu tr, .occupation-row"
    )

    for item in candidates:
        link = item.find("a")
        if not link:
            continue

        meslek_adi = link.get_text(strip=True)
        if not meslek_adi:
            continue

        href = link.get("href", "")

        # Try to extract ISCO code from a dedicated element or attribute
        isco_el = item.select_one(".isco, [data-isco], td:nth-child(2)")
        meslek_kodu = ""
        if isco_el:
            candidate_code = isco_el.get_text(strip=True)
            if candidate_code.isdigit():
                meslek_kodu = candidate_code
            else:
                # data-isco attribute fallback
                meslek_kodu = item.get("data-isco", "")

        # URL fallback: extract trailing numeric segment from href
        if not meslek_kodu and href:
            parts = href.rstrip("/").split("/")
            if parts and parts[-1].isdigit():
                meslek_kodu = parts[-1]

        # Build absolute URL
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            url = f"{ISKUR_BASE}{href}"
        else:
            url = f"{ISKUR_BASE}/{href}" if href else ""

        occupations.append({
            "meslek_adi": meslek_adi,
            "meslek_kodu": meslek_kodu,
            "url": url,
            "slug": slugify(meslek_adi),
        })

    return occupations


# ---------------------------------------------------------------------------
# Playwright helpers (I/O — not unit-tested, tested via integration)
# ---------------------------------------------------------------------------

def scrape_index(page) -> str:
    """Navigate to the İŞKUR meslek sozlugu and return the full rendered HTML.

    Handles simple pagination: if a "next page" or "load more" button
    is present it is clicked until exhausted.
    """
    page.goto(ISKUR_SOZLUK, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)  # Allow dynamic content to render

    # Exhaust pagination if present
    while True:
        more_btn = page.query_selector(
            "[class*='more'], [class*='devam'], .pagination .next, "
            "a[rel='next'], button.yukle-daha"
        )
        if not more_btn:
            break
        try:
            more_btn.click()
            time.sleep(2)
        except Exception:
            break

    return page.content()


def scrape_detail(page, url: str) -> str:
    """Scrape a single occupation detail page and return its HTML."""
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    time.sleep(1)
    return page.content()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="İŞKUR Meslek Sozlugu Scraper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--start", type=int, default=0,
                        help="Start index for detail scraping (inclusive)")
    parser.add_argument("--end", type=int, default=None,
                        help="End index for detail scraping (exclusive)")
    parser.add_argument("--force", action="store_true",
                        help="Re-scrape pages even if cached HTML exists")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Polite delay in seconds between detail requests")
    parser.add_argument("--index-only", action="store_true",
                        help="Only scrape the occupation index, skip detail pages")
    args = parser.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)

    with sync_playwright() as p:
        # Non-headless for easier debugging and bypassing bot-detection
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "tr-TR,tr;q=0.9"})

        # ------------------------------------------------------------------
        # Step 1: Get occupation index
        # ------------------------------------------------------------------
        if not os.path.exists(INDEX_FILE) or args.force:
            print("Scraping İŞKUR meslek sozlugu index...")
            index_html = scrape_index(page)

            # Save raw HTML for manual selector debugging
            debug_path = os.path.join(RAW_DIR, "_index.html")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(index_html)
            print(f"Saved raw index HTML to {debug_path}")

            occupations = parse_iskur_index(index_html)
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(occupations, f, ensure_ascii=False, indent=2)
            print(f"Found {len(occupations)} occupations → {INDEX_FILE}")
        else:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                occupations = json.load(f)
            print(f"Loaded {len(occupations)} occupations from cache ({INDEX_FILE})")

        if args.index_only:
            browser.close()
            return

        # ------------------------------------------------------------------
        # Step 2: Scrape detail pages (incremental, cache-aware)
        # ------------------------------------------------------------------
        subset = occupations[args.start:args.end]
        to_scrape = []
        for occ in subset:
            cache_path = os.path.join(RAW_DIR, f"{occ['meslek_kodu']}.html")
            if not os.path.exists(cache_path) or args.force:
                to_scrape.append(occ)

        cached_count = len(subset) - len(to_scrape)
        print(
            f"Scraping {len(to_scrape)} detail pages "
            f"(skipping {cached_count} cached)..."
        )

        for i, occ in enumerate(to_scrape, start=1):
            cache_path = os.path.join(RAW_DIR, f"{occ['meslek_kodu']}.html")
            try:
                html = scrape_detail(page, occ["url"])
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  [{i}/{len(to_scrape)}] {occ['meslek_adi']} "
                      f"({occ['meslek_kodu']}) — {len(html):,} bytes")
            except Exception as exc:
                print(f"  [{i}/{len(to_scrape)}] ERROR {occ['meslek_adi']}: {exc}")

            # Polite delay between requests (skip after last item)
            if i < len(to_scrape):
                time.sleep(args.delay)

        browser.close()

    cached_total = len(
        [f for f in os.listdir(RAW_DIR) if f.endswith(".html") and not f.startswith("_")]
    )
    print(f"\nDone. {cached_total} detail pages cached in {RAW_DIR}/")


if __name__ == "__main__":
    main()
