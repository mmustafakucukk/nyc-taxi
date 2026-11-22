# NYC Taxi dashboard (2. Kisi)
#
# Ham veriyi degil, analiz scriptlerinin urettigi kucuk sonuc dosyalarini okur:
#   results/agg/*.csv                          -> src/aggregations.py             (2. Kisi)
#   results/*_benchmark.csv, model_sonuclari   -> src/benchmark_*.py, model_egit.py (3. Kisi)
#   docs/*.md                                  -> tum ekibin raporlari
#   sorular/*.md                               -> sinav sorulari
# Bu yuzden 10 milyon satirlik veri olsa da saniyeler icinde acilir ve Spark gerektirmez.
#
# Kullanim (proje ana klasorunden):
#   python src/aggregations.py      # once sonuclari uret
#   streamlit run dashboard/app.py  # tarayicida acilir
#
# Tasarim: PatiPortal tasarim sistemi (krem zemin, petrol yesili, Nunito + Inter, beyaz kartlar).
# Renk kurali: secilen / one cikan veri yesil, digerleri gri. Ikinci bir seri gerekiyorsa turuncu.

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJE = Path(__file__).resolve().parent.parent
AGG = PROJE / "results" / "agg"
SONUC = PROJE / "results"
DOCS = PROJE / "docs"
SORULAR = PROJE / "sorular"

# ---------------- Sabitler ----------------
ODEME_ADLARI = {0: "Flex Fare", 1: "Kredi kartı", 2: "Nakit", 3: "Ücretsiz", 4: "İtirazlı"}
GUN_ADLARI = {1: "Pazar", 2: "Pazartesi", 3: "Salı", 4: "Çarşamba", 5: "Perşembe", 6: "Cuma", 7: "Cumartesi"}
GUN_SIRASI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
SAATLER = [f"{h:02d}:00" for h in range(24)]
MIL_KM = 1.609

# Arayuz renkleri (PatiPortal)
ANA = "#1F5F5B"
METIN, METIN_IKINCIL, METIN_SOLUK = "#1E2523", "#4F5856", "#646B69"
CIZGI, KENARLIK = "#E7E1D8", "#D9D1C5"

# Grafik renkleri (renk korlugu testinden gecti). Her renk bir varligi temsil eder, sirayla degil.
YESIL, TURUNCU, MAVI, HARDAL = "#008C80", "#D9692A", "#4F86C6", "#B8860B"
GRI, GRI_ACIK = "#B9B2A7", "#DDD7CE"
KIRMIZI = "#B42318"   # sadece "bellek yetmedi"
SIRALI = ["#F4F8F7", "#CFE0DC", "#8DB5B0", "#2E7D76", "#174744"]

GUN_TIPI_RENK = {"Hafta içi": YESIL, "Hafta sonu": TURUNCU}
ODEME_RENK = {"Kredi kartı": YESIL, "Nakit": TURUNCU, "Flex Fare": MAVI, "İtirazlı": HARDAL, "Ücretsiz": GRI}
YONTEM_ADLARI = {"spark": "PySpark", "pandas_tum": "pandas (tüm sütunlar)", "pandas_secili": "pandas (seçili sütunlar)"}
YONTEM_RENK = {"PySpark": YESIL, "pandas (tüm sütunlar)": TURUNCU, "pandas (seçili sütunlar)": MAVI}
FORMAT_RENK = {"CSV": TURUNCU, "Parquet": YESIL}
ISLEM_ADLARI = {
    "csv_yaz": ("Yazma", "CSV"), "parquet_yaz": ("Yazma", "Parquet"),
    "csv_oku_tum": ("Okuma: tüm sütunlar", "CSV"), "parquet_oku_tum": ("Okuma: tüm sütunlar", "Parquet"),
    "csv_oku_3sutun": ("Okuma: 3 sütun", "CSV"), "parquet_oku_3sutun": ("Okuma: 3 sütun", "Parquet"),
}
ISLEM_SIRASI = ["Yazma", "Okuma: tüm sütunlar", "Okuma: 3 sütun"]
KULLANILABILIR_RAM_GB = 15  # 3. Kisinin benchmark bilgisayari: 16 GB, isletim sistemi sonrasi ~15 GB
MESAFE_SIRASI = ["0-1 mil", "1-2 mil", "2-5 mil", "5-10 mil", "10+ mil"]
MESAFE_KM = {"0-1 mil": "0–1,6 km", "1-2 mil": "1,6–3,2 km", "2-5 mil": "3,2–8 km", "5-10 mil": "8–16 km",
             "10+ mil": "16+ km"}

# Temizlik kurallarinin acik dilde anlamlari (1. Kisinin kurallari, docs/temizlik_raporu.md)
KURAL_ACIKLAMA = {
    "tarih araligi disi": ("Ocak–Mart 2026 dışındaki tarihler",
                           "Taksimetre saati yanlış ayarlanmış araçlardan 2008–2009 tarihli ya da Nisan'a taşan kayıtlar."),
    "mesafe <= 0": ("Mesafe 0 veya negatif",
                    "Taksimetre açılmış ama araç hareket etmemiş; iptal edilen ya da yanlışlıkla başlatılan yolculuklar."),
    "ucret veya toplam <= 0": ("Ücret veya toplam tutar 0 ya da negatif",
                               "İade, düzeltme ve iptal kayıtları. Gerçek bir ödeme yok."),
    "sure < 1 dk": ("1 dakikadan kısa",
                    "Taksimetrenin açılıp hemen kapandığı kayıtlar; gerçek bir yolculuk olamayacak kadar kısa."),
    "sure > 180 dk": ("3 saatten uzun",
                      "Taksimetrenin kapatılmasının unutulduğu kayıtlar; şehir içinde 3 saat süren yolculuk pek mümkün değil."),
    "mesafe > 100 mil": ("160 km'den uzun",
                         "Ölçüm hatası; ham veride 328.522 mil (yarım milyon km) gibi imkânsız değerler var."),
    "ucret > 500 $": ("Ücret 500 $'dan fazla", "Elle yanlış girilmiş tutarlar."),
    "hiz > 80 mph": ("Ortalama hız 130 km/sa'ten fazla",
                     "Mesafe ya da süreden biri hatalı; şehir içi taksi için imkânsız hız."),
    "birebir tekrar eden satir": ("Birebir tekrar eden satır", "Aynı kaydın iki kez gönderilmesi. Bu veride hiç yok."),
}

st.set_page_config(page_title="NYC Taksi Analizi", page_icon="🚕", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Nunito:wght@700;800&display=swap');
:root {
  --renk-ana: #1F5F5B; --renk-ana-soluk: #EEF4F3; --zemin: #FBF8F4; --kart: #FFFFFF;
  --metin: #1E2523; --metin-ikincil: #4F5856; --metin-soluk: #646B69; --cizgi: #E7E1D8;
  --uyari: #8A4B0F; --uyari-zemin: #FCE9D2;
  --font-baslik: 'Nunito', 'Segoe UI', system-ui, sans-serif;
  --font-govde: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
}
.stApp { background: var(--zemin); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp td, .stApp th { font-family: var(--font-govde); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 3rem; }
[data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4 {
  font-family: var(--font-baslik); font-weight: 800; color: var(--metin); letter-spacing: -0.01em; line-height: 1.2; }
[data-testid="stHeaderActionElements"] { display: none; }

/* Sol menu */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--cizgi); }
[data-testid="stSidebar"] [role="radiogroup"] { gap: 2px; width: 100%; }
[data-testid="stSidebar"] [role="radiogroup"] > div { width: 100%; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] { width: 100%; margin: 0; padding: 9px 12px; border-radius: 10px;
  transition: background-color 150ms ease; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) { display: none; }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover { background: var(--zemin); }
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] { background: var(--renk-ana-soluk); }
[data-testid="stSidebar"] [data-testid="stRadioOption"] p { color: var(--metin-ikincil); font-size: 15px; font-weight: 500; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] [data-testid="stIconMaterial"] { font-size: 19px; margin-right: 4px; }
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p,
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] [data-testid="stIconMaterial"] {
  color: var(--renk-ana) !important; font-weight: 600; }
.pp-logo { display: flex; align-items: center; gap: 10px; margin: -6px 0 4px; color: var(--renk-ana);
  font-family: var(--font-baslik); font-weight: 800; font-size: 21px; }
.pp-logo svg { width: 26px; height: 26px; stroke: var(--renk-ana); fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.pp-logo-alt { color: var(--metin-soluk); font-size: 13px; margin: 0 0 18px 36px; }
.pp-menu-baslik { color: var(--metin-soluk); font-size: 12px; font-weight: 600; letter-spacing: .06em;
  text-transform: uppercase; margin: 4px 0 6px 12px; }
.pp-yan-alt { color: var(--metin-soluk); font-size: 12.5px; line-height: 1.5; margin: 22px 0 0 12px; }

/* Sayfa basligi */
.pp-ust { margin: 0 0 10px; color: var(--renk-ana); font-size: 13px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }
.pp-sayfa-baslik h1 { font-size: clamp(28px, 4vw, 38px) !important; margin: 0 0 8px !important; padding: 0 !important; }
.pp-giris { color: var(--metin-ikincil); font-size: 16.5px; line-height: 1.6; max-width: 780px; margin: 0 0 18px; }

/* Sayac kutulari */
.pp-sayaclar { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 12px; margin: 0 0 6px; }
.pp-sayac { background: var(--kart); border: 1px solid var(--cizgi); border-radius: 16px; padding: 16px 18px; }
.pp-sayac-etiket { display: block; color: var(--metin-ikincil); font-size: 14px; line-height: 1.35; }
.pp-sayac-deger { display: block; margin-top: 4px; color: var(--metin); font-family: var(--font-baslik); font-size: 28px;
  font-weight: 800; line-height: 1.15; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pp-sayac-alt { display: block; margin-top: 3px; color: var(--metin-soluk); font-size: 12.5px; }
.pp-sayac.vurgu .pp-sayac-deger { color: var(--renk-ana); }
.pp-sayac.kirmizi .pp-sayac-deger { color: #B42318; }

/* Kart */
[class*="st-key-kart"] { background: var(--kart); border: 1px solid var(--cizgi); border-radius: 18px; padding: 22px 24px 16px; }
.pp-kart-baslik h3 { font-size: 19px !important; margin: 0 0 2px !important; padding: 0 !important; }
.pp-kart-baslik p { margin: 0 0 4px; color: var(--metin-soluk); font-size: 14px; }

/* Yorum: grafigin altindaki aciklama */
.pp-yorum { border-top: 1px solid var(--cizgi); padding-top: 12px; margin-top: 2px; color: var(--metin-ikincil);
  font-size: 14.5px; line-height: 1.6; }
.pp-yorum b { color: var(--metin); }
.pp-yorum-etiket { display: inline-block; color: var(--renk-ana); font-weight: 600; font-size: 12px; letter-spacing: .06em;
  text-transform: uppercase; margin-right: 8px; }

/* Bulgu listesi */
.pp-bulgular { list-style: none; padding: 0; margin: 4px 0 0; counter-reset: b; }
.pp-bulgular li { counter-increment: b; display: flex; gap: 14px; padding: 12px 0; border-bottom: 1px solid var(--cizgi);
  color: var(--metin-ikincil); font-size: 15px; line-height: 1.55; }
.pp-bulgular li:last-child { border-bottom: none; }
.pp-bulgular li::before { content: counter(b); flex: none; width: 26px; height: 26px; border-radius: 50%;
  background: var(--renk-ana-soluk); color: var(--renk-ana); font-weight: 700; font-size: 13px;
  display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.pp-bulgular b { color: var(--metin); }
.pp-bulgular small { display: block; color: var(--metin-soluk); font-size: 12.5px; margin-top: 2px; }

/* Arastirma sorusu (Ozet sayfasinin alti) */
.pp-soru { background: var(--kart); border: 1px solid var(--cizgi); border-left: 4px solid var(--renk-ana);
  border-radius: 14px; padding: 20px 24px; margin-top: 8px; }
.pp-soru h3 { font-size: 20px !important; margin: 4px 0 10px !important; padding: 0 !important; }
.pp-soru p { color: var(--metin-ikincil); font-size: 15.5px; line-height: 1.65; margin: 0 0 8px; }
.pp-soru-sayilar { display: flex; flex-wrap: wrap; gap: 10px 28px; margin-top: 12px; padding-top: 12px;
  border-top: 1px solid var(--cizgi); }
.pp-soru-sayilar div { font-size: 13.5px; color: var(--metin-soluk); }
.pp-soru-sayilar b { display: block; font-family: var(--font-baslik); font-size: 22px; color: var(--metin); }

/* Kucuk kutular */
.pp-not { display: flex; gap: 12px; padding: 12px 16px; border-radius: 12px; background: var(--uyari-zemin);
  border: 1px solid #F3D2AA; color: var(--metin); font-size: 14.5px; line-height: 1.55; margin: 4px 0 8px; }
.pp-not b { color: var(--uyari); }
.pp-kural { background: var(--zemin); border: 1px solid var(--cizgi); border-radius: 14px; padding: 16px 18px; }
.pp-kural h4 { font-size: 17px !important; margin: 0 0 6px !important; padding: 0 !important; }
.pp-kural p { color: var(--metin-ikincil); font-size: 14.5px; line-height: 1.55; margin: 0 0 10px; }
.pp-kural-sayilar { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.pp-kural-sayilar div { font-size: 12.5px; color: var(--metin-soluk); }
.pp-kural-sayilar b { display: block; font-size: 17px; color: var(--metin); }
.pp-durum { border: 1px solid var(--cizgi); border-radius: 14px; padding: 14px 16px; height: 100%; background: var(--kart); }
.pp-durum b { display: block; color: var(--metin); font-size: 15px; margin-bottom: 4px; }
.pp-durum span { color: var(--metin-ikincil); font-size: 14px; line-height: 1.5; }
.pp-durum .sayi { display: block; font-family: var(--font-baslik); font-weight: 800; font-size: 22px; color: var(--renk-ana); margin-bottom: 2px; }

/* Soru karti */
.pp-soru-no { color: var(--renk-ana); font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }
.pp-dogru { color: #17603F; font-weight: 600; } .pp-yanlis { color: #B42318; font-weight: 600; }
.pp-bos { color: var(--metin-soluk); font-weight: 600; }

.pp-alt { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--cizgi); color: var(--metin-soluk); font-size: 13px; }
</style>
""", unsafe_allow_html=True)


# ---------------- Yardimci fonksiyonlar ----------------
def tr(sayi, ondalik=0):
    """Sayiyi Turkce bicimde yazar: 1234567.8 -> '1.234.567,8'"""
    metin = f"{sayi:,.{ondalik}f}"
    return metin.replace(",", "§").replace(".", ",").replace("§", ".")


# Turkce ekler sayinin okunusundaki son kelimeye gore degisir: %86'sı (altı), %90'ı (doksan), 18:00'de (sekiz)
_SON_RAKAM = {"0": "sıfır", "1": "bir", "2": "iki", "3": "üç", "4": "dört", "5": "beş", "6": "altı", "7": "yedi",
              "8": "sekiz", "9": "dokuz"}
_ONLAR = {"1": "on", "2": "yirmi", "3": "otuz", "4": "kırk", "5": "elli", "6": "altmış", "7": "yetmiş",
          "8": "seksen", "9": "doksan"}


def _son_kelime(metin):
    """'87,9' -> 'dokuz', '40' -> 'kırk', '100' -> 'yüz', '18:00' -> 'sekiz'"""
    metin = metin.split(":")[0].lstrip("0") or "0"
    rakamlar = metin.split(",")[-1] if "," in metin else metin.replace(".", "")
    if rakamlar[-1] != "0" or len(rakamlar) == 1:
        return _SON_RAKAM[rakamlar[-1]]
    if len(rakamlar) >= 2 and rakamlar[-2] != "0":
        return _ONLAR[rakamlar[-2]]
    return "yüz" if len(rakamlar) == 3 else "bin"


def _son_unlu(kelime):
    return [h for h in kelime if h in "aeıioöuü"][-1]


def iyelik(metin):
    """%86 -> 'sı', %90 -> 'ı', %88 -> 'i' (binişlerin %86'sı)"""
    k = _son_kelime(metin)
    u = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[_son_unlu(k)]
    return ("s" + u) if k[-1] in "aeıioöuü" else u


def bulunma(metin):
    """18:00 -> 'de', 03:00 -> 'te', 19:00 -> 'da'"""
    k = _son_kelime(metin)
    u = "a" if _son_unlu(k) in "aıou" else "e"
    return ("t" if k[-1] in "fstkçşhp" else "d") + u


def yuzde(deger, ondalik=0):
    """'%86'sı' gibi ekli yuzde metni"""
    m = tr(deger, ondalik)
    return f"%{m}'{iyelik(m)}"


def saat_de(saat):
    return f"{saat}'{bulunma(saat)}"


def kisa(sayi):
    """Sayac kutulari icin kisa yazim: 10452582 -> '10,45 M'"""
    return f"{tr(sayi / 1e6, 2)} M" if sayi >= 1e6 else tr(sayi)


def milyon(sayi):
    return f"{tr(sayi / 1e6, 2)} milyon"


@st.cache_data
def oku(ad):
    yol = AGG / f"{ad}.csv"
    return pd.read_csv(yol) if yol.exists() else None


@st.cache_data
def sonuc_oku(ad):
    yol = SONUC / ad
    return pd.read_csv(yol) if yol.exists() else None


@st.cache_data
def md_tablo(dosya, ilk_sutun):
    """docs/<dosya> icinde basligi ilk_sutun ile baslayan markdown tablosunu DataFrame olarak dondurur.
    1. Kisinin kodunu degistirmemek icin sonuclarini dogrudan markdown raporlarindan okuyoruz."""
    yol = DOCS / dosya
    if not yol.exists():
        return None
    satirlar = yol.read_text(encoding="utf-8").splitlines()
    for i, satir in enumerate(satirlar):
        hucreler = [h.strip() for h in satir.strip().strip("|").split("|")]
        if satir.startswith("|") and hucreler[0] == ilk_sutun:
            veri = []
            for s_ in satirlar[i + 2:]:
                if not s_.startswith("|"):
                    break
                veri.append([h.strip().strip("*") for h in s_.strip().strip("|").split("|")])
            return pd.DataFrame(veri, columns=hucreler)
    return None


def sayi(x):
    """'11,077,196' gibi metinleri sayiya cevirir."""
    return pd.to_numeric(str(x).replace(",", "").replace("x", ""), errors="coerce")


def stil(fig, yukseklik=360, legend=True):
    """Tum grafiklere ayni sade gorunum (seffaf zemin: kartin beyazi gorunur, Turkce sayi bicimi)."""
    fig.update_layout(
        template="plotly_white", height=yukseklik, separators=",.",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=4, r=16, t=34 if legend else 10, b=8),
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=13, color=METIN_IKINCIL),
        hoverlabel=dict(bgcolor="white", bordercolor=KENARLIK,
                        font=dict(family="Inter, sans-serif", size=13, color=METIN)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="",
                    font=dict(size=13, color=METIN_IKINCIL)),
        showlegend=legend, barcornerradius=4, bargap=0.28,
    )
    fig.update_xaxes(showgrid=False, linecolor=KENARLIK, tickfont=dict(color=METIN_SOLUK),
                     title_font=dict(size=12, color=METIN_SOLUK))
    fig.update_yaxes(gridcolor="#EFE9E1", zeroline=False, tickfont=dict(color=METIN_SOLUK),
                     title_font=dict(size=12, color=METIN_SOLUK))
    for eksen in ("xaxis", "yaxis"):
        ax = fig.layout[eksen]
        if ax.type in (None, "-", "linear") and ax.tickvals is None and not ax.tickformat:
            ax.tickformat = ",~r"
    fig.update_coloraxes(colorbar_tickformat=",~r")
    # Cubuk disindaki etiketler kesilmesin: deger ekseninde %18 bosluk birak
    try:
        for yon, eksen in (("h", "xaxis"), ("v", "yaxis")):
            cubuklar = [t for t in fig.data if t.type == "bar" and (t.orientation or "v") == yon
                        and t.textposition == "outside"]
            ax = fig.layout[eksen]
            if cubuklar and ax.range is None and ax.type != "log":
                degerler = pd.concat([pd.Series(t.x if yon == "h" else t.y, dtype="float") for t in cubuklar])
                if degerler.max() > 0:
                    ax.range = [0, degerler.max() * 1.18]
    except (TypeError, ValueError):
        pass
    return fig


def ciz(fig):
    st.plotly_chart(fig, config={"displayModeBar": False})


_kart_sayaci = [0]


def kart(baslik=None, alt=None):
    """Beyaz, ince cizgili, yuvarlak kose kart. `with kart("Baslik", "alt yazi"):`"""
    _kart_sayaci[0] += 1
    c = st.container(key=f"kart_{_kart_sayaci[0]}")
    if baslik:
        alt_html = f"<p>{alt}</p>" if alt else ""
        c.markdown(f"<div class='pp-kart-baslik'><h3>{baslik}</h3>{alt_html}</div>", unsafe_allow_html=True)
    return c


def yorum(metin, etiket="Yorum"):
    st.markdown(f"<div class='pp-yorum'><span class='pp-yorum-etiket'>{etiket}</span>{metin}</div>",
                unsafe_allow_html=True)


def sayaclar(liste):
    """liste: [(deger, etiket, alt_yazi_veya_None, ton)]  ton: '' / 'vurgu' / 'kirmizi'"""
    html = "".join(
        f"<div class='pp-sayac {ton}'><span class='pp-sayac-etiket'>{etiket}</span>"
        f"<span class='pp-sayac-deger' title='{deger}'>{deger}</span>"
        + (f"<span class='pp-sayac-alt'>{alt}</span>" if alt else "") + "</div>"
        for deger, etiket, alt, ton in liste)
    st.markdown(f"<div class='pp-sayaclar'>{html}</div>", unsafe_allow_html=True)


def sayfa_basligi(ust, baslik, giris):
    st.markdown(f"<div class='pp-sayfa-baslik'><p class='pp-ust'>{ust}</p><h1>{baslik}</h1>"
                f"<p class='pp-giris'>{giris}</p></div>", unsafe_allow_html=True)


def not_kutusu(metin):
    st.markdown(f"<div class='pp-not'><div>{metin}</div></div>", unsafe_allow_html=True)


def eksik(dosya, komut):
    not_kutusu(f"<b>Veri eksik:</b> <code>{dosya}</code> bulunamadı. Proje klasöründe <code>{komut}</code> "
               "çalıştırıp sayfayı yenileyin.")


def tek_secim(etiket, secenekler, varsayilan, anahtar, **kw):
    """Segmented control; kullanici secimi kaldirirsa varsayilana doner."""
    v = st.segmented_control(etiket, secenekler, default=varsayilan, key=anahtar, **kw)
    return v if v is not None else varsayilan


def indir(df, dosya_adi, etiket="Tabloyu indir (CSV)"):
    st.download_button(etiket, df.to_csv(index=False).encode("utf-8-sig"), file_name=dosya_adi, mime="text/csv",
                       icon=":material/download:")


def alt_bilgi():
    st.markdown("<div class='pp-alt'>Veri: NYC Taksi ve Limuzin Komisyonu (TLC) Trip Record Data, Ocak–Mart 2026 · "
                "Hesaplama: PySpark · Büyük Veri Analitiği projesi</div>", unsafe_allow_html=True)


def md_oku(dosya):
    yol = DOCS / dosya
    return yol.read_text(encoding="utf-8") if yol.exists() else None


def md_goster(metin, klasor=DOCS):
    """Markdown'i gosterir; icindeki ![](...) resimlerini st.image ile cizer."""
    parcalar = re.split(r"!\[[^\]]*\]\(([^)]+)\)", metin)
    for i, parca in enumerate(parcalar):
        if i % 2 == 0:
            if parca.strip():
                st.markdown(parca)
        else:
            yol = (klasor / parca).resolve()
            if yol.exists():
                st.image(str(yol))


@st.cache_data
def sorulari_oku():
    sorular = []
    for dosya in sorted(SORULAR.glob("kisi*_sorular.md")):
        kisi = re.search(r"kisi(\d)", dosya.name).group(1)
        for blok in dosya.read_text(encoding="utf-8").split("\n---"):
            m = re.search(r"SORU\s*(\d+):\s*(.*?)\n\s*\n(.*?)CEVAP:\s*([A-E])", blok, re.S)
            if not m:
                continue
            secenekler = re.findall(r"^([A-E])\)\s*(.+)$", m.group(3), re.M)
            if len(secenekler) < 2:
                continue
            sorular.append({"kisi": kisi, "no": int(m.group(1)), "metin": " ".join(m.group(2).split()),
                            "secenekler": secenekler, "cevap": m.group(4)})
    return sorular


# ---------------- Veri ----------------
genel_df = oku("genel_ozet")
if genel_df is None:
    sayfa_basligi("NYC Taksi · Kurulum", "Analiz sonuçları bulunamadı",
                  "Dashboard, analiz scriptlerinin ürettiği küçük sonuç dosyalarını okur.")
    not_kutusu("Proje klasöründe önce <code>python src/aggregations.py</code> çalıştırın, sonra sayfayı yenileyin. "
               "Dashboard'u her zaman proje ana klasöründen başlatın: <code>streamlit run dashboard/app.py</code>")
    st.stop()
genel = genel_df.iloc[0]

saatlik = oku("saatlik")
if saatlik is not None:
    saatlik = saatlik.copy()
    saatlik["gun_tipi"] = saatlik["gun_tipi"].replace({"Hafta ici": "Hafta içi"})
    saatlik["saat"] = saatlik["pickup_hour"].map(lambda h: f"{h:02d}:00")
binis = oku("binis_bolgeleri")
odeme = oku("odeme_turu")
if odeme is not None:
    odeme = odeme.copy()
    odeme["odeme"] = odeme["payment_type"].map(ODEME_ADLARI).fillna(odeme["payment_type"].astype(str))
    odeme["pay"] = odeme["yolculuk"] / odeme["yolculuk"].sum() * 100
ps = sonuc_oku("pandas_spark_benchmark.csv")
model = sonuc_oku("model_sonuclari.csv")

# ---------------- Sol menu ----------------
SAYFALAR = {
    "Özet": "space_dashboard",
    "Veri ve temizlik": "cleaning_services",
    "Zaman analizi": "schedule",
    "Bölge analizi": "location_on",
    "Ödeme analizi": "credit_card",
    "Performans": "speed",
    "Süre tahmini": "model_training",
    "Proje dokümanları": "description",
    "Sınav soruları": "quiz",
}
with st.sidebar:
    st.markdown(
        "<div class='pp-logo'><svg viewBox='0 0 24 24'><path d='M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9"
        "C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4"
        "c0 .6.4 1 1 1h2'/><circle cx='7' cy='17' r='2'/><path d='M9 17h6'/><circle cx='17' cy='17' r='2'/></svg>"
        "NYC Taksi Analizi</div><div class='pp-logo-alt'>Şehir içi hareket örüntüleri</div>"
        "<div class='pp-menu-baslik'>Bölümler</div>", unsafe_allow_html=True)
    sayfa = st.radio("Bölüm", list(SAYFALAR), label_visibility="collapsed",
                     format_func=lambda s: f":material/{SAYFALAR[s]}: {s}")
    st.markdown("<div class='pp-yan-alt'>Veri: NYC TLC, Ocak–Mart 2026<br>"
                f"{milyon(genel['toplam_yolculuk'])} yolculuk</div>", unsafe_allow_html=True)


# =====================================================================
# OZET
# =====================================================================
if sayfa == "Özet":
    sayfa_basligi("Genel bakış", "New York sarı taksi yolculukları",
                  f"Ocak–Mart 2026 arasındaki {milyon(genel['toplam_yolculuk'])} yolculuk PySpark ile analiz edildi. "
                  "Bu sayfa ana sonuçları özetler; her başlığın ayrıntısı soldaki bölümlerde.")
    sayaclar([
        (kisa(genel["toplam_yolculuk"]), "Analiz edilen yolculuk", f"milyon · {tr(genel['gun_sayisi'])} gün", "vurgu"),
        (tr(genel["toplam_yolculuk"] / genel["gun_sayisi"]), "Günde ortalama yolculuk", None, ""),
        (f"{tr(genel['ort_ucret'], 2)} $", "Ortalama ücret", "ekler ve bahşiş hariç", ""),
        (f"{tr(genel['ort_mesafe_mil'] * MIL_KM, 1)} km", "Ortalama mesafe", None, ""),
        (f"{tr(genel['ort_sure_dk'], 0)} dk", "Ortalama süre", None, ""),
    ])
    st.write("")

    sol, sag = st.columns([1.35, 1])
    if saatlik is not None:
        hi = saatlik[saatlik["gun_tipi"] == "Hafta içi"]
        z = hi.loc[hi["gunluk_ort_yolculuk"].idxmax()]
        d = hi.loc[hi["gunluk_ort_yolculuk"].idxmin()]
        with sol:
            with kart("Gün içinde talep", "Saate göre günde ortalama yolculuk"):
                fig = px.line(saatlik, x="saat", y="gunluk_ort_yolculuk", color="gun_tipi",
                              color_discrete_map=GUN_TIPI_RENK, custom_data=["gun_tipi"])
                fig.update_traces(line_width=2.5,
                                  hovertemplate="%{customdata[0]}, %{x}<br><b>%{y:,.0f}</b> yolculuk/gün<extra></extra>")
                fig.update_xaxes(title="", tickvals=SAATLER[::3])
                fig.update_yaxes(title="")
                ciz(stil(fig, 270))
    if binis is not None:
        pay = binis.groupby("PU_Borough")["yolculuk"].sum().sort_values()
        oran = pay / pay.sum() * 100
        man = oran.get("Manhattan", 0)
        with sag:
            with kart("İlçelere göre biniş", "Tüm binişlerin yüzdesi"):
                pdf = oran.reset_index().rename(columns={"yolculuk": "oran"})
                pdf["etiket"] = pdf["oran"].map(lambda v: "%" + tr(v, 1))
                pdf["renk"] = pdf["PU_Borough"].map(lambda b: YESIL if b == "Manhattan" else GRI_ACIK)
                fig = go.Figure(go.Bar(x=pdf["oran"], y=pdf["PU_Borough"], orientation="h", text=pdf["etiket"],
                                       marker_color=pdf["renk"], textposition="outside", cliponaxis=False,
                                       hovertemplate="%{y}: %{text}<extra></extra>"))
                fig.update_xaxes(title="", showticklabels=False, range=[0, 115])
                fig.update_yaxes(title="")
                ciz(stil(fig, 270, legend=False))

    # Ana bulgular: hepsi veriden hesaplaniyor
    bulgular = []
    if saatlik is not None:
        bulgular.append(f"Talep hafta içi <b>{saat_de(z['saat'])}</b> zirve yapıyor (günde {tr(z['gunluk_ort_yolculuk'])} "
                        f"yolculuk), {saat_de(d['saat'])} ise {tr(d['gunluk_ort_yolculuk'])} yolculuğa düşüyor."
                        "<small>Zaman analizi</small>")
    if binis is not None:
        bulgular.append(f"Binişlerin <b>{yuzde(man)}</b> Manhattan'da. Sarı taksi esas olarak Manhattan'a hizmet "
                        f"veriyor; en yoğun bölge {binis.iloc[0]['PU_Zone']}.<small>Bölge analizi</small>")
    if odeme is not None:
        kartla = odeme[odeme["payment_type"] == 1]
        if len(kartla):
            bulgular.append(f"Yolculukların <b>{yuzde(kartla.iloc[0]['pay'])}</b> kartla ödeniyor. Kartla ödeyenlerin "
                            f"{yuzde(kartla.iloc[0]['bahsis_veren_yuzde'])} bahşiş veriyor; nakitte bahşiş sıfır "
                            "görünüyor çünkü nakit bahşiş sisteme kaydedilmiyor.<small>Ödeme analizi</small>")
    hv0 = oku("havalimani")
    if hv0 is not None and len(hv0) >= 2:
        s_ = hv0[hv0["yolculuk_tipi"] == "Sehir ici"]
        h_ = hv0[hv0["yolculuk_tipi"] == "Havalimanindan binis"]
        if len(s_) and len(h_):
            bulgular.append(f"Havalimanı yolculuğu şehir içinden <b>{tr(h_.iloc[0]['ort_ucret'] / s_.iloc[0]['ort_ucret'], 0)} "
                            f"kat</b> pahalı ama {tr(h_.iloc[0]['ort_hiz_mph'] / s_.iloc[0]['ort_hiz_mph'], 1)} kat hızlı; "
                            "km başına daha ucuz.<small>Ödeme analizi</small>")
    if model is not None:
        bulgular.append(f"Yolculuk süresi binişte bilinen bilgilerle ortalama <b>± {tr(model['MAE'].min(), 1)} dakika</b> "
                        "hatayla tahmin edilebiliyor.<small>Süre tahmini</small>")
    if bulgular:
        with kart("Öne çıkan bulgular"):
            st.markdown("<ol class='pp-bulgular'>" + "".join(f"<li><div>{b}</div></li>" for b in bulgular) + "</ol>",
                        unsafe_allow_html=True)

    # Arastirma sorusu: sayfanin en altinda
    sayilar = ""
    if ps is not None:
        p_ = ps.copy()
        cokme = p_[p_["durum"] != "tamam"].groupby("yontem")["satir"].min()
        sp_ = p_[(p_["yontem"] == "spark") & (p_["durum"] == "tamam")]
        if "pandas_tum" in cokme.index:
            sayilar += f"<div><b>{milyon(cokme['pandas_tum'])}</b>pandas'ın belleğe sığmadığı boyut</div>"
        if len(sp_):
            sayilar += f"<div><b>{milyon(sp_['satir'].max())}</b>Spark'ın sorunsuz işlediği boyut</div>"
    sayilar += f"<div><b>{KULLANILABILIR_RAM_GB} GB</b>test bilgisayarının kullanılabilir belleği</div>"
    st.markdown(
        "<div class='pp-soru'><p class='pp-ust'>Araştırma sorusu</p>"
        "<h3>Veri büyüdükçe klasik analiz yaklaşımı ne zaman yetersiz kalıyor?</h3>"
        "<p><b>Veri tek bir bilgisayarın belleğine sığdığı sürece klasik yaklaşım (pandas) hem daha basit hem daha "
        "hızlı.</b> Spark'ın her işte ödediği sabit bir başlatma ve planlama maliyeti var; küçük veride bu maliyet işin "
        "kendisinden büyük.</p>"
        "<p>Veri belleği aştığı anda pandas yavaşlamıyor, tamamen çalışamıyor. Spark ise veriyi parça parça işlediği "
        "için aynı bilgisayarda çok daha büyük veriyi işleyebiliyor. Bizim donanımımızda bu sınır 20–60 milyon satır "
        "arasında; bu da yaklaşık 6–17 aylık New York taksi verisine karşılık geliyor.</p>"
        f"<div class='pp-soru-sayilar'>{sayilar}</div></div>", unsafe_allow_html=True)


# =====================================================================
# VERI VE TEMIZLIK (1. Kisi)
# =====================================================================
elif sayfa == "Veri ve temizlik":
    sayfa_basligi("1. Kişi · Veri hazırlama", "Veri ve temizlik",
                  "Ham veri NYC Taksi ve Limuzin Komisyonu'ndan indirildi. Taksimetreden otomatik gelen kayıtlarda "
                  "makine kaynaklı hatalar olduğu için veri, sırayla uygulanan kurallarla temizlendi.")

    kurallar = md_tablo("temizlik_raporu.md", "#")
    sozluk = md_tablo("veri_sozlugu.md", "Sutun")
    if kurallar is not None:
        kurallar = kurallar.copy()
        kurallar["sira"] = kurallar["#"].map(sayi)
        kurallar["silinen"] = kurallar["Sirali silinen"].map(sayi).fillna(0)
        kurallar["tek"] = kurallar["Tek basina"].map(sayi)
        kurallar["kalan"] = kurallar["Kalan"].map(sayi)
        ham = int(kurallar["kalan"].iloc[0] + kurallar["silinen"].iloc[0])
        temiz = int(kurallar["kalan"].iloc[-1])
        sayaclar([
            (kisa(ham), "Ham veri", "milyon satır, 3 ay", ""),
            (kisa(temiz), "Temiz veri", "milyon satır, analizde kullanılan", "vurgu"),
            (tr(ham - temiz), "Silinen satır", f"verinin {yuzde((ham - temiz) / ham * 100, 2)}", ""),
            ("20 → 30", "Sütun sayısı", "10 sütun türetildi", ""),
        ])
    st.write("")

    sek = st.tabs(["Temizlik adımları", "Veri sözlüğü", "Dosya boyutları", "Benchmark veri setleri"])

    with sek[0]:
        if kurallar is None:
            eksik("docs/temizlik_raporu.md", "python src/temizle.py")
        else:
            sol, sag = st.columns([1.5, 1])
            with sol:
                with kart("Her kural kaç satır sildi?", "Kurallar yukarıdan aşağı sırayla uygulandı"):
                    k_ = kurallar[kurallar["silinen"] > 0].copy()
                    k_["ad"] = k_["Kural"].map(lambda k: KURAL_ACIKLAMA.get(k, (k, ""))[0])
                    secili_kural = st.selectbox("Ayrıntısını görmek istediğiniz kural",
                                                kurallar["Kural"].tolist(), index=1,
                                                format_func=lambda k: KURAL_ACIKLAMA.get(k, (k, ""))[0])
                    k_["renk"] = k_["Kural"].map(lambda k: YESIL if k == secili_kural else GRI_ACIK)
                    k_ = k_.iloc[::-1]
                    fig = go.Figure(go.Bar(x=k_["silinen"], y=k_["ad"], orientation="h", marker_color=k_["renk"],
                                           text=k_["silinen"], texttemplate="%{text:,.0f}", textposition="outside",
                                           cliponaxis=False, hovertemplate="%{y}<br>%{x:,.0f} satır silindi<extra></extra>"))
                    fig.update_xaxes(title="", showticklabels=False)
                    fig.update_yaxes(title="")
                    ciz(stil(fig, 300, legend=False))
            with sag:
                r = kurallar[kurallar["Kural"] == secili_kural].iloc[0]
                ad, aciklama = KURAL_ACIKLAMA.get(secili_kural, (secili_kural, ""))
                tek = "–" if pd.isna(r["tek"]) else tr(r["tek"])
                st.markdown(
                    f"<div class='pp-kural'><p class='pp-ust'>Kural {int(r['sira'])}</p><h4>{ad}</h4><p>{aciklama}</p>"
                    f"<div class='pp-kural-sayilar'><div><b>{tek}</b>tek başına yakalar</div>"
                    f"<div><b>{tr(r['silinen'])}</b>sırayla silinen</div>"
                    f"<div><b>{milyon(r['kalan'])}</b>kalan satır</div></div></div>", unsafe_allow_html=True)
                st.write("")
                yorum("<b>Tek başına</b>: kural tek başına uygulansaydı kaç satır yakalardı. <b>Sırayla silinen</b>: "
                      "önceki kurallardan geçen satırlardan kaçını bu kural sildi. İki sayı farklıysa, o hatalı "
                      "satırların bir kısmı zaten önceki bir kurala takılmış demektir.", "Nasıl okunur")

            metin = md_oku("temizlik_raporu.md") or ""
            def _sayi_bul(desen):
                m = re.search(desen, metin)
                return m.group(1).replace(",", ".") if m else "–"
            n_yolcu = _sayi_bul(r"passenger_count = 0:\*\* ([\d,]+)")
            n_flex = _sayi_bul(r"temiz veride ([\d,]+) satir")
            n_bolge = _sayi_bul(r"Outside of NYC\):\*\* ([\d,]+)")
            st.write("")
            with kart("Silinmeyen ama ayrıca ele alınan durumlar",
                      "Bu satırlar hatalı değil; silinseydi gerçek yolculuklar kaybolurdu"):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"<div class='pp-durum'><span class='sayi'>{n_yolcu}</span>"
                            "<b>Yolcu sayısı 0</b><span>Yolculuk geçerli, sadece sürücü yolcu sayısını girmemiş. Değer "
                            "“bilinmiyor” yapıldı, satır korundu.</span></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='pp-durum'><span class='sayi'>{n_flex}</span>"
                            "<b>Flex Fare yolculukları</b><span>5 sütun boş, ama bu bir hata değil: bu ödeme türünde "
                            "taksimetre o alanları göndermiyor. Toptan silmek verinin dörtte birini kaybettirirdi.</span></div>",
                            unsafe_allow_html=True)
                c3.markdown(f"<div class='pp-durum'><span class='sayi'>{n_bolge}</span>"
                            "<b>Bilinmeyen bölge</b><span>Bölge kodu 264/265. Süre, mesafe ve ücret geçerli olduğu için "
                            "korundu; sadece bölge analizinde dışarıda bırakıldı.</span></div>", unsafe_allow_html=True)

            with st.expander("Tüm kurallar ve eşik değerleri (tablo)"):
                tablo = kurallar[["sira", "Kural", "tek", "silinen", "kalan"]].copy()
                tablo["Kural"] = tablo["Kural"].map(lambda k: KURAL_ACIKLAMA.get(k, (k, ""))[0])
                tablo.columns = ["#", "Kural", "Tek başına", "Sırayla silinen", "Kalan"]
                st.dataframe(tablo, hide_index=True)
                indir(tablo, "temizlik_kurallari.csv")

    with sek[1]:
        if sozluk is None:
            eksik("docs/veri_sozlugu.md", "python src/veri_profili.py")
        else:
            with kart("Ham veri sütunları", "Kaynak: NYC TLC veri sözlüğü. Arama kutusuna sütun adı ya da kelime yazın."):
                ara = st.text_input("Sütun ara", placeholder="ör. tip, ücret, bölge", label_visibility="collapsed")
                s_ = sozluk.rename(columns={"Sutun": "Sütun", "Aciklama": "Açıklama", "Bos %": "Boş %"})
                if ara:
                    s_ = s_[s_.apply(lambda r: ara.lower() in " ".join(r.astype(str)).lower(), axis=1)]
                st.dataframe(s_, hide_index=True, height=min(38 * (len(s_) + 1) + 4, 560))
                st.caption(f"{len(s_)} sütun gösteriliyor. Boş % sütunundaki 27,6'lık boşluk rastgele değil; hepsi Flex "
                           "Fare yolculuklarında (bkz. Temizlik adımları).")
            st.write("")
            sol, sag = st.columns(2)
            with sol:
                odeme_kod = md_tablo("veri_sozlugu.md", "Kod")
                with kart("Ödeme türü kodları", "payment_type sütunundaki sayılar kategori, miktar değil"):
                    if odeme_kod is not None:
                        st.dataframe(odeme_kod.rename(columns={"Anlami": "Anlamı"}), hide_index=True)
            with sag:
                metin = md_oku("veri_sozlugu.md") or ""
                with kart("Temizlikte eklenen sütunlar", "Analiz ve model için türetildi"):
                    m = re.search(r"## Temizlikte turetilecek sutunlar\s*\n(.*?)(\n## |\Z)", metin, re.S)
                    if m:
                        satirlar = [s.strip().strip("|").split("|") for s in m.group(1).splitlines()
                                    if s.startswith("|") and not s.startswith("|---")]
                        if len(satirlar) > 1:
                            st.dataframe(pd.DataFrame([[h.strip() for h in s] for s in satirlar[1:]],
                                                      columns=["Sütun", "Hesap", "Neden"]), hide_index=True)
                    st.caption("Ayrıca bölge kodları zone tablosuyla birleştirilerek (join) PU/DO_Borough ve "
                               "PU/DO_Zone sütunları eklendi.")

    with sek[2]:
        boyut = md_tablo("boyut_analizi.md", "Dosya")
        tahmin = md_tablo("boyut_analizi.md", "Veri")
        if boyut is None:
            eksik("docs/boyut_analizi.md", "python src/boyut_analizi.py")
        else:
            b_ = boyut[~boyut["Dosya"].str.contains("Toplam")].copy()
            b_["ay"] = b_["Dosya"].str.extract(r"(\d{4}-\d{2})")[0].map(
                lambda a: {"01": "Ocak", "02": "Şubat", "03": "Mart"}.get(str(a)[-2:], a))
            uzun = b_.melt(id_vars="ay", value_vars=["Parquet (MB)", "CSV (MB)", "Pandas RAM (MB)"],
                           var_name="hal", value_name="mb")
            uzun["mb"] = uzun["mb"].map(sayi)
            uzun["hal"] = uzun["hal"].map({"Parquet (MB)": "Diskte Parquet", "CSV (MB)": "Diskte CSV",
                                           "Pandas RAM (MB)": "Bellekte (pandas)"})
            sol, sag = st.columns([1.4, 1])
            with sol:
                with kart("Aynı veri, üç farklı boyut", "Her ayın ham verisi, MB"):
                    fig = px.bar(uzun, x="ay", y="mb", color="hal", barmode="group", text="mb",
                                 color_discrete_map={"Diskte Parquet": YESIL, "Diskte CSV": TURUNCU,
                                                     "Bellekte (pandas)": GRI})
                    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False,
                                      hovertemplate="%{x} · %{fullData.name}<br>%{y:,.0f} MB<extra></extra>")
                    fig.update_xaxes(title="")
                    fig.update_yaxes(title="")
                    ciz(stil(fig, 320))
                    yorum("Parquet veriyi sütun sütun ve sıkıştırarak saklıyor; CSV her sayıyı düz metin olarak yazıyor "
                          "(yaklaşık 6 kat büyük). pandas veriyi belleğe aldığında sıkıştırmayı açtığı için Parquet "
                          "dosyasının yaklaşık 10 katı yer kaplıyor.")
            with sag:
                with kart("Veri büyüdükçe pandas ne kadar bellek ister?", "Satır başına ~183 bayt ile tahmin"):
                    if tahmin is not None:
                        st.dataframe(tahmin.rename(columns={"Satir (yaklasik)": "Satır (yaklaşık)"}), hide_index=True)
                    yorum(f"Test bilgisayarında kullanılabilir bellek yaklaşık <b>{KULLANILABILIR_RAM_GB} GB</b>. "
                          "Bir yıllık veri bile bu sınırı zorluyor.")

    with sek[3]:
        orn = md_tablo("orneklemler.md", "Veri seti")
        with kart("Benchmark için hazırlanan veri setleri",
                  "Aylar birikimli eklendi: küçük set büyüğün içinde. Performans bölümündeki ölçümler bunlarla yapıldı."):
            if orn is not None:
                st.dataframe(orn.rename(columns={"Satir": "Satır"}), hide_index=True)
            else:
                eksik("docs/orneklemler.md", "python src/orneklem_olustur.py")


# =====================================================================
# ZAMAN ANALIZI
# =====================================================================
elif sayfa == "Zaman analizi":
    sayfa_basligi("2. Kişi · Zaman analizi", "Taksiye ne zaman biniliyor?",
                  "Saatlik değerler gün başına ortalamadır; böylece 5 günlük hafta içi ile 2 günlük hafta sonu adil "
                  "karşılaştırılır. Aşağıdan ölçütü ve karşılaştırmayı seçin.")
    if saatlik is None:
        eksik("results/agg/saatlik.csv", "python src/aggregations.py")
        st.stop()
    gs = oku("gun_saat")
    if gs is not None:
        gs = gs.copy()
        gs["gun"] = gs["pickup_dayofweek"].map(GUN_ADLARI)
        gs["saat"] = gs["pickup_hour"].map(lambda h: f"{h:02d}:00")

    OLCUT = {
        "Yolculuk sayısı": ("gunluk_ort_yolculuk", 1, "yolculuk/gün", 0),
        "Ortalama ücret": ("ort_ucret", 1, "$", 2),
        "Ortalama mesafe": ("ort_mesafe_mil", MIL_KM, "km", 1),
        "Ortalama süre": ("ort_sure_dk", 1, "dk", 1),
        "Ortalama hız": ("ort_hiz_mph", MIL_KM, "km/sa", 1),
    }
    olcut = tek_secim("Ölçüt", list(OLCUT), "Yolculuk sayısı", "zaman_olcut")
    mod = tek_secim("Karşılaştırma", ["Hafta içi / sonu", "Tek gün"], "Hafta içi / sonu", "zaman_mod")
    sut, carpan, birim, ond = OLCUT[olcut]

    if mod == "Tek gün":
        gun = st.selectbox("Gün", GUN_SIRASI, index=4)
        if gs is None or sut not in gs.columns:
            not_kutusu("Gün gün karşılaştırma için analizin yeni sürümü gerekiyor. Proje klasöründe "
                       "<code>python src/aggregations.py</code> komutunu bir kez daha çalıştırın.")
            veri = saatlik.assign(seri=saatlik["gun_tipi"])
        else:
            gun_veri = gs[gs["gun"] == gun].assign(seri=gun)
            # Tum gunlerin ortalamasi: her gunun degeri gun sayisiyla agirliklandirilir
            ort = (gs.assign(_agirlik=gs[sut] * gs["gun_sayisi"])
                   .groupby(["pickup_hour", "saat"], as_index=False)[["_agirlik", "gun_sayisi"]].sum())
            ort[sut] = ort["_agirlik"] / ort["gun_sayisi"]
            ort = ort.assign(seri="Tüm günlerin ortalaması")
            veri = pd.concat([ort, gun_veri], ignore_index=True)
        renkler = {"Tüm günlerin ortalaması": GRI, "Hafta içi": YESIL, "Hafta sonu": TURUNCU}
        renkler.setdefault(gun, YESIL)
    else:
        veri = saatlik.assign(seri=saatlik["gun_tipi"])
        renkler = GUN_TIPI_RENK
    veri = veri.copy()
    veri["deger"] = veri[sut] * carpan

    ana = veri[veri["seri"] != "Tüm günlerin ortalaması"]
    ilk = ana[ana["seri"] == ana["seri"].iloc[0]]
    ust_ = ilk.loc[ilk["deger"].idxmax()]
    alt_ = ilk.loc[ilk["deger"].idxmin()]
    with kart(f"{olcut}, saate göre", f"{ust_['seri']}: en yüksek {saat_de(ust_['saat'])} "
              f"({tr(ust_['deger'], ond)} {birim}), en düşük {saat_de(alt_['saat'])} ({tr(alt_['deger'], ond)} {birim})"):
        fig = px.line(veri, x="saat", y="deger", color="seri", markers=True, color_discrete_map=renkler,
                      custom_data=["seri"])
        fig.update_traces(line_width=2.5, marker_size=6,
                          hovertemplate="%{customdata[0]}, %{x}<br><b>%{y:,." + str(ond) + "f}</b> " + birim
                                        + "<extra></extra>")
        for tr_ in fig.data:
            if tr_.name == "Tüm günlerin ortalaması":
                tr_.update(line=dict(dash="dot", width=2), marker_size=0)
        fig.update_xaxes(title="", tickvals=SAATLER[::2])
        fig.update_yaxes(title=birim, rangemode="tozero")
        ciz(stil(fig, 360))
        hi = saatlik[saatlik["gun_tipi"] == "Hafta içi"].set_index("pickup_hour")
        hs = saatlik[saatlik["gun_tipi"] == "Hafta sonu"].set_index("pickup_hour")
        if olcut == "Yolculuk sayısı":
            m = (f"Yoğun saat ile sakin saat arasında <b>{tr(ust_['deger'] / alt_['deger'], 0)} kat</b> fark var. ")
            if 8 in hi.index and hs.loc[8, sut] > 0 and hi.loc[8, sut] / hs.loc[8, sut] > 1.3:
                m += (f"Sabah 08:00'de hafta içi talebi hafta sonunun <b>{tr(hi.loc[8, sut] / hs.loc[8, sut], 1)} katı</b>: "
                      "sabahı işe gidiş belirliyor. ")
            if 1 in hi.index and hi.loc[1, sut] > 0 and hs.loc[1, sut] / hi.loc[1, sut] > 1.2:
                m += (f"Gece 01:00'de ise tersine, hafta sonu talebi hafta içinin <b>{tr(hs.loc[1, sut] / hi.loc[1, sut], 1)} "
                      "katı</b>: hafta sonu geceleri sosyal hayat yolculuk üretiyor.")
        elif olcut == "Ortalama hız":
            m = ("Gece yollar boşken taksiler gündüzün iki katından hızlı gidiyor. En yavaş saat ile en yoğun talep saati "
                 "aynı olmak zorunda değil: yol trafiğini taksilerin yanında ticari araçlar ve servisler de oluşturuyor.")
        elif olcut == "Ortalama ücret":
            m = ("Gece ve sabahın erken saatlerinde kısa şehir içi yolculuklar azalıyor; havalimanı gibi uzun "
                 "yolculukların payı arttığı için ortalama ücret yükseliyor.")
        elif olcut == "Ortalama mesafe":
            m = ("Mesafe sabah erken saatlerde en uzun: bu saatlerde yolculukların önemli kısmı havalimanına ya da "
                 "şehir dışına gidiyor.")
        else:
            m = ("Süre, mesafe ile trafiğin birleşimi: gündüz kısa mesafeler bile trafik yüzünden uzun sürüyor.")
        yorum(m)

    if gs is not None:
        isi_sut = sut if sut in gs.columns else "gunluk_ort_yolculuk"
        isi_olcut = olcut if sut in gs.columns else "Yolculuk sayısı"
        isi_veri = gs.assign(deger=gs[isi_sut] * (carpan if isi_sut == sut else 1))
        en = isi_veri.loc[isi_veri["deger"].idxmax()]
        with kart(f"Haftanın günü ve saat: {isi_olcut.lower()}",
                  f"Koyu renk = yüksek. En yüksek hücre: {en['gun']} {en['saat']}"):
            isi = isi_veri.pivot(index="gun", columns="pickup_hour", values="deger").reindex(GUN_SIRASI)
            isi.columns = [f"{c:02d}" for c in isi.columns]
            fig = px.imshow(isi, aspect="auto", color_continuous_scale=SIRALI)
            fig.update_traces(xgap=2, ygap=2,
                              hovertemplate="%{y} %{x}:00<br><b>%{z:,.1f}</b><extra></extra>")
            fig.update_xaxes(title="", side="bottom")
            fig.update_yaxes(title="")
            fig.update_layout(coloraxis_colorbar=dict(title="", thickness=10, outlinewidth=0))
            ciz(stil(fig, 300, legend=False))
            if isi_sut != sut:
                st.caption("Bu ölçüt için gün × saat verisi yok; yolculuk sayısı gösteriliyor. "
                           "python src/aggregations.py tekrar çalıştırılınca güncellenir.")

    gunluk = oku("gunluk")
    if gunluk is not None:
        gunluk = gunluk.copy()
        gunluk["pickup_date"] = pd.to_datetime(gunluk["pickup_date"])
        ilk_g, son_g = gunluk["pickup_date"].min().date(), gunluk["pickup_date"].max().date()
        with kart("Günlük seyir", "Tarih aralığını daraltarak belirli haftalara yakından bakabilirsiniz"):
            c1, c2 = st.columns([2, 1])
            with c1:
                aralik = st.slider("Tarih aralığı", min_value=ilk_g, max_value=son_g, value=(ilk_g, son_g),
                                   format="DD.MM.YYYY")
            with c2:
                g_olcut = tek_secim("Ölçüt", ["Yolculuk", "Ortalama ücret"], "Yolculuk", "gunluk_olcut")
            g_ = gunluk[(gunluk["pickup_date"].dt.date >= aralik[0]) & (gunluk["pickup_date"].dt.date <= aralik[1])]
            gsut = "yolculuk" if g_olcut == "Yolculuk" else "ort_ucret"
            fig = go.Figure()
            fig.add_bar(x=g_["pickup_date"], y=g_[gsut], name="Günlük", marker_color="#CFE0DC",
                        hovertemplate="%{x|%d.%m.%Y}<br>%{y:,.2f}<extra></extra>" if gsut == "ort_ucret"
                        else "%{x|%d.%m.%Y}<br>%{y:,.0f} yolculuk<extra></extra>")
            if gsut == "yolculuk":
                fig.add_scatter(x=g_["pickup_date"], y=g_["ort_7gun"], name="7 günlük ortalama", mode="lines",
                                line=dict(color=ANA, width=2.5),
                                hovertemplate="%{x|%d.%m.%Y}<br>7 günlük ort.: %{y:,.0f}<extra></extra>")
            fig.update_xaxes(title="", tickformat="%d.%m")
            fig.update_yaxes(title="")
            ciz(stil(fig, 320))
            en_az = gunluk.loc[gunluk["yolculuk"].idxmin()]
            m = (f"En sakin gün <b>{en_az['pickup_date']:%d.%m.%Y}</b> ({tr(en_az['yolculuk'])} yolculuk). ")
            if str(en_az["pickup_date"].date()) == "2026-02-23":
                m += ("O gün New York'ta büyük bir kar fırtınası vardı: Central Park'a 48 cm kar yağdı, acil durum ilan "
                      "edildi, okullar kapatıldı. ")
            m += ("Koyu çizgi Spark'ın window fonksiyonuyla hesaplanan 7 günlük hareketli ortalama; haftalık iniş "
                  "çıkışları düzleştirip genel eğilimi gösteriyor.")
            yorum(m)


# =====================================================================
# BOLGE ANALIZI
# =====================================================================
elif sayfa == "Bölge analizi":
    sayfa_basligi("2. Kişi · Bölge analizi", "Taksiler nereden nereye gidiyor?",
                  "New York 5 ilçe (borough) ve 263 bölgeden (zone) oluşuyor. Filtrelerle ilçe seçebilir, bölgeleri "
                  "farklı ölçütlere göre sıralayabilir ve sonucu indirebilirsiniz.")
    if binis is None:
        eksik("results/agg/binis_bolgeleri.csv", "python src/aggregations.py")
        st.stop()
    inis = oku("inis_bolgeleri")

    with kart("Filtreler"):
        f1, f2, f3, f4 = st.columns([0.9, 1.7, 1.1, 1.5])
        with f1:
            yon = tek_secim("Yön", ["Biniş", "İniş"], "Biniş", "bolge_yon")
        kaynak = binis.rename(columns={"PU_Borough": "İlçe", "PU_Zone": "Bölge"})
        if yon == "İniş":
            if inis is None:
                kaynak = None
            else:
                kaynak = inis.rename(columns={"DO_Borough": "İlçe", "DO_Zone": "Bölge"})
        ilceler = sorted(binis["PU_Borough"].dropna().unique().tolist())
        with f2:
            sec_ilce = st.multiselect("İlçe", ilceler, default=ilceler, placeholder="İlçe seçin")
        with f3:
            sirala = st.selectbox("Sırala", ["Yolculuk sayısı", "Ortalama ücret", "Ortalama mesafe"])
        with f4:
            adet = tek_secim("Göster", ["10", "20", "50", "Tümü"], "20", "bolge_adet")
        ara = st.text_input("Bölge ara", placeholder="Bölge adı yazın, ör. Midtown, Airport, Harlem")

    if kaynak is None:
        not_kutusu("İniş bölgeleri için analizin yeni sürümü gerekiyor. Proje klasöründe "
                   "<code>python src/aggregations.py</code> komutunu bir kez daha çalıştırın.")
        st.stop()

    k_ = kaynak[kaynak["İlçe"].isin(sec_ilce)].copy()
    if ara:
        k_ = k_[k_["Bölge"].str.contains(ara, case=False, na=False)]
    k_["mesafe_km"] = k_["ort_mesafe_mil"] * MIL_KM
    sira_sut = {"Yolculuk sayısı": "yolculuk", "Ortalama ücret": "ort_ucret", "Ortalama mesafe": "mesafe_km"}[sirala]
    k_ = k_.sort_values(sira_sut, ascending=False)
    gosterilen = k_ if adet == "Tümü" else k_.head(int(adet))

    toplam_yon = kaynak["yolculuk"].sum()
    pay_ilce = kaynak.groupby("İlçe")["yolculuk"].sum().sort_values(ascending=False) / toplam_yon * 100
    sayaclar([(f"%{tr(v, 1)}", f"{il}", f"{yon.lower()} payı", "vurgu" if il == "Manhattan" else "")
              for il, v in pay_ilce.head(5).items()])
    st.write("")

    if gosterilen.empty:
        not_kutusu("Bu filtrelere uyan bölge yok. İlçe seçimini ya da arama metnini değiştirin.")
    else:
        cizilen = gosterilen.head(50)
        birim = {"yolculuk": "", "ort_ucret": " $", "mesafe_km": " km"}[sira_sut]
        ondalik = {"yolculuk": 0, "ort_ucret": 2, "mesafe_km": 1}[sira_sut]
        with kart(f"{yon} bölgeleri: {sirala.lower()}",
                  f"{len(k_)} bölgeden {len(gosterilen)} tanesi gösteriliyor"
                  + (" (grafikte ilk 50)" if len(gosterilen) > 50 else "")):
            c_ = cizilen.iloc[::-1]
            fig = go.Figure(go.Bar(
                x=c_[sira_sut], y=c_["Bölge"], orientation="h",
                marker_color=[YESIL if i == "Manhattan" else TURUNCU if i == "Queens" else MAVI for i in c_["İlçe"]],
                text=c_[sira_sut].map(lambda v: tr(v, ondalik) + birim), textposition="outside", cliponaxis=False,
                customdata=c_[["İlçe", "yolculuk", "ort_ucret", "mesafe_km"]].values,
                hovertemplate="<b>%{y}</b> (%{customdata[0]})<br>%{customdata[1]:,.0f} yolculuk<br>"
                              "Ort. ücret %{customdata[2]:,.2f} $ · Ort. mesafe %{customdata[3]:,.1f} km<extra></extra>"))
            fig.update_xaxes(title="", showticklabels=False)
            fig.update_yaxes(title="")
            ciz(stil(fig, max(260, len(c_) * 24), legend=False))
            st.markdown("<div style='font-size:13px;color:#646B69'>"
                        f"<span style='color:{YESIL}'>■</span> Manhattan &nbsp; <span style='color:{TURUNCU}'>■</span> "
                        f"Queens &nbsp; <span style='color:{MAVI}'>■</span> diğer ilçeler</div>", unsafe_allow_html=True)
            if yon == "Biniş" and sirala == "Yolculuk sayısı" and len(sec_ilce) == len(ilceler) and not ara:
                yorum(f"Binişlerin {yuzde(pay_ilce.get('Manhattan', 0))} Manhattan'da. Sarı taksi sokakta el kaldırarak "
                      "çevrilen bir hizmet; yaya trafiğinin ve iş/eğlence merkezlerinin yoğun olduğu Manhattan'da işe "
                      "yarıyor. Dış ilçelerde bu talebi yeşil taksiler ve Uber/Lyft karşılıyor. Queens'teki yüksek "
                      "değerler JFK ve LaGuardia havalimanlarından geliyor.")
            elif sirala == "Ortalama ücret":
                yorum("Ortalama ücreti en yüksek bölgeler genelde havalimanları ve şehrin kenarındaki bölgeler: oradan "
                      "binen yolculuklar uzun mesafeli.")
        with st.expander(f"Tablo olarak göster ({len(gosterilen)} bölge)"):
            tablo = gosterilen[["Bölge", "İlçe", "yolculuk", "ort_ucret", "mesafe_km"]].rename(columns={
                "yolculuk": "Yolculuk", "ort_ucret": "Ort. ücret ($)", "mesafe_km": "Ort. mesafe (km)"}).round(2)
            st.dataframe(tablo, hide_index=True)
            indir(tablo, f"{yon.lower()}_bolgeleri.csv")

    st.write("")
    sek = st.tabs(["İlçeler arası hareket", "En sık rotalar", "Saate göre en yoğun bölgeler"])
    with sek[0]:
        im = oku("ilce_matrisi")
        if im is not None:
            im = im[~im["PU_Borough"].isin(["Unknown", "N/A"]) & ~im["DO_Borough"].isin(["Unknown", "N/A"])]
            mat = im.pivot(index="PU_Borough", columns="DO_Borough", values="yolculuk").fillna(0)
            sira = [b for b in pay_ilce.index if b in mat.index] if yon == "Biniş" else list(mat.index)
            mat = mat.reindex(index=sira, columns=[b for b in sira if b in mat.columns]).fillna(0)
            mat_y = mat / mat.values.sum() * 100
            ic = sum(mat_y.loc[b, b] for b in mat_y.index if b in mat_y.columns)
            with kart(f"Yolculukların {yuzde(ic)} aynı ilçe içinde kalıyor",
                      "Satır: biniş ilçesi, sütun: iniş ilçesi. Hücre: tüm yolculukların yüzde kaçı"):
                fig = px.imshow(mat_y, aspect="auto", text_auto=".1f", color_continuous_scale=SIRALI)
                fig.update_traces(xgap=2, ygap=2, hovertemplate="%{y} → %{x}<br>yüzde <b>%{z:,.2f}</b><extra></extra>")
                fig.update_xaxes(title="", side="top")
                fig.update_yaxes(title="")
                fig.update_coloraxes(showscale=False)
                ciz(stil(fig, 330, legend=False))
    with sek[1]:
        rot = oku("top_rotalar")
        if rot is not None:
            with kart("En sık 20 rota", "Bölgeden bölgeye; aramayla belirli bir bölgeyi içeren rotaları bulun"):
                ara_r = st.text_input("Rota ara", placeholder="ör. Upper East Side", key="rota_ara")
                r_ = rot.copy()
                if ara_r:
                    r_ = r_[r_["PU_Zone"].str.contains(ara_r, case=False, na=False)
                            | r_["DO_Zone"].str.contains(ara_r, case=False, na=False)]
                tablo = r_.rename(columns={"PU_Zone": "Biniş", "DO_Zone": "İniş", "yolculuk": "Yolculuk",
                                           "ort_ucret": "Ort. ücret ($)", "ort_sure_dk": "Ort. süre (dk)"})
                st.dataframe(tablo, hide_index=True)
                yorum(f"En sık 10 rotanın ortalama süresi {tr(rot.head(10)['ort_sure_dk'].mean(), 0)} dakika: taksi uzun "
                      "yolların yanında kısa, mahalle içi yolculuklar için de yoğun kullanılıyor.")
    with sek[2]:
        top5 = oku("saatlik_top5_bolge")
        if top5 is not None:
            with kart("Her saatin en yoğun 5 biniş bölgesi", "Spark window fonksiyonu (rank) ile hesaplandı"):
                saat = st.select_slider("Saat", options=list(range(24)), value=8, format_func=lambda h: f"{h:02d}:00")
                secili = top5[top5["pickup_hour"] == saat].sort_values("yolculuk")
                fig = go.Figure(go.Bar(x=secili["yolculuk"], y=secili["PU_Zone"], orientation="h", marker_color=YESIL,
                                       text=secili["yolculuk"], texttemplate="%{text:,.0f}", textposition="outside",
                                       cliponaxis=False, hovertemplate="%{y}<br>%{x:,.0f} biniş<extra></extra>"))
                fig.update_xaxes(title="", showticklabels=False)
                fig.update_yaxes(title="")
                ciz(stil(fig, 230, legend=False))
                yorum("Kaydırıcıyla saati değiştirin: sabah yerleşim bölgeleri ve iş merkezleri, gece eğlence bölgeleri "
                      "ve havalimanları öne çıkıyor.", "İpucu")


# =====================================================================
# ODEME ANALIZI
# =====================================================================
elif sayfa == "Ödeme analizi":
    sayfa_basligi("2. Kişi · Ödeme analizi", "Nasıl ödeniyor?",
                  "Ödeme türlerini seçin; seçtiğiniz türlerin ücret, bahşiş, saat, mesafe ve ilçe dağılımı aşağıda "
                  "açılır ve karşılaştırılır.")
    if odeme is None:
        eksik("results/agg/odeme_turu.csv", "python src/aggregations.py")
        st.stop()

    secenekler = odeme.sort_values("yolculuk", ascending=False)["odeme"].tolist()
    secim = st.pills("Ödeme türü", secenekler, selection_mode="multi",
                     default=[s for s in ["Kredi kartı", "Nakit"] if s in secenekler], key="odeme_sec")

    with kart("Ödeme türlerinin payı", "Tüm yolculukların yüzdesi; seçili türler renkli"):
        o = odeme.sort_values("yolculuk")
        renk = [ODEME_RENK.get(a, GRI) if a in secim else GRI_ACIK for a in o["odeme"]]
        fig = go.Figure(go.Bar(x=o["pay"], y=o["odeme"], orientation="h", marker_color=renk,
                               text=o["pay"].map(lambda v: "%" + tr(v, 1)), textposition="outside", cliponaxis=False,
                               customdata=o["yolculuk"],
                               hovertemplate="%{y}: %{text}<br>%{customdata:,.0f} yolculuk<extra></extra>"))
        fig.update_xaxes(title="", showticklabels=False, range=[0, o["pay"].max() * 1.15])
        fig.update_yaxes(title="")
        ciz(stil(fig, 220, legend=False))

    if not secim:
        not_kutusu("Karşılaştırmak için yukarıdan en az bir ödeme türü seçin.")
    else:
        s_ = odeme[odeme["odeme"].isin(secim)].set_index("odeme").reindex(secim).reset_index()
        renk_map = {a: ODEME_RENK.get(a, GRI) for a in secim}
        with kart("Seçili türlerin karşılaştırması"):
            sutunlar = st.columns(3)
            for col, (sut, baslik, bicim) in zip(sutunlar, [
                    ("ort_ucret", "Ortalama ücret", lambda v: tr(v, 2) + " $"),
                    ("bahsis_orani_yuzde", "Bahşiş / ücret", lambda v: "%" + tr(v, 1)),
                    ("bahsis_veren_yuzde", "Bahşiş kaydedilen yolculuk", lambda v: "%" + tr(v, 0))]):
                with col:
                    st.caption(baslik)
                    fig = go.Figure(go.Bar(x=s_["odeme"], y=s_[sut], marker_color=[renk_map[a] for a in s_["odeme"]],
                                           text=s_[sut].map(bicim), textposition="outside", cliponaxis=False,
                                           hovertemplate="%{x}<br>%{text}<extra></extra>"))
                    fig.update_xaxes(title="")
                    fig.update_yaxes(title="", showticklabels=False, showgrid=False,
                                     range=[0, max(s_[sut].max() * 1.25, 1)])
                    ciz(stil(fig, 230, legend=False))
            notlar = []
            if "Nakit" in secim:
                notlar.append("<b>Nakitte bahşiş sıfır görünüyor, ama bu bir yanılgı.</b> Nakit verilen bahşiş "
                              "taksimetreye girilmiyor; veride hiç yok. Kart ve nakit yolculuklarının ortalama ücreti "
                              "neredeyse aynı olduğuna göre iki grup aynı tür yolculuklar yapıyor; fark verinin nasıl "
                              "toplandığından geliyor. Bahşiş analizinde yalnızca kartla ödenen yolculuklar kullanılmalı.")
            if "Kredi kartı" in secim and "Nakit" not in secim:
                notlar.append("Kartla ödeyenlerin büyük çoğunluğu bahşiş veriyor; kart ekranındaki hazır bahşiş "
                              "seçenekleri (%20, %25, %30) bu oranı yükseltiyor.")
            if "Flex Fare" in secim:
                notlar.append("<b>Flex Fare</b>: ücretin yolculuktan önce belirlendiği, uygulama üzerinden çağrılan "
                              "yolculuklar. Bu kanalda bazı alanlar gönderilmediği için bahşiş de büyük ölçüde kayıtsız.")
            if "Ücretsiz" in secim:
                notlar.append("<b>Ücretsiz</b> (kod 3, “No charge”): taksimetre ücreti hesaplamış ama yolcudan "
                              "alınmamış. Sürücü yanlış rota, şikâyet ya da taksimetre arızası gibi durumlarda ücret "
                              "almamayı seçebiliyor; yarıda iptal edilen yolculuklar da bu koda düşüyor. Çok küçük bir "
                              "grup (%0,2), analiz sonuçlarını etkilemiyor.")
            if "İtirazlı" in secim:
                notlar.append("<b>İtirazlı</b> (kod 4, “Dispute”): yolcunun ücrete itiraz ettiği yolculuklar. "
                              "Bu grup da çok küçük; bahşiş beklendiği gibi yok.")
            yorum(" ".join(notlar) if notlar else "Seçili türlerin ortalama ücret ve bahşiş değerleri yukarıda.")

        od_saat, od_mes, od_ilce = oku("odeme_saat"), oku("odeme_mesafe"), oku("odeme_ilce")
        if od_saat is None or od_mes is None or od_ilce is None:
            not_kutusu("Saat, mesafe ve ilçe kırılımları için analizin yeni sürümü gerekiyor. Proje klasöründe "
                       "<code>python src/aggregations.py</code> komutunu bir kez daha çalıştırın.")
        else:
            def _hazirla(df_):
                df_ = df_.copy()
                df_["odeme"] = df_["payment_type"].map(ODEME_ADLARI)
                df_ = df_[df_["odeme"].isin(secim)]
                df_["pay"] = df_["yolculuk"] / df_.groupby("odeme")["yolculuk"].transform("sum") * 100
                return df_

            with kart("Gün içinde ödeme türleri", "Her türün yolculuklarının saatlere dağılımı (%)"):
                d_ = _hazirla(od_saat)
                d_["saat"] = d_["pickup_hour"].map(lambda h: f"{h:02d}:00")
                fig = px.line(d_, x="saat", y="pay", color="odeme", color_discrete_map=renk_map, markers=True,
                              custom_data=["odeme", "yolculuk"])
                fig.update_traces(line_width=2.5, marker_size=5,
                                  hovertemplate="%{customdata[0]}, %{x}<br>yüzde <b>%{y:,.1f}</b> · "
                                                "%{customdata[1]:,.0f} yolculuk<extra></extra>")
                fig.update_xaxes(title="", tickvals=SAATLER[::2])
                fig.update_yaxes(title="yolculukların %'si")
                ciz(stil(fig, 300))
                yorum("Çizgiler her türün kendi içindeki dağılımı; böylece az kullanılan türler de çok kullanılanlarla "
                      "aynı ölçekte karşılaştırılabiliyor.", "Nasıl okunur")

            sol, sag = st.columns(2)
            with sol:
                with kart("Mesafeye göre", "Her türün yolculuklarının mesafe dilimlerine dağılımı (%)"):
                    d_ = _hazirla(od_mes)
                    d_["dilim"] = pd.Categorical(d_["mesafe_dilimi"].map(MESAFE_KM),
                                                 [MESAFE_KM[m] for m in MESAFE_SIRASI], ordered=True)
                    d_ = d_.sort_values("dilim")
                    fig = px.bar(d_, x="dilim", y="pay", color="odeme", barmode="group", color_discrete_map=renk_map,
                                 custom_data=["odeme"])
                    fig.update_traces(hovertemplate="%{customdata[0]}, %{x}<br>yüzde <b>%{y:,.1f}</b><extra></extra>")
                    fig.update_xaxes(title="")
                    fig.update_yaxes(title="%")
                    ciz(stil(fig, 300))
            with sag:
                with kart("İlçeye göre", "Her türün binişlerinin ilçelere dağılımı (%)"):
                    d_ = _hazirla(od_ilce)
                    d_ = d_[~d_["PU_Borough"].isin(["Unknown", "N/A"])]
                    fig = px.bar(d_, x="PU_Borough", y="pay", color="odeme", barmode="group",
                                 color_discrete_map=renk_map, custom_data=["odeme"],
                                 category_orders={"PU_Borough": ["Manhattan", "Queens", "Brooklyn", "Bronx",
                                                                 "Staten Island", "EWR"]})
                    fig.update_traces(hovertemplate="%{customdata[0]}, %{x}<br>yüzde <b>%{y:,.1f}</b><extra></extra>")
                    fig.update_xaxes(title="")
                    fig.update_yaxes(title="%")
                    ciz(stil(fig, 300))

    st.write("")
    hv = oku("havalimani")
    if hv is not None:
        hv = hv.copy()
        hv["yolculuk_tipi"] = hv["yolculuk_tipi"].replace({
            "Sehir ici": "Şehir içi", "Havalimanindan binis": "Havalimanından biniş",
            "Havalimanina gidis": "Havalimanına gidiş"})
        hv["km"] = hv["ort_mesafe_mil"] * MIL_KM
        hv["kmh"] = hv["ort_hiz_mph"] * MIL_KM
        hv["usd_km"] = hv["ort_ucret"] / hv["km"]
        sehir = hv[hv["yolculuk_tipi"] == "Şehir içi"].iloc[0]
        hava = hv[hv["yolculuk_tipi"] == "Havalimanından biniş"].iloc[0]
        with kart("Havalimanı ve şehir içi yolculuklar",
                  f"Havalimanı yolculuğu {tr(hava['ort_ucret'] / sehir['ort_ucret'], 0)} kat pahalı ama km başına "
                  "daha ucuz"):
            H = {"Ortalama ücret": ("ort_ucret", "$", 2), "Ortalama mesafe": ("km", "km", 1),
                 "Ortalama süre": ("ort_sure_dk", "dk", 0), "Ortalama hız": ("kmh", "km/sa", 0),
                 "Km başına ücret": ("usd_km", "$", 2)}
            h_sec = tek_secim("Ölçüt", list(H), "Ortalama ücret", "hava_olcut")
            hs_, hb_, ho_ = H[h_sec]
            fig = go.Figure(go.Bar(
                x=hv["yolculuk_tipi"], y=hv[hs_],
                marker_color=[GRI if t == "Şehir içi" else YESIL for t in hv["yolculuk_tipi"]],
                text=hv[hs_].map(lambda v: f"{tr(v, ho_)} {hb_}"), textposition="outside", cliponaxis=False,
                customdata=hv["yolculuk"], hovertemplate="%{x}<br>%{text} · %{customdata:,.0f} yolculuk<extra></extra>"))
            fig.update_xaxes(title="")
            fig.update_yaxes(title="", showticklabels=False, range=[0, hv[hs_].max() * 1.2])
            ciz(stil(fig, 260, legend=False))
            yorum(f"Havalimanı yolculukları çoğunlukla otoyolda geçtiği için şehir içinden {tr(hava['kmh'] / sehir['kmh'], 1)} "
                  "kat hızlı. Taksimetre hem mesafeye hem süreye göre işliyor; şehir içindeki sıkışık trafikte süre "
                  "ücreti birikiyor. Ayrıca JFK–Manhattan arasında sabit tarife var. Bu yüzden havalimanı yolculuğu "
                  "toplamda pahalı, km başına ucuz.")


# =====================================================================
# PERFORMANS (3. Kisi + 2. Kisi)
# =====================================================================
elif sayfa == "Performans":
    sayfa_basligi("3. Kişi · Performans ve ölçeklenebilirlik", "Veri büyüdükçe ne oluyor?",
                  "Aynı analiz farklı büyüklükteki verilerde pandas (tek bilgisayar, tüm veri bellekte) ve PySpark "
                  "(veriyi parçalara bölerek paralel işleme) ile çalıştırıldı. Her ölçüm 3 kez tekrarlandı; ortanca "
                  "değer gösteriliyor.")
    oz = cokme = None
    if ps is not None:
        p = ps.copy()
        p["yontem_adi"] = p["yontem"].map(YONTEM_ADLARI).fillna(p["yontem"])
        tamam = p[p["durum"] == "tamam"]
        oz = (tamam.groupby(["satir", "yontem_adi"], as_index=False)
              .agg(sure_sn=("sure_sn", "median"), ram_mb=("tepe_ram_mb", "median"), bas=("baslatma_sn", "median")))
        oz["milyon"] = oz["satir"] / 1e6
        oz["ram_gb"] = oz["ram_mb"] / 1024
        cokme = p[p["durum"] != "tamam"].groupby("yontem_adi")["satir"].min()
        sp = oz[oz["yontem_adi"] == "PySpark"]
        k = []
        if "pandas (tüm sütunlar)" in cokme.index:
            k.append((kisa(cokme["pandas (tüm sütunlar)"]), "pandas'ın belleğe sığmadığı boyut", "milyon satır · bellek yetmedi",
                      "kirmizi"))
        if len(sp):
            en = sp.loc[sp["satir"].idxmax()]
            k.append((kisa(en["satir"]), "Spark'ın işlediği en büyük veri",
                      f"milyon satır · {tr(en['sure_sn'], 1)} sn · {tr(en['ram_gb'], 1)} GB bellek", "vurgu"))
            if sp["bas"].notna().any():
                k.append((f"{tr(sp['bas'].median(), 1)} sn", "Spark'ın açılış maliyeti", "her çalıştırmada sabit", ""))
        if k:
            sayaclar(k)
        st.write("")

    sek = st.tabs(["pandas mı, Spark mı?", "CSV mi, Parquet mi?", "Analiz süreleri"])
    with sek[0]:
        if oz is None:
            eksik("results/pandas_spark_benchmark.csv", "python src/benchmark_pandas_spark.py")
        else:
            c1, c2 = st.columns([1, 2])
            with c1:
                p_olcut = tek_secim("Ölçüt", ["İşlem süresi", "Bellek kullanımı"], "İşlem süresi", "perf_olcut")
            with c2:
                yontemler = st.pills("Yöntem", list(YONTEM_RENK), selection_mode="multi", default=list(YONTEM_RENK),
                                     key="perf_yontem")
            ysut, ybirim = ("sure_sn", "sn") if p_olcut == "İşlem süresi" else ("ram_gb", "GB")
            o_ = oz[oz["yontem_adi"].isin(yontemler)]
            baslik = ("Küçük veride pandas hızlı, büyük veride sadece Spark ayakta kalıyor" if ysut == "sure_sn"
                      else "pandas'ın bellek ihtiyacı veriyle büyüyor, Spark'ınki neredeyse sabit")
            with kart(baslik, f"{p_olcut} ({ybirim}) · yatay eksen: satır sayısı, milyon (logaritmik)"):
                fig = px.line(o_, x="milyon", y=ysut, color="yontem_adi", markers=True, log_x=True,
                              color_discrete_map=YONTEM_RENK, custom_data=["yontem_adi", "satir"])
                fig.update_traces(line_width=2.5, marker_size=8,
                                  hovertemplate="%{customdata[0]}<br>%{customdata[1]:,.0f} satır<br><b>%{y:,.1f} "
                                                + ybirim + "</b><extra></extra>")
                for yontem, satir in cokme.items():
                    if yontem not in yontemler:
                        continue
                    son = oz[oz["yontem_adi"] == yontem].sort_values("satir").tail(1)
                    if len(son):
                        fig.add_scatter(x=[satir / 1e6], y=[son[ysut].iloc[0]], mode="markers+text",
                                        marker=dict(symbol="x", size=13, color=KIRMIZI), text=["bellek yetmedi"],
                                        textposition="top center", textfont=dict(color=KIRMIZI, size=11),
                                        showlegend=False, hovertemplate=f"{yontem}<br>{tr(satir)} satır: bellek yetmedi"
                                                                        "<extra></extra>")
                if ysut == "ram_gb":
                    fig.add_hline(y=KULLANILABILIR_RAM_GB, line_dash="dash", line_color=KIRMIZI, line_width=1.5,
                                  annotation_text=f"Kullanılabilir bellek ≈ {KULLANILABILIR_RAM_GB} GB",
                                  annotation_position="top left", annotation_font=dict(color=KIRMIZI, size=12))
                fig.update_xaxes(title="", tickvals=[0.1, 1, 3.5, 10, 20, 30, 60],
                                 ticktext=["0,1", "1", "3,5", "10", "20", "30", "60"])
                fig.update_yaxes(title=ybirim, rangemode="tozero")
                ciz(stil(fig, 380))
                if ysut == "sure_sn":
                    yorum("Spark her işte görevleri planlama ve işçilere dağıtma gibi sabit bir maliyet ödüyor; küçük "
                          "veride bu maliyet işin kendisinden büyük olduğu için pandas daha hızlı. pandas'ın süresi ise "
                          "veriyle birlikte hızla artıyor ve veri belleği aştığı anda çalışamıyor (✕).")
                else:
                    yorum("pandas tüm veriyi aynı anda belleğe yüklüyor ve işlem sırasında geçici kopyalar oluşturuyor; "
                          "bu yüzden kırmızı çizgiye ulaşmadan çöküyor. Sadece gereken sütunları okumak sınırı ileri "
                          "itiyor ama kaldırmıyor. Spark veriyi parçalar hâlinde işlediği için bellek kullanımı veri "
                          "büyüdükçe neredeyse değişmiyor.")
            with st.expander("Ölçüm tablosu"):
                tablo = oz[["satir", "yontem_adi", "sure_sn", "ram_gb"]].rename(columns={
                    "satir": "Satır", "yontem_adi": "Yöntem", "sure_sn": "Süre (sn)", "ram_gb": "Bellek (GB)"}).round(2)
                st.dataframe(tablo, hide_index=True)
                indir(tablo, "pandas_spark_olcumleri.csv")

    with sek[1]:
        fb = sonuc_oku("format_benchmark.csv")
        if fb is None:
            eksik("results/format_benchmark.csv", "python src/benchmark_format.py")
        else:
            fb = fb.copy()
            fb[["islem_tipi", "format"]] = fb["islem"].map(ISLEM_ADLARI).apply(pd.Series)
            ozf = fb.groupby(["satir", "islem_tipi", "format"], as_index=False)["sure_sn"].median()
            boyutlar = sorted(ozf["satir"].unique())
            c1, c2 = st.columns([1.3, 1])
            with c1:
                v_sec = st.select_slider("Veri büyüklüğü", options=boyutlar, value=boyutlar[-1],
                                         format_func=lambda v: milyon(v))
            f_ = ozf[ozf["satir"] == v_sec]
            piv = f_.pivot(index="islem_tipi", columns="format", values="sure_sn")
            kat = (piv["CSV"] / piv["Parquet"]) if {"CSV", "Parquet"}.issubset(piv.columns) else None
            with kart("İşlem süresi: CSV ve Parquet",
                      f"{milyon(v_sec)} satır, pandas ile" + (f" · Parquet {tr(kat.max(), 0)} kata kadar hızlı"
                                                               if kat is not None else "")):
                fig = px.bar(f_, x="sure_sn", y="islem_tipi", color="format", barmode="group", orientation="h",
                             text="sure_sn", color_discrete_map=FORMAT_RENK, custom_data=["format"])
                fig.update_traces(texttemplate="%{text:,.2f} sn", textposition="outside", cliponaxis=False,
                                  hovertemplate="%{y} · %{customdata[0]}<br><b>%{x:,.2f} sn</b><extra></extra>")
                fig.update_xaxes(title="", showticklabels=False)
                fig.update_yaxes(title="", categoryorder="array", categoryarray=ISLEM_SIRASI[::-1])
                ciz(stil(fig, 280))
                yorum("CSV düz metin: 3 sütun gerekse bile her satırı baştan sona okuyup sayıya çevirmek gerekiyor. "
                      "Parquet veriyi sütun sütun ve sıkıştırılmış tuttuğu için yalnızca istenen sütunlar diskten "
                      "okunuyor (column pruning). Fark en çok az sütun okunurken ve veri büyüdükçe açılıyor.")
            disk = []
            for satir in (md_oku("benchmark_format.md") or "").splitlines():
                m = re.match(r"\|\s*(\w+)\s*\|\s*([\d,]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)x\s*\|$", satir)
                if m:
                    disk.append({"Veri seti": m[1], "satir": int(m[2].replace(",", "")), "CSV": float(m[3]),
                                 "Parquet": float(m[4])})
            if disk:
                d_ = pd.DataFrame(disk)
                with kart("Diskte kapladığı yer", "MB"):
                    u_ = d_.melt(id_vars=["Veri seti", "satir"], value_vars=["CSV", "Parquet"], var_name="format",
                                 value_name="mb")
                    u_["etiket"] = u_["satir"].map(milyon)
                    fig = px.bar(u_, x="etiket", y="mb", color="format", barmode="group", text="mb",
                                 color_discrete_map=FORMAT_RENK)
                    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False,
                                      hovertemplate="%{x} · %{fullData.name}<br>%{y:,.0f} MB<extra></extra>")
                    fig.update_xaxes(title="")
                    fig.update_yaxes(title="MB")
                    ciz(stil(fig, 280))

    with sek[2]:
        sure = oku("_sure_olcumleri")
        if sure is None:
            eksik("results/agg/_sure_olcumleri.csv", "python src/aggregations.py")
        else:
            ozel = sure.set_index("analiz")
            analiz = sure[~sure["analiz"].str.startswith("_")].sort_values("sure_sn")
            k = []
            if "_okuma_ve_cache" in ozel.index:
                k.append((f"{tr(ozel.loc['_okuma_ve_cache', 'sure_sn'], 1)} sn", "Veriyi okuyup belleğe alma", None, ""))
            k.append((f"{tr(analiz['sure_sn'].sum(), 1)} sn", f"{len(analiz)} analizin toplamı", None, "vurgu"))
            if "_toplam" in ozel.index:
                k.append((f"{tr(ozel.loc['_toplam', 'sure_sn'], 1)} sn", "Tamamı", "Spark açılışı dahil", ""))
            sayaclar(k)
            st.write("")
            with kart("Bu dashboard'daki analizler Spark'ta ne kadar sürdü? (2. Kişi)",
                      f"{milyon(genel['toplam_yolculuk'])} satır, veri belleğe alındıktan (cache) sonra"):
                fig = go.Figure(go.Bar(x=analiz["sure_sn"], y=analiz["aciklama"], orientation="h", marker_color=YESIL,
                                       text=analiz["sure_sn"], texttemplate="%{text:,.2f} sn", textposition="outside",
                                       cliponaxis=False, hovertemplate="%{y}<br>%{x:,.2f} sn<extra></extra>"))
                fig.update_xaxes(title="", showticklabels=False)
                fig.update_yaxes(title="")
                ciz(stil(fig, max(260, len(analiz) * 28), legend=False))
                yorum("Veri bir kez okunup belleğe alındıktan sonra her analiz birkaç saniyede bitiyor. Belleğe "
                      "alınmasaydı her analiz dosyaları baştan okuyacaktı. Dashboard ise ham veriyi değil bu "
                      "analizlerin küçük sonuç dosyalarını okuduğu için anında açılıyor.")


# =====================================================================
# SURE TAHMINI (3. Kisi)
# =====================================================================
elif sayfa == "Süre tahmini":
    sayfa_basligi("3. Kişi · Makine öğrenmesi", "Yolculuk kaç dakika sürecek?",
                  "Yolcu taksiye bindiği anda bilinen bilgilerle (nereden, nereye, saat, gün, mesafe) yolculuğun süresi "
                  "tahmin edildi. Model Ocak ve Şubat verisiyle eğitildi, hiç görmediği Mart verisiyle test edildi.")
    if model is None:
        eksik("results/model_sonuclari.csv", "python src/model_egit.py")
        st.stop()
    en_iyi = model.loc[model["MAE"].idxmin()]
    taban = model[model["model"].str.contains("Baseline", case=False)]
    kisa_ad = {"HistGradientBoosting": "Gradient Boosting", "Linear Regression": "Doğrusal regresyon"}
    k = [(kisa_ad.get(en_iyi["model"], en_iyi["model"]), "En iyi model", en_iyi["model"], "vurgu"),
         (f"± {tr(en_iyi['MAE'], 1)} dk", "Ortalama hata (MAE)", "Mart verisinde", ""),
         (f"%{tr(en_iyi['R2'] * 100, 0)}", "Açıklanan değişkenlik (R²)", None, "")]
    if len(taban):
        k.append((f"%{tr((1 - en_iyi['MAE'] / taban.iloc[0]['MAE']) * 100, 0)}", "Hatadaki azalma",
                  "tahminsiz duruma göre", ""))
    sayaclar(k)
    st.write("")
    rapor = md_oku("model_raporu.md") or ""
    sek = st.tabs(["Model karşılaştırması", "Hangi bilgi önemli?", "Hata nerede büyüyor?", "Model nasıl kuruldu?"])

    with sek[0]:
        with kart("Üç modelin karşılaştırması"):
            M = {"Ortalama hata (MAE)": ("MAE", "dk", 2, True), "Büyük hatalara duyarlı hata (RMSE)": ("RMSE", "dk", 2, True),
                 "Açıklanan değişkenlik (R²)": ("R2", "", 3, False), "Eğitim süresi": ("egitim_sn", "sn", 1, True)}
            m_sec = tek_secim("Ölçüt", list(M), "Ortalama hata (MAE)", "model_olcut")
            ms, mb, mo, kucuk_iyi = M[m_sec]
            m_ = model.copy()
            m_["ad"] = m_["model"].replace({"Baseline (ortalama)": "Tahminsiz (hep ortalamayı söyle)"})
            fig = go.Figure(go.Bar(
                x=m_[ms], y=m_["ad"], orientation="h",
                marker_color=[YESIL if a == en_iyi["model"] else GRI_ACIK for a in m_["model"]],
                text=m_[ms].map(lambda v: f"{tr(v, mo)} {mb}".strip()), textposition="outside", cliponaxis=False,
                hovertemplate="%{y}<br>%{text}<extra></extra>"))
            fig.update_xaxes(title="", showticklabels=False)
            fig.update_yaxes(title="", autorange="reversed")
            ciz(stil(fig, 200, legend=False))
            aciklama = {
                "MAE": "Tahminin gerçek süreden ortalama kaç dakika saptığı. Küçük olan iyi.",
                "RMSE": "Büyük hataları daha ağır cezalandıran hata ölçüsü. MAE'den çok büyükse model bazı yolculuklarda "
                        "çok yanılıyor demektir.",
                "R2": "Süredeki değişkenliğin ne kadarını modelin açıkladığı. 1 mükemmel, 0 hiç açıklamıyor.",
                "egitim_sn": "Modelin eğitilmesi için geçen süre. Daha iyi model daha uzun sürede eğitiliyor.",
            }
            yorum(aciklama[ms] + " Doğrusal model mesafe ile süre arasındaki düz ilişkiyi yakalıyor; karar ağaçlarına "
                  "dayalı HistGradientBoosting ise “bu saatte bu bölgede trafik yoğun” gibi etkileşimleri de "
                  "öğrenebildiği için daha başarılı.", "Ne anlama geliyor")

    with sek[1]:
        onem = md_tablo("model_raporu.md", "Ozellik")
        with kart("Model en çok hangi bilgiye güveniyor?",
                  "Bir bilgi karıştırıldığında modelin başarısı (R²) ne kadar düşüyor?"):
            if onem is None:
                eksik("docs/model_raporu.md", "python src/model_egit.py")
            else:
                ADLAR = {"trip_distance": "Mesafe", "pickup_hour": "Biniş saati", "PU_bolge_kodu": "Biniş bölgesi",
                         "DO_bolge_kodu": "İniş bölgesi", "RatecodeID": "Tarife türü", "pickup_dayofweek": "Haftanın günü",
                         "DO_Borough": "İniş ilçesi", "PU_Borough": "Biniş ilçesi", "VendorID": "Taksimetre firması"}
                o_ = onem.copy()
                o_["dusus"] = o_["R2 dususu"].map(lambda v: pd.to_numeric(v, errors="coerce"))
                o_["ad"] = o_["Ozellik"].map(lambda v: ADLAR.get(v, v))
                o_ = o_.sort_values("dusus")
                fig = go.Figure(go.Bar(x=o_["dusus"], y=o_["ad"], orientation="h",
                                       marker_color=[YESIL if a == "Mesafe" else "#8DB5B0" for a in o_["ad"]],
                                       text=o_["dusus"].map(lambda v: tr(v, 3)), textposition="outside",
                                       cliponaxis=False, hovertemplate="%{y}<br>R² düşüşü: %{text}<extra></extra>"))
                fig.update_xaxes(title="", showticklabels=False)
                fig.update_yaxes(title="")
                ciz(stil(fig, 320, legend=False))
                yorum("Süreyi en çok <b>mesafe</b> belirliyor; ardından biniş saati (trafik) ve bölgeler geliyor. "
                      "Taksimetre firmasının neredeyse hiç etkisi yok; bu da beklenen bir sonuç.")

    with sek[2]:
        hata = md_tablo("model_raporu.md", "Gercek sure")
        with kart("Uzun yolculuklarda hata büyüyor", "HistGradientBoosting, gerçek süreye göre ortalama hata (dk)"):
            if hata is None:
                eksik("docs/model_raporu.md", "python src/model_egit.py")
            else:
                h_ = hata.copy()
                h_["mae"] = h_["MAE (dk)"].map(lambda v: pd.to_numeric(v, errors="coerce"))
                h_["adet"] = h_["Yolculuk"].map(sayi)
                fig = go.Figure(go.Bar(x=h_["Gercek sure"], y=h_["mae"], marker_color=YESIL,
                                       text=h_["mae"].map(lambda v: f"± {tr(v, 1)} dk"), textposition="outside",
                                       cliponaxis=False, customdata=h_["adet"],
                                       hovertemplate="%{x}<br>%{text} · %{customdata:,.0f} yolculuk<extra></extra>"))
                fig.update_xaxes(title="Gerçek yolculuk süresi")
                fig.update_yaxes(title="", showticklabels=False, range=[0, h_["mae"].max() * 1.2])
                ciz(stil(fig, 300, legend=False))
                yorum("Kısa yolculuklarda model 2 dakika civarında yanılıyor; 1 saati aşan yolculuklarda hata çok "
                      "büyüyor. Uzun yolculuklar az ve trafik sıkışması gibi binişte bilinemeyen etkenlere daha açık.")

    with sek[3]:
        with kart("Kurulum"):
            egitim = re.search(r"Egitim:[^(]*\(([\d,]+) yolculuk\)", rapor)
            test = re.search(r"Test:[^(]*\(([\d,]+) yolculuk\)", rapor)
            egitim_n = f" · {egitim.group(1).replace(',', '.')} yolculuk" if egitim else ""
            test_n = f" · {test.group(1).replace(',', '.')} yolculuk" if test else ""
            st.markdown(
                "<ol class='pp-bulgular'>"
                "<li><div><b>Hedef:</b> yolculuk süresi (dakika).</div></li>"
                f"<li><div><b>Eğitim verisi:</b> Ocak + Şubat 2026{egitim_n}.</div></li>"
                f"<li><div><b>Test verisi:</b> Mart 2026{test_n}. "
                "Model bu ayı eğitimde hiç görmedi.</div></li>"
                "<li><div><b>Kullanılan bilgiler:</b> mesafe, biniş ve iniş bölgesi/ilçesi, saat, haftanın günü, tarife "
                "türü, taksimetre firması.</div></li>"
                "<li><div><b>Bilerek kullanılmayanlar (veri sızıntısı):</b> iniş zamanı, ortalama hız, ücret ve bahşiş. "
                "Bunlar yolculuk bitince belli oluyor ve süreyi dolaylı olarak içeriyor; kullanılsaydı model gerçekte "
                "olduğundan çok daha başarılı görünürdü.</div></li></ol>", unsafe_allow_html=True)
        grafik = SONUC / "model_grafik.png"
        if grafik.exists():
            with st.expander("3. Kişinin model grafikleri"):
                st.image(str(grafik))


# =====================================================================
# PROJE DOKUMANLARI
# =====================================================================
elif sayfa == "Proje dokümanları":
    sayfa_basligi("Proje", "Proje dokümanları",
                  "Ekibin hazırladığı raporlar, veri sözlüğü ve mimari şema. Bir doküman seçin; içeriği aşağıda açılır "
                  "ve indirilebilir.")
    DOKUMANLAR = {
        "Proje mimarisi": "mimari.md",
        "Aggregation analizleri raporu (2. Kişi)": "rapor_kisi2_aggregation.md",
        "Ölçeklenebilirlik ve model raporu (3. Kişi)": "rapor_kisi3_benchmark.md",
        "Model raporu (3. Kişi)": "model_raporu.md",
        "pandas / Spark benchmark (3. Kişi)": "benchmark_pandas_spark.md",
        "CSV / Parquet benchmark (3. Kişi)": "benchmark_format.md",
        "Temizlik raporu (1. Kişi)": "temizlik_raporu.md",
        "Veri sözlüğü (1. Kişi)": "veri_sozlugu.md",
        "Ham veri profili (1. Kişi)": "veri_profili.md",
        "Boyut analizi (1. Kişi)": "boyut_analizi.md",
        "Benchmark veri setleri (1. Kişi)": "orneklemler.md",
        "Aggregation sonuç özeti (2. Kişi)": "aggregation_sonuclari.md",
    }
    mevcut = {ad: d for ad, d in DOKUMANLAR.items() if (DOCS / d).exists()}
    if not mevcut:
        eksik("docs/", "git pull")
        st.stop()
    c1, c2 = st.columns([3, 1])
    with c1:
        dok = st.selectbox("Doküman", list(mevcut))
    metin = md_oku(mevcut[dok])
    with c2:
        st.write("")
        st.download_button("İndir (.md)", metin.encode("utf-8"), file_name=mevcut[dok], mime="text/markdown",
                           icon=":material/download:")
    with kart():
        md_goster(metin)


# =====================================================================
# SINAV SORULARI
# =====================================================================
elif sayfa == "Sınav soruları":
    sayfa_basligi("Proje", "Sınav soruları",
                  "Ekibin projeyle ilgili hazırladığı çoktan seçmeli sorular. Cevaplarınızı işaretleyip "
                  "“Cevapları kontrol et” düğmesine basın.")
    sorular = sorulari_oku()
    if not sorular:
        eksik("sorular/kisi*_sorular.md", "git pull")
        st.stop()
    kisiler = sorted({s["kisi"] for s in sorular})
    filtre = tek_secim("Konu", ["Tümü"] + [f"{k}. Kişi" for k in kisiler], "Tümü", "soru_filtre")
    secili = [s for s in sorular if filtre == "Tümü" or filtre.startswith(s["kisi"])]
    st.caption(f"{len(secili)} soru")
    with st.form("sinav"):
        cevaplar = {}
        for i, s in enumerate(secili, 1):
            with kart():
                st.markdown(f"<span class='pp-soru-no'>Soru {i} · {s['kisi']}. Kişi</span>", unsafe_allow_html=True)
                st.markdown(f"**{s['metin']}**")
                cevaplar[i] = st.radio("Cevap", [h for h, _ in s["secenekler"]], index=None,
                                       format_func=lambda h, s=s: f"{h}) {dict(s['secenekler'])[h]}",
                                       key=f"soru_{filtre}_{i}", label_visibility="collapsed")
        gonder = st.form_submit_button("Cevapları kontrol et", type="primary")
    if gonder:
        dogru = sum(1 for i, s in enumerate(secili, 1) if cevaplar[i] == s["cevap"])
        bos = sum(1 for v in cevaplar.values() if v is None)
        sayaclar([(f"{dogru} / {len(secili)}", "Doğru", None, "vurgu"),
                  (str(len(secili) - dogru - bos), "Yanlış", None, ""),
                  (str(bos), "Boş", None, "")])
        with kart("Cevap anahtarı"):
            satirlar = []
            for i, s in enumerate(secili, 1):
                v = cevaplar[i]
                durum = ("<span class='pp-dogru'>Doğru</span>" if v == s["cevap"] else
                         "<span class='pp-bos'>Boş</span>" if v is None else
                         f"<span class='pp-yanlis'>Yanlış ({v})</span>")
                satirlar.append(f"<li><div><b>Soru {i}:</b> {durum} · doğru cevap <b>{s['cevap']})</b> "
                                f"{dict(s['secenekler'])[s['cevap']]}</div></li>")
            st.markdown("<ol class='pp-bulgular' style='counter-reset:none'>" + "".join(satirlar) + "</ol>",
                        unsafe_allow_html=True)

alt_bilgi()
