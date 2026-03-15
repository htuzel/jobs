"""
Tests for score_tr.py - Gemini 2.5 Flash dual-metric scoring engine.

All tests are offline (no API calls). They cover:
- JSON response parsing (with and without markdown code fences)
- User prompt construction
- Score field validation helpers
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest


# ---------------------------------------------------------------------------
# parse_score_response
# ---------------------------------------------------------------------------

def test_parse_score_response_with_json_fence():
    """Test parsing LLM response wrapped in ```json ... ``` code fences."""
    from score_tr import parse_score_response

    raw = '''```json
    {
        "meslek": "Muhasebeci",
        "ai_skor": 8,
        "rationale": "Muhasebe isleri buyuk olcude dijitaldir.",
        "bes_yil_tahmini": "Her 3 muhasebeciden 1'i gereksiz kalacak.",
        "kayit_disi_notu": "Kayit disi calisanlar daha gec etkilenecek."
    }
    ```'''

    result = parse_score_response(raw)
    assert result["ai_skor"] == 8
    assert result["bes_yil_tahmini"].startswith("Her 3")
    assert "kayit_disi_notu" in result
    assert result["meslek"] == "Muhasebeci"


def test_parse_score_response_with_plain_fence():
    """Test parsing LLM response wrapped in plain ``` code fences."""
    from score_tr import parse_score_response

    raw = '''```
{
    "meslek": "Kuafor",
    "ai_skor": 2,
    "rationale": "Fiziksel is.",
    "bes_yil_tahmini": "AI etkisi minimal.",
    "kayit_disi_notu": "Yuksek kayit disi."
}
```'''

    result = parse_score_response(raw)
    assert result["ai_skor"] == 2
    assert result["meslek"] == "Kuafor"


def test_parse_score_response_no_fences():
    """Test parsing bare JSON with no markdown code fences."""
    from score_tr import parse_score_response

    raw = '{"meslek": "Kuafor", "ai_skor": 1, "rationale": "Fiziksel is.", "bes_yil_tahmini": "AI etkisi minimal.", "kayit_disi_notu": "Yuksek kayit disi."}'

    result = parse_score_response(raw)
    assert result["ai_skor"] == 1


def test_parse_score_response_preserves_turkish_chars():
    """Test that Turkish characters survive the round-trip through JSON parsing."""
    from score_tr import parse_score_response

    raw = json.dumps({
        "meslek": "Çilingir",
        "ai_skor": 0,
        "rationale": "Tamamen fiziksel, tahmin edilemez ortam.",
        "bes_yil_tahmini": "Güvenlik sektörü AI'dan minimal etkilenir.",
        "kayit_disi_notu": "Kayıt dışı oran yüksek.",
    }, ensure_ascii=False)

    result = parse_score_response(raw)
    assert result["meslek"] == "Çilingir"
    assert "Güvenlik" in result["bes_yil_tahmini"]
    assert "ı" in result["kayit_disi_notu"]


def test_parse_score_response_score_range():
    """Test that ai_skor values at boundary 0 and 10 parse correctly."""
    from score_tr import parse_score_response

    for score in (0, 10):
        raw = json.dumps({
            "meslek": "Test",
            "ai_skor": score,
            "rationale": "Test.",
            "bes_yil_tahmini": "Test tahmin.",
            "kayit_disi_notu": "Test notu.",
        })
        result = parse_score_response(raw)
        assert result["ai_skor"] == score


def test_parse_score_response_raises_on_invalid_json():
    """Test that invalid JSON raises an appropriate exception."""
    from score_tr import parse_score_response

    with pytest.raises((json.JSONDecodeError, ValueError)):
        parse_score_response("bu bir JSON degil")


def test_parse_score_response_strips_whitespace_around_fences():
    """Test that extra whitespace around fences is handled correctly."""
    from score_tr import parse_score_response

    raw = """

```json
{"meslek": "Grafiker", "ai_skor": 9, "rationale": "Dijital.", "bes_yil_tahmini": "Risk yuksek.", "kayit_disi_notu": "Dusuk kayit disi."}
```

"""
    result = parse_score_response(raw)
    assert result["ai_skor"] == 9
    assert result["meslek"] == "Grafiker"


# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------

def test_build_user_prompt_includes_required_fields():
    """Test that user prompt includes occupation name and ISCO code."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Muhasebeci",
        "meslek_kodu": "2411",
        "sektor": "Profesyonel Meslekler",
        "istihdam_sayisi": 185000,
        "ortalama_maas": 28500,
    }
    md_content = "# Muhasebeci\nMali islemleri kayit altina alir."

    prompt = build_user_prompt(occ, md_content)
    assert "Muhasebeci" in prompt
    assert "2411" in prompt
    # Employment figure should appear in some recognisable form
    assert "185,000" in prompt or "185000" in prompt


def test_build_user_prompt_includes_salary_when_present():
    """Test that salary is included in prompt when available."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Avukat",
        "meslek_kodu": "2611",
        "sektor": "Profesyonel",
        "istihdam_sayisi": 80000,
        "ortalama_maas": 45000,
    }
    prompt = build_user_prompt(occ, None)
    assert "45,000" in prompt or "45000" in prompt


def test_build_user_prompt_omits_salary_when_absent():
    """Test that salary line is omitted when ortalama_maas is None."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Balıkçı",
        "meslek_kodu": "6221",
        "sektor": "Tarim ve Ormancilik",
        "istihdam_sayisi": 50000,
        "ortalama_maas": None,
    }
    prompt = build_user_prompt(occ, None)
    assert "Maas" not in prompt and "Ücret" not in prompt


def test_build_user_prompt_includes_informality_rate():
    """Test that kayit_disi_orani is included when available."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Berber",
        "meslek_kodu": "5141",
        "sektor": "Hizmet",
        "istihdam_sayisi": 120000,
        "ortalama_maas": 18000,
        "kayit_disi_orani": 45.0,
    }
    prompt = build_user_prompt(occ, None)
    assert "45" in prompt


def test_build_user_prompt_includes_md_content_when_provided():
    """Test that Markdown definition content is appended to the prompt."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Yazilim Gelistirici",
        "meslek_kodu": "2512",
        "sektor": "Bilisim",
        "istihdam_sayisi": 200000,
        "ortalama_maas": 60000,
    }
    md_content = "## Görevler\n- Kod yazar\n- Test yapar"

    prompt = build_user_prompt(occ, md_content)
    assert "Kod yazar" in prompt
    assert "Test yapar" in prompt


def test_build_user_prompt_no_md_content():
    """Test that prompt is still valid when Markdown content is None."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Garson",
        "meslek_kodu": "5131",
        "sektor": "Konaklama",
        "istihdam_sayisi": 400000,
        "ortalama_maas": 15000,
    }
    prompt = build_user_prompt(occ, None)
    assert "Garson" in prompt
    # Should not crash or contain 'None'
    assert "None" not in prompt


def test_build_user_prompt_includes_sector():
    """Test that sector information is present in the prompt."""
    from score_tr import build_user_prompt

    occ = {
        "meslek_adi": "Hemsire",
        "meslek_kodu": "2221",
        "sektor": "Saglik Hizmetleri",
        "istihdam_sayisi": 300000,
        "ortalama_maas": 22000,
    }
    prompt = build_user_prompt(occ, None)
    assert "Saglik" in prompt


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT content checks
# ---------------------------------------------------------------------------

def test_system_prompt_contains_ai_ecosystem():
    """Test that SYSTEM_PROMPT includes current AI model references."""
    from score_tr import SYSTEM_PROMPT

    # Spec requires: Claude Opus 4.6, Sonnet 4.6, GPT 5.4, Codex, Nano Banana 2, Seedance 2
    assert "Claude" in SYSTEM_PROMPT
    assert "Opus 4.6" in SYSTEM_PROMPT
    assert "Sonnet 4.6" in SYSTEM_PROMPT
    assert "GPT 5.4" in SYSTEM_PROMPT
    assert "Codex" in SYSTEM_PROMPT
    assert "Nano Banana 2" in SYSTEM_PROMPT
    assert "Seedance 2" in SYSTEM_PROMPT


def test_system_prompt_contains_benchmarks():
    """Test that SYSTEM_PROMPT includes key AI benchmark results."""
    from score_tr import SYSTEM_PROMPT

    # Spec requires: SWE-bench, GPQA, MMLU, AIME, Bar Exam, USMLE, CPA, WMT
    assert "SWE-bench" in SYSTEM_PROMPT
    assert "GPQA" in SYSTEM_PROMPT
    assert "MMLU" in SYSTEM_PROMPT
    assert "AIME" in SYSTEM_PROMPT
    assert "Baro" in SYSTEM_PROMPT or "Bar" in SYSTEM_PROMPT
    assert "USMLE" in SYSTEM_PROMPT
    assert "CPA" in SYSTEM_PROMPT
    assert "WMT" in SYSTEM_PROMPT


def test_system_prompt_contains_anthropic_research():
    """Test that SYSTEM_PROMPT includes Anthropic labor market research findings."""
    from score_tr import SYSTEM_PROMPT

    # Spec requires: observed exposure metric, 94% CS coverage, youth hiring slowdown
    assert "Anthropic" in SYSTEM_PROMPT
    assert "%94" in SYSTEM_PROMPT or "94" in SYSTEM_PROMPT
    assert "genc" in SYSTEM_PROMPT.lower() or "genç" in SYSTEM_PROMPT.lower()


def test_system_prompt_contains_turkey_factors():
    """Test that SYSTEM_PROMPT includes Turkey-specific context."""
    from score_tr import SYSTEM_PROMPT

    # Spec requires: informal economy, digital maturity, regional inequality
    assert "kayit disi" in SYSTEM_PROMPT.lower() or "kayıt dışı" in SYSTEM_PROMPT.lower()
    assert "dijital" in SYSTEM_PROMPT.lower()
    assert "bolgesel" in SYSTEM_PROMPT.lower() or "bölgesel" in SYSTEM_PROMPT.lower()


def test_system_prompt_contains_guardrails():
    """Test that SYSTEM_PROMPT includes the required guardrail instructions."""
    from score_tr import SYSTEM_PROMPT

    # Spec requires: no company targeting, no demographic generalizations, probabilistic language
    assert "sirket" in SYSTEM_PROMPT.lower() or "şirket" in SYSTEM_PROMPT.lower()
    # Probabilistic / conditional framing
    assert "olabilir" in SYSTEM_PROMPT.lower() or "trendler" in SYSTEM_PROMPT.lower()


def test_system_prompt_specifies_output_format():
    """Test that SYSTEM_PROMPT specifies JSON output format with required fields."""
    from score_tr import SYSTEM_PROMPT

    assert "ai_skor" in SYSTEM_PROMPT
    assert "bes_yil_tahmini" in SYSTEM_PROMPT
    assert "rationale" in SYSTEM_PROMPT
    assert "kayit_disi_notu" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT
