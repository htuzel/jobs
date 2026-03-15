"""
Tests for build_master_list.py - İŞKUR + TÜİK data merger.

Focuses on merge logic, filtering, field mapping, and the Turkish
slugify helper that lives in this module.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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

    # Results are sorted descending by istihdam_sayisi, so 5141 (320k) comes first
    codes = [r["meslek_kodu"] for r in result]
    assert "2411" in codes
    assert "5141" in codes

    # Verify salary lookup via isco_nace_map: 2411 → NACE K → 28500
    muhasebeci = next(r for r in result if r["meslek_kodu"] == "2411")
    assert muhasebeci["istihdam_sayisi"] == 185000
    assert muhasebeci["ortalama_maas"] == 28500


def test_merge_filters_out_no_employment():
    """Occupations without TÜİK employment data must be excluded."""
    from build_master_list import merge_data

    iskur_data = [
        {"meslek_adi": "Hayali Meslek", "meslek_kodu": "0000", "url": "", "slug": "hayali-meslek"},
    ]

    result = merge_data(iskur_data, {}, {})
    assert result == []


def test_merge_sorted_by_employment_desc():
    """Results must be sorted largest employment count first."""
    from build_master_list import merge_data

    iskur_data = [
        {"meslek_adi": "Az Calisan", "meslek_kodu": "1111", "url": "", "slug": "az"},
        {"meslek_adi": "Cok Calisan", "meslek_kodu": "2222", "url": "", "slug": "cok"},
    ]

    tuik_employment = {
        "1111": {"istihdam": 1000},
        "2222": {"istihdam": 500000},
    }

    result = merge_data(iskur_data, tuik_employment, {})
    assert result[0]["meslek_kodu"] == "2222"
    assert result[1]["meslek_kodu"] == "1111"


def test_merge_generates_slug_when_missing():
    """If source data has no slug, build_master_list should generate one."""
    from build_master_list import merge_data

    iskur_data = [
        {"meslek_adi": "Şoför", "meslek_kodu": "8322", "url": ""},
    ]

    tuik_employment = {"8322": {"istihdam": 50000}}

    result = merge_data(iskur_data, tuik_employment, {})
    assert len(result) == 1
    assert result[0]["slug"] == "sofor"


def test_merge_salary_fallback_when_nace_missing():
    """If NACE code has no salary entry, ortalama_maas should be None."""
    from build_master_list import merge_data

    iskur_data = [
        {"meslek_adi": "Balikci", "meslek_kodu": "6221", "url": "", "slug": "balikci"},
    ]

    tuik_employment = {"6221": {"istihdam": 80000}}
    tuik_salary = {}  # No salary data at all

    result = merge_data(iskur_data, tuik_employment, tuik_salary)
    assert result[0]["ortalama_maas"] is None


def test_merge_required_fields_present():
    """Every merged entry must carry all required top-level fields."""
    from build_master_list import merge_data

    REQUIRED_FIELDS = {
        "meslek_adi", "meslek_kodu", "slug", "url", "sektor", "nace_kodu",
        "istihdam_sayisi", "ortalama_maas", "egitim_seviyesi",
        "kayit_disi_orani", "buyume_trendi",
    }

    iskur_data = [
        {"meslek_adi": "Muhasebeci", "meslek_kodu": "2411", "url": "http://x", "slug": "muhasebeci"},
    ]
    tuik_employment = {"2411": {"istihdam": 100000}}

    result = merge_data(iskur_data, tuik_employment, {})
    assert len(result) == 1
    for field in REQUIRED_FIELDS:
        assert field in result[0], f"Missing field: {field}"


def test_slugify_turkish():
    """Test Turkish slug generation handles special characters."""
    from build_master_list import slugify_tr

    assert slugify_tr("Muhasebeci") == "muhasebeci"
    assert slugify_tr("Çilingir") == "cilingir"
    assert slugify_tr("Güvenlik Görevlisi") == "guvenlik-gorevlisi"
    assert slugify_tr("İnşaat İşçisi") == "insaat-iscisi"


def test_slugify_tr_all_special_chars():
    """Test every Turkish special character is mapped correctly."""
    from build_master_list import slugify_tr

    assert slugify_tr("ç") == "c"
    assert slugify_tr("ğ") == "g"
    assert slugify_tr("ı") == "i"
    assert slugify_tr("ö") == "o"
    assert slugify_tr("ş") == "s"
    assert slugify_tr("ü") == "u"
    # Uppercase variants should also work after lowercasing
    assert slugify_tr("Ü") == "u"
    assert slugify_tr("Ş") == "s"
    assert slugify_tr("Ö") == "o"


def test_get_sector_for_isco():
    """Test that ISCO major group maps to the expected broad sector."""
    from build_master_list import get_sector_for_isco

    result = get_sector_for_isco("2411")
    assert result["sektor"] == "Profesyonel Meslekler"
    assert result["nace"] == "M"

    result = get_sector_for_isco("6221")
    assert result["sektor"] == "Tarim ve Ormancilik"

    result = get_sector_for_isco("")
    assert result["sektor"] == "Diger"


def test_get_sector_for_isco_unknown_code():
    """Unknown ISCO codes (not matching any major group) return 'Diger'."""
    from build_master_list import get_sector_for_isco

    result = get_sector_for_isco("XXXX")
    assert result["sektor"] == "Diger"
    assert result["nace"] == "X"
