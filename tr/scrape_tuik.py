"""
TÜİK Data Downloader & Parser

Downloads employment, salary, and informality data from TÜİK (Türkiye İstatistik
Kurumu). TÜİK publishes tables as Excel/CSV files rather than scrapable HTML, so
this module uses pandas/openpyxl for parsing rather than Playwright.

Playwright is used only for the interactive download step (navigating data.tuik.gov.tr
to trigger file downloads). The parse functions are pure pandas and are tested
independently without any browser.

Pipeline position: step 2 of 7
  scrape_iskur.py → **scrape_tuik.py** → parse_tr.py → build_master_list.py
                  → make_csv_tr.py → score_tr.py → build_site_data_tr.py

Output: data/raw/tuik/*_parsed.json  (one file per table type)

Usage:
    python scrape_tuik.py --download   # Navigate TÜİK portal and download files
    python scrape_tuik.py --parse      # Parse already-downloaded Excel/CSV files
    python scrape_tuik.py --download --parse  # Both steps
"""

import argparse
import json
import os
import time

import pandas as pd

RAW_DIR = "data/raw/tuik"

# ---------------------------------------------------------------------------
# TÜİK table registry
#
# Each entry maps a logical key to the local filename where the Excel/CSV
# should be saved after manual or automated download from data.tuik.gov.tr.
#
# NOTE: TÜİK does not expose stable direct-download URLs. The download step
# opens a browser session so the operator can navigate to the correct table
# page and trigger the download. The browser context is configured to save
# files into RAW_DIR automatically.
# ---------------------------------------------------------------------------
TUIK_TABLES = {
    "employment": {
        "description": "İstihdam istatistikleri - meslek grubuna göre (ISCO-08)",
        "filename": "istihdam.xlsx",
        "hint": "data.tuik.gov.tr → İşgücü → Meslek grubuna göre istihdam",
    },
    "salary": {
        "description": "Kazanç istatistikleri - sektöre göre ortalama brüt ücret",
        "filename": "kazanc.xlsx",
        "hint": "data.tuik.gov.tr → Kazanç → Ekonomik faaliyete göre ortalama ücret",
    },
    "informality": {
        "description": "Kayıt dışı istihdam oranları - sektöre göre",
        "filename": "kayitdisi.xlsx",
        "hint": "data.tuik.gov.tr → İşgücü → Kayıt dışı istihdam",
    },
    "education": {
        "description": "İstihdam - eğitim düzeyine göre",
        "filename": "egitim_istihdam.xlsx",
        "hint": "data.tuik.gov.tr → İşgücü → Eğitim düzeyine göre istihdam",
    },
    "growth": {
        "description": "Yıllık istihdam değişimi - sektöre göre",
        "filename": "buyume.xlsx",
        "hint": "data.tuik.gov.tr → İşgücü → Yıllık değişim",
    },
}


# ---------------------------------------------------------------------------
# Column name detection helpers
#
# TÜİK uses inconsistent column names across table versions and years.
# These helper functions use keyword matching to find the right column
# regardless of exact naming.
# ---------------------------------------------------------------------------

def _find_column(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """Return the first column name that contains any of the given keywords.

    Comparison is case-insensitive and ignores leading/trailing whitespace.
    Returns None if no match is found.
    """
    for col in df.columns:
        if not isinstance(col, str):
            continue
        col_lower = col.strip().lower()
        for kw in keywords:
            if kw in col_lower:
                return col
    return None


# ---------------------------------------------------------------------------
# Pure parse functions (testable, no I/O side-effects)
# ---------------------------------------------------------------------------

def parse_employment_data(df: pd.DataFrame) -> dict:
    """Parse TÜİK employment statistics by occupation group.

    Expects a DataFrame with at least:
    - An ISCO-08 code column (column name containing "isco" or "meslek kodu")
    - An employment count column (column name containing "istihdam" or "toplam")

    TÜİK typically reports employment in thousands. Values < 100,000 are
    multiplied by 1,000. Values >= 100,000 are kept as-is.

    Returns:
        dict keyed by ISCO-08 code (str) → {"istihdam": int}
    """
    isco_col = _find_column(df, ["isco", "meslek kodu", "meslek_kodu"])
    emp_col = _find_column(df, ["istihdam", "toplam"])

    if isco_col is None or emp_col is None:
        print(
            f"WARNING: parse_employment_data – could not identify ISCO/employment "
            f"columns. Available: {list(df.columns)}"
        )
        return {}

    result: dict[str, dict] = {}
    for _, row in df.iterrows():
        raw_code = row[isco_col]
        if pd.isna(raw_code):
            continue
        code = str(raw_code).strip()
        if not code or code.lower() == "nan":
            continue

        raw_emp = row[emp_col]
        if pd.isna(raw_emp):
            emp = 0
        else:
            emp_val = float(raw_emp)
            # TÜİK frequently publishes in thousands (e.g., 185 → 185,000 people)
            emp = int(emp_val * 1000) if emp_val < 100_000 else int(emp_val)

        result[code] = {"istihdam": emp}

    return result


def parse_salary_data(df: pd.DataFrame) -> dict:
    """Parse TÜİK salary statistics by sector (NACE Rev.2 code).

    Expects a DataFrame with at least:
    - A NACE / economic activity column
    - A salary/wage column (brüt ücret, kazanç, maaş, etc.)

    Returns:
        dict keyed by NACE sector code (str) → {"ortalama_maas": int}
    """
    nace_col = _find_column(df, ["nace", "faaliyet"])
    salary_col = _find_column(df, ["ücret", "kazanç", "maaş", "ucret", "kazanc", "maas"])

    if nace_col is None or salary_col is None:
        print(
            f"WARNING: parse_salary_data – could not identify NACE/salary columns. "
            f"Available: {list(df.columns)}"
        )
        return {}

    result: dict[str, dict] = {}
    for _, row in df.iterrows():
        raw_code = row[nace_col]
        if pd.isna(raw_code):
            continue
        code = str(raw_code).strip()
        if not code or code.lower() == "nan":
            continue

        raw_salary = row[salary_col]
        salary = int(float(raw_salary)) if pd.notna(raw_salary) else 0
        result[code] = {"ortalama_maas": salary}

    return result


def parse_informality_data(df: pd.DataFrame) -> dict:
    """Parse TÜİK informal employment rates by sector.

    Expects a DataFrame with at least:
    - A sector name column ("sektör", "faaliyet")
    - An informality rate column ("kayıt", "informal", "oran")

    Returns:
        dict keyed by sector name (str) → float (percentage, e.g. 18.5 for 18.5%)
    """
    sector_col = _find_column(df, ["sektör", "sektor", "faaliyet"])
    rate_col = _find_column(df, ["kayıt", "kayit", "informal", "oran"])

    if sector_col is None or rate_col is None:
        print(
            f"WARNING: parse_informality_data – could not identify sector/rate "
            f"columns. Available: {list(df.columns)}"
        )
        return {}

    result: dict[str, float] = {}
    for _, row in df.iterrows():
        raw_sector = row[sector_col]
        if pd.isna(raw_sector):
            continue
        sector = str(raw_sector).strip()
        if not sector or sector.lower() == "nan":
            continue

        raw_rate = row[rate_col]
        rate = float(raw_rate) if pd.notna(raw_rate) else 0.0
        result[sector] = rate

    return result


# ---------------------------------------------------------------------------
# File parsing orchestrator
# ---------------------------------------------------------------------------

def parse_all(raw_dir: str = RAW_DIR) -> dict:
    """Parse all downloaded TÜİK Excel/CSV files and save per-table JSON files.

    For each table in TUIK_TABLES, if the corresponding .xlsx file exists in
    raw_dir, it is parsed with the appropriate function and the result is saved
    as <key>_parsed.json in the same directory.

    Returns:
        dict of {table_key: parsed_data}
    """
    results: dict = {}

    for key, table in TUIK_TABLES.items():
        filepath = os.path.join(raw_dir, table["filename"])
        if not os.path.exists(filepath):
            print(f"SKIP {key}: {filepath} not found")
            continue

        print(f"Parsing {key}: {table['description']}...")
        try:
            df = pd.read_excel(filepath, engine="openpyxl")
        except Exception as exc:
            # Try CSV fallback (some TÜİK tables are CSV despite .xlsx extension)
            try:
                df = pd.read_csv(filepath.replace(".xlsx", ".csv"), encoding="utf-8-sig")
            except Exception:
                print(f"  ERROR reading {filepath}: {exc}")
                continue

        if key == "employment":
            results[key] = parse_employment_data(df)
        elif key == "salary":
            results[key] = parse_salary_data(df)
        elif key == "informality":
            results[key] = parse_informality_data(df)
        else:
            # education, growth – save generic row-list for downstream use
            results[key] = df.to_dict(orient="records")

        # Persist parsed JSON alongside the raw file
        out_path = os.path.join(raw_dir, f"{key}_parsed.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results[key], f, ensure_ascii=False, indent=2)
        print(f"  Saved → {out_path}")

    return results


# ---------------------------------------------------------------------------
# Download step (requires Playwright; operator-guided)
# ---------------------------------------------------------------------------

def download_tuik_files(raw_dir: str = RAW_DIR, force: bool = False) -> None:
    """Open a browser session so the operator can download TÜİK Excel files.

    TÜİK's data portal (data.tuik.gov.tr) does not have stable direct-download
    URLs; tables must be located through the portal UI. This function:
    1. Creates raw_dir if needed.
    2. Opens a Chromium browser with the download directory configured.
    3. Navigates to data.tuik.gov.tr and waits for the operator to manually
       download each file listed in TUIK_TABLES.
    4. The browser is left open until the operator presses Enter.

    After running this step, run --parse to convert the .xlsx files to JSON.
    """
    # Imported here to keep the module importable when Playwright is absent
    # (e.g. during unit tests that only exercise the pure parse functions).
    from playwright.sync_api import sync_playwright  # type: ignore

    os.makedirs(raw_dir, exist_ok=True)

    missing = [
        key for key, tbl in TUIK_TABLES.items()
        if not os.path.exists(os.path.join(raw_dir, tbl["filename"]))
    ]
    if not missing and not force:
        print("All TÜİK files already downloaded. Use --force to re-download.")
        return

    print("=== TÜİK Manual Download Guide ===")
    print(f"Files will be saved to: {os.path.abspath(raw_dir)}\n")
    for key in missing:
        tbl = TUIK_TABLES[key]
        print(f"  [{key}] {tbl['description']}")
        print(f"    Hint: {tbl['hint']}")
        print(f"    Save as: {tbl['filename']}\n")

    print("Opening browser... download each file and save it to the directory above.")
    print("Press Enter in this terminal when all files are downloaded.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            accept_downloads=True,
            locale="tr-TR",
        )
        page = context.new_page()
        page.set_extra_http_headers({"Accept-Language": "tr-TR,tr;q=0.9"})
        page.goto("https://data.tuik.gov.tr", timeout=30_000)

        try:
            input("Press Enter when all files are downloaded...")
        except EOFError:
            # Non-interactive environment; sleep to give some download time
            time.sleep(60)

        browser.close()

    print("Browser closed. Run --parse to process downloaded files.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TÜİK Data Downloader & Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Step 1: open browser to download files from TÜİK
  python scrape_tuik.py --download

  # Step 2: parse downloaded files to JSON
  python scrape_tuik.py --parse

  # Both steps at once
  python scrape_tuik.py --download --parse

  # Force re-download even if files exist
  python scrape_tuik.py --download --force
""",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Open browser session to download TÜİK Excel files",
    )
    parser.add_argument(
        "--parse",
        action="store_true",
        help="Parse already-downloaded Excel/CSV files to JSON",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download / re-parse even if output files exist",
    )
    args = parser.parse_args()

    if not args.download and not args.parse:
        parser.print_help()
        print("\nTip: Run --download first, then --parse.")
        return

    if args.download:
        download_tuik_files(force=args.force)

    if args.parse:
        results = parse_all()
        print(f"\nParsed {len(results)} table(s).")


if __name__ == "__main__":
    main()
