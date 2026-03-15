"""
Tests for scrape_iskur.py - İŞKUR meslek sozlugu scraper.

Tests use sample HTML that matches the real İŞKUR table structure:
  Meslek Kodu | Meslek | Eğitim Seviyesi | Kategori | Dosya
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SAMPLE_TABLE_HTML = """
<html><body>
<table cellspacing="0" cellpadding="0">
<tr>
  <td>Meslek Kodu</td><td>Meslek</td><td>Eğitim Seviyesi</td><td>Kategori</td><td>Dosya</td>
</tr>
<tr>
  <td>3258.02</td>
  <td>Acil Tıp Teknisyeni</td>
  <td>Lise Meslekleri</td>
  <td>Sağlık Meslekleri Tanıyalım</td>
  <td><a href="javascript:MeslekDetayPopUp('3258.02')">Detay</a></td>
</tr>
<tr>
  <td>2411.01</td>
  <td>Muhasebeci</td>
  <td>Fakülte Meslekleri</td>
  <td>Ekonomi/Finans Mesleklerini Tanıyalım</td>
  <td><a href="javascript:MeslekDetayPopUp('2411.01')">Detay</a></td>
</tr>
<tr>
  <td>5141.03</td>
  <td>Kuaför</td>
  <td>Kurs Meslekleri</td>
  <td>Sanat Mesleklerini Tanıyalım</td>
  <td></td>
</tr>
</table>
</body></html>
"""


def test_parse_table_basic():
    """Test parsing the real İŞKUR table structure."""
    from scrape_iskur import parse_iskur_table

    result = parse_iskur_table(SAMPLE_TABLE_HTML)
    assert len(result) == 3

    assert result[0]["meslek_adi"] == "Acil Tıp Teknisyeni"
    assert result[0]["meslek_kodu"] == "3258.02"
    assert result[0]["egitim_seviyesi"] == "Lise"

    assert result[1]["meslek_adi"] == "Muhasebeci"
    assert result[1]["meslek_kodu"] == "2411.01"
    assert result[1]["egitim_seviyesi"] == "Lisans"


def test_parse_table_kategori_cleaned():
    """Test that category names are cleaned (suffix removed)."""
    from scrape_iskur import parse_iskur_table

    result = parse_iskur_table(SAMPLE_TABLE_HTML)
    assert result[0]["kategori"] == "Sağlık"
    assert result[1]["kategori"] == "Ekonomi/Finans"
    assert result[2]["kategori"] == "Sanat"


def test_parse_table_popup_link():
    """Test meslek_kodu extraction from MeslekDetayPopUp() link."""
    from scrape_iskur import parse_iskur_table

    result = parse_iskur_table(SAMPLE_TABLE_HTML)
    # Rows with popup links should use the code from the link
    assert result[0]["meslek_kodu"] == "3258.02"
    assert "3258.02" in result[0]["url"]


def test_parse_table_detail_url():
    """Test that detail URLs point to ViewMeslekDetayPopUp."""
    from scrape_iskur import parse_iskur_table

    result = parse_iskur_table(SAMPLE_TABLE_HTML)
    assert "ViewMeslekDetayPopUp.aspx" in result[0]["url"]
    assert result[0]["url"].endswith("3258.02")


def test_parse_table_empty():
    """Test graceful handling of empty / unrecognised page."""
    from scrape_iskur import parse_iskur_table

    result = parse_iskur_table("<html><body><p>404</p></body></html>")
    assert result == []


def test_parse_table_skips_header():
    """Test that header row is skipped."""
    from scrape_iskur import parse_iskur_table

    html = """
    <table cellspacing="0">
    <tr><td>Meslek Kodu</td><td>Meslek</td><td>Eğitim</td><td>Kategori</td></tr>
    <tr><td>1234.01</td><td>Test Meslek</td><td>Lise</td><td>Test</td></tr>
    </table>
    """
    result = parse_iskur_table(html)
    assert len(result) == 1
    assert result[0]["meslek_adi"] == "Test Meslek"


def test_parse_table_skips_invalid_code():
    """Test that rows without valid ISCO codes are skipped."""
    from scrape_iskur import parse_iskur_table

    html = """
    <table cellspacing="0">
    <tr><td>ABC</td><td>Invalid</td><td>Lise</td></tr>
    <tr><td>2411.01</td><td>Valid</td><td>Lisans</td></tr>
    </table>
    """
    result = parse_iskur_table(html)
    assert len(result) == 1
    assert result[0]["meslek_adi"] == "Valid"


def test_parse_table_slug():
    """Test slug generation for parsed occupations."""
    from scrape_iskur import parse_iskur_table

    result = parse_iskur_table(SAMPLE_TABLE_HTML)
    assert result[0]["slug"] == "acil-tip-teknisyeni"
    assert result[1]["slug"] == "muhasebeci"
    assert result[2]["slug"] == "kuafor"


def test_backward_compat_parse_iskur_index():
    """Test that parse_iskur_index is an alias for parse_iskur_table."""
    from scrape_iskur import parse_iskur_index

    result = parse_iskur_index(SAMPLE_TABLE_HTML)
    assert len(result) == 3


def test_slugify_basic():
    """Test slug generation for plain ASCII-safe Turkish words."""
    from scrape_iskur import slugify

    assert slugify("Muhasebeci") == "muhasebeci"
    assert slugify("kuafor") == "kuafor"


def test_slugify_turkish_chars():
    """Test that Turkish special characters are transliterated correctly."""
    from scrape_iskur import slugify

    assert slugify("Çilingir") == "cilingir"
    assert slugify("Güvenlik Görevlisi") == "guvenlik-gorevlisi"
    assert slugify("İnşaat İşçisi") == "insaat-iscisi"
    assert slugify("Şoför") == "sofor"
    assert slugify("Üniversite Öğrencisi") == "universite-ogrencisi"


def test_slugify_strips_special_chars():
    """Test that non-alphanumeric characters become hyphens and are trimmed."""
    from scrape_iskur import slugify

    assert slugify("  Aşçı  ") == "asci"
    assert slugify("A/B Testi") == "a-b-testi"
    assert slugify("---Doktor---") == "doktor"
