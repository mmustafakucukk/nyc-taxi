# NYC Taxi Buyuk Veri Analitigi

Bu proje Buyuk Veri Analitigi dersi (2026-2027 Guz) proje calismasidir.

**Problem:** Milyonlarca taksi yolculugundan sehir ici ulasim davranislarini analiz etmek.

**Arastirma sorusu:** Veri buyudukce klasik analiz yaklasimi ne zaman yetersiz kaliyor?

## Klasor yapisi

```
data/
  raw/         ham veri (TLC'den indirilen dosyalar)
  processed/   temizlenmis veri (CSV + Parquet)
  samples/     benchmark icin 100K / 1M / 5M kayitlik ornekler
src/           Python scriptleri
notebooks/     analiz notebook'lari
docs/          veri sozlugu ve rapor dosyalari
sorular/       coktan secmeli sinav sorulari
```

Veri dosyalari buyuk oldugu icin GitHub'a yuklenmez, `data/` klasorleri bos gelir.

## Kurulum

Gereksinimler: Python 3.12, Java 17 veya 21.

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Windows notu:** Bilgisayarda birden fazla Python varsa Spark yanlis Python'u acip hata
verebilir. Bunu onlemek icin Spark baslatilmadan once su degiskenler ayarlanmali:

```python
import os, sys
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
```

## Gorev dagilimi

| Kisi | Gorev |
|------|-------|
| 1. Kisi | Veri temini, veri sozlugu, temizleme pipeline'i, CSV/Parquet donusumu, repo yapisi |
| 2. Kisi | PySpark aggregation analizleri, gorsellestirme ve dashboard |
| 3. Kisi | ML modeli (sure/ucret tahmini), Pandas vs PySpark ve CSV vs Parquet benchmark |

## Veri kaynagi

NYC Taxi & Limousine Commission (TLC) Trip Record Data:
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

Projede Yellow Taxi verisinin Ocak, Subat ve Mart 2026 aylari kullanildi (toplam 11.077.206 yolculuk).

| Dosya | Satir |
|-------|-------|
| yellow_tripdata_2026-01.parquet | 3.724.889 |
| yellow_tripdata_2026-02.parquet | 3.399.866 |
| yellow_tripdata_2026-03.parquet | 3.952.451 |
| taxi_zone_lookup.csv | 265 |

Veriyi indirmek icin:

```bash
python src/veri_indir.py
```
