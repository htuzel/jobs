"""
Tests for build_site_data_tr.py - merges meslekler.csv + skorlar.json into
site/data.json for frontend consumption.

All tests are pure (no filesystem I/O). They use in-memory data structures
that mirror what the CSV reader and JSON loader produce.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ---------------------------------------------------------------------------
# merge_data
# ---------------------------------------------------------------------------

def test_merge_data_basic():
    """Test that CSV rows and LLM scores are merged on meslek_kodu."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Muhasebeci",
            "meslek_kodu": "2411",
            "slug": "muhasebeci",
            "sektor": "Profesyonel",
            "istihdam_sayisi": "185000",
            "ortalama_maas": "28500",
            "egitim_seviyesi": "Lisans",
            "kayit_disi_orani": "15",
            "buyume_trendi": "3",
            "url": "",
        }
    ]

    scores = [
        {
            "meslek": "Muhasebeci",
            "meslek_kodu": "2411",
            "ai_skor": 8,
            "rationale": "Dijital meslek.",
            "bes_yil_tahmini": "Risk yuksek.",
            "kayit_disi_notu": "Kayit disi etki.",
        }
    ]

    result = merge_data(csv_rows, scores)
    assert len(result) == 1
    assert result[0]["ai_skor"] == 8
    assert result[0]["maas"] == 28500
    assert result[0]["istihdam"] == 185000
    assert result[0]["bes_yil_tahmini"] == "Risk yuksek."
    assert result[0]["kayit_disi_notu"] == "Kayit disi etki."


def test_merge_data_left_join_missing_score():
    """Test that CSV rows without a matching score still appear (left join)."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Muhasebeci",
            "meslek_kodu": "2411",
            "slug": "muhasebeci",
            "sektor": "Profesyonel",
            "istihdam_sayisi": "185000",
            "ortalama_maas": "28500",
            "egitim_seviyesi": "Lisans",
            "kayit_disi_orani": "15",
            "buyume_trendi": "3",
            "url": "",
        },
        {
            "meslek_adi": "Kuafor",
            "meslek_kodu": "5141",
            "slug": "kuafor",
            "sektor": "Hizmet",
            "istihdam_sayisi": "320000",
            "ortalama_maas": "18000",
            "egitim_seviyesi": "Meslek Lisesi",
            "kayit_disi_orani": "45",
            "buyume_trendi": "",
            "url": "",
        },
    ]

    # Only score for Muhasebeci
    scores = [
        {
            "meslek": "Muhasebeci",
            "meslek_kodu": "2411",
            "ai_skor": 8,
            "rationale": "Dijital.",
            "bes_yil_tahmini": "Risk yuksek.",
            "kayit_disi_notu": "Etki var.",
        }
    ]

    result = merge_data(csv_rows, scores)

    # Both rows must be present (left join)
    assert len(result) == 2

    kuafor = next(r for r in result if r["meslek_kodu"] == "5141")
    # Unscored occupation: ai_skor should be None
    assert kuafor["ai_skor"] is None
    assert kuafor["bes_yil_tahmini"] == ""

    muhasebeci = next(r for r in result if r["meslek_kodu"] == "2411")
    assert muhasebeci["ai_skor"] == 8


def test_merge_data_numeric_type_coercions():
    """Test that string CSV values are converted to appropriate Python types."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Hemsire",
            "meslek_kodu": "2221",
            "slug": "hemsire",
            "sektor": "Saglik",
            "istihdam_sayisi": "300000",
            "ortalama_maas": "22000",
            "egitim_seviyesi": "Lisans",
            "kayit_disi_orani": "8.5",
            "buyume_trendi": "-2",
            "url": "http://example.com",
        }
    ]
    scores = []

    result = merge_data(csv_rows, scores)
    row = result[0]
    assert isinstance(row["istihdam"], int)
    assert isinstance(row["maas"], int)
    assert isinstance(row["kayit_disi"], float)
    assert row["kayit_disi"] == 8.5
    assert isinstance(row["buyume"], int)
    assert row["buyume"] == -2


def test_merge_data_empty_numeric_fields():
    """Test that empty string CSV values produce None, not errors."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Balikci",
            "meslek_kodu": "6221",
            "slug": "balikci",
            "sektor": "Tarim",
            "istihdam_sayisi": "",
            "ortalama_maas": "",
            "egitim_seviyesi": "",
            "kayit_disi_orani": "",
            "buyume_trendi": "",
            "url": "",
        }
    ]
    scores = []

    result = merge_data(csv_rows, scores)
    row = result[0]
    assert row["istihdam"] is None
    assert row["maas"] is None
    assert row["kayit_disi"] is None
    assert row["buyume"] is None


def test_merge_data_output_includes_required_frontend_fields():
    """Test that every output record has all fields the frontend expects."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Grafiker",
            "meslek_kodu": "2166",
            "slug": "grafiker",
            "sektor": "Yaratici",
            "istihdam_sayisi": "75000",
            "ortalama_maas": "30000",
            "egitim_seviyesi": "Lisans",
            "kayit_disi_orani": "12",
            "buyume_trendi": "5",
            "url": "",
        }
    ]
    scores = [
        {
            "meslek": "Grafiker",
            "meslek_kodu": "2166",
            "ai_skor": 9,
            "rationale": "Gorsel uretim tamamen dijital.",
            "bes_yil_tahmini": "Foto editoru biter, prompt yazari dogdu.",
            "kayit_disi_notu": "Serbest calisanlar etkilenecek.",
        }
    ]

    required_keys = {
        "meslek_adi", "meslek_kodu", "slug", "sektor",
        "maas", "istihdam", "egitim", "kayit_disi", "buyume",
        "ai_skor", "rationale", "bes_yil_tahmini", "kayit_disi_notu", "url",
    }

    result = merge_data(csv_rows, scores)
    assert len(result) == 1
    assert required_keys.issubset(result[0].keys())


def test_merge_data_preserves_turkish_characters():
    """Test that Turkish characters in text fields survive the merge."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Çilingir",
            "meslek_kodu": "7321",
            "slug": "cilingir",
            "sektor": "Zanaat ve El Sanatları",
            "istihdam_sayisi": "40000",
            "ortalama_maas": "16000",
            "egitim_seviyesi": "Meslek Lisesi",
            "kayit_disi_orani": "60",
            "buyume_trendi": "-1",
            "url": "",
        }
    ]
    scores = [
        {
            "meslek": "Çilingir",
            "meslek_kodu": "7321",
            "ai_skor": 1,
            "rationale": "Fiziksel, güvenlik işi. AI etkisi çok az.",
            "bes_yil_tahmini": "Sektör durağan kalacak.",
            "kayit_disi_notu": "Kayıt dışı oran yüksek.",
        }
    ]

    result = merge_data(csv_rows, scores)
    row = result[0]
    assert row["meslek_adi"] == "Çilingir"
    assert "güvenlik" in row["rationale"]
    assert "Kayıt" in row["kayit_disi_notu"]


def test_merge_data_score_with_no_meslek_kodu_is_ignored():
    """Test that score entries missing meslek_kodu do not cause KeyError."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {
            "meslek_adi": "Avukat",
            "meslek_kodu": "2611",
            "slug": "avukat",
            "sektor": "Hukuk",
            "istihdam_sayisi": "80000",
            "ortalama_maas": "45000",
            "egitim_seviyesi": "Lisans",
            "kayit_disi_orani": "5",
            "buyume_trendi": "1",
            "url": "",
        }
    ]
    # Score entry lacks meslek_kodu (malformed)
    scores = [
        {
            "meslek": "Avukat",
            "ai_skor": 7,
            "rationale": "Hukuk belgesi hazirliyor.",
            "bes_yil_tahmini": "AI hukuk asistani yaygınlaşacak.",
            "kayit_disi_notu": "Resmi sektor.",
        }
    ]

    result = merge_data(csv_rows, scores)
    # Should not raise; the unmatched score is silently ignored
    assert len(result) == 1
    # The CSV row is still present but with no score
    assert result[0]["ai_skor"] is None


def test_merge_data_empty_inputs():
    """Test that empty CSV and/or scores inputs return empty list."""
    from build_site_data_tr import merge_data

    assert merge_data([], []) == []
    assert merge_data([], [{"meslek_kodu": "2411", "ai_skor": 8}]) == []


def test_merge_data_multiple_occupations_correct_join():
    """Test correct join across multiple occupations with partial score coverage."""
    from build_site_data_tr import merge_data

    csv_rows = [
        {"meslek_adi": "A", "meslek_kodu": "1111", "slug": "a", "sektor": "S",
         "istihdam_sayisi": "10000", "ortalama_maas": "20000",
         "egitim_seviyesi": "Lisans", "kayit_disi_orani": "10",
         "buyume_trendi": "2", "url": ""},
        {"meslek_adi": "B", "meslek_kodu": "2222", "slug": "b", "sektor": "S",
         "istihdam_sayisi": "20000", "ortalama_maas": "30000",
         "egitim_seviyesi": "Lise", "kayit_disi_orani": "20",
         "buyume_trendi": "", "url": ""},
        {"meslek_adi": "C", "meslek_kodu": "3333", "slug": "c", "sektor": "S",
         "istihdam_sayisi": "30000", "ortalama_maas": "",
         "egitim_seviyesi": "", "kayit_disi_orani": "",
         "buyume_trendi": "", "url": ""},
    ]
    scores = [
        {"meslek_kodu": "1111", "ai_skor": 5, "rationale": "R",
         "bes_yil_tahmini": "T", "kayit_disi_notu": "N"},
        {"meslek_kodu": "3333", "ai_skor": 9, "rationale": "R2",
         "bes_yil_tahmini": "T2", "kayit_disi_notu": "N2"},
    ]

    result = merge_data(csv_rows, scores)
    assert len(result) == 3

    by_code = {r["meslek_kodu"]: r for r in result}
    assert by_code["1111"]["ai_skor"] == 5
    assert by_code["2222"]["ai_skor"] is None   # no score → None
    assert by_code["3333"]["ai_skor"] == 9
    assert by_code["3333"]["maas"] is None       # empty string → None
