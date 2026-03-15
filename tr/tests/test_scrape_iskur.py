"""
Tests for scrape_iskur.py - İŞKUR meslek sozlugu scraper.

Tests use sample HTML that mimics the expected structure (spec says selectors
are placeholders until real site is inspected).  We test both the nominal
selector path and the URL-fallback code path.
"""
import sys
import os

# Allow importing from parent tr/ directory when running pytest from tr/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_parse_iskur_index_html():
    """Test that we can extract occupation entries from İŞKUR index page HTML."""
    from scrape_iskur import parse_iskur_index

    # Sample HTML mimicking İŞKUR meslek sozlugu structure
    sample_html = """
    <html><body>
    <div class="meslek-listesi">
        <div class="meslek-item">
            <a href="/meslek/2411">Muhasebeci</a>
            <span class="isco">2411</span>
        </div>
        <div class="meslek-item">
            <a href="/meslek/5141">Kuafor</a>
            <span class="isco">5141</span>
        </div>
    </div>
    </body></html>
    """

    result = parse_iskur_index(sample_html)
    assert len(result) == 2
    assert result[0]["meslek_adi"] == "Muhasebeci"
    assert result[0]["meslek_kodu"] == "2411"
    assert result[1]["meslek_adi"] == "Kuafor"
    assert result[1]["meslek_kodu"] == "5141"


def test_parse_iskur_index_url_fallback():
    """Test ISCO code extraction from URL when .isco span is absent."""
    from scrape_iskur import parse_iskur_index

    sample_html = """
    <html><body>
    <div class="meslek-item">
        <a href="/is-arayan/meslek-sozlugu/3141">Elektrik Teknisyeni</a>
    </div>
    </body></html>
    """

    result = parse_iskur_index(sample_html)
    assert len(result) == 1
    assert result[0]["meslek_adi"] == "Elektrik Teknisyeni"
    assert result[0]["meslek_kodu"] == "3141"


def test_parse_iskur_index_absolute_url():
    """Test that absolute URLs are kept as-is while relative ones get base prepended."""
    from scrape_iskur import parse_iskur_index

    sample_html = """
    <html><body>
    <div class="meslek-item">
        <a href="https://iskur.gov.tr/meslek/1234">Mutfak Sefi</a>
        <span class="isco">1234</span>
    </div>
    </body></html>
    """

    result = parse_iskur_index(sample_html)
    assert result[0]["url"].startswith("https://")
    assert "1234" in result[0]["url"]


def test_parse_iskur_index_empty_page():
    """Test graceful handling of an empty / unrecognised page structure."""
    from scrape_iskur import parse_iskur_index

    result = parse_iskur_index("<html><body><p>Sayfa bulunamadi</p></body></html>")
    assert result == []


def test_parse_iskur_index_skips_items_without_link():
    """Items that have no <a> tag must be silently skipped."""
    from scrape_iskur import parse_iskur_index

    sample_html = """
    <html><body>
    <div class="meslek-item">
        <span class="isco">9999</span>
    </div>
    <div class="meslek-item">
        <a href="/meslek/7777">Seramikci</a>
        <span class="isco">7777</span>
    </div>
    </body></html>
    """

    result = parse_iskur_index(sample_html)
    assert len(result) == 1
    assert result[0]["meslek_kodu"] == "7777"


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


def test_parse_iskur_index_slug_field():
    """Verify that the slug field is populated in the result."""
    from scrape_iskur import parse_iskur_index

    sample_html = """
    <html><body>
    <div class="meslek-item">
        <a href="/meslek/2411">Muhasebeci</a>
        <span class="isco">2411</span>
    </div>
    </body></html>
    """

    result = parse_iskur_index(sample_html)
    assert result[0]["slug"] == "muhasebeci"
