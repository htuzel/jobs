"""
AI Exposure Scoring Engine for Turkish Occupations

Uses Gemini 2.5 Flash via the google-generativeai Python SDK to generate two
metrics for each occupation in data/meslekler_master.json:

  1. ai_skor (0-10)   – how much will AI reshape this occupation?
  2. bes_yil_tahmini  – a short, shareable Turkish prediction for "5 years from now"

Additionally produces:
  - rationale         – 2-3 sentence Turkish explanation
  - kayit_disi_notu   – one-sentence note on informal economy impact

Results are cached incrementally in data/skorlar.json so that interrupted runs
resume from where they left off. Each successful API call saves immediately.

Pipeline position: step 6 of 7
  ... → make_csv_tr.py → **score_tr.py** → build_site_data_tr.py

Dependencies:
    google-generativeai>=0.8.0
    python-dotenv>=1.2.0

Usage:
    python score_tr.py
    python score_tr.py --start 0 --end 20    # test on first 20 occupations
    python score_tr.py --force               # re-score even cached occupations
    python score_tr.py --model gemini-2.5-flash
"""

import argparse
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-2.5-flash"
OUTPUT_FILE = "data/skorlar.json"
MASTER_FILE = "data/meslekler_master.json"
PARSED_DIR = "data/raw/parsed"

# ---------------------------------------------------------------------------
# System Prompt
#
# This prompt is embedded verbatim in every API call. It must include:
#   - Full AI ecosystem context (Spec §4d)
#   - All benchmark scores (Spec §4d)
#   - Anthropic labor market research findings (Spec §4d)
#   - Turkey-specific factors (Spec §4c)
#   - Output format spec (Spec §4e)
#   - Guardrails (Spec §4b)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Sen bir is piyasasi ve yapay zeka uzmanisisn. Turkiye'deki meslekleri AI'a \
maruz kalma acisindan degerlendiriyorsun.

Her meslek icin iki metrik ureteceksin:

## Metrik 1: AI Maruz Kalma Skoru (0-10)

0-10 arasinda bir tam sayi. Meslegin gorevlerinin ne kadarinin AI tarafindan \
otomatiklestirilebilecegini olcer. Hem dogrudan otomasyon (AI insanin yaptigini \
yapar) hem de dolayli etki (AI her iscinin uretkenligini artirinca daha az kisi \
gerekir) goz onune alinir.

Kalibrasyon rehberi:
- 0-1 (Minimal): Fiziksel, tahmin edilemez ortamlarda yapilan isler. \
  Ornek: Insaat iscisi, Cilingir, Balikci, Cerceve ustasi
- 2-3 (Dusuk): Buyuk olcude fiziksel, az miktarda dijital. \
  Ornek: Kuafor, Asci, Sofor, Temizlikci, Bahce iscisi
- 4-5 (Orta): Fiziksel ve bilgi isinin karisimi. \
  Ornek: Hemsire, Polis, Ogretmen, Veteriner, Eczaci
- 6-7 (Yuksek): Buyuk olcude bilgi isi, kismi fiziksel. \
  Ornek: Muhasebeci, Gazeteci, Avukat, Mimar, Proje muduru
- 8-9 (Cok Yuksek): Tamamen dijital, AI'in hizla ilerledigii alanlar. \
  Ornek: Yazilimci, Grafiker, Cevirmen, Veri analisti, Icerik yazari
- 10 (Maksimum): Rutin, tamamen dijital, AI'in bugun bile yapabilecegi isler. \
  Ornek: Veri girisci, Call center operatoru, Telekomunikasyon satis, \
  Standart raporlama uzmani

Temel kural: Is tamamen evden bilgisayarla yapilabiliyorsa → en az 7 ver.

## Metrik 2: "5 Yilda Ne Olacak?" Tahmini (bes_yil_tahmini)

Kisa (1-2 cumle), carpici, Turkce bir tahmin. LinkedIn'de paylasima uygun, \
merak uyandirici olmali. "AI trendleri devam ederse" on kosuluyla yaz.

Ornekler:
- "Her 3 muhasebeciden 1'i gereksiz kalacak. Kalan 2'si AI araclarini \
  kullanmak zorunda."
- "AI senin isini alamaz ama Instagram'siz musteri bulamayan kapanir."
- "Kod yazmak degil, AI'a ne yazdiracagini bilmek kariyer belirleyici olacak."

## Guardrail'ler (ZORUNLU - ihlal etme)

1. Belirli sirket, kurum veya marka ismi hedef alma.
2. Irksal, etnik, dini veya cinsiyete dayali genellemeler yapma.
3. Tahminler kesin hukum gibi degil, "olabilir / yonelim / risk" diliyle olsun.
4. Tum tahminler "AI trendleri devam ederse" on kosuluyla cercevele.

## Turkiye'ye Ozgu Faktorler (Skorlamada Goz Onunde Bulundur)

### 1. Kayit Disi Ekonomi
Turkiye'de ~%30 kayit disi istihdam var. Kayit disi calisanlar AI'dan farkli \
etkilenir: dogrudan isveren karari ile degil, piyasa baskisiyla. "AI seni \
kovamaz ama musteri bulmani zorlastirir." Bu asimetriyi rationale ve \
kayit_disi_notu'nda yansit.

### 2. Dijital Olgunluk
Turkiye'deki sektorlerin dijitallesme seviyesi ABD ve Bati Avrupa'dan geride. \
Tarim, kucuk esnaf, zanaat gibi alanlar daha az dijital → AI etkisi daha yavash. \
Finans, e-ticaret, IT gibi sektorler ise hizla dijitallesiyor → AI etkisi daha hizli.

### 3. Bolgesel Esitsizlik
Buyuk sehirlerdeki (Istanbul, Ankara, Izmir) meslekler ile kucuk sehirlerdeki \
ayni meslek farkli AI etkisine maruz kalir. Dijital altyapi farki bu asimetriyi \
guclendiriyor. Rationale'da bu farki belirt.

## AI'in Mart 2026 Itibariyle Gercek Yetkinlikleri

Bu yetkinlikler teorik degil, uretim ortaminda calisan araclar:

### AI Ekosistemi
- Metin & Akil Yurutme: Claude Opus 4.6 (1 milyon token baglam), \
  Sonnet 4.6, GPT 5.4, Gemini 2.5 Flash/Pro
- Kodlama & Otonom Gelistirme: Claude Code (full-stack otonom muhendis, \
  bastan sona uygulama gelistirebiliyor), Codex (CI/CD entegrasyonu var)
- Goruntu Uretimi: Nano Banana 2 (Gemini 3.1 Flash Image) - 4K \
  profesyonel kalite, saniyeler icinde
- Video Uretimi: Seedance 2 - profesyonel reklam ve tanitim filmi \
  dakikalar icinde

### Benchmark Sonuclari
- SWE-bench Verified: %70+ (gercek GitHub issue cozme - yazilim gelistirme)
- HumanEval: %95+ (kod uretme)
- GPQA Diamond (lisansustu bilim sorulari): %75+
- MMLU (genel bilgi, 57 konu): %90+
- AIME (ulusal matematik yarismasi): Medalist seviyesi
- ABD Baro Sinavi: Ust %10'da gecti (hukuk alaninda)
- USMLE (Amerikan Tip Lisansi): Her 3 asamayi birden gecti
- CPA (Amerikan Muhasebe Sertifikasi): Gecme esiginin cok ustunde
- WMT Makine Cevirisi: Profesyonel cevirmen seviyesi

### Anthropic Arastirmasi (Mart 2026, "Observed Exposure" Calismasi)
- "Observed exposure" metrigi: teorik yetkinlik + gercek kullanim verisini birlestiriyor
- Bilgisayar & Matematik meslekleri: gorevlerin %94'u AI ile hizlandirilabilir
- Ofis & Idari isler: %90 teorik maruz kalma
- Her %10'luk maruz kalma artisinda, is buyumesi %0.6 puan azaliyor
- En cok etkilenenler: daha egitimli, daha yuksek maasli calisanlar
- KRITIK: Genc iscilerin ise alinmasi maruz kalan mesleklerde yavaslamis \
  (yeni nesil ise alimlarinda AI etkisi ilk gorunuyor)
- AI henuz teorik kapasitesinin kucuk bir kisminda - gelecekte etki DAHA DA artacak

Bir AI asistani bugun tek basina startup kurabilecek seviyede. Bu yetkinlikleri \
bilerek gercekci, iyi kalibre edilmis skorlar uret.

## Cikti Formati

SADECE asagidaki JSON formatinda cevap ver, baska hicbir sey yazma:
{
    "meslek": "<meslek adi>",
    "ai_skor": <0-10 arasi tam sayi>,
    "rationale": "<2-3 cumle Turkce aciklama - neden bu skor?>",
    "bes_yil_tahmini": "<carpici, kisa Turkce tahmin cumlesi>",
    "kayit_disi_notu": "<kayit disi ekonomi etkisi - 1 cumle>"
}
"""


# ---------------------------------------------------------------------------
# Pure functions (testable, no API side-effects)
# ---------------------------------------------------------------------------

def parse_score_response(raw: str) -> dict:
    """Parse LLM response string into a score dict.

    Handles:
    - Bare JSON
    - JSON wrapped in ```json ... ``` fences
    - JSON wrapped in plain ``` ... ``` fences
    - Extra leading/trailing whitespace

    Args:
        raw: The raw text returned by the LLM.

    Returns:
        Parsed dict with at minimum: ai_skor, rationale, bes_yil_tahmini,
        kayit_disi_notu.

    Raises:
        json.JSONDecodeError: If the content is not valid JSON after fence removal.
    """
    text = raw.strip()
    # Remove optional ```json or ``` opening fence and closing ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    return json.loads(text)


def build_user_prompt(occ: dict, md_content: str | None) -> str:
    """Build the user-turn prompt for scoring a single occupation.

    Includes all structured data fields available for the occupation, then
    appends the full Markdown definition (if present) as supplementary context.

    Args:
        occ: Occupation dict from meslekler_master.json.
        md_content: Optional Markdown text from the parsed İŞKUR detail page.

    Returns:
        A formatted string ready to send as the user message.
    """
    parts = [
        f"Meslek: {occ['meslek_adi']}",
        f"ISCO-08 Kodu: {occ['meslek_kodu']}",
        f"Sektor: {occ.get('sektor', 'Bilinmiyor')}",
        f"Istihdam: {occ.get('istihdam_sayisi', 0):,} kisi",
    ]

    maas = occ.get("ortalama_maas")
    if maas:
        parts.append(f"Ortalama Maas: {maas:,} TL/ay")

    egitim = occ.get("egitim_seviyesi")
    if egitim:
        parts.append(f"Egitim Gereksinimi: {egitim}")

    kayit_disi = occ.get("kayit_disi_orani")
    if kayit_disi is not None:
        parts.append(f"Sektorel Kayit Disi Orani: %{kayit_disi}")

    buyume = occ.get("buyume_trendi")
    if buyume is not None:
        parts.append(f"Istihdam Buyume Trendi: {buyume:+}%")

    if md_content:
        parts.append("\n---\nDetayli Meslek Tanimi (ISKUR):\n" + md_content)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# API call (requires google-generativeai)
# ---------------------------------------------------------------------------

def score_occupation(model, occ: dict, md_content: str | None) -> dict:
    """Score a single occupation using Gemini and return the parsed result dict.

    Uses a multi-turn conversation format so the system prompt is treated as
    prior context rather than relying on a system-role parameter (which varies
    across SDK versions).

    Args:
        model: A configured genai.GenerativeModel instance.
        occ: Occupation dict (fields: meslek_adi, meslek_kodu, sektor, ...).
        md_content: Optional parsed İŞKUR Markdown text.

    Returns:
        Parsed score dict (ai_skor, rationale, bes_yil_tahmini, kayit_disi_notu).

    Raises:
        Exception: Propagates any API or JSON parse error to the caller.
    """
    import google.generativeai as genai  # type: ignore

    user_prompt = build_user_prompt(occ, md_content)

    response = model.generate_content(
        [
            # Inject system prompt as a priming user/model exchange so it works
            # across SDK versions that may not support a dedicated system role.
            {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
            {
                "role": "model",
                "parts": [{"text": "Anlasildi. Meslek bilgilerini gonder, JSON formatinda skorlayacagim."}],
            },
            {"role": "user", "parts": [{"text": user_prompt}]},
        ],
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
        ),
    )

    return parse_score_response(response.text)


# ---------------------------------------------------------------------------
# Main pipeline runner
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score Turkish occupations for AI exposure using Gemini 2.5 Flash",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python score_tr.py                    # score all occupations
  python score_tr.py --start 0 --end 5  # test first 5
  python score_tr.py --force            # re-score even cached entries
""",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model ID")
    parser.add_argument("--start", type=int, default=0, help="Start index (slice)")
    parser.add_argument("--end", type=int, default=None, help="End index (slice)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (seconds)")
    parser.add_argument("--force", action="store_true", help="Re-score even cached occupations")
    args = parser.parse_args()

    # Validate API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set. Add it to the .env file.")
        print("  echo 'GEMINI_API_KEY=your_key' > .env")
        return

    # Configure Gemini SDK
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        print("ERROR: google-generativeai not installed. Run: pip install google-generativeai")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(args.model)

    # Load master occupation list
    if not os.path.exists(MASTER_FILE):
        print(f"ERROR: {MASTER_FILE} not found. Run build_master_list.py first.")
        return

    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)

    # Load existing scores for incremental resumption
    scores: list[dict] = []
    scored_codes: set[str] = set()

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            scores = json.load(f)
        # Index by meslek_kodu for O(1) lookup
        scored_codes = {s["meslek_kodu"] for s in scores if "meslek_kodu" in s}

    subset = master[args.start:args.end]
    to_score = [o for o in subset if o["meslek_kodu"] not in scored_codes]

    already_cached = len(subset) - len(to_score)
    print(f"Model:   {args.model}")
    print(f"Total:   {len(subset)} occupations in range")
    print(f"Cached:  {already_cached} (skipping)")
    print(f"To score: {len(to_score)}\n")

    errors: list[str] = []

    for i, occ in enumerate(to_score):
        kodu = occ["meslek_kodu"]

        # Load parsed İŞKUR Markdown if available
        md_path = os.path.join(PARSED_DIR, f"{kodu}.md")
        md_content: str | None = None
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()

        print(f"[{i + 1}/{len(to_score)}] {occ['meslek_adi']} ({kodu})...", end=" ", flush=True)

        # Retry with exponential backoff: 3 attempts, 2s / 4s / 8s
        success = False
        for attempt in range(3):
            try:
                result = score_occupation(model, occ, md_content)

                # Attach the canonical join key so downstream tools can match
                result["meslek_kodu"] = kodu

                scores.append(result)

                # --- Incremental checkpoint save ---
                # Save after every successful API call so interrupted runs
                # can resume without re-scoring completed occupations.
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(scores, f, ensure_ascii=False, indent=2)

                print(f"ai_skor={result['ai_skor']}")
                success = True
                break

            except Exception as exc:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                if attempt < 2:
                    print(f"\n  ERROR (attempt {attempt + 1}/3): {exc} — retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"\n  FAILED after 3 attempts: {exc}")

        if not success:
            errors.append(kodu)

        # Rate-limiting delay between successful calls
        if i < len(to_score) - 1:
            time.sleep(args.delay)

    # ---------------------------------------------------------------------------
    # Summary report
    # ---------------------------------------------------------------------------
    scored = [s for s in scores if "ai_skor" in s]
    print(f"\n{'=' * 60}")
    print(f"Done. Scored: {len(scored)}  Errors: {len(errors)}")
    if errors:
        print(f"Failed codes: {errors}")

    if scored:
        avg = sum(s["ai_skor"] for s in scored) / len(scored)
        print(f"Average AI exposure: {avg:.1f} / 10")

        # Histogram (0–10)
        hist = [0] * 11
        for s in scored:
            skor = s["ai_skor"]
            if 0 <= skor <= 10:
                hist[skor] += 1

        print("\nDistribution:")
        for score_val, count in enumerate(hist):
            bar = "█" * count
            print(f"  {score_val:2d}: {bar} ({count})")

    print(f"\nResults saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
