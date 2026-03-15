"""
İŞKUR HTML Parser
Converts İŞKUR occupation detail pages (HTML) to structured Markdown.

The Markdown output is stored per-occupation and fed to the LLM for scoring.
Each İŞKUR page typically contains:
  - Occupation name / title
  - Tanım (definition / description)
  - Görevler (tasks / duties)
  - Eğitim (education requirements)
  - Çalışma Koşulları (working conditions)

Pipeline position:
    scrape_iskur.py → build_master_list.py → [this script] → make_csv_tr.py

Output: data/raw/parsed/<meslek_kodu>.md  (one Markdown file per occupation)

Usage:
    python parse_tr.py           # parse all occupations in master list
    python parse_tr.py --force   # re-parse even if output already exists

NOTE: CSS selectors are placeholders — update after inspecting real İŞKUR HTML.
"""
import argparse
import json
import os
import re
import sys
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RAW_DIR = "data/raw/iskur"
PARSED_DIR = "data/raw/parsed"
MASTER_FILE = "data/meslekler_master.json"

# Education level detection — ordered from most specific (longest match) to
# least specific.  Earlier entries win because the loop returns on first match.
#
# IMPORTANT ordering rules:
#   1. "lisansüstü" / "yüksek lisans" / "doktora" before "lisans" (they contain it)
#   2. "ön lisans" / "meslek yüksekokulu" before "lisans" ("ön lisans" contains "lisans")
#   3. "meslek lisesi" before "lise" ("meslek lisesi" contains "lise")
EDUCATION_LEVELS = [
    ("lisansüstü",          "Lisansustu"),
    ("yüksek lisans",       "Lisansustu"),
    ("doktora",             "Lisansustu"),
    ("ön lisans",           "On Lisans"),
    ("meslek yüksekokulu",  "On Lisans"),
    ("lisans",              "Lisans"),
    ("üniversite",          "Lisans"),
    ("meslek lisesi",       "Meslek Lisesi"),
    ("lise",                "Lise"),
    ("ilköğretim",          "Ilkogretim"),
    ("ortaokul",            "Ilkogretim"),
]


# ---------------------------------------------------------------------------
# Pure helpers (no I/O — fully testable)
# ---------------------------------------------------------------------------

def clean(text: str) -> str:
    """Collapse all whitespace runs (including newlines) to a single space."""
    return re.sub(r"\s+", " ", text).strip()


def extract_education_level(text: str) -> str:
    """Detect and return a standardised education level from Turkish text.

    Returns one of:
        "Lisansustu", "Lisans", "On Lisans", "Meslek Lisesi",
        "Lise", "Ilkogretim", "Egitim sarti yok", "Belirtilmemis"
    """
    if not text:
        return "Belirtilmemis"

    text_lower = text.lower()

    for keyword, level in EDUCATION_LEVELS:
        if keyword in text_lower:
            return level

    # Explicit "no requirement" phrasing
    if "eğitim" in text_lower and (
        "yok" in text_lower or "şart" in text_lower or "aranm" in text_lower
    ):
        return "Egitim sarti yok"

    return "Belirtilmemis"


def parse_iskur_detail(html: str) -> str:
    """Parse an İŞKUR occupation detail page into structured Markdown.

    Strategy:
    1. Try named section selectors (.meslek-tanim, .meslek-gorevler, etc.)
    2. If fewer than 2 sections were found, fall back to walking all
       meaningful block-level elements (h2, h3, p, li) to capture content
       regardless of the actual CSS class names.

    Returns a Markdown string.  The output always starts with a '# Title'
    heading so the LLM scoring prompt has a consistent structure.

    NOTE: Selectors are placeholders — update after inspecting live İŞKUR pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    parts = []

    # ------------------------------------------------------------------
    # 1. Title
    # ------------------------------------------------------------------
    title_el = soup.select_one(
        "h1, .page-title, .meslek-baslik, .entry-title, "
        "[class*='baslik'], [class*='title']"
    )
    title = clean(title_el.get_text()) if title_el else "Bilinmeyen Meslek"
    parts.append(f"# {title}\n")

    # ------------------------------------------------------------------
    # 2. Definition / Description (Tanım)
    # ------------------------------------------------------------------
    tanim_el = soup.select_one(
        ".meslek-tanim, .tanim, #tanim, "
        "[class*='tanim'], [class*='definition'], [class*='aciklama']"
    )
    if tanim_el:
        parts.append("## Tanım\n")
        for p in tanim_el.find_all("p"):
            text = clean(p.get_text())
            if text:
                parts.append(text + "\n")

    # ------------------------------------------------------------------
    # 3. Tasks / Duties (Görevler)
    # ------------------------------------------------------------------
    gorev_el = soup.select_one(
        ".meslek-gorevler, .gorevler, #gorevler, "
        "[class*='gorev'], [class*='gorevler'], [class*='duties'], [class*='tasks']"
    )
    if gorev_el:
        parts.append("\n## Görevler\n")
        for li in gorev_el.find_all("li"):
            text = clean(li.get_text())
            if text:
                parts.append(f"- {text}")
        for p in gorev_el.find_all("p"):
            text = clean(p.get_text())
            if text:
                parts.append(text)

    # ------------------------------------------------------------------
    # 4. Education (Eğitim)
    # ------------------------------------------------------------------
    egitim_el = soup.select_one(
        ".meslek-egitim, .egitim, #egitim, "
        "[class*='egitim'], [class*='education']"
    )
    if egitim_el:
        parts.append("\n## Eğitim\n")
        parts.append(clean(egitim_el.get_text()))

    # ------------------------------------------------------------------
    # 5. Working Conditions (Çalışma Koşulları)
    # ------------------------------------------------------------------
    kosul_el = soup.select_one(
        ".calisma-kosullari, .kosullar, #kosullar, "
        "[class*='kosul'], [class*='conditions']"
    )
    if kosul_el:
        parts.append("\n## Çalışma Koşulları\n")
        parts.append(clean(kosul_el.get_text()))

    # ------------------------------------------------------------------
    # 6. Fallback: walk all block-level elements if few sections found
    # ------------------------------------------------------------------
    # Count substantive sections (title doesn't count)
    section_count = sum(1 for p in parts if p.startswith("## "))
    if section_count == 0:
        # Generic extraction — grab every meaningful text block
        for el in soup.find_all(["h2", "h3", "p", "li"]):
            text = clean(el.get_text())
            if len(text) < 5:
                continue
            if el.name in ("h2", "h3"):
                parts.append(f"\n## {text}\n")
            elif el.name == "li":
                parts.append(f"- {text}")
            else:
                parts.append(text)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse İŞKUR detail HTML pages to Markdown",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--force", action="store_true",
                        help="Re-parse even if output Markdown already exists")
    args = parser.parse_args()

    os.makedirs(PARSED_DIR, exist_ok=True)

    if not os.path.exists(MASTER_FILE):
        print(
            f"ERROR: {MASTER_FILE} not found. "
            "Run scrape_iskur.py and build_master_list.py first."
        )
        sys.exit(1)

    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)

    parsed_count = 0
    skipped_cached = 0
    skipped_no_html = 0

    for occ in master:
        kodu = occ["meslek_kodu"]
        html_path = os.path.join(RAW_DIR, f"{kodu}.html")
        md_path = os.path.join(PARSED_DIR, f"{kodu}.md")

        if os.path.exists(md_path) and not args.force:
            skipped_cached += 1
            continue

        if not os.path.exists(html_path):
            print(f"SKIP (no HTML): {occ['meslek_adi']} ({kodu})")
            skipped_no_html += 1
            continue

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        md = parse_iskur_detail(html)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

        parsed_count += 1
        print(f"[{parsed_count}] {occ['meslek_adi']} ({kodu}) → {len(md):,} chars")

    print(
        f"\nDone. Parsed: {parsed_count} | "
        f"Cached (skipped): {skipped_cached} | "
        f"No HTML: {skipped_no_html}"
    )


if __name__ == "__main__":
    main()
