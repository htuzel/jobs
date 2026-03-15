# Turkiye AI Maruz Kalma Analizi - Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Turkish AI job exposure analysis web app with ~250-350 occupations, dual scoring metrics (AI exposure 0-10 + "5 year prediction"), adapted from the existing US version.

**Architecture:** Fork & Adapt the existing US pipeline (scrape → parse → CSV → LLM score → site data → frontend). Each pipeline step is a standalone Python script in `tr/` subdirectory. Frontend is a single-page vanilla HTML/CSS/JS app with search-first UX, card-based listing, and side-by-side comparison feature.

**Tech Stack:** Python 3.10+, Playwright (İŞKUR scraping), pandas/openpyxl (TÜİK Excel), google-generativeai SDK (Gemini 2.5 Flash), vanilla HTML/CSS/JS (frontend)

**Spec:** `docs/superpowers/specs/2026-03-15-turkiye-ai-exposure-design.md`

**Reference:** Existing US pipeline at project root (scrape.py, score.py, site/index.html etc.)

---

## Chunk 1: Project Setup & Data Collection

### Task 1: Project Scaffolding

**Files:**
- Create: `tr/requirements.txt`
- Create: `tr/.env.example`
- Create: `tr/data/raw/iskur/.gitkeep`
- Create: `tr/data/raw/tuik/.gitkeep`
- Create: `tr/site/.gitkeep`
- Create: `tr/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p tr/data/raw/iskur tr/data/raw/tuik tr/data/raw/parsed tr/site tr/tests
```

- [ ] **Step 2: Create requirements.txt**

```
# tr/requirements.txt
playwright>=1.58.0
pandas>=2.2.0
openpyxl>=3.1.0
google-generativeai>=0.8.0
python-dotenv>=1.2.0
beautifulsoup4>=4.14.0
pytest>=8.0.0
```

- [ ] **Step 3: Create .env.example**

```
# tr/.env.example
GEMINI_API_KEY=your_gemini_api_key_here
```

- [ ] **Step 4: Create .gitkeep files for empty directories**

```bash
touch tr/data/raw/iskur/.gitkeep tr/data/raw/tuik/.gitkeep tr/site/.gitkeep tr/tests/__init__.py
```

- [ ] **Step 5: Install dependencies and Playwright**

```bash
cd tr && pip install -r requirements.txt && playwright install chromium
```

- [ ] **Step 6: Commit**

```bash
git add tr/
git commit -m "feat(tr): scaffold Turkish AI exposure project structure"
```

---

### Task 2: İŞKUR Meslek Sozlugu Scraper

**Files:**
- Create: `tr/scrape_iskur.py`
- Create: `tr/tests/test_scrape_iskur.py`
- Reference: `scrape.py` (US version pattern)

**Context:** İŞKUR Meslek Sozlugu (iskur.gov.tr/is-arayan/meslek-sozlugu) lists Turkish occupations by ISCO-08 codes with definitions, education requirements, and related info. We need to scrape the occupation index page to get the full list, then scrape each occupation's detail page.

- [ ] **Step 1: Write test for occupation list parser**

```python
# tr/tests/test_scrape_iskur.py
import json
import os

def test_parse_iskur_index_html():
    """Test that we can extract occupation entries from İŞKUR index page HTML."""
    from scrape_iskur import parse_iskur_index

    # Sample HTML mimicking İŞKUR meslek sozlugu structure
    sample_html = """
    <html><body>
    <div class="meslek-listesi">
        <div class="meslek-item">
            <a href="/meslek/2411">Muhasebeci</a>
            <span class="isco">2411</span>
        </div>
        <div class="meslek-item">
            <a href="/meslek/5141">Kuafor</a>
            <span class="isco">5141</span>
        </div>
    </div>
    </body></html>
    """

    result = parse_iskur_index(sample_html)
    assert len(result) == 2
    assert result[0]["meslek_adi"] == "Muhasebeci"
    assert result[0]["meslek_kodu"] == "2411"
    assert result[1]["meslek_adi"] == "Kuafor"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tr && python -m pytest tests/test_scrape_iskur.py::test_parse_iskur_index_html -v
```
Expected: FAIL - `ModuleNotFoundError: No module named 'scrape_iskur'`

- [ ] **Step 3: Implement scrape_iskur.py**

```python
# tr/scrape_iskur.py
"""
İŞKUR Meslek Sozlugu Scraper
Scrapes Turkish occupation definitions from İŞKUR.
Uses Playwright for dynamic page rendering.
Cache: data/raw/iskur/<meslek_kodu>.html
"""
import argparse
import json
import os
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ISKUR_BASE = "https://iskur.gov.tr"
ISKUR_SOZLUK = f"{ISKUR_BASE}/is-arayan/meslek-sozlugu"
RAW_DIR = "data/raw/iskur"
INDEX_FILE = "data/iskur_meslekler_raw.json"


def parse_iskur_index(html: str) -> list[dict]:
    """Parse İŞKUR meslek sozlugu index page to extract occupation list."""
    soup = BeautifulSoup(html, "html.parser")
    occupations = []

    # NOTE: Actual CSS selectors must be determined by inspecting İŞKUR HTML.
    # These are placeholders - update after first manual inspection.
    for item in soup.select(".meslek-item, tr[data-isco], .list-group-item"):
        link = item.find("a")
        if not link:
            continue

        meslek_adi = link.get_text(strip=True)
        href = link.get("href", "")

        # Extract ISCO code from page or URL
        isco_el = item.select_one(".isco, [data-isco], td:nth-child(2)")
        meslek_kodu = isco_el.get_text(strip=True) if isco_el else ""

        # Fallback: try extracting code from URL
        if not meslek_kodu and "/" in href:
            parts = href.rstrip("/").split("/")
            candidate = parts[-1]
            if candidate.isdigit():
                meslek_kodu = candidate

        if meslek_adi:
            occupations.append({
                "meslek_adi": meslek_adi,
                "meslek_kodu": meslek_kodu,
                "url": href if href.startswith("http") else f"{ISKUR_BASE}{href}",
                "slug": slugify(meslek_adi),
            })

    return occupations


def slugify(text: str) -> str:
    """Generate URL-safe slug from Turkish text."""
    import re
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    slug = text.lower().translate(tr_map)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def scrape_index(page) -> str:
    """Navigate to İŞKUR meslek sozlugu and get full HTML."""
    page.goto(ISKUR_SOZLUK, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)  # Wait for dynamic content

    # Some pages have "load more" or pagination - handle if present
    while True:
        more_btn = page.query_selector("[class*='more'], [class*='devam'], .pagination .next")
        if not more_btn:
            break
        more_btn.click()
        time.sleep(2)

    return page.content()


def scrape_detail(page, url: str) -> str:
    """Scrape a single occupation detail page."""
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    time.sleep(1)
    return page.content()


def main():
    parser = argparse.ArgumentParser(description="İŞKUR Meslek Sozlugu Scraper")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Re-scrape cached pages")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests (seconds)")
    parser.add_argument("--index-only", action="store_true", help="Only scrape the index page")
    args = parser.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "tr-TR,tr;q=0.9"})

        # Step 1: Get occupation index
        if not os.path.exists(INDEX_FILE) or args.force:
            print("Scraping İŞKUR meslek sozlugu index...")
            index_html = scrape_index(page)

            # Save raw index HTML for debugging
            with open(f"{RAW_DIR}/_index.html", "w", encoding="utf-8") as f:
                f.write(index_html)

            occupations = parse_iskur_index(index_html)
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(occupations, f, ensure_ascii=False, indent=2)
            print(f"Found {len(occupations)} occupations")
        else:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                occupations = json.load(f)
            print(f"Loaded {len(occupations)} occupations from cache")

        if args.index_only:
            browser.close()
            return

        # Step 2: Scrape detail pages
        subset = occupations[args.start:args.end]
        to_scrape = []
        for occ in subset:
            cache_path = f"{RAW_DIR}/{occ['meslek_kodu']}.html"
            if not os.path.exists(cache_path) or args.force:
                to_scrape.append(occ)

        print(f"Scraping {len(to_scrape)} detail pages (skipping {len(subset) - len(to_scrape)} cached)...")

        for i, occ in enumerate(to_scrape):
            try:
                html = scrape_detail(page, occ["url"])
                cache_path = f"{RAW_DIR}/{occ['meslek_kodu']}.html"
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[{i+1}/{len(to_scrape)}] {occ['meslek_adi']} ({len(html)} bytes)")
            except Exception as e:
                print(f"[{i+1}/{len(to_scrape)}] ERROR {occ['meslek_adi']}: {e}")

            time.sleep(args.delay)

        browser.close()

    print("Done!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd tr && python -m pytest tests/test_scrape_iskur.py -v
```
Expected: PASS

- [ ] **Step 5: Manual inspection step**

Before running the full scraper, manually inspect İŞKUR's HTML structure:

```bash
cd tr && python -c "
from playwright.sync_api import sync_playwright
import time
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://iskur.gov.tr/is-arayan/meslek-sozlugu', wait_until='domcontentloaded')
    time.sleep(5)
    html = page.content()
    with open('data/raw/iskur/_index_debug.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Saved {len(html)} bytes')
    browser.close()
"
```

Then inspect `_index_debug.html` and update CSS selectors in `parse_iskur_index()` to match actual HTML structure.

- [ ] **Step 6: Update selectors and re-run tests**

After inspecting actual HTML, update the selectors in `scrape_iskur.py` and corresponding test HTML in `test_scrape_iskur.py` to match real structure.

- [ ] **Step 7: Run full index scrape**

```bash
cd tr && python scrape_iskur.py --index-only
```
Expected: `data/iskur_meslekler_raw.json` with occupation list

- [ ] **Step 8: Commit**

```bash
git add tr/scrape_iskur.py tr/tests/test_scrape_iskur.py
git commit -m "feat(tr): add İŞKUR meslek sozlugu scraper"
```

---

### Task 3: TÜİK Data Downloader & Parser

**Files:**
- Create: `tr/scrape_tuik.py`
- Create: `tr/tests/test_scrape_tuik.py`

**Context:** TÜİK publishes employment, salary, and informality data as Excel/CSV files on data.tuik.gov.tr. Unlike İŞKUR which needs Playwright, TÜİK data is downloaded directly and parsed with pandas.

- [ ] **Step 1: Write test for TÜİK Excel parsing**

```python
# tr/tests/test_scrape_tuik.py
import pandas as pd
import json
import os

def test_parse_tuik_employment_excel():
    """Test parsing TÜİK employment data from Excel format."""
    from scrape_tuik import parse_employment_data

    # Create a sample DataFrame mimicking TÜİK structure
    df = pd.DataFrame({
        "Meslek grubu": ["Muhasebe uzmanları", "Kuaförler"],
        "ISCO-08": ["2411", "5141"],
        "Toplam istihdam (bin)": [185, 320],
    })

    result = parse_employment_data(df)
    assert len(result) == 2
    assert result["2411"]["istihdam"] == 185000
    assert result["5141"]["istihdam"] == 320000


def test_parse_tuik_salary_data():
    """Test parsing TÜİK salary statistics."""
    from scrape_tuik import parse_salary_data

    df = pd.DataFrame({
        "Ekonomik faaliyet": ["Mali hizmetler", "Kisisel hizmetler"],
        "NACE Rev.2": ["K", "S"],
        "Ortalama brüt ücret (TL)": [28500, 18000],
    })

    result = parse_salary_data(df)
    assert result["K"]["ortalama_maas"] == 28500


def test_parse_tuik_informality():
    """Test parsing TÜİK informal employment rates."""
    from scrape_tuik import parse_informality_data

    df = pd.DataFrame({
        "Sektör": ["Sanayi", "Hizmet"],
        "Kayıt dışı oranı (%)": [18.5, 32.1],
    })

    result = parse_informality_data(df)
    assert result["Sanayi"] == 18.5
    assert result["Hizmet"] == 32.1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tr && python -m pytest tests/test_scrape_tuik.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement scrape_tuik.py**

```python
# tr/scrape_tuik.py
"""
TÜİK Data Downloader & Parser
Downloads employment, salary, and informality data from TÜİK.
Uses pandas for Excel/CSV parsing.
Output: data/raw/tuik/*.json (parsed statistics)
"""
import argparse
import json
import os
import pandas as pd
from playwright.sync_api import sync_playwright

TUIK_DATA = "https://data.tuik.gov.tr"
RAW_DIR = "data/raw/tuik"

# TÜİK table IDs - these are the statistical tables we need
# NOTE: Exact table IDs must be confirmed on data.tuik.gov.tr
TUIK_TABLES = {
    "employment": {
        "description": "İstihdam istatistikleri - meslek grubuna göre",
        "filename": "istihdam.xlsx",
    },
    "salary": {
        "description": "Kazanç istatistikleri - sektöre göre ortalama ücret",
        "filename": "kazanc.xlsx",
    },
    "informality": {
        "description": "Kayıt dışı istihdam oranları - sektöre göre",
        "filename": "kayitdisi.xlsx",
    },
    "education": {
        "description": "İstihdam - eğitim düzeyine göre",
        "filename": "egitim_istihdam.xlsx",
    },
    "growth": {
        "description": "Yıllık istihdam değişimi - sektöre göre",
        "filename": "buyume.xlsx",
    },
}


def parse_employment_data(df: pd.DataFrame) -> dict:
    """Parse TÜİK employment statistics by occupation group.
    Returns dict keyed by ISCO-08 code with employment counts.
    """
    result = {}

    # Try common TÜİK column naming patterns
    isco_col = None
    emp_col = None

    for col in df.columns:
        col_lower = col.lower() if isinstance(col, str) else ""
        if "isco" in col_lower or "meslek kodu" in col_lower:
            isco_col = col
        if "istihdam" in col_lower or "toplam" in col_lower:
            emp_col = col

    if isco_col is None or emp_col is None:
        print(f"WARNING: Could not find ISCO/employment columns. Columns: {list(df.columns)}")
        return result

    for _, row in df.iterrows():
        code = str(row[isco_col]).strip()
        if not code or code == "nan":
            continue
        emp = row[emp_col]
        # TÜİK often reports in thousands
        if isinstance(emp, (int, float)) and emp < 100000:
            emp = int(emp * 1000)
        else:
            emp = int(emp) if pd.notna(emp) else 0
        result[code] = {"istihdam": emp}

    return result


def parse_salary_data(df: pd.DataFrame) -> dict:
    """Parse TÜİK salary statistics by sector (NACE code).
    Returns dict keyed by NACE sector code.
    """
    result = {}

    nace_col = None
    salary_col = None

    for col in df.columns:
        col_lower = col.lower() if isinstance(col, str) else ""
        if "nace" in col_lower or "faaliyet" in col_lower:
            nace_col = col
        if "ücret" in col_lower or "kazanç" in col_lower or "maaş" in col_lower:
            salary_col = col

    if nace_col is None or salary_col is None:
        print(f"WARNING: Could not find NACE/salary columns. Columns: {list(df.columns)}")
        return result

    for _, row in df.iterrows():
        code = str(row[nace_col]).strip()
        if not code or code == "nan":
            continue
        salary = int(row[salary_col]) if pd.notna(row[salary_col]) else 0
        result[code] = {"ortalama_maas": salary}

    return result


def parse_informality_data(df: pd.DataFrame) -> dict:
    """Parse TÜİK informal employment rates by sector.
    Returns dict keyed by sector name with percentage.
    """
    result = {}

    sector_col = None
    rate_col = None

    for col in df.columns:
        col_lower = col.lower() if isinstance(col, str) else ""
        if "sektör" in col_lower or "faaliyet" in col_lower:
            sector_col = col
        if "kayıt" in col_lower or "informal" in col_lower or "oran" in col_lower:
            rate_col = col

    if sector_col is None or rate_col is None:
        print(f"WARNING: Could not find sector/rate columns. Columns: {list(df.columns)}")
        return result

    for _, row in df.iterrows():
        sector = str(row[sector_col]).strip()
        if not sector or sector == "nan":
            continue
        rate = float(row[rate_col]) if pd.notna(row[rate_col]) else 0
        result[sector] = rate

    return result


def download_tuik_files(force: bool = False):
    """Download Excel/CSV files from TÜİK using Playwright.

    NOTE: TÜİK's data portal may require navigating interactive pages.
    This function handles the download flow.
    """
    os.makedirs(RAW_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_extra_http_headers({"Accept-Language": "tr-TR,tr;q=0.9"})

        for key, table in TUIK_TABLES.items():
            filepath = os.path.join(RAW_DIR, table["filename"])
            if os.path.exists(filepath) and not force:
                print(f"Skipping {key}: {filepath} exists")
                continue

            print(f"Downloading {key}: {table['description']}")
            # NOTE: Manual step - navigate to correct TÜİK page and download
            # The implementer must identify exact URLs and download buttons
            # on data.tuik.gov.tr for each table type.
            print(f"  → Manual: Navigate to TÜİK and download {table['filename']}")
            print(f"  → Save to: {filepath}")

        browser.close()


def parse_all():
    """Parse all downloaded TÜİK files and save as JSON."""
    results = {}

    for key, table in TUIK_TABLES.items():
        filepath = os.path.join(RAW_DIR, table["filename"])
        if not os.path.exists(filepath):
            print(f"Skipping {key}: {filepath} not found")
            continue

        print(f"Parsing {key}...")
        df = pd.read_excel(filepath, engine="openpyxl")

        if key == "employment":
            results[key] = parse_employment_data(df)
        elif key == "salary":
            results[key] = parse_salary_data(df)
        elif key == "informality":
            results[key] = parse_informality_data(df)
        else:
            # Generic: save as list of dicts
            results[key] = df.to_dict(orient="records")

        # Save individual parsed JSON
        out_path = os.path.join(RAW_DIR, f"{key}_parsed.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results[key], f, ensure_ascii=False, indent=2)
        print(f"  → Saved to {out_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="TÜİK Data Downloader & Parser")
    parser.add_argument("--download", action="store_true", help="Download files from TÜİK")
    parser.add_argument("--parse", action="store_true", help="Parse downloaded files")
    parser.add_argument("--force", action="store_true", help="Re-download/re-parse")
    args = parser.parse_args()

    if args.download:
        download_tuik_files(force=args.force)

    if args.parse:
        parse_all()

    if not args.download and not args.parse:
        print("Use --download and/or --parse. Run --download first, then --parse.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd tr && python -m pytest tests/test_scrape_tuik.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tr/scrape_tuik.py tr/tests/test_scrape_tuik.py
git commit -m "feat(tr): add TÜİK data downloader and parser"
```

---

### Task 4: Master Occupation List Builder

**Files:**
- Create: `tr/build_master_list.py`
- Create: `tr/tests/test_build_master_list.py`

**Context:** Merges İŞKUR occupation definitions with TÜİK employment data to create `data/meslekler_master.json` - the canonical starting point for the entire pipeline. Uses `meslek_kodu` (ISCO-08) as the join key.

- [ ] **Step 1: Write test for master list merging**

```python
# tr/tests/test_build_master_list.py

def test_merge_iskur_tuik():
    """Test merging İŞKUR occupations with TÜİK employment data."""
    from build_master_list import merge_data

    iskur_data = [
        {"meslek_adi": "Muhasebeci", "meslek_kodu": "2411", "url": "http://...", "slug": "muhasebeci"},
        {"meslek_adi": "Kuafor", "meslek_kodu": "5141", "url": "http://...", "slug": "kuafor"},
        {"meslek_adi": "Bilinmeyen", "meslek_kodu": "9999", "url": "http://...", "slug": "bilinmeyen"},
    ]

    tuik_employment = {
        "2411": {"istihdam": 185000},
        "5141": {"istihdam": 320000},
    }

    tuik_salary = {
        "K": {"ortalama_maas": 28500},  # Mali hizmetler
    }

    # ISCO-08 to NACE sector mapping (simplified)
    isco_nace_map = {"2411": "K", "5141": "S"}

    result = merge_data(iskur_data, tuik_employment, tuik_salary, isco_nace_map)

    # Only occupations with employment data should be included
    assert len(result) == 2
    assert result[0]["meslek_kodu"] == "2411"
    assert result[0]["istihdam_sayisi"] == 185000
    assert result[0]["ortalama_maas"] == 28500


def test_slugify_turkish():
    """Test Turkish slug generation handles special characters."""
    from build_master_list import slugify_tr

    assert slugify_tr("Muhasebeci") == "muhasebeci"
    assert slugify_tr("Çilingir") == "cilingir"
    assert slugify_tr("Güvenlik Görevlisi") == "guvenlik-gorevlisi"
    assert slugify_tr("İnşaat İşçisi") == "insaat-iscisi"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tr && python -m pytest tests/test_build_master_list.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement build_master_list.py**

```python
# tr/build_master_list.py
"""
Master Occupation List Builder
Merges İŞKUR definitions with TÜİK employment/salary data.
Output: data/meslekler_master.json
Join key: meslek_kodu (ISCO-08)
"""
import json
import os
import re

ISKUR_INDEX = "data/iskur_meslekler_raw.json"
TUIK_DIR = "data/raw/tuik"
MASTER_FILE = "data/meslekler_master.json"

# Simplified ISCO major group to NACE sector mapping
# ISCO-08 first 1-2 digits → broad sector
ISCO_SECTOR_MAP = {
    "1": {"sektor": "Yonetim", "nace": "M"},
    "2": {"sektor": "Profesyonel Meslekler", "nace": "M"},
    "3": {"sektor": "Teknisyenler", "nace": "M"},
    "4": {"sektor": "Buro Hizmetleri", "nace": "N"},
    "5": {"sektor": "Hizmet ve Satis", "nace": "G"},
    "6": {"sektor": "Tarim ve Ormancilik", "nace": "A"},
    "7": {"sektor": "Sanatkârlar", "nace": "C"},
    "8": {"sektor": "Makine Operatorleri", "nace": "C"},
    "9": {"sektor": "Nitelik Gerektirmeyen", "nace": "N"},
    "0": {"sektor": "Silahli Kuvvetler", "nace": "O"},
}


def slugify_tr(text: str) -> str:
    """Generate URL-safe slug from Turkish text."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")
    slug = text.lower().translate(tr_map)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def get_sector_for_isco(meslek_kodu: str) -> dict:
    """Map ISCO-08 code to broad sector."""
    if not meslek_kodu:
        return {"sektor": "Diger", "nace": "X"}
    first_digit = meslek_kodu[0]
    return ISCO_SECTOR_MAP.get(first_digit, {"sektor": "Diger", "nace": "X"})


def merge_data(
    iskur_data: list[dict],
    tuik_employment: dict,
    tuik_salary: dict,
    isco_nace_map: dict | None = None,
) -> list[dict]:
    """Merge İŞKUR + TÜİK into unified occupation list.
    Only includes occupations that have employment data.
    """
    merged = []

    for occ in iskur_data:
        kodu = occ.get("meslek_kodu", "")

        # Skip if no employment data
        emp_data = tuik_employment.get(kodu)
        if not emp_data:
            continue

        # Determine sector
        if isco_nace_map and kodu in isco_nace_map:
            nace = isco_nace_map[kodu]
        else:
            nace = get_sector_for_isco(kodu).get("nace", "X")

        sector_info = get_sector_for_isco(kodu)
        salary_info = tuik_salary.get(nace, {})

        merged.append({
            "meslek_adi": occ["meslek_adi"],
            "meslek_kodu": kodu,
            "slug": occ.get("slug") or slugify_tr(occ["meslek_adi"]),
            "url": occ.get("url", ""),
            "sektor": sector_info["sektor"],
            "nace_kodu": nace,
            "istihdam_sayisi": emp_data.get("istihdam", 0),
            "ortalama_maas": salary_info.get("ortalama_maas"),
            "egitim_seviyesi": None,  # Filled from İŞKUR detail pages later
            "kayit_disi_orani": None,  # Filled from TÜİK sector data later
            "buyume_trendi": None,  # Filled from TÜİK yearly comparison later
        })

    # Sort by employment count descending
    merged.sort(key=lambda x: x["istihdam_sayisi"], reverse=True)
    return merged


def main():
    # Load İŞKUR data
    if not os.path.exists(ISKUR_INDEX):
        print(f"ERROR: {ISKUR_INDEX} not found. Run scrape_iskur.py first.")
        return

    with open(ISKUR_INDEX, "r", encoding="utf-8") as f:
        iskur_data = json.load(f)
    print(f"Loaded {len(iskur_data)} occupations from İŞKUR")

    # Load TÜİK data
    tuik_employment = {}
    tuik_salary = {}

    emp_path = os.path.join(TUIK_DIR, "employment_parsed.json")
    if os.path.exists(emp_path):
        with open(emp_path, "r", encoding="utf-8") as f:
            tuik_employment = json.load(f)
        print(f"Loaded {len(tuik_employment)} employment records from TÜİK")

    sal_path = os.path.join(TUIK_DIR, "salary_parsed.json")
    if os.path.exists(sal_path):
        with open(sal_path, "r", encoding="utf-8") as f:
            tuik_salary = json.load(f)
        print(f"Loaded {len(tuik_salary)} salary records from TÜİK")

    # Merge
    master = merge_data(iskur_data, tuik_employment, tuik_salary)

    # Save
    os.makedirs(os.path.dirname(MASTER_FILE), exist_ok=True)
    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

    print(f"\nMaster list: {len(master)} occupations")
    print(f"Total employment: {sum(o['istihdam_sayisi'] for o in master):,}")
    print(f"Saved to {MASTER_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd tr && python -m pytest tests/test_build_master_list.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tr/build_master_list.py tr/tests/test_build_master_list.py
git commit -m "feat(tr): add master occupation list builder (İŞKUR + TÜİK merge)"
```

---

## Chunk 2: Data Processing & LLM Scoring

### Task 5: İŞKUR HTML Parser (parse_tr.py)

**Files:**
- Create: `tr/parse_tr.py`
- Create: `tr/tests/test_parse_tr.py`
- Reference: `parse_detail.py` (US version)

**Context:** Parses İŞKUR occupation detail HTML pages into structured Markdown. The output Markdown is fed to the LLM for scoring. Each İŞKUR page contains: occupation definition, required education, typical tasks, working conditions.

- [ ] **Step 1: Write test for İŞKUR detail parsing**

```python
# tr/tests/test_parse_tr.py

def test_parse_iskur_detail():
    """Test parsing İŞKUR occupation detail page to Markdown."""
    from parse_tr import parse_iskur_detail

    sample_html = """
    <html><body>
    <h1 class="page-title">Muhasebeci</h1>
    <div class="meslek-tanim">
        <h2>Tanım</h2>
        <p>İşletmelerin mali işlemlerini kaydeden ve raporlayan kişidir.</p>
    </div>
    <div class="meslek-gorevler">
        <h2>Görevleri</h2>
        <ul>
            <li>Fatura ve belge düzenleme</li>
            <li>Vergi beyannamesi hazırlama</li>
            <li>Mali tablo analizi</li>
        </ul>
    </div>
    <div class="meslek-egitim">
        <h2>Eğitim</h2>
        <p>Lisans düzeyinde eğitim gerektirir.</p>
    </div>
    </body></html>
    """

    result = parse_iskur_detail(sample_html)
    assert "Muhasebeci" in result
    assert "mali işlemleri" in result
    assert "Vergi beyannamesi" in result
    assert "Lisans" in result


def test_extract_education_level():
    """Test extracting standardized education level from text."""
    from parse_tr import extract_education_level

    assert extract_education_level("Lisans düzeyinde eğitim") == "Lisans"
    assert extract_education_level("Lise mezunu olmalı") == "Lise"
    assert extract_education_level("Ön lisans veya meslek yüksekokulu") == "On Lisans"
    assert extract_education_level("Herhangi bir eğitim şartı yok") == "Egitim sarti yok"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tr && python -m pytest tests/test_parse_tr.py -v
```

- [ ] **Step 3: Implement parse_tr.py**

```python
# tr/parse_tr.py
"""
İŞKUR HTML Parser
Converts İŞKUR occupation detail pages to structured Markdown.
Output: data/raw/parsed/<meslek_kodu>.md
"""
import json
import os
import re
import sys
from bs4 import BeautifulSoup

RAW_DIR = "data/raw/iskur"
PARSED_DIR = "data/raw/parsed"
MASTER_FILE = "data/meslekler_master.json"

EDUCATION_LEVELS = [
    ("lisansüstü", "Lisansustu"),
    ("yüksek lisans", "Lisansustu"),
    ("doktora", "Lisansustu"),
    ("lisans", "Lisans"),
    ("üniversite", "Lisans"),
    ("ön lisans", "On Lisans"),
    ("meslek yüksekokulu", "On Lisans"),
    ("meslek lisesi", "Meslek Lisesi"),
    ("lise", "Lise"),
    ("ilköğretim", "Ilkogretim"),
    ("ortaokul", "Ilkogretim"),
]


def clean(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


def extract_education_level(text: str) -> str:
    """Extract standardized education level from Turkish text."""
    text_lower = text.lower()
    for keyword, level in EDUCATION_LEVELS:
        if keyword in text_lower:
            return level

    if "eğitim" in text_lower and ("yok" in text_lower or "şart" in text_lower):
        return "Egitim sarti yok"

    return "Belirtilmemis"


def parse_iskur_detail(html: str) -> str:
    """Parse İŞKUR occupation detail page to Markdown.

    NOTE: CSS selectors are placeholders - update after inspecting
    actual İŞKUR page structure.
    """
    soup = BeautifulSoup(html, "html.parser")
    parts = []

    # Title
    title_el = soup.select_one("h1, .page-title, .meslek-baslik")
    title = clean(title_el.get_text()) if title_el else "Bilinmeyen Meslek"
    parts.append(f"# {title}\n")

    # Definition / Description
    tanim_el = soup.select_one(".meslek-tanim, .tanim, #tanim")
    if tanim_el:
        parts.append("## Tanım\n")
        for p in tanim_el.find_all("p"):
            parts.append(clean(p.get_text()) + "\n")

    # Tasks / Duties
    gorev_el = soup.select_one(".meslek-gorevler, .gorevler, #gorevler")
    if gorev_el:
        parts.append("\n## Görevler\n")
        for li in gorev_el.find_all("li"):
            parts.append(f"- {clean(li.get_text())}")
        # Also get paragraphs
        for p in gorev_el.find_all("p"):
            text = clean(p.get_text())
            if text:
                parts.append(text)

    # Education
    egitim_el = soup.select_one(".meslek-egitim, .egitim, #egitim")
    if egitim_el:
        parts.append("\n## Eğitim\n")
        parts.append(clean(egitim_el.get_text()))

    # Working conditions
    kosul_el = soup.select_one(".calisma-kosullari, .kosullar, #kosullar")
    if kosul_el:
        parts.append("\n## Çalışma Koşulları\n")
        parts.append(clean(kosul_el.get_text()))

    # Generic content fallback - grab all text content if specific selectors fail
    if len(parts) <= 1:
        # Fallback: extract all meaningful text
        for el in soup.find_all(["h2", "h3", "p", "li"]):
            text = clean(el.get_text())
            if len(text) > 10:
                if el.name in ("h2", "h3"):
                    parts.append(f"\n## {text}\n")
                elif el.name == "li":
                    parts.append(f"- {text}")
                else:
                    parts.append(text)

    return "\n".join(parts)


def main():
    os.makedirs(PARSED_DIR, exist_ok=True)

    if not os.path.exists(MASTER_FILE):
        print(f"ERROR: {MASTER_FILE} not found. Run build_master_list.py first.")
        return

    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)

    parsed_count = 0
    skipped = 0

    for occ in master:
        kodu = occ["meslek_kodu"]
        html_path = os.path.join(RAW_DIR, f"{kodu}.html")
        md_path = os.path.join(PARSED_DIR, f"{kodu}.md")

        if os.path.exists(md_path):
            skipped += 1
            continue

        if not os.path.exists(html_path):
            print(f"SKIP: No HTML for {occ['meslek_adi']} ({kodu})")
            continue

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        md = parse_iskur_detail(html)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

        parsed_count += 1
        print(f"[{parsed_count}] {occ['meslek_adi']} → {len(md)} chars")

    print(f"\nParsed: {parsed_count}, Skipped (cached): {skipped}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd tr && python -m pytest tests/test_parse_tr.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tr/parse_tr.py tr/tests/test_parse_tr.py
git commit -m "feat(tr): add İŞKUR HTML parser with education level extraction"
```

---

### Task 6: CSV Generator (make_csv_tr.py)

**Files:**
- Create: `tr/make_csv_tr.py`
- Create: `tr/tests/test_make_csv_tr.py`
- Reference: `make_csv.py` (US version)

**Context:** Merges master list + parsed data into `data/meslekler.csv`. This CSV is the structured input for scoring and final data merge.

- [ ] **Step 1: Write test**

```python
# tr/tests/test_make_csv_tr.py
import csv
import io

def test_build_csv_row():
    """Test building a CSV row from master data + parsed content."""
    from make_csv_tr import build_csv_row

    master_entry = {
        "meslek_adi": "Muhasebeci",
        "meslek_kodu": "2411",
        "slug": "muhasebeci",
        "sektor": "Profesyonel Meslekler",
        "istihdam_sayisi": 185000,
        "ortalama_maas": 28500,
        "egitim_seviyesi": None,
        "kayit_disi_orani": None,
        "buyume_trendi": None,
    }

    parsed_md = "# Muhasebeci\n## Eğitim\nLisans düzeyinde eğitim gerektirir."

    row = build_csv_row(master_entry, parsed_md)
    assert row["meslek_adi"] == "Muhasebeci"
    assert row["meslek_kodu"] == "2411"
    assert row["egitim_seviyesi"] == "Lisans"
    assert row["istihdam_sayisi"] == 185000
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tr && python -m pytest tests/test_make_csv_tr.py -v
```

- [ ] **Step 3: Implement make_csv_tr.py**

```python
# tr/make_csv_tr.py
"""
CSV Generator for Turkish occupations.
Merges master list with parsed İŞKUR data into meslekler.csv.
"""
import csv
import json
import os
from parse_tr import extract_education_level

MASTER_FILE = "data/meslekler_master.json"
PARSED_DIR = "data/raw/parsed"
CSV_FILE = "data/meslekler.csv"

FIELDNAMES = [
    "meslek_adi", "meslek_kodu", "slug", "sektor",
    "istihdam_sayisi", "ortalama_maas", "egitim_seviyesi",
    "kayit_disi_orani", "buyume_trendi", "url",
]


def build_csv_row(master_entry: dict, parsed_md: str | None = None) -> dict:
    """Build a CSV row from master data + parsed Markdown content."""
    row = {
        "meslek_adi": master_entry["meslek_adi"],
        "meslek_kodu": master_entry["meslek_kodu"],
        "slug": master_entry.get("slug", ""),
        "sektor": master_entry.get("sektor", ""),
        "istihdam_sayisi": master_entry.get("istihdam_sayisi", 0),
        "ortalama_maas": master_entry.get("ortalama_maas"),
        "egitim_seviyesi": master_entry.get("egitim_seviyesi"),
        "kayit_disi_orani": master_entry.get("kayit_disi_orani"),
        "buyume_trendi": master_entry.get("buyume_trendi"),
        "url": master_entry.get("url", ""),
    }

    # Extract education level from parsed Markdown if not already set
    if not row["egitim_seviyesi"] and parsed_md:
        row["egitim_seviyesi"] = extract_education_level(parsed_md)

    return row


def main():
    if not os.path.exists(MASTER_FILE):
        print(f"ERROR: {MASTER_FILE} not found.")
        return

    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)

    rows = []
    for entry in master:
        # Try to load parsed Markdown
        md_path = os.path.join(PARSED_DIR, f"{entry['meslek_kodu']}.md")
        parsed_md = None
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                parsed_md = f.read()

        rows.append(build_csv_row(entry, parsed_md))

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} occupations to {CSV_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd tr && python -m pytest tests/test_make_csv_tr.py -v
```

- [ ] **Step 5: Commit**

```bash
git add tr/make_csv_tr.py tr/tests/test_make_csv_tr.py
git commit -m "feat(tr): add Turkish CSV generator"
```

---

### Task 7: LLM Scoring with Gemini 2.5 Flash (score_tr.py)

**Files:**
- Create: `tr/score_tr.py`
- Create: `tr/tests/test_score_tr.py`
- Reference: `score.py` (US version)

**Context:** Core scoring engine. Uses Gemini 2.5 Flash via google-generativeai SDK to generate dual metrics: AI exposure score (0-10) + "5 year prediction" for each Turkish occupation. Includes AI ecosystem benchmarks + Anthropic research in the system prompt.

- [ ] **Step 1: Write test for score parsing**

```python
# tr/tests/test_score_tr.py
import json

def test_parse_score_response():
    """Test parsing LLM JSON response into score dict."""
    from score_tr import parse_score_response

    raw = '''```json
    {
        "meslek": "Muhasebeci",
        "ai_skor": 8,
        "rationale": "Muhasebe isleri buyuk olcude dijitaldir.",
        "bes_yil_tahmini": "Her 3 muhasebeciden 1'i gereksiz kalacak.",
        "kayit_disi_notu": "Kayit disi calisanlar daha gec etkilenecek."
    }
    ```'''

    result = parse_score_response(raw)
    assert result["ai_skor"] == 8
    assert result["bes_yil_tahmini"].startswith("Her 3")
    assert "kayit_disi_notu" in result


def test_parse_score_response_no_fences():
    """Test parsing without markdown code fences."""
    from score_tr import parse_score_response

    raw = '{"meslek": "Kuafor", "ai_skor": 1, "rationale": "Fiziksel is.", "bes_yil_tahmini": "AI etkisi minimal.", "kayit_disi_notu": "Yuksek kayit disi."}'

    result = parse_score_response(raw)
    assert result["ai_skor"] == 1


def test_build_user_prompt():
    """Test that user prompt includes occupation data."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Muhasebeci",
        "meslek_kodu": "2411",
        "sektor": "Profesyonel Meslekler",
        "istihdam_sayisi": 185000,
        "ortalama_maas": 28500,
    }
    md_content = "# Muhasebeci\nMali islemleri kayit altina alir."

    prompt = build_user_prompt(occ, md_content)
    assert "Muhasebeci" in prompt
    assert "2411" in prompt
    assert "185,000" in prompt or "185000" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd tr && python -m pytest tests/test_score_tr.py -v
```

- [ ] **Step 3: Implement score_tr.py**

```python
# tr/score_tr.py
"""
AI Exposure Scoring for Turkish Occupations
Uses Gemini 2.5 Flash via google-generativeai SDK.
Dual metric: AI exposure (0-10) + 5-year prediction.
Output: data/skorlar.json
"""
import argparse
import json
import os
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

OUTPUT_FILE = "data/skorlar.json"
MASTER_FILE = "data/meslekler_master.json"
PARSED_DIR = "data/raw/parsed"
DEFAULT_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """Sen bir is piyasasi ve yapay zeka uzmanisisn. Turkiye'deki meslekleri AI'a maruz kalma acisindan degerlendiriyorsun.

Her meslek icin iki metrik ureteceksin:

## Metrik 1: AI Maruz Kalma Skoru (0-10)

0-10 arasinda bir tam sayi. Meslegin gorevlerinin ne kadarinin AI tarafindan otomatiklestirilebilecegini olcer.

Kalibrasyon rehberi:
- 0-1 (Minimal): Fiziksel, tahmin edilemez ortamlarda yapilan isler. Ornek: Insaat iscisi, Cilingir, Balikci
- 2-3 (Dusuk): Buyuk olcude fiziksel, az miktarda dijital. Ornek: Kuafor, Asci, Sofor, Temizlikci
- 4-5 (Orta): Fiziksel ve bilgi isinin karisimi. Ornek: Hemsire, Polis, Ogretmen, Veteriner
- 6-7 (Yuksek): Buyuk olcude bilgi isi, kismi fiziksel. Ornek: Muhasebeci, Gazeteci, Avukat, Mimar
- 8-9 (Cok Yuksek): Tamamen dijital, AI'in hizla ilerlediigi alanlar. Ornek: Yazilimci, Grafiker, Cevirmen
- 10 (Maksimum): Rutin, tamamen dijital, AI'in bugun bile yapabilecegi isler. Ornek: Veri girisci, Call center, Telekomunikasyon satis

Temel kural: Is tamamen evden bilgisayarla yapilabiliyorsa → en az 7.

## Metrik 2: "5 Yilda Ne Olacak?" Tahmini

Kisa, carpici, Turkce bir cumle. LinkedIn'de paylasima uygun, merak uyandirici olmali.
AI trendleri devam ederse onkosuluyla cercevele.
Belirli sirket/kurum isimleri hedef alma.
Irksal/etnik/cinsiyete dayali genellemeler yapma.

## Turkiye'ye Ozgu Faktorler

Skorlarken su Turkiye gerceklerini goz onunde bulundur:
1. KAYIT DISI EKONOMI: Turkiye'de ~%30 kayit disi istihdam var. Kayit disi calisanlar AI'dan farkli etkilenir - dogrudan isveren karari yerine piyasa dinamikleri ile.
2. DIJITAL OLGUNLUK: Turkiye'deki sektorlerin dijitallesme seviyesi ABD'den farkli. Tarim, kucuk esnaf, zanaat gibi alanlar daha az dijital.
3. BOLGESEL FARK: Buyuk sehirlerdeki (Istanbul, Ankara, Izmir) meslekler vs kucuk sehirlerdeki ayni meslek farkli etkilenir.

## AI'in Mart 2026 Itibariyle Guncel Yetkinlikleri

Skorlamani gercekci yapmak icin AI'in BUGUN neler yapabildigini bil:

### AI Ekosistemi
- Metin & Akil Yurutme: Claude Opus 4.6 (1M token context), Sonnet 4.6, GPT 5.4, Gemini 2.5 Flash/Pro
- Kodlama & Otonom Gelistirme: Claude Code (full-stack otonom muhendis, bastan sona uygulama gelistirebiliyor), Codex (CI/CD entegrasyonu)
- Goruntu Uretimi: Nano Banana 2 (Gemini 3.1 Flash Image) - 4K profesyonel kalite, saniyeler icinde
- Video Uretimi: Seedance 2 - profesyonel reklam/tanitim filmi dakikalar icinde

### Benchmark Sonuclari
- SWE-bench Verified: %70+ (gercek GitHub issue cozme)
- HumanEval: %95+ (kod uretme)
- GPQA Diamond (lisansustu bilim): %75+
- MMLU (genel bilgi): %90+
- AIME (matematik yarismasi): Medalist seviyesi
- ABD Baro Sinavi: Ust %10'da gecti
- USMLE (Tip Lisans): Her 3 asamayi gecti
- CPA (Muhasebe Sinavi): Gecme esiginin cok ustunde
- WMT ceviri: Profesyonel cevirmen seviyesi

### Anthropic Arastirmasi (Mart 2026)
- "Observed exposure" metrigi: teorik yetkinlik + gercek kullanim verisi
- Bilgisayar & Matematik meslekleri: gorevlerin %94'u AI ile hizlandirilabilir
- Ofis & Idari isler: %90 teorik maruz kalma
- Her %10'luk maruz kalma artisinda, is buyumesi %0.6 puan dusuyor
- En cok etkilenenler: daha egitimli, daha yuksek maasli calisanlar
- KRITIK: Genc iscilerin ise alinmasi maruz kalan mesleklerde yavaslamis
- AI henuz teorik kapasitesinin kucuk bir kisminda - etki DAHA DA artacak

Bu yetkinlikler deneysel degil - gunluk kullanilan, uretim ortaminda calisan araclar. Bir AI asistani bugun tek basina startup kurabilecek seviyede.

## Cikti Formati

SADECE JSON formatinda cevap ver, baska bir sey yazma:
{
    "meslek": "<meslek adi>",
    "ai_skor": <0-10 arasi tam sayi>,
    "rationale": "<2-3 cumle Turkce aciklama>",
    "bes_yil_tahmini": "<carpici, kisa Turkce tahmin cumlesi>",
    "kayit_disi_notu": "<kayit disi ekonomi etkisi - 1 cumle>"
}
"""


def parse_score_response(raw: str) -> dict:
    """Parse LLM response, handling optional markdown code fences."""
    text = raw.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def build_user_prompt(occ: dict, md_content: str | None) -> str:
    """Build the user prompt for a single occupation."""
    parts = [
        f"Meslek: {occ['meslek_adi']}",
        f"ISCO-08 Kodu: {occ['meslek_kodu']}",
        f"Sektor: {occ.get('sektor', 'Bilinmiyor')}",
        f"Istihdam: {occ.get('istihdam_sayisi', 0):,} kisi",
    ]

    if occ.get("ortalama_maas"):
        parts.append(f"Ortalama Maas: ₺{occ['ortalama_maas']:,}/ay")

    if occ.get("egitim_seviyesi"):
        parts.append(f"Egitim: {occ['egitim_seviyesi']}")

    if occ.get("kayit_disi_orani"):
        parts.append(f"Sektorel Kayit Disi Orani: %{occ['kayit_disi_orani']}")

    if md_content:
        parts.append(f"\n---\nDetayli Meslek Tanimi:\n{md_content}")

    return "\n".join(parts)


def score_occupation(model, occ: dict, md_content: str | None) -> dict:
    """Score a single occupation using Gemini."""
    user_prompt = build_user_prompt(occ, md_content)

    response = model.generate_content(
        [
            {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
            {"role": "model", "parts": [{"text": "Anlasıldı. Meslek bilgilerini gonder, JSON formatinda skorlayacagim."}]},
            {"role": "user", "parts": [{"text": user_prompt}]},
        ],
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
        ),
    )

    return parse_score_response(response.text)


def main():
    parser = argparse.ArgumentParser(description="AI Exposure Scoring (Turkish)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set. Add it to .env file.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(args.model)

    # Load master list
    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)

    # Load existing scores (cache)
    scores = []
    scored_codes = set()
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            scores = json.load(f)
        scored_codes = {s["meslek_kodu"] for s in scores if "meslek_kodu" in s}

    subset = master[args.start:args.end]
    to_score = [o for o in subset if o["meslek_kodu"] not in scored_codes]

    print(f"Scoring {len(to_score)} occupations (skipping {len(subset) - len(to_score)} cached)...")

    for i, occ in enumerate(to_score):
        kodu = occ["meslek_kodu"]

        # Load parsed Markdown if available
        md_path = os.path.join(PARSED_DIR, f"{kodu}.md")
        md_content = None
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()

        # Score with retry
        for attempt in range(3):
            try:
                result = score_occupation(model, occ, md_content)
                result["meslek_kodu"] = kodu
                scores.append(result)

                # Incremental save
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(scores, f, ensure_ascii=False, indent=2)

                print(f"[{i+1}/{len(to_score)}] {occ['meslek_adi']}: {result['ai_skor']}/10")
                break
            except Exception as e:
                wait = 2 ** (attempt + 1)
                print(f"  ERROR (attempt {attempt+1}/3): {e}. Retrying in {wait}s...")
                time.sleep(wait)
        else:
            print(f"  FAILED: {occ['meslek_adi']} - could not score after 3 attempts")

        time.sleep(args.delay)

    # Summary
    scored = [s for s in scores if "ai_skor" in s]
    if scored:
        avg = sum(s["ai_skor"] for s in scored) / len(scored)
        print(f"\nScored: {len(scored)} occupations")
        print(f"Average AI exposure: {avg:.1f}/10")

        # Histogram
        hist = [0] * 11
        for s in scored:
            hist[s["ai_skor"]] += 1
        for i, count in enumerate(hist):
            bar = "█" * count
            print(f"  {i:2d}: {bar} ({count})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
cd tr && python -m pytest tests/test_score_tr.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tr/score_tr.py tr/tests/test_score_tr.py
git commit -m "feat(tr): add Gemini 2.5 Flash dual-metric scoring engine"
```

---

### Task 8: Site Data Builder (build_site_data_tr.py)

**Files:**
- Create: `tr/build_site_data_tr.py`
- Create: `tr/tests/test_build_site_data_tr.py`
- Reference: `build_site_data.py` (US version)

**Context:** Merges meslekler.csv + skorlar.json into site/data.json for frontend consumption. Uses meslek_kodu as join key.

- [ ] **Step 1: Write test**

```python
# tr/tests/test_build_site_data_tr.py

def test_merge_csv_scores():
    """Test merging CSV data with LLM scores."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Muhasebeci", "meslek_kodu": "2411", "slug": "muhasebeci",
            "sektor": "Profesyonel", "istihdam_sayisi": "185000",
            "ortalama_maas": "28500", "egitim_seviyesi": "Lisans",
            "kayit_disi_orani": "15", "buyume_trendi": "3", "url": "",
        }
    ]

    scores = [
        {
            "meslek": "Muhasebeci", "meslek_kodu": "2411", "ai_skor": 8,
            "rationale": "Dijital meslek.", "bes_yil_tahmini": "Risk yuksek.",
            "kayit_disi_notu": "Kayit disi etki.",
        }
    ]

    result = merge_data(csv_rows, scores)
    assert len(result) == 1
    assert result[0]["ai_skor"] == 8
    assert result[0]["maas"] == 28500
    assert result[0]["istihdam"] == 185000
    assert result[0]["bes_yil_tahmini"] == "Risk yuksek."
```

- [ ] **Step 2: Run test, verify fail, then implement**

```python
# tr/build_site_data_tr.py
"""
Site Data Builder - merges CSV + scores into site/data.json
"""
import csv
import json
import os

CSV_FILE = "data/meslekler.csv"
SCORES_FILE = "data/skorlar.json"
SITE_DATA = "site/data.json"


def merge_data(csv_rows: list[dict], scores: list[dict]) -> list[dict]:
    """Merge CSV rows with LLM scores using meslek_kodu as join key."""
    score_map = {s["meslek_kodu"]: s for s in scores if "meslek_kodu" in s}

    data = []
    for row in csv_rows:
        kodu = row["meslek_kodu"]
        score = score_map.get(kodu, {})

        data.append({
            "meslek_adi": row["meslek_adi"],
            "meslek_kodu": kodu,
            "slug": row.get("slug", ""),
            "sektor": row.get("sektor", ""),
            "maas": int(row["ortalama_maas"]) if row.get("ortalama_maas") else None,
            "istihdam": int(row["istihdam_sayisi"]) if row.get("istihdam_sayisi") else None,
            "egitim": row.get("egitim_seviyesi", ""),
            "kayit_disi": float(row["kayit_disi_orani"]) if row.get("kayit_disi_orani") else None,
            "buyume": int(row["buyume_trendi"]) if row.get("buyume_trendi") else None,
            "ai_skor": score.get("ai_skor"),
            "rationale": score.get("rationale", ""),
            "bes_yil_tahmini": score.get("bes_yil_tahmini", ""),
            "kayit_disi_notu": score.get("kayit_disi_notu", ""),
            "url": row.get("url", ""),
        })

    return data


def main():
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))

    with open(SCORES_FILE, "r", encoding="utf-8") as f:
        scores = json.load(f)

    data = merge_data(csv_rows, scores)

    os.makedirs("site", exist_ok=True)
    with open(SITE_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_jobs = sum(d["istihdam"] or 0 for d in data)
    scored = sum(1 for d in data if d["ai_skor"] is not None)
    print(f"Built site data: {len(data)} occupations, {scored} scored, {total_jobs:,} total jobs")
    print(f"Saved to {SITE_DATA}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests**

```bash
cd tr && python -m pytest tests/test_build_site_data_tr.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tr/build_site_data_tr.py tr/tests/test_build_site_data_tr.py
git commit -m "feat(tr): add site data builder (CSV + scores merge)"
```

---

## Chunk 3: Frontend Web App

### Task 9: Core Frontend - Search, Result Card, List View

**Files:**
- Create: `tr/site/index.html`

**Context:** Single-page Turkish web app. Search-first UX with card-based listing. Dark theme, mobile-first, no frameworks. All HTML/CSS/JS in one file. Loads data.json on startup.

NOTE: This is a NEW frontend, not an adaptation of the US canvas-based treemap. Only the color palette and dark theme are referenced from the US version.

- [ ] **Step 1: Create the full index.html**

The complete HTML file should implement:

1. **Head**: UTF-8 charset, Turkish meta tags, OG tags for social sharing, responsive viewport
2. **CSS** (~300 lines): Dark theme (`#0a0a0f` bg), card styles, risk color coding (red 8-10, orange 5-7, green 0-4), mobile-first responsive, search input styling, filter bar
3. **HTML structure**:
   - Hero section with title "Turkiye'de Mesleginin AI Riski" and search box
   - Result card template (hidden by default)
   - Filter bar (kategori, risk seviyesi, egitim, maas)
   - Preset filter buttons ("En riskli 10", "En guvenli 10", etc.)
   - Card grid/list container
   - Summary stats bar
   - Sector bar chart (simple CSS-based, no canvas needed)
4. **JavaScript** (~400 lines):
   - `fetch("data.json")` on load
   - Search: fuzzy match on `meslek_adi` using `toLocaleLowerCase('tr-TR')`
   - Show result card on search match
   - Render card list with filters and sorting
   - Compute summary stats (total jobs at risk, sector averages)
   - Risk color function: `riskColor(score)` → red/orange/green
   - Format helpers: `formatMaas(val)`, `formatIstihdam(val)`
   - Share button: copy URL with `?m=<meslek_kodu>` to clipboard
   - Preset lists: filter and sort by predefined criteria
   - Scroll-based lazy rendering for performance with 300+ cards

Key technical decisions:
- Use `data.meslek_kodu` in URL params for sharing (`?m=2411`)
- Turkish locale for all string operations
- No canvas - pure DOM cards for accessibility and simplicity
- CSS Grid for card layout (responsive columns)

- [ ] **Step 2: Test locally**

```bash
cd tr/site && python -m http.server 8080
```
Open http://localhost:8080 and verify:
- Search works with Turkish characters
- Cards display correctly
- Filters work
- Mobile responsive (use browser dev tools)
- Preset lists populate correctly

- [ ] **Step 3: Commit**

```bash
git add tr/site/index.html
git commit -m "feat(tr): add Turkish AI exposure web app (search + cards)"
```

---

### Task 10: Comparison Feature

**Files:**
- Modify: `tr/site/index.html`

**Context:** Add side-by-side occupation comparison. URL format: `?k=2411&k=5141`. Strongest virality mechanism.

- [ ] **Step 1: Add comparison UI and logic**

Add to index.html:
1. **"Bir arkadasinla karsilastir" button** on result card
2. **Second search input** that appears on click
3. **Comparison card layout** - side-by-side with risk bars
4. **URL handling**: Parse `?k=` params on load, show comparison if two codes present
5. **Share button**: Generate URL with both meslek codes

```javascript
// URL-based comparison detection
function checkComparisonURL() {
    const params = new URLSearchParams(window.location.search);
    const codes = params.getAll('k');
    if (codes.length === 2) {
        showComparison(codes[0], codes[1]);
    }
}

// Comparison card render
function showComparison(code1, code2) {
    const m1 = DATA.find(d => d.meslek_kodu === code1);
    const m2 = DATA.find(d => d.meslek_kodu === code2);
    if (!m1 || !m2) return;
    // Render side-by-side cards...
}
```

CSS for comparison:
```css
.comparison {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    max-width: 800px;
    margin: 0 auto;
}

@media (max-width: 600px) {
    .comparison {
        grid-template-columns: 1fr;
    }
}
```

- [ ] **Step 2: Test comparison flow**

```bash
cd tr/site && python -m http.server 8080
```
Test: http://localhost:8080/?k=2411&k=5141
Verify:
- Two cards appear side by side
- Share button generates correct URL
- Mobile: cards stack vertically
- "Sen de dene" CTA visible

- [ ] **Step 3: Commit**

```bash
git add tr/site/index.html
git commit -m "feat(tr): add side-by-side occupation comparison for virality"
```

---

### Task 11: Stats, Share, and Polish

**Files:**
- Modify: `tr/site/index.html`

- [ ] **Step 1: Add summary statistics section**

At top of page (below search, above card list):
- Total occupations analyzed
- Total jobs represented
- Job-weighted average AI exposure
- "X milyon is yuksek risk altinda" headline stat

- [ ] **Step 2: Add sector bar chart**

Simple horizontal CSS bar chart showing average AI exposure by sector.
No canvas needed - just `<div>` bars with percentage widths.

```html
<div class="sector-chart">
    <!-- Generated by JS from data -->
    <div class="bar-row">
        <span class="bar-label">Bilisim</span>
        <div class="bar" style="width: 85%; background: #e74c3c;">8.5</div>
    </div>
    ...
</div>
```

- [ ] **Step 3: Add OG meta tags for social sharing**

```html
<meta property="og:title" content="Turkiye'de Mesleginin AI Riski">
<meta property="og:description" content="342 Turk meslegi icin AI maruz kalma analizi">
<meta property="og:type" content="website">
<meta property="og:image" content="og-image.png">
<meta name="twitter:card" content="summary_large_image">
```

Dynamic OG tags for shared individual occupations require server-side rendering.
For static hosting: share button copies a text snippet instead of relying on OG tags.

- [ ] **Step 4: Add share functionality**

```javascript
function shareOccupation(meslek) {
    const text = `${meslek.meslek_adi}: AI Riski ${meslek.ai_skor}/10\n${meslek.bes_yil_tahmini}\n\nSenin meslegin ne kadar risk altinda?`;
    const url = `${window.location.origin}${window.location.pathname}?m=${meslek.meslek_kodu}`;

    if (navigator.share) {
        navigator.share({ title: meslek.meslek_adi, text, url });
    } else {
        navigator.clipboard.writeText(`${text}\n${url}`);
        // Show "Kopyalandi!" toast
    }
}
```

- [ ] **Step 5: Final test**

```bash
cd tr/site && python -m http.server 8080
```
Full checklist:
- [ ] Search with Turkish chars (ç, ğ, ı, ö, ş, ü)
- [ ] Result card shows all fields
- [ ] Comparison works via URL params
- [ ] Filters and sorting work
- [ ] Preset lists populate
- [ ] Stats section shows correct numbers
- [ ] Sector bar chart renders
- [ ] Share button copies text
- [ ] Mobile responsive (320px, 375px, 768px)
- [ ] Dark theme consistent
- [ ] Page loads under 2s with 300+ occupations

- [ ] **Step 6: Commit**

```bash
git add tr/site/index.html
git commit -m "feat(tr): add stats, sector chart, sharing, and mobile polish"
```

---

## Execution Notes

### Pipeline Run Order
```bash
cd tr

# 1. Scrape İŞKUR (manual selector tuning needed)
python scrape_iskur.py --index-only
python scrape_iskur.py --delay 2.0

# 2. Download/parse TÜİK data
python scrape_tuik.py --download
python scrape_tuik.py --parse

# 3. Build master list
python build_master_list.py

# 4. Parse İŞKUR detail pages
python parse_tr.py

# 5. Generate CSV
python make_csv_tr.py

# 6. Score (requires GEMINI_API_KEY in .env)
python score_tr.py --delay 1.0

# 7. Build site data
python build_site_data_tr.py

# 8. Test locally
cd site && python -m http.server 8080
```

### Known Risks
1. **İŞKUR HTML structure** - CSS selectors are placeholders, must be updated after manual inspection
2. **TÜİK data format** - Excel column names may vary between releases, parser must be adaptive
3. **Gemini API rate limits** - May need to increase delay between calls
4. **Data gaps** - Some occupations may lack salary or employment data
5. **tiiny.site size limit** - Monitor data.json size (target < 2MB)

### Dependencies Between Tasks
- Task 2 (İŞKUR) and Task 3 (TÜİK) are **independent** - can run in parallel
- Task 4 (Master List) depends on Tasks 2 + 3
- Task 5 (Parse) depends on Task 2 (İŞKUR HTML files)
- Task 6 (CSV) depends on Tasks 4 + 5
- Task 7 (Score) depends on Tasks 4 + 5
- Task 8 (Site Data) depends on Tasks 6 + 7
- Tasks 9-11 (Frontend) depend on Task 8 for data, but can be developed in parallel with mock data
