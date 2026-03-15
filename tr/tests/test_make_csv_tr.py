"""
Tests for make_csv_tr.py - Turkish occupation CSV generator.

Tests cover: row building, education level extraction from Markdown,
field completeness, and correct handling of missing/None values.
"""
import sys
import os
import csv
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_build_csv_row_basic():
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
        "url": "https://iskur.gov.tr/meslek/2411",
    }

    parsed_md = "# Muhasebeci\n## Eğitim\nLisans düzeyinde eğitim gerektirir."

    row = build_csv_row(master_entry, parsed_md)
    assert row["meslek_adi"] == "Muhasebeci"
    assert row["meslek_kodu"] == "2411"
    assert row["egitim_seviyesi"] == "Lisans"
    assert row["istihdam_sayisi"] == 185000


def test_build_csv_row_all_required_fields():
    """CSV row must contain every column defined in FIELDNAMES."""
    from make_csv_tr import build_csv_row, FIELDNAMES

    master_entry = {
        "meslek_adi": "Kuafor",
        "meslek_kodu": "5141",
        "slug": "kuafor",
        "sektor": "Hizmet ve Satis",
        "istihdam_sayisi": 320000,
        "ortalama_maas": 18000,
        "egitim_seviyesi": None,
        "kayit_disi_orani": 45.0,
        "buyume_trendi": "+2%",
        "url": "https://iskur.gov.tr/meslek/5141",
    }

    row = build_csv_row(master_entry, None)
    for field in FIELDNAMES:
        assert field in row, f"Missing CSV field: {field}"


def test_build_csv_row_education_from_master_not_overwritten():
    """If egitim_seviyesi is already set in master, parsed_md must not override it."""
    from make_csv_tr import build_csv_row

    master_entry = {
        "meslek_adi": "Doktor",
        "meslek_kodu": "2211",
        "slug": "doktor",
        "sektor": "Saglik",
        "istihdam_sayisi": 90000,
        "ortalama_maas": 55000,
        "egitim_seviyesi": "Lisansustu",   # already set
        "kayit_disi_orani": None,
        "buyume_trendi": None,
        "url": "",
    }

    # Markdown says Lise - should NOT override master value
    parsed_md = "# Doktor\nLise düzeyinde yeterli."

    row = build_csv_row(master_entry, parsed_md)
    assert row["egitim_seviyesi"] == "Lisansustu"


def test_build_csv_row_no_parsed_md():
    """build_csv_row must work correctly when parsed_md is None."""
    from make_csv_tr import build_csv_row

    master_entry = {
        "meslek_adi": "Şoför",
        "meslek_kodu": "8322",
        "slug": "sofor",
        "sektor": "Ulasim",
        "istihdam_sayisi": 400000,
        "ortalama_maas": None,
        "egitim_seviyesi": None,
        "kayit_disi_orani": None,
        "buyume_trendi": None,
        "url": "",
    }

    row = build_csv_row(master_entry, None)
    assert row["meslek_adi"] == "Şoför"
    assert row["meslek_kodu"] == "8322"
    # Education is unknown but should not raise
    assert row["egitim_seviyesi"] is None or isinstance(row["egitim_seviyesi"], str)


def test_build_csv_row_extracts_lisansustu():
    """Education extraction should correctly identify postgraduate level."""
    from make_csv_tr import build_csv_row

    master_entry = {
        "meslek_adi": "Akademisyen",
        "meslek_kodu": "2310",
        "slug": "akademisyen",
        "sektor": "Egitim",
        "istihdam_sayisi": 60000,
        "ortalama_maas": 35000,
        "egitim_seviyesi": None,
        "kayit_disi_orani": None,
        "buyume_trendi": None,
        "url": "",
    }

    parsed_md = "# Akademisyen\n## Eğitim\nDoktora derecesi zorunludur."

    row = build_csv_row(master_entry, parsed_md)
    assert row["egitim_seviyesi"] == "Lisansustu"


def test_build_csv_row_numeric_fields_preserved():
    """Numeric fields (istihdam, maas) must be passed through unchanged."""
    from make_csv_tr import build_csv_row

    master_entry = {
        "meslek_adi": "Muhasebeci",
        "meslek_kodu": "2411",
        "slug": "muhasebeci",
        "sektor": "Mali",
        "istihdam_sayisi": 185000,
        "ortalama_maas": 28500,
        "egitim_seviyesi": "Lisans",
        "kayit_disi_orani": 12.5,
        "buyume_trendi": "-3%",
        "url": "",
    }

    row = build_csv_row(master_entry, None)
    assert row["istihdam_sayisi"] == 185000
    assert row["ortalama_maas"] == 28500
    assert row["kayit_disi_orani"] == 12.5
    assert row["buyume_trendi"] == "-3%"


def test_build_csv_row_slug_preserved():
    """Slug must be copied from master entry unchanged."""
    from make_csv_tr import build_csv_row

    master_entry = {
        "meslek_adi": "Çilingir",
        "meslek_kodu": "7521",
        "slug": "cilingir",
        "sektor": "Zanaat",
        "istihdam_sayisi": 25000,
        "ortalama_maas": 20000,
        "egitim_seviyesi": None,
        "kayit_disi_orani": None,
        "buyume_trendi": None,
        "url": "",
    }

    row = build_csv_row(master_entry, None)
    assert row["slug"] == "cilingir"


def test_csv_output_is_valid_csv():
    """Round-trip a row through csv.DictWriter/Reader to verify CSV formatting."""
    from make_csv_tr import build_csv_row, FIELDNAMES

    master_entry = {
        "meslek_adi": "Grafik Tasarımcı",
        "meslek_kodu": "2166",
        "slug": "grafik-tasarimci",
        "sektor": "Yaratici Endüstriler",
        "istihdam_sayisi": 75000,
        "ortalama_maas": 32000,
        "egitim_seviyesi": None,
        "kayit_disi_orani": 20.0,
        "buyume_trendi": "+5%",
        "url": "https://iskur.gov.tr/meslek/2166",
    }

    parsed_md = "# Grafik Tasarımcı\n## Eğitim\nLisans veya ön lisans yeterli."
    row = build_csv_row(master_entry, parsed_md)

    # Write to in-memory CSV buffer and read back
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerow(row)

    buf.seek(0)
    reader = csv.DictReader(buf)
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["meslek_adi"] == "Grafik Tasarımcı"
    assert rows[0]["meslek_kodu"] == "2166"
