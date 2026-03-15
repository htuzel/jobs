"""
Tests for parse_tr.py - İŞKUR HTML → Markdown parser.

Tests cover: section extraction, education level normalisation,
fallback behaviour when expected CSS selectors are absent, and
the batch main() logic flow (via unit-testing helpers).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_parse_iskur_detail_basic():
    """Test parsing İŞKUR occupation detail page to Markdown."""
    from parse_tr import parse_iskur_detail

    sample_html = """
    <html><body>
    <h1 class="page-title">Muhasebeci</h1>
    <div class="meslek-tanim">
        <h2>Tanım</h2>
        <p>İşletmelerin mali işlemlerini kaydeden ve raporlayan kişidir.</p>
    </div>
    <div class="meslek-gorevler">
        <h2>Görevleri</h2>
        <ul>
            <li>Fatura ve belge düzenleme</li>
            <li>Vergi beyannamesi hazırlama</li>
            <li>Mali tablo analizi</li>
        </ul>
    </div>
    <div class="meslek-egitim">
        <h2>Eğitim</h2>
        <p>Lisans düzeyinde eğitim gerektirir.</p>
    </div>
    </body></html>
    """

    result = parse_iskur_detail(sample_html)
    assert "Muhasebeci" in result
    assert "mali işlemleri" in result
    assert "Vergi beyannamesi" in result
    assert "Lisans" in result


def test_parse_iskur_detail_title_extracted():
    """Markdown output must start with a H1 heading containing the title."""
    from parse_tr import parse_iskur_detail

    html = "<html><body><h1>Elektrik Mühendisi</h1></body></html>"
    result = parse_iskur_detail(html)
    assert result.startswith("# Elektrik Mühendisi")


def test_parse_iskur_detail_tasks_as_list():
    """List items inside görevler div must appear as Markdown bullet points."""
    from parse_tr import parse_iskur_detail

    html = """
    <html><body>
    <h1>Yazılımcı</h1>
    <div class="meslek-gorevler">
        <ul>
            <li>Kod yaz</li>
            <li>Test et</li>
        </ul>
    </div>
    </body></html>
    """

    result = parse_iskur_detail(html)
    assert "- Kod yaz" in result
    assert "- Test et" in result


def test_parse_iskur_detail_fallback_when_no_selectors():
    """When specific selectors are absent the fallback should still capture text."""
    from parse_tr import parse_iskur_detail

    html = """
    <html><body>
    <h1>Bilinmeyen Meslek</h1>
    <h2>Genel Bilgi</h2>
    <p>Bu meslek hakkinda bilgi mevcuttur.</p>
    <ul>
        <li>Gorev 1</li>
    </ul>
    </body></html>
    """

    result = parse_iskur_detail(html)
    assert "Bilinmeyen Meslek" in result
    assert "bilgi mevcuttur" in result


def test_parse_iskur_detail_empty_html():
    """Parsing an empty / trivial HTML should return at minimum a title line."""
    from parse_tr import parse_iskur_detail

    result = parse_iskur_detail("<html><body></body></html>")
    # Should not raise; should return something (even a fallback title)
    assert isinstance(result, str)


def test_parse_iskur_detail_unknown_title_fallback():
    """When there is no h1, title should be a safe placeholder."""
    from parse_tr import parse_iskur_detail

    html = "<html><body><p>Icerik var ama baslik yok</p></body></html>"
    result = parse_iskur_detail(html)
    # Fallback title must appear
    assert "Bilinmeyen Meslek" in result or "Meslek" in result


def test_extract_education_level_lisans():
    """Lisans keyword maps to 'Lisans' level."""
    from parse_tr import extract_education_level

    assert extract_education_level("Lisans düzeyinde eğitim") == "Lisans"
    assert extract_education_level("Üniversite mezunu olmak zorunludur") == "Lisans"


def test_extract_education_level_lise():
    """Lise keyword maps to 'Lise' level."""
    from parse_tr import extract_education_level

    assert extract_education_level("Lise mezunu olmalı") == "Lise"


def test_extract_education_level_on_lisans():
    """Ön lisans / meslek yüksekokulu keywords map to 'On Lisans'."""
    from parse_tr import extract_education_level

    assert extract_education_level("Ön lisans veya meslek yüksekokulu") == "On Lisans"
    assert extract_education_level("Meslek yüksekokulu mezunu") == "On Lisans"


def test_extract_education_level_no_requirement():
    """Phrases indicating no education requirement map to 'Egitim sarti yok'."""
    from parse_tr import extract_education_level

    assert extract_education_level("Herhangi bir eğitim şartı yok") == "Egitim sarti yok"
    assert extract_education_level("Eğitim şartı aranmamaktadır") == "Egitim sarti yok"


def test_extract_education_level_lisansustu():
    """Postgraduate keywords map to 'Lisansustu'."""
    from parse_tr import extract_education_level

    assert extract_education_level("Yüksek lisans veya doktora") == "Lisansustu"
    assert extract_education_level("Lisansüstü eğitim tercih sebebidir") == "Lisansustu"
    assert extract_education_level("Doktora derecesi") == "Lisansustu"


def test_extract_education_level_unknown():
    """Text with no recognizable keyword should return 'Belirtilmemis'."""
    from parse_tr import extract_education_level

    assert extract_education_level("Bu alanda uzmanlaşmak gerekir") == "Belirtilmemis"
    assert extract_education_level("") == "Belirtilmemis"


def test_extract_education_level_priority_lisansustu_over_lisans():
    """'Lisansüstü' must win over plain 'Lisans' because it is listed first."""
    from parse_tr import extract_education_level

    # The text contains both "lisansüstü" and "lisans" - higher level should win
    result = extract_education_level("Lisansüstü (yüksek lisans veya doktora) veya lisans")
    assert result == "Lisansustu"


def test_clean_collapses_whitespace():
    """clean() helper must collapse multiple spaces/newlines into one space."""
    from parse_tr import clean

    assert clean("  merhaba   dunya  ") == "merhaba dunya"
    assert clean("satir\nbasi") == "satir basi"
    assert clean("cok   fazla    bosluk") == "cok fazla bosluk"
