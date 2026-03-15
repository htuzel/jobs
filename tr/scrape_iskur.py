"""
İŞKUR Meslek Sozlugu Scraper
Scrapes Turkish occupation definitions from İŞKUR (esube.iskur.gov.tr).
Uses Playwright for dynamic ASP.NET page rendering.

Cache strategy: data/raw/iskur/<meslek_kodu>.html per detail page,
data/iskur_meslekler_raw.json for the full index list.

Usage:
    python scrape_iskur.py                        # scrape index + all detail pages
    python scrape_iskur.py --index-only           # only build the occupation list
    python scrape_iskur.py --start 0 --end 10     # scrape first 10 detail pages
    python scrape_iskur.py --force                # re-scrape ignoring cache

İŞKUR page structure (MeslekleriTaniyalim.aspx):
  - ASP.NET postback page with category dropdowns
  - Table with columns: Meslek Kodu | Meslek | Eğitim Seviyesi | Kategori | Dosya
  - Detail popup: ViewMeslekDetayPopUp.aspx?uiID=<meslek_kodu>
  - 10 categories to iterate through
"""
import argparse
import json
import os
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from utils import slugify_tr as slugify

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ISKUR_BASE = "https://esube.iskur.gov.tr"
ISKUR_SOZLUK = f"{ISKUR_BASE}/Meslek/MeslekleriTaniyalim.aspx"
ISKUR_DETAIL = f"{ISKUR_BASE}/Meslek/ViewMeslekDetayPopUp.aspx?uiID="
RAW_DIR = "data/raw/iskur"
INDEX_FILE = "data/iskur_meslekler_raw.json"

# İŞKUR categories (value attributes from the dropdown)
KATEGORILER = [
    "Adalet Mesleklerini Tanıyalım",
    "Bilişim Mesleklerini Tanıyalım",
    "Ekonomi/Finans Mesleklerini Tanıyalım",
    "Mühendislik Mesleklerini Tanıyalım",
    "Öğretmenlik Mesleklerini Tanıyalım",
    "Sağlık Meslekleri Tanıyalım",
    "Sanat Mesleklerini Tanıyalım",
    "Spor Mesleklerini Tanıyalım",
    "Tarım/Hayvancılık Mesleklerini Tanıyalım",
    "Turizm Mesleklerini Tanıyalım",
]

EGITIM_SEVIYELERI = [
    "Fakülte Meslekleri",
    "Meslek Yüksekokul Meslekleri",
    "Lise Meslekleri",
    "Mesleki Eğitim Merkezi Meslekleri",
    "Kurs Meslekleri",
]

# Map İŞKUR education labels to our standardized levels
EGITIM_MAP = {
    "Fakülte Meslekleri": "Lisans",
    "Meslek Yüksekokul Meslekleri": "On Lisans",
    "Lise Meslekleri": "Lise",
    "Mesleki Eğitim Merkezi Meslekleri": "Meslek Lisesi",
    "Kurs Meslekleri": "Kurs",
}


# ---------------------------------------------------------------------------
# Pure parsing helpers (no I/O — testable without Playwright)
# ---------------------------------------------------------------------------

def parse_iskur_table(html: str) -> list:
    """Parse İŞKUR MeslekleriTaniyalim results table.

    The table has columns: Meslek Kodu | Meslek | Eğitim Seviyesi | Kategori | Dosya
    Detail popup links use: javascript:MeslekDetayPopUp('CODE')

    Returns list of dicts with keys:
        meslek_adi, meslek_kodu, egitim_seviyesi, kategori, url, slug
    """
    soup = BeautifulSoup(html, "html.parser")
    occupations = []

    # Find all table rows - skip header rows
    for tr in soup.select("table[cellspacing='0'] tr, table.table tr, #ctl04_gridMeslekleriTaniyalim tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        meslek_kodu = tds[0].get_text(strip=True)
        meslek_adi = tds[1].get_text(strip=True)

        # Skip header-like rows
        if meslek_kodu == "Meslek Kodu" or not meslek_kodu:
            continue

        # Validate meslek_kodu format (should be like "2411" or "3258.02")
        if not re.match(r"^\d{4}", meslek_kodu):
            continue

        egitim = tds[2].get_text(strip=True) if len(tds) > 2 else ""
        kategori = tds[3].get_text(strip=True) if len(tds) > 3 else ""

        # Build detail URL
        url = f"{ISKUR_DETAIL}{meslek_kodu}"

        # Also check for popup links in the row
        popup_link = tr.find("a", href=re.compile(r"MeslekDetayPopUp"))
        if popup_link:
            match = re.search(r"MeslekDetayPopUp\('([^']+)'\)", popup_link.get("href", ""))
            if match:
                code_from_link = match.group(1)
                if code_from_link:
                    meslek_kodu = code_from_link
                    url = f"{ISKUR_DETAIL}{meslek_kodu}"

        occupations.append({
            "meslek_adi": meslek_adi,
            "meslek_kodu": meslek_kodu,
            "egitim_seviyesi": EGITIM_MAP.get(egitim, egitim),
            "kategori": kategori.replace(" Mesleklerini Tanıyalım", "").replace(" Meslekleri Tanıyalım", ""),
            "url": url,
            "slug": slugify(meslek_adi),
        })

    return occupations


def parse_iskur_index(html: str) -> list:
    """Backward-compatible wrapper for parse_iskur_table."""
    return parse_iskur_table(html)


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------

def scrape_by_category(page, delay: float = 2.0) -> list:
    """Scrape occupations by iterating through all categories.

    For each category, selects it in the dropdown and clicks search.
    Collects all results across categories, deduplicating by meslek_kodu.
    """
    all_occupations = {}

    page.goto(ISKUR_SOZLUK, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # Uncheck "Sadece meslek bilgisi dosyası olanları getir" if present
    checkbox = page.query_selector("input[type='checkbox'][id*='meslek']")
    if checkbox and checkbox.is_checked():
        checkbox.click()
        time.sleep(1)

    # Try each education level - this gives broader coverage
    for egitim in EGITIM_SEVIYELERI:
        print(f"  Searching education level: {egitim}...")
        try:
            # Select education level
            egitim_select = page.query_selector("select[id*='EgitimSeviye'], select[id*='egitim'], select[name*='EgitimSeviye']")
            if egitim_select:
                page.select_option(egitim_select, label=egitim)
                time.sleep(1)

            # Click search button
            search_btn = page.query_selector("a[id*='Search'], input[id*='Search'], button[id*='Search'], a.btn-primary")
            if search_btn:
                search_btn.click()
                time.sleep(3)

            # Parse results
            html = page.content()
            results = parse_iskur_table(html)
            for occ in results:
                if occ["meslek_kodu"] not in all_occupations:
                    all_occupations[occ["meslek_kodu"]] = occ

            print(f"    Found {len(results)} occupations (total unique: {len(all_occupations)})")

            # Click clear/reset
            clear_btn = page.query_selector("a[id*='ClearUI'], a.btn-info")
            if clear_btn:
                clear_btn.click()
                time.sleep(2)

        except Exception as e:
            print(f"    ERROR: {e}")

        time.sleep(delay)

    # Also try each category
    for kat in KATEGORILER:
        print(f"  Searching category: {kat}...")
        try:
            page.goto(ISKUR_SOZLUK, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # Select category
            kat_select = page.query_selector("select[id*='Kategori'], select[id*='kategori']")
            if kat_select:
                page.select_option(kat_select, label=kat)
                time.sleep(1)

            # Click search
            search_btn = page.query_selector("a[id*='Search'], a.btn-primary")
            if search_btn:
                search_btn.click()
                time.sleep(3)

            html = page.content()
            results = parse_iskur_table(html)
            for occ in results:
                if occ["meslek_kodu"] not in all_occupations:
                    all_occupations[occ["meslek_kodu"]] = occ

            print(f"    Found {len(results)} occupations (total unique: {len(all_occupations)})")

        except Exception as e:
            print(f"    ERROR: {e}")

        time.sleep(delay)

    return list(all_occupations.values())


def scrape_detail(page, url: str) -> str:
    """Scrape a single occupation detail popup page."""
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
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--index-only", action="store_true")
    args = parser.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(INDEX_FILE) or ".", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "tr-TR,tr;q=0.9"})

        # Step 1: Get occupation index
        if not os.path.exists(INDEX_FILE) or args.force:
            print("Scraping İŞKUR meslek sozlugu by category + education level...")
            occupations = scrape_by_category(page, delay=args.delay)

            # Save raw HTML of last page for debugging
            debug_html = page.content()
            with open(os.path.join(RAW_DIR, "_index.html"), "w", encoding="utf-8") as f:
                f.write(debug_html)

            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(occupations, f, ensure_ascii=False, indent=2)
            print(f"\nFound {len(occupations)} unique occupations → {INDEX_FILE}")
        else:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                occupations = json.load(f)
            print(f"Loaded {len(occupations)} occupations from cache ({INDEX_FILE})")

        if args.index_only:
            browser.close()
            return

        # Step 2: Scrape detail pages
        subset = occupations[args.start:args.end]
        to_scrape = [
            occ for occ in subset
            if not os.path.exists(os.path.join(RAW_DIR, f"{occ['meslek_kodu']}.html")) or args.force
        ]

        print(f"Scraping {len(to_scrape)} detail pages (skipping {len(subset) - len(to_scrape)} cached)...")

        for i, occ in enumerate(to_scrape, start=1):
            cache_path = os.path.join(RAW_DIR, f"{occ['meslek_kodu']}.html")
            try:
                html = scrape_detail(page, occ["url"])
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  [{i}/{len(to_scrape)}] {occ['meslek_adi']} ({occ['meslek_kodu']}) — {len(html):,} bytes")
            except Exception as exc:
                print(f"  [{i}/{len(to_scrape)}] ERROR {occ['meslek_adi']}: {exc}")

            if i < len(to_scrape):
                time.sleep(args.delay)

        browser.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
