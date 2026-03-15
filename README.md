# Turkiye AI Maruz Kalma Analizi 2026

**1,123 Turk meslegi icin yapay zeka ve robotik risk analizi**

[Canli Demo](https://tiiny.site) | [ABD Orijinal Versiyonu (Karpathy)](https://github.com/karpathy/jobs)

---

## Proje Hakkinda

Bu proje, [Andrej Karpathy'nin ABD is piyasasi AI maruz kalma analizinin](https://github.com/karpathy/jobs) Turkiye versiyonudur. ABD versiyonu 342 Amerikan meslegi icin tek bir AI maruz kalma skoru hesaplarken, bu proje 1,123 Turk meslegi icin hem **AI maruz kalma** hem de **robotik risk** olmak uzere cift metrik kullanir.

### Istatistikler

| Metrik | Deger |
|--------|-------|
| Toplam meslek | 1,123 |
| AI maruz kalma ortalamasi | 4.2 / 10 |
| Robotik risk ortalamasi | 2.6 / 10 |
| Veri kaynaklari | ISKUR, TUIK (2023-2024) |
| Skorlama modeli | Claude Opus 4.6 |

---

## Metodoloji

### Veri Kaynaklari

1. **ISKUR Meslek Sozlugu** - 1,123 meslek tanimi, ISCO-08 kodlari, egitim gereksinimleri
2. **TUIK Kazanc Yapisi Istatistikleri 2023** - Sektor ve meslek grubuna gore maas verileri
3. **TUIK Ucretli Calisan Istatistikleri 2024** - Istihdam sayilari, sektorel dagilim
4. **TUIK Kayit Disi Istihdam Verileri** - ISCO ve NACE bazli kayit disi oranlar

### Cift Metrik Yaklasimi

**AI Maruz Kalma Skoru (0-10):** Meslegin yapay zeka tarafindan ne olcude donusturulecegini olcer. Hem dogrudan otomasyon (AI'in isi yapmasi) hem de dolayli etkiler (AI'in iscileri o kadar verimli kilmasi ki daha az isci gerekmesi) dikkate alinir.

| Skor | Kademe | Ornek |
|------|--------|-------|
| 0-1 | Minimal | Insaat iscisi, Cilingir |
| 2-3 | Dusuk | Kuafor, Asci, Sofor |
| 4-5 | Orta | Hemsire, Polis, Ogretmen |
| 6-7 | Yuksek | Muhasebeci, Gazeteci, Avukat |
| 8-9 | Cok Yuksek | Yazilimci, Grafiker, Cevirmen |
| 10 | Maksimum | Veri girisci, Call center |

**Robotik Risk Skoru (0-10):** Meslegin fiziksel otomasyon ve robotik tarafindan ne olcude etkilenecegini olcer. AI'dan ayri bir eksen olarak degerlendirilir.

### Skorlama Sureci

- **Model:** Claude Opus 4.6 (1M context)
- **Yontem:** 12 paralel agent ile her meslek tek tek degerlendirildi
- **Prompt baglami:** Mart 2026 AI benchmark sonuclari, Anthropic is piyasasi arastirmasi, Turkiye-spesifik faktorler
- Her meslek icin AI skoru, gerekce, 5 yillik tahmin ve kayit disi ekonomi notu uretildi
- Robotik risk ayri bir pass olarak degerlendirildi

### Turkiye'ye Ozgu Faktorler

Skorlama prompt'una gomulu 3 ek katman:

1. **Kayit disi ekonomi (~%30):** Kayit disi calisanlar AI'dan farkli etkilenir. Dogrudan is kaybi degil, musteri ve is bulma kanallarinin dijitallesmesi ile dolayli etki.
2. **Genc issizlik (%25+):** Giris seviyesi isler en cok etkilenen kategori. Anthropic arastirmasiyla uyumlu: genc iscilerin ise alinmasi AI-maruz mesleklerde yavaslamis.
3. **Bolgesel esitsizlik:** Istanbul'daki yazilimci ile Sanliurfa'daki ciftci arasindaki dijital olgunluk farki.

### AI Yetkinlik Baglami (Mart 2026)

Skorlar su benchmark gercekligine gore kalibre edildi:
- SWE-bench Verified: %70+ | HumanEval: %95+
- ABD Baro Sinavi: Ust %10 | USMLE: 3/3 gecti
- WMT ceviri: Profesyonel cevirmen seviyesi
- Claude Code: Full-stack otonom muhendislik
- Goruntu/video uretimi: Profesyonel kalite

### Enflasyon Duzeltmesi

TUIK 2023 maas verileri, %65 enflasyon tahmini ile 2026 yilina guncellenmiistir. Maas verileri aylk brut TL cinsindendir.

---

## Veri Pipeline'i

```
1. scrape_iskur.py       -> data/raw/iskur/          (ISKUR meslek sozlugu)
2. scrape_tuik.py        -> data/raw/tuik/           (TUIK Excel dosyalari)
3. parse_tr.py           -> data/raw/tuik/*_parsed.json (yapisal veri)
4. build_master_list.py  -> data/meslekler_master.json (1,123 meslek)
5. score_tr.py           -> data/skorlar.json         (AI skorlari)
                         -> data/robotik_skorlar.json  (robotik skorlari)
6. build_site_data_tr.py -> site/data.json            (frontend verisi)
```

Her adim bagimsiz calisir, onceki adimlarin ciktisini cache olarak kullanir.

## Kurulum

```bash
# Bagimliliklari kur
pip install -r requirements.txt

# Playwright browser'i kur (sadece ISKUR scraping icin)
playwright install chromium

# API anahtari ayarla
cp .env.example .env
# .env dosyasina ANTHROPIC_API_KEY veya GEMINI_API_KEY ekle
```

## Calistirma

```bash
# 1. ISKUR mesleklerini cek (Playwright gerektirir)
python scrape_iskur.py

# 2. TUIK verilerini indir ve parse et
python scrape_tuik.py

# 3. Ham veriyi yapisal JSON'a cevir
python parse_tr.py

# 4. Master meslek listesi olustur
python build_master_list.py

# 5. AI ve robotik skorlama (API anahtari gerektirir)
python score_tr.py

# 6. Site verisini olustur
python build_site_data_tr.py

# 7. Yerel sunucu
cd site && python -m http.server 8000
```

## Dizin Yapisi

```
tr/
  scrape_iskur.py          # ISKUR meslek sozlugu scraper (Playwright)
  scrape_tuik.py           # TUIK Excel indirme + parse (pandas)
  build_master_list.py     # Master meslek listesi
  parse_tr.py              # Veri parser
  make_csv_tr.py           # CSV export
  score_tr.py              # AI + robotik skorlama
  build_site_data_tr.py    # Site verisi hazirlama
  utils.py                 # Yardimci fonksiyonlar
  data/
    meslekler_master.json  # 1,123 meslek (birlestirilmis veri)
    skorlar.json           # AI skorlari + 5 yil tahminleri
    robotik_skorlar.json   # Robotik risk skorlari
    iskur_meslekler_raw.json  # ISKUR ham veri
    raw/
      iskur/               # ISKUR Excel export
      tuik/                # TUIK Excel + parsed JSON
  site/
    index.html             # Tek sayfa web app (Turkce)
    data.json              # Frontend verisi
  tests/                   # Test dosyalari
```

---

# English

## Turkey AI Exposure Analysis 2026

**AI and robotics risk analysis for 1,123 Turkish occupations**

This is the Turkish adaptation of [Andrej Karpathy's US job market AI exposure analysis](https://github.com/karpathy/jobs). While the US version scores 342 American occupations on a single AI exposure axis, this project evaluates 1,123 Turkish occupations using dual metrics: **AI exposure** and **robotics risk**.

### Key Differences from the US Version

- **Data sources:** ISKUR (Turkish Employment Agency) occupation dictionary + TUIK (Turkish Statistical Institute) employment and salary statistics, instead of BLS OOH
- **Dual metrics:** AI exposure score (0-10) + Robotics risk score (0-10)
- **Scoring model:** Claude Opus 4.6 with 12 parallel agents, each occupation evaluated individually
- **Turkey-specific context:** Informal economy (~30%), youth unemployment (25%+), regional digital divide
- **Scale:** 1,123 occupations (vs 342 in the US version)

### Statistics

| Metric | Value |
|--------|-------|
| Total occupations | 1,123 |
| Average AI exposure | 4.2 / 10 |
| Average robotics risk | 2.6 / 10 |

### How to Run

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Add your API key to .env

python scrape_iskur.py        # Scrape ISKUR occupations
python scrape_tuik.py         # Download TUIK data
python parse_tr.py            # Parse raw data
python build_master_list.py   # Build master list
python score_tr.py            # Score occupations (requires API key)
python build_site_data_tr.py  # Build site data
cd site && python -m http.server 8000
```

### Attribution

This project is a fork and adaptation of [karpathy/jobs](https://github.com/karpathy/jobs). The original analysis covers the US labor market using BLS data. This version adapts the methodology for the Turkish labor market using ISKUR and TUIK data, with significant additions including dual-metric scoring, informal economy analysis, and Turkey-specific socioeconomic context.

## License

Same as the original [karpathy/jobs](https://github.com/karpathy/jobs) project.
