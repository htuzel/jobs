"""
Tests for scrape_tuik.py - TÜİK Excel/CSV parser functions.

These tests exercise the pure parsing functions only (no network, no Playwright).
All test data uses DataFrames that mimic TÜİK Excel table structure.
"""
import sys
import os

# Allow importing from tr/ when running pytest from project root or tr/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# parse_employment_data
# ---------------------------------------------------------------------------

def test_parse_employment_data_basic():
    """Test parsing TÜİK employment data from standard ISCO-08 Excel format."""
    from scrape_tuik import parse_employment_data

    df = pd.DataFrame({
        "Meslek grubu": ["Muhasebe uzmanları", "Kuaförler"],
        "ISCO-08": ["2411", "5141"],
        "Toplam istihdam (bin)": [185, 320],
    })

    result = parse_employment_data(df)
    assert len(result) == 2
    # TÜİK reports in thousands → multiply by 1000
    assert result["2411"]["istihdam"] == 185000
    assert result["5141"]["istihdam"] == 320000


def test_parse_employment_data_large_values():
    """Test that already-large employment values are not double-multiplied."""
    from scrape_tuik import parse_employment_data

    df = pd.DataFrame({
        "Meslek kodu": ["1120", "3311"],
        "ISCO-08": ["1120", "3311"],
        "Toplam istihdam (bin)": [250000, 150000],
    })

    result = parse_employment_data(df)
    # Values >= 100000 should be kept as-is (not multiplied)
    assert result["1120"]["istihdam"] == 250000
    assert result["3311"]["istihdam"] == 150000


def test_parse_employment_data_missing_columns():
    """Test graceful handling when expected columns are absent."""
    from scrape_tuik import parse_employment_data

    df = pd.DataFrame({
        "Bilinmeyen kolon": ["X", "Y"],
        "Baska kolon": [1, 2],
    })

    result = parse_employment_data(df)
    # Should return empty dict, not raise
    assert result == {}


def test_parse_employment_data_skips_nan_codes():
    """Test that rows with NaN ISCO codes are skipped."""
    from scrape_tuik import parse_employment_data

    import numpy as np
    df = pd.DataFrame({
        "ISCO-08": ["2411", None, "5141"],
        "Toplam istihdam (bin)": [185, 100, 320],
    })

    result = parse_employment_data(df)
    assert "2411" in result
    assert "5141" in result
    # The None/nan row should be skipped
    assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_salary_data
# ---------------------------------------------------------------------------

def test_parse_salary_data_basic():
    """Test parsing TÜİK salary statistics by sector."""
    from scrape_tuik import parse_salary_data

    df = pd.DataFrame({
        "Ekonomik faaliyet": ["Mali hizmetler", "Kisisel hizmetler"],
        "NACE Rev.2": ["K", "S"],
        "Ortalama brüt ücret (TL)": [28500, 18000],
    })

    result = parse_salary_data(df)
    assert result["K"]["ortalama_maas"] == 28500
    assert result["S"]["ortalama_maas"] == 18000


def test_parse_salary_data_missing_columns():
    """Test graceful handling when salary columns are absent."""
    from scrape_tuik import parse_salary_data

    df = pd.DataFrame({
        "Tamamen alakasiz": ["A", "B"],
        "Diger": [1, 2],
    })

    result = parse_salary_data(df)
    assert result == {}


def test_parse_salary_data_skips_nan():
    """Test that rows with NaN sector codes are skipped."""
    from scrape_tuik import parse_salary_data

    import numpy as np
    df = pd.DataFrame({
        "NACE Rev.2": ["K", None, "S"],
        "Ortalama brüt ücret (TL)": [28500, 15000, 18000],
    })

    result = parse_salary_data(df)
    assert "K" in result
    assert "S" in result
    assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_informality_data
# ---------------------------------------------------------------------------

def test_parse_informality_data_basic():
    """Test parsing TÜİK informal employment rates by sector."""
    from scrape_tuik import parse_informality_data

    df = pd.DataFrame({
        "Sektör": ["Sanayi", "Hizmet"],
        "Kayıt dışı oranı (%)": [18.5, 32.1],
    })

    result = parse_informality_data(df)
    assert result["Sanayi"] == 18.5
    assert result["Hizmet"] == 32.1


def test_parse_informality_data_alternative_column_names():
    """Test recognition of alternative TÜİK column naming patterns."""
    from scrape_tuik import parse_informality_data

    df = pd.DataFrame({
        "Ekonomik faaliyet": ["Tarim", "Insaat"],
        "Informal istihdam orani": [55.0, 40.2],
    })

    result = parse_informality_data(df)
    assert "Tarim" in result
    assert result["Tarim"] == 55.0


def test_parse_informality_data_missing_columns():
    """Test graceful handling when informality columns are absent."""
    from scrape_tuik import parse_informality_data

    df = pd.DataFrame({
        "Tamamen alakasiz": ["A", "B"],
    })

    result = parse_informality_data(df)
    assert result == {}


def test_parse_informality_data_skips_nan():
    """Test that rows with NaN sector names are skipped."""
    from scrape_tuik import parse_informality_data

    import numpy as np
    df = pd.DataFrame({
        "Sektör": ["Sanayi", None, "Hizmet"],
        "Kayıt dışı oranı (%)": [18.5, 20.0, 32.1],
    })

    result = parse_informality_data(df)
    assert "Sanayi" in result
    assert "Hizmet" in result
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Integration: parse chain
# ---------------------------------------------------------------------------

def test_employment_keys_are_strings():
    """Test that ISCO-08 keys are always returned as strings (not ints)."""
    from scrape_tuik import parse_employment_data

    df = pd.DataFrame({
        "ISCO-08": [2411, 5141],           # integers as they may appear in Excel
        "Toplam istihdam (bin)": [185, 320],
    })

    result = parse_employment_data(df)
    # Keys must be strings for consistent join key behaviour
    for key in result:
        assert isinstance(key, str), f"Expected str key, got {type(key)}: {key!r}"
