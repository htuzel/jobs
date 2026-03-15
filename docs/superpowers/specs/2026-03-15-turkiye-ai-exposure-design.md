# Turkiye AI Maruz Kalma Analizi - Tasarim Dokumani

**Tarih:** 2026-03-15
**Durum:** Onaylandi
**Yaklasim:** Fork & Adapt (mevcut ABD pipeline'ini Turkiye'ye adapte et)

---

## 1. Proje Ozeti

Karpathy'nin ABD is piyasasi AI maruz kalma analizini (~342 meslek) Turkiye is piyasasina adapte eden bir proje. TUİK/İŞKUR verilerini kullanarak ~250-350 Turk meslegi icin AI maruz kalma analizi yapacak ve sonuclari tek sayfalik bir Turkce web app olarak sunacak.

### Hedef Kitle
Genel Turk LinkedIn kitlesi - "Turkiye'de hangi meslekler yok olacak, hangileri yukselecek?" viral icerik.

### Ana Mesaj
Tahrik edici, paylasima uygun, tartisma yaratan icerik. Dusuk dijital okuryazarlik varsayimi ile basit ve anlasilir grafikler.

### Ciktilar (Faz 1)
- Turkce web app (tek sayfa, tiiny.site deployment)
- Data (CSV/JSON)

### Gelecek Ciktilar (Faz 2 - ayri spec)
- LinkedIn/blog icerigi (meslek bazli kisa analizler oncelikli)

---

## 2. Turkiye'ye Ozgu Sosyo-Ekonomik Faktorler

ABD versiyonunda olmayan, Turkiye anlatisini farklilasitiracak 3 temel unsur:

### 2a. Kayit Disi Ekonomi
- Turkiye'de ~%30 kayit disi istihdam
- AI kayit disi calisanlari farkli etkiler: "AI seni kovamaz ama musteri bulmani zorlastirir"
- Sektorel kayit disi orani her meslege atanacak

### 2b. Genc Nufus + Issizlik
- %25+ genc issizlik orani
- "Universite okuyup ne olacak?" sorusu
- Giris seviyesi isler en cok etkilenecek (Anthropic arastirmasi ile uyumlu)

### 2c. Bolgesel Esitsizlik
- Istanbul'daki yazilimci vs Sanliurfa'daki ciftci
- AI'in fark derinlestirme potansiyeli
- Dijital olgunluk farki sektorler ve bolgeler arasi

---

## 3. Veri Pipeline'i

### 3a. Veri Kaynaklari
| Kaynak | Veri | Yaklasim | Hedef URL/Format |
|--------|------|----------|------------------|
| İŞKUR Meslek Sozlugu | Meslek tanimlari, ISCO-08 kodlari | Playwright scraping | iskur.gov.tr/is-arayan/meslek-sozlugu |
| TUİK İstihdam İstatistikleri | İstihdam sayilari, sektorel veriler | Excel/CSV indirme | data.tuik.gov.tr (istihdam tablolari) |
| TUİK Kazanc İstatistikleri | Maas verileri, egitim bazli | Excel/CSV indirme | data.tuik.gov.tr (kazanc tablolari) |
| TUİK Kayit Disi | Sektorel kayit disi orani | Excel/CSV indirme | data.tuik.gov.tr (isgucü tablolari) |
| ISCO-08 | Uluslararasi meslek siniflandirmasi (bosluk doldurma) | Referans JSON | ILO standart listesi |

**Not:** TUİK verilerinin cogu scrapable HTML degil, Excel/CSV tablosu olarak indirilebilir. Pipeline buna gore tasarlanmistir - Playwright sadece İŞKUR meslek sayfalari icin, TUİK icin dogrudan dosya indirme + pandas ile parse.

### 3a-bis. Ana Meslek Listesi Olusturma (Pipeline Baslangic Noktasi)
Pipeline'in ilk adimi `data/meslekler_master.json` olusturmaktir:
1. İŞKUR Meslek Sozlugu'nden tum meslekleri ISCO-08 kodlariyla cek
2. TUİK istihdam verileriyle eslestir (ISCO-08 kodu ortak anahtar)
3. İstihdam verisi olan meslekleri filtrele → hedef ~250-350 meslek
4. `meslek_kodu` (ISCO-08) tum pipeline boyunca kanonik birlesim anahtari olarak kullanilir

### 3b. Meslek Basina Toplanacak Veri
| Alan | Kaynak | Ornek |
|------|--------|-------|
| `meslek_adi` | İŞKUR | "Muhasebeci" |
| `meslek_kodu` | ISCO-08 | "2411" |
| `tanim` | İŞKUR | Meslek tanimi |
| `istihdam_sayisi` | TUİK | 185,000 |
| `ortalama_maas` | TUİK/sektorel | ₺28,500/ay |
| `egitim_seviyesi` | İŞKUR | "Lisans" |
| `sektor` | TUİK | "Mali Hizmetler" |
| `kayit_disi_orani` | TUİK sektorel | %15 |
| `buyume_trendi` | TUİK yillik | "+%3" veya "-%5" |

### 3c. Scraping Stratejisi
- **İŞKUR**: Playwright ile meslek sozlugu sayfalari (meslek tanimlari, egitim gereksinimleri)
- **TUİK**: Excel/CSV dosyalari dogrudan indirilip pandas ile parse edilir (HTML scraping degil)
- Veri eksik kalirsa Chrome tools ile canli sayfalardan tamamla
- Her scrape/indirme sonucu `data/raw/` altinda cache'le
- Hedef: ~250-350 meslek
- Anti-scraping onlemi: İŞKUR icin istekler arasi 2-3sn bekleme, User-Agent header

### 3d. Veri Eksikligi Stratejisi
- **Maas**: TUİK yoksa → sektorel ortalama
- **İstihdam sayisi**: TUİK sektorel veri → ISCO alt gruplarina oransal dagitim
- **Kayit disi orani**: TUİK sektorel oran → ayni sektordeki tum mesleklere atanir (sektorel granularite, meslek bazli degil - bu sinirlilik UI'da belirtilir)
- **Buyume trendi**: TUİK yillik karsilastirma, yoksa "veri yok"

---

## 4. Skorlama Sistemi

### 4a. LLM
Gemini 2.5 Flash - direkt Google AI API (`google-generativeai` Python SDK). Kullanici API key saglayacak (`.env` dosyasinda `GEMINI_API_KEY`). ABD versiyonundaki OpenRouter/httpx yaklasimi kullanilmayacak.

### 4b. Cift Metrik Yaklasimi

**Metrik 1: AI Maruz Kalma Skoru (0-10)**

| Skor | Kademe | Turkiye Ornegi |
|------|--------|----------------|
| 0-1 | Minimal | İnsaat iscisi, Cilingir |
| 2-3 | Dusuk | Kuafor, Asci, Sofor |
| 4-5 | Orta | Hemsire, Polis, Ogretmen |
| 6-7 | Yuksek | Muhasebeci, Gazeteci, Avukat |
| 8-9 | Cok Yuksek | Yazilimci, Grafiker, Cevirmen |
| 10 | Maksimum | Veri girisci, Call center |

**Metrik 2: "5 Yilda Ne Olacak?" Tahmini**

Kisa, tahrik edici, paylasima uygun bir cumle. Ornekler:
- "Her 3 muhasebeciden 1'i gereksiz kalacak. Kalan 2'si AI araclarini kullanmak zorunda."
- "AI senin isini alamaz ama Instagram'da musteri bulamayan kapanir"

**Prompt Guardrail'leri:** Tahminler tahrik edici ama sorumlu olmali herhangi bir gercegi manipule etmemeli:
- Belirli sirket/kurum isimleri hedef alinmayacak
- Irksal/etnik/cinsiyete dayali genellemeler yapilmayacak
- Tahminler "olabilir/yonelim/risk" diliyle, kesin hukum gibi degil
- Tum tahminler "AI trendleri devam ederse" on kosuluyla cercevelenecek

### 4c. Skorlama Prompt'u Turkiye Adaptasyonlari

LLM prompt'una 3 ek katman:
1. **Kayit disi ekonomi faktoru**: Kayit disi calisanlar AI'dan nasil farkli etkilenir
2. **Dijital olgunluk**: Sektorun Turkiye'deki dijitallesme seviyesi
3. **Bolgesel fark**: Buyuk sehir vs kucuk sehir etkisi

### 4d. AI Guncel Yetkinlik Baglami (Prompt'a Gomulecek)

Skorlama prompt'u su bilgileri icerecek ki LLM gercekci skorlar versin:

**AI Ekosistemi - Mart 2026:**
- Metin & Akil Yurutme: Claude Opus 4.6 (1M context), Sonnet 4.6, GPT 5.4, Gemini 2.5 Flash/Pro
- Kodlama & Otonom Gelistirme: Claude Code (full-stack otonom muhendis), Codex (CI/CD entegrasyonu)
- Goruntu Uretimi: Nano Banana 2 (Gemini 3.1 Flash Image) - 4K, profesyonel kalite
- Video Uretimi: Seedance 2 - reklam/tanitim filmi dakikalar icinde

**Benchmark Sonuclari:**
- SWE-bench Verified: %70+ | HumanEval: %95+
- GPQA Diamond: %75+ | MMLU: %90+ | AIME: Medalist seviyesi
- ABD Baro Sinavi: Ust %10 | USMLE: 3/3 gecti | CPA: Gecti
- WMT ceviri: Profesyonel cevirmen seviyesi

**Anthropic Arastirmasi (Mart 2026) - labor-market-impacts:**
- "Observed exposure" metrigi: teorik yetkinlik + gercek kullanim verisi
- Bilgisayar & Matematik: %94, Ofis & İdari: %90 teorik maruz kalma
- Her %10 maruz kalma artisinda buyume tahmini %0.6 puan dusuyor
- En cok etkilenenler: daha egitimli, daha yuksek maasli, %16 daha fazla kadin
- KRITIK: Genc iscilerin ise alinmasi maruz kalan mesleklerde yavaslamis
- AI henuz teorik kapasitesinin kucuk bir kisminda - etki artacak

### 4e. Skorlama Cikti Formati
```json
{
  "meslek": "Muhasebeci",
  "meslek_kodu": "2411",
  "ai_skor": 8,
  "rationale": "Fatura kesme, beyanname, defter tutma islerinin %80'i...",
  "bes_yil_tahmini": "Her 3 muhasebeciden 1'i gereksiz kalacak. Kalan 2'si AI araclarini kullanmak zorunda.",
  "kayit_disi_notu": "Kayit disi calisanlar daha gec etkilenecek ama musteri kaybedecek."
}
```

### 4f. Skorlama Sureci
- Her meslek icin tek API call'da iki metrik birden alinir
- Incremental caching - yarim kalirsa kaldigi yerden devam eder
- `data/skorlar.json`'a yazilir
- **Hata yonetimi:** Basarisiz API call'lar icin 3 deneme, exponential backoff (2s, 4s, 8s). Kalici hatalar log'lanir, meslek "skorlanamadi" olarak isaretlenir
- **Birlesim anahtari:** `meslek_kodu` (ISCO-08) tum pipeline dosyalari arasinda kanonik join key

---

## 5. Web App UI/UX

### 5a. Genel Ilkeler
- Tek sayfa, Turkce, karanlik tema
- Mobil-oncelikli, basit, hizli yuklenen
- Dusuk dijital okuryazarlik varsayimi
- Vanilla HTML/CSS/JS (framework yok)
- `<meta charset="UTF-8">` zorunlu, Turkce karakter destegi (I/i, G/g, S/s, C/c)
- Arama/filtre fonksiyonu Turkce locale-aware case folding kullanacak (toLocaleLowerCase('tr-TR'))
- **Not:** Frontend ABD versiyonunun canvas treemap'inden tamamen farkli bir UX (arama+kart). Bu bir adaptasyon degil, yeni yazim olacak. ABD kodundan sadece renk paleti ve genel tasarim dili referans alinir.

### 5b. Kullanici Akisi

**Adim 1 - Giris Ekrani (Kanca)**
```
"Meslegini yaz, AI riskini ogren"
[____arama kutusu____] [Goster]
```
Amac: Kisinin "benim meslegim ne olacak?" merakiyla baslamasi - en guclu viral kanca.

**Adim 2 - Kisisel Sonuc Karti**
```
┌─────────────────────────────────┐
│ MUHASEBECI              8/10   │
│ ██████████████████░░  Yuksek   │
│                                │
│ 5 Yilda Ne Olacak?             │
│ "Her 3 muhasebeciden 1'i       │
│  gereksiz kalacak..."          │
│                                │
│ Maas: ₺28,500/ay              │
│ Calisan: 185,000 kisi          │
│ Egitim: Lisans                 │
│ Kayit disi: %15               │
│                                │
│ [Tum meslekleri gor]           │
└─────────────────────────────────┘
```

**Adim 3 - Liste Gorunumu (asagi scroll)**
- Filtreler: Kategori | Risk seviyesi | Egitim | Maas arailigi
- Siralama: En riskli → En guvenli (varsayilan)
- Hazir listeler: "En riskli 10", "En guvenli 10", "Universite mezunlari icin", "Kayit disi ekonomi"
- Her meslek bir kart - tiklaninca detay acar

### 5c. Kart Tasarimi
- Buyuk, okunakli font boyutlari
- Risk renk kodlari: Kirmizi (8-10), Turuncu (5-7), Yesil (0-4)
- Animasyon yok - performans onceligi
- Karanlik tema

### 5d. Ozel Bolumler
- **Ozet istatistikler**: "X milyon is risk altinda", "En guvenli sektor: Y"
- **Turkiye'nin AI Haritasi**: Basit bar chart - sektorlere gore ortalama risk
- **Paylasim butonu**: Meslek kartini gorsel olarak LinkedIn/Twitter'a paylas

---

## 6. Teknik Mimari

### 6a. Dizin Yapisi
```
jobs/
├── tr/                          # Turkiye projesi
│   ├── scrape_iskur.py           # İŞKUR meslek sozlugu scraper (Playwright)
│   ├── scrape_tuik.py            # TUİK Excel/CSV indirme + parse (pandas)
│   ├── build_master_list.py      # Master meslek listesi olusturma
│   ├── parse_tr.py              # İŞKUR HTML → yapisal metin (iki kaynak icin ayri parser fonksiyonlari)
│   ├── make_csv_tr.py           # CSV olusturma
│   ├── score_tr.py              # Gemini 2.5 Flash skorlama
│   ├── build_site_data_tr.py    # Site verisi hazirlama
│   ├── data/
│   │   ├── raw/                 # Scrape cache
│   │   ├── meslekler.csv        # Ana meslek listesi
│   │   ├── skorlar.json         # AI skorlari + 5 yil tahmini
│   │   └── occupations_tr.json  # Zenginlestirilmis veri
│   └── site/
│       ├── index.html           # Tek sayfa app (Turkce)
│       └── data.json            # Frontend verisi
├── site/                        # Mevcut ABD versiyonu (dokunulmaz)
├── scrape.py                    # Mevcut ABD kodlari (referans)
└── ...
```

### 6b. Pipeline Calisma Sirasi
```
1. scrape_iskur.py       → data/raw/iskur/*.html (meslek tanimlari)
2. scrape_tuik.py        → data/raw/tuik/*.xlsx (istihdam/maas/kayitdisi)
3. parse_tr.py           → data/raw/parsed/*.json (yapisal veri)
4. build_master_list.py  → data/meslekler_master.json (birlestirilmis liste)
5. make_csv_tr.py        → data/meslekler.csv (CSV export)
6. score_tr.py           → data/skorlar.json (cift metrik)
7. build_site_data_tr.py → site/data.json (frontend hazir)
```

Her adim bagimsiz calisir, cache kullanir, yarim kalirsa devam eder.

### 6c. Teknoloji
- Python (pipeline)
- Playwright (İŞKUR scraping)
- pandas (TUİK Excel/CSV parse)
- google-generativeai SDK (Gemini 2.5 Flash)
- Vanilla HTML/CSS/JS (frontend)
- tiiny.site (deployment, ~3-10MB limit - data.json boyutu izlenecek)

### 6d. Bagimliliklar (`tr/requirements.txt`)
```
playwright
pandas
openpyxl
google-generativeai
python-dotenv
```

---

## 7. Gelecek Calismalar (Faz 2)

Bu spec Faz 1'i kapsar. Faz 2 ayri bir spec ile ele alinacak:
- Meslek bazli kisa analizler (2-3 paragraf LinkedIn postu sablonu) - **oncelikli**
- "Top 10" listeleri (en riskli, en guvenli, universite mezunlari icin vs.)
- Kapsamli Turkiye raporu blog yazisi
- Rapordan 2-3 blog icerigi cikarilacak

---

## 8. Basari Kriterleri

1. En az 200 Turk meslegi skorlanmis ve web app'te goruntulenebilir
2. Cift metrik (AI skor + 5 yil tahmini) her meslek icin mevcut
3. Turkce UI, mobilde sorunsuz calisir
4. Kayit disi ekonomi / genc issizlik / bolgesel fark anlatisi veride yansir
5. OG meta tag'leri dogru calisir - LinkedIn/Twitter'da paylasinca meslek adi, skor ve tahmin iceren onizleme karti gorunur
