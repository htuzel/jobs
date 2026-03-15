"""
Master Occupation List Builder
Merges İŞKUR occupation definitions with TÜİK employment/salary/informality data
into a single canonical list: data/meslekler_master.json.

Join key: meslek_kodu (ISCO-08) — used throughout the entire pipeline.

Pipeline position:
    scrape_iskur.py → scrape_tuik.py → [this script] → parse_tr.py → make_csv_tr.py

Usage:
    python build_master_list.py           # merge and save master list
    python build_master_list.py --force   # overwrite existing master list
"""
import argparse
import json
import os

from utils import slugify_tr

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ISKUR_INDEX = "data/iskur_meslekler_raw.json"
TUIK_DIR = "data/raw/tuik"
MASTER_FILE = "data/meslekler_master.json"

# Mapping from ISCO-08 major group (first digit) to a broad sector label and
# approximate NACE Rev.2 letter.  Used as fallback when the caller does not
# supply an explicit isco_nace_map.
ISCO_SECTOR_MAP = {
    "0": {"sektor": "Silahli Kuvvetler",       "nace": "O"},
    "1": {"sektor": "Yonetim",                  "nace": "M"},
    "2": {"sektor": "Profesyonel Meslekler",    "nace": "M"},
    "3": {"sektor": "Teknisyenler",              "nace": "M"},
    "4": {"sektor": "Buro Hizmetleri",           "nace": "N"},
    "5": {"sektor": "Hizmet ve Satis",           "nace": "G"},
    "6": {"sektor": "Tarim ve Ormancilik",       "nace": "A"},
    "7": {"sektor": "Sanatkârlar",               "nace": "C"},
    "8": {"sektor": "Makine Operatorleri",       "nace": "C"},
    "9": {"sektor": "Nitelik Gerektirmeyen",     "nace": "N"},
}


# ---------------------------------------------------------------------------
# Pure helpers (no I/O — testable)
# ---------------------------------------------------------------------------

def get_sector_for_isco(meslek_kodu: str) -> dict:
    """Return sector label and NACE letter for an ISCO-08 code.

    Uses the first digit of meslek_kodu as the major-group key.
    Returns {"sektor": "Diger", "nace": "X"} for unrecognised codes.
    """
    if not meslek_kodu or not meslek_kodu[0].isdigit():
        return {"sektor": "Diger", "nace": "X"}
    return ISCO_SECTOR_MAP.get(meslek_kodu[0], {"sektor": "Diger", "nace": "X"})


def merge_data(
    iskur_data: list,
    tuik_employment: dict,
    tuik_salary: dict,
    isco_nace_map: dict = None,
) -> list:
    """Merge İŞKUR occupations with TÜİK statistics into a unified list.

    Only occupations that have a matching entry in tuik_employment are included
    (this filters to the ~250-350 occupations that have real employment data).

    Args:
        iskur_data:      List of dicts from parse_iskur_index() / index JSON.
        tuik_employment: Dict keyed by ISCO-08 code → {"istihdam": int}.
        tuik_salary:     Dict keyed by NACE letter  → {"ortalama_maas": int}.
        isco_nace_map:   Optional explicit ISCO→NACE mapping.  When absent the
                         ISCO_SECTOR_MAP broad-group fallback is used.

    Returns:
        List of merged occupation dicts, sorted by istihdam_sayisi descending.
    """
    merged = []

    for occ in iskur_data:
        kodu = occ.get("meslek_kodu", "")

        # Employment data is the gate — skip if not present
        emp_data = tuik_employment.get(kodu)
        if not emp_data:
            continue

        # Resolve NACE sector
        if isco_nace_map and kodu in isco_nace_map:
            nace = isco_nace_map[kodu]
        else:
            nace = get_sector_for_isco(kodu).get("nace", "X")

        sector_info = get_sector_for_isco(kodu)
        salary_info = tuik_salary.get(nace, {})

        merged.append({
            "meslek_adi":       occ["meslek_adi"],
            "meslek_kodu":      kodu,
            "slug":             occ.get("slug") or slugify_tr(occ["meslek_adi"]),
            "url":              occ.get("url", ""),
            "sektor":           sector_info["sektor"],
            "nace_kodu":        nace,
            "istihdam_sayisi":  emp_data.get("istihdam", 0),
            "ortalama_maas":    salary_info.get("ortalama_maas") or None,
            # Fields populated later by parse_tr.py / make_csv_tr.py
            "egitim_seviyesi":  None,
            "kayit_disi_orani": None,
            "buyume_trendi":    None,
        })

    # Sort by employment count descending (most employed first)
    merged.sort(key=lambda x: x["istihdam_sayisi"], reverse=True)
    return merged


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build master occupation list from İŞKUR + TÜİK data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing master list")
    args = parser.parse_args()

    if os.path.exists(MASTER_FILE) and not args.force:
        print(f"Master list already exists at {MASTER_FILE}. Use --force to rebuild.")
        return

    # ------------------------------------------------------------------
    # Load İŞKUR index
    # ------------------------------------------------------------------
    if not os.path.exists(ISKUR_INDEX):
        print(f"ERROR: {ISKUR_INDEX} not found. Run scrape_iskur.py --index-only first.")
        return

    with open(ISKUR_INDEX, "r", encoding="utf-8") as f:
        iskur_data = json.load(f)
    print(f"Loaded {len(iskur_data)} İŞKUR occupations")

    # ------------------------------------------------------------------
    # Load TÜİK data (optional — merges whatever is available)
    # ------------------------------------------------------------------
    tuik_employment: dict = {}
    tuik_salary: dict = {}
    tuik_informality: dict = {}

    emp_path = os.path.join(TUIK_DIR, "employment_parsed.json")
    if os.path.exists(emp_path):
        with open(emp_path, "r", encoding="utf-8") as f:
            tuik_employment = json.load(f)
        print(f"Loaded {len(tuik_employment)} TÜİK employment records")
    else:
        print(f"WARNING: {emp_path} not found — employment data unavailable")

    sal_path = os.path.join(TUIK_DIR, "salary_parsed.json")
    if os.path.exists(sal_path):
        with open(sal_path, "r", encoding="utf-8") as f:
            tuik_salary = json.load(f)
        print(f"Loaded {len(tuik_salary)} TÜİK salary records")
    else:
        print(f"WARNING: {sal_path} not found — salary data unavailable")

    inf_path = os.path.join(TUIK_DIR, "informality_parsed.json")
    if os.path.exists(inf_path):
        with open(inf_path, "r", encoding="utf-8") as f:
            tuik_informality = json.load(f)
        print(f"Loaded {len(tuik_informality)} TÜİK informality sector records")

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------
    master = merge_data(iskur_data, tuik_employment, tuik_salary)

    # Enrich with informality rates (sector-level, not per-occupation — noted
    # as a limitation in the spec)
    if tuik_informality:
        for occ in master:
            sector = occ.get("sektor", "")
            if sector in tuik_informality:
                occ["kayit_disi_orani"] = tuik_informality[sector]

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    os.makedirs(os.path.dirname(MASTER_FILE) or ".", exist_ok=True)
    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

    total_emp = sum(o["istihdam_sayisi"] for o in master)
    print(f"\nMaster list: {len(master)} occupations")
    print(f"Total represented employment: {total_emp:,}")
    print(f"Saved to {MASTER_FILE}")


if __name__ == "__main__":
    main()
