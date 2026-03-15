"""
CSV Generator for Turkish Occupations
Merges the master occupation list with parsed İŞKUR Markdown data and writes
data/meslekler.csv — the structured input for LLM scoring and site generation.

Pipeline position:
    build_master_list.py → parse_tr.py → [this script] → score_tr.py

Each row in meslekler.csv corresponds to one occupation from meslekler_master.json.
Education level is back-filled from the parsed Markdown if not already set in the
master record.

Usage:
    python make_csv_tr.py           # generate CSV
    python make_csv_tr.py --force   # overwrite existing CSV
"""
import argparse
import csv
import json
import os

from parse_tr import extract_education_level

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MASTER_FILE = "data/meslekler_master.json"
PARSED_DIR = "data/raw/parsed"
CSV_FILE = "data/meslekler.csv"

# Column order in the output CSV — this is the canonical schema consumed by
# score_tr.py and build_site_data_tr.py.
FIELDNAMES = [
    "meslek_adi",
    "meslek_kodu",
    "slug",
    "sektor",
    "istihdam_sayisi",
    "ortalama_maas",
    "egitim_seviyesi",
    "kayit_disi_orani",
    "buyume_trendi",
    "url",
]


# ---------------------------------------------------------------------------
# Pure helper (no I/O — testable)
# ---------------------------------------------------------------------------

def build_csv_row(master_entry: dict, parsed_md: str = None) -> dict:
    """Build a single CSV row dict from a master list entry and optional Markdown.

    Education level resolution order:
    1. Use master_entry["egitim_seviyesi"] if already set (not None / empty).
    2. Otherwise extract from parsed_md using extract_education_level().
    3. Leave as None if parsed_md is also unavailable.

    All other fields are copied directly from master_entry.  Missing keys
    default to None / empty string to avoid KeyError on partial records.

    Args:
        master_entry: One dict from meslekler_master.json.
        parsed_md:    Markdown string from parse_tr.py, or None.

    Returns:
        Dict with exactly the keys defined in FIELDNAMES.
    """
    # Resolve education level
    egitim = master_entry.get("egitim_seviyesi")
    if not egitim and parsed_md:
        egitim = extract_education_level(parsed_md)
        # Treat "Belirtilmemis" as absent so we don't store noise
        if egitim == "Belirtilmemis":
            egitim = None

    return {
        "meslek_adi":       master_entry["meslek_adi"],
        "meslek_kodu":      master_entry["meslek_kodu"],
        "slug":             master_entry.get("slug", ""),
        "sektor":           master_entry.get("sektor", ""),
        "istihdam_sayisi":  master_entry.get("istihdam_sayisi", 0),
        "ortalama_maas":    master_entry.get("ortalama_maas"),
        "egitim_seviyesi":  egitim,
        "kayit_disi_orani": master_entry.get("kayit_disi_orani"),
        "buyume_trendi":    master_entry.get("buyume_trendi"),
        "url":              master_entry.get("url", ""),
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate meslekler.csv from master list + parsed Markdown",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing CSV even if it exists")
    args = parser.parse_args()

    if os.path.exists(CSV_FILE) and not args.force:
        print(f"CSV already exists at {CSV_FILE}. Use --force to regenerate.")
        return

    if not os.path.exists(MASTER_FILE):
        print(f"ERROR: {MASTER_FILE} not found. Run build_master_list.py first.")
        return

    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)

    rows = []
    md_found = 0
    md_missing = 0

    for entry in master:
        kodu = entry["meslek_kodu"]
        md_path = os.path.join(PARSED_DIR, f"{kodu}.md")
        parsed_md = None

        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                parsed_md = f.read()
            md_found += 1
        else:
            md_missing += 1

        rows.append(build_csv_row(entry, parsed_md))

    os.makedirs(os.path.dirname(CSV_FILE) or ".", exist_ok=True)
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    # Summary stats
    with_edu = sum(1 for r in rows if r["egitim_seviyesi"])
    with_salary = sum(1 for r in rows if r["ortalama_maas"])
    with_emp = sum(1 for r in rows if r["istihdam_sayisi"])

    print(f"Wrote {len(rows)} occupations to {CSV_FILE}")
    print(f"  Parsed Markdown available: {md_found} / {len(rows)}")
    print(f"  Education level populated: {with_edu} / {len(rows)}")
    print(f"  Salary populated:          {with_salary} / {len(rows)}")
    print(f"  Employment populated:      {with_emp} / {len(rows)}")

    # Quick sample
    print("\nSample rows:")
    for r in rows[:3]:
        print(
            f"  {r['meslek_adi']} ({r['meslek_kodu']}): "
            f"istihdam={r['istihdam_sayisi']:,}, "
            f"egitim={r['egitim_seviyesi']}"
        )


if __name__ == "__main__":
    main()
