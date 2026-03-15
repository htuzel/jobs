from __future__ import annotations

"""
Site Data Builder - merges meslekler.csv and skorlar.json into site/data.json

Reads:
  data/meslekler.csv     – structured occupation data (employment, salary, etc.)
  data/skorlar.json      – LLM-generated AI exposure scores + 5-year predictions

Writes:
  site/data.json         – flat JSON array ready for the frontend to consume

Join key: meslek_kodu (ISCO-08). This is a left join: every occupation from
the CSV is included even if it has no matching score (ai_skor will be None).

Pipeline position: step 7 of 7 (final step before deployment)
  ... → score_tr.py → **build_site_data_tr.py** → site/data.json → Deploy

Usage:
    python build_site_data_tr.py
    python build_site_data_tr.py --csv data/meslekler.csv --scores data/skorlar.json
"""

import argparse
import csv
import json
import os

CSV_FILE = "data/meslekler.csv"
SCORES_FILE = "data/skorlar.json"
SITE_DATA = "site/data.json"


# ---------------------------------------------------------------------------
# Pure merge function (testable, no I/O side-effects)
# ---------------------------------------------------------------------------

def _to_int(value: str | None) -> int | None:
    """Convert a string to int, returning None for empty or non-numeric values."""
    if not value and value != 0:
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def _to_float(value: str | None) -> float | None:
    """Convert a string to float, returning None for empty or non-numeric values."""
    if not value and value != 0:
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def merge_data(csv_rows: list[dict], scores: list[dict]) -> list[dict]:
    """Merge CSV occupation rows with LLM score records.

    Performs a left join on meslek_kodu: all CSV rows are retained. Score
    fields for unmatched rows are set to None / empty string.

    Args:
        csv_rows: List of dicts as returned by csv.DictReader. All values are
                  strings (as-read from CSV).
        scores:   List of dicts from skorlar.json. Each entry should have a
                  "meslek_kodu" key; entries without one are silently skipped.

    Returns:
        List of dicts with the shape expected by site/index.html. The output
        uses Turkish field names consistent with the rest of the pipeline:
          meslek_adi, meslek_kodu, slug, sektor, maas, istihdam,
          egitim, kayit_disi, buyume, ai_skor, rationale,
          bes_yil_tahmini, kayit_disi_notu, url
    """
    # Build score lookup keyed by meslek_kodu (ISCO-08)
    score_map: dict[str, dict] = {
        s["meslek_kodu"]: s
        for s in scores
        if "meslek_kodu" in s
    }

    data: list[dict] = []
    for row in csv_rows:
        kodu = row.get("meslek_kodu", "")
        score = score_map.get(kodu, {})

        data.append({
            # --- Identity fields ---
            "meslek_adi": row.get("meslek_adi", ""),
            "meslek_kodu": kodu,
            "slug": row.get("slug", ""),

            # --- Classification ---
            "sektor": row.get("sektor", ""),
            "egitim": row.get("egitim_seviyesi", ""),

            # --- Labour market stats (numeric coercion from CSV strings) ---
            "maas": _to_int(row.get("ortalama_maas")),
            "istihdam": _to_int(row.get("istihdam_sayisi")),
            "kayit_disi": _to_float(row.get("kayit_disi_orani")),
            "buyume": _to_int(row.get("buyume_trendi")),

            # --- AI exposure (from LLM; None if not yet scored) ---
            "ai_skor": score.get("ai_skor"),
            "rationale": score.get("rationale", ""),
            "bes_yil_tahmini": score.get("bes_yil_tahmini", ""),
            "kayit_disi_notu": score.get("kayit_disi_notu", ""),

            # --- Source link ---
            "url": row.get("url", ""),
        })

    return data


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_csv(path: str) -> list[dict]:
    """Read meslekler.csv and return a list of row dicts (all values as str)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_scores(path: str) -> list[dict]:
    """Read skorlar.json and return the list of score dicts."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_site_data(data: list[dict], path: str) -> None:
    """Write data.json to the given path, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # ensure_ascii=False preserves Turkish characters (ç, ğ, ı, ö, ş, ü)
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build site/data.json by merging CSV occupation data with LLM scores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_site_data_tr.py
  python build_site_data_tr.py --csv data/meslekler.csv --scores data/skorlar.json
  python build_site_data_tr.py --out site/data.json
""",
    )
    parser.add_argument(
        "--csv",
        default=CSV_FILE,
        help=f"Path to meslekler.csv (default: {CSV_FILE})",
    )
    parser.add_argument(
        "--scores",
        default=SCORES_FILE,
        help=f"Path to skorlar.json (default: {SCORES_FILE})",
    )
    parser.add_argument(
        "--out",
        default=SITE_DATA,
        help=f"Output path for data.json (default: {SITE_DATA})",
    )
    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.csv):
        print(f"ERROR: CSV file not found: {args.csv}")
        print("  Run make_csv_tr.py first.")
        return

    if not os.path.exists(args.scores):
        print(f"ERROR: Scores file not found: {args.scores}")
        print("  Run score_tr.py first.")
        return

    # Load
    print(f"Loading CSV:    {args.csv}")
    csv_rows = load_csv(args.csv)
    print(f"  {len(csv_rows)} occupation rows")

    print(f"Loading scores: {args.scores}")
    scores = load_scores(args.scores)
    print(f"  {len(scores)} scored entries")

    # Merge
    data = merge_data(csv_rows, scores)

    # Write
    write_site_data(data, args.out)

    # Summary
    total_istihdam = sum(d["istihdam"] or 0 for d in data)
    scored_count = sum(1 for d in data if d["ai_skor"] is not None)
    unscored_count = len(data) - scored_count

    print(f"\nMerge complete:")
    print(f"  Total occupations:   {len(data)}")
    print(f"  Scored:              {scored_count}")
    print(f"  Unscored (ai_skor=None): {unscored_count}")
    print(f"  Total employment:    {total_istihdam:,}")
    print(f"\nOutput: {args.out}")

    # Quick score distribution for sanity check
    skor_vals = [d["ai_skor"] for d in data if d["ai_skor"] is not None]
    if skor_vals:
        avg = sum(skor_vals) / len(skor_vals)
        at_risk = sum(1 for v in skor_vals if v >= 7)
        print(f"\nScore stats:")
        print(f"  Average:       {avg:.1f} / 10")
        print(f"  High risk (>=7): {at_risk} occupations ({at_risk * 100 // len(skor_vals)}%)")


if __name__ == "__main__":
    main()
