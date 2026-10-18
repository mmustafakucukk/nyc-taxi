# Ham verinin profilini cikarir: satir sayisi, her sutunun bos orani, min/max degerleri,
# kodlu sutunlarin dagilimi ve onemli sutunlarin yuzdelik dilimleri.
# Sonuclar ekrana yazilir ve docs/veri_profili.md dosyasina kaydedilir.
# Kullanim: python src/veri_profili.py

import time
from pyspark.sql import functions as F
from spark_baslat import spark_olustur, ham_dosyalar

baslangic = time.time()
spark = spark_olustur("veri_profili")

df = spark.read.parquet(*ham_dosyalar())
toplam = df.count()
print("toplam satir:", toplam)
print("sutun sayisi:", len(df.columns))

satirlar = []  # markdown dosyasina yazilacak satirlar
satirlar.append("# Ham Veri Profili (Ocak-Mart 2026)\n")
satirlar.append(f"Toplam satir: **{toplam:,}**, sutun sayisi: **{len(df.columns)}**\n")

# ---- 1) Her sutun icin bos sayisi, min ve max ----
# Hepsini tek bir agg() icinde istiyoruz ki Spark veriyi sadece bir kez okusun.
ifadeler = []
for sutun in df.columns:
    ifadeler.append(F.sum(F.col(sutun).isNull().cast("int")).alias(sutun + "__bos"))
    ifadeler.append(F.min(sutun).alias(sutun + "__min"))
    ifadeler.append(F.max(sutun).alias(sutun + "__max"))
sonuc = df.agg(*ifadeler).collect()[0]

satirlar.append("## Sutunlar\n")
satirlar.append("| Sutun | Tip | Bos | Bos % | Min | Max |")
satirlar.append("|---|---|---|---|---|---|")
for sutun, tip in df.dtypes:
    bos = sonuc[sutun + "__bos"]
    satirlar.append(
        f"| {sutun} | {tip} | {bos:,} | {bos / toplam * 100:.1f} | "
        f"{sonuc[sutun + '__min']} | {sonuc[sutun + '__max']} |"
    )

# ---- 2) Kodlu sutunlarin dagilimi ----
# Bu sutunlardaki sayilar miktar degil kategori (ornek: payment_type 1 = kredi karti).
for sutun in ["VendorID", "payment_type", "RatecodeID"]:
    dagilim = df.groupBy(sutun).count().orderBy(F.desc("count")).collect()
    satirlar.append(f"\n## {sutun} dagilimi\n")
    satirlar.append("| Deger | Yolculuk | % |")
    satirlar.append("|---|---|---|")
    for r in dagilim:
        satirlar.append(f"| {r[sutun]} | {r['count']:,} | {r['count'] / toplam * 100:.1f} |")

# ---- 3) Turetilen sure sutunu ve yuzdelik dilimler ----
# Temizlikte kullanacagimiz esikleri (orn. sure < 1 dk, mesafe > 100 mil) bu degerlere bakarak sececegiz.
df = df.withColumn(
    "sure_dk",
    (F.unix_timestamp("tpep_dropoff_datetime") - F.unix_timestamp("tpep_pickup_datetime")) / 60,
)
yuzdelikler = [0.01, 0.25, 0.5, 0.75, 0.99, 0.999]
satirlar.append("\n## Yuzdelik dilimler\n")
satirlar.append("| Sutun | " + " | ".join(f"p{y * 100:g}" for y in yuzdelikler) + " |")
satirlar.append("|---|" + "---|" * len(yuzdelikler))
for sutun in ["trip_distance", "sure_dk", "fare_amount", "total_amount", "passenger_count"]:
    # approxQuantile tam siralama yapmadan yaklasik deger bulur, buyuk veride cok daha hizli.
    # Son parametre hata payi: 0.001 verince p99.9 dogrudan max degere kayiyordu, 0.0001 yeterli.
    degerler = df.approxQuantile(sutun, yuzdelikler, 0.0001)
    satirlar.append(f"| {sutun} | " + " | ".join(f"{d:.2f}" for d in degerler) + " |")

# ---- 4) Tarih araligi disindaki kayitlar ----
aralik_disi = df.filter(
    (F.col("tpep_pickup_datetime") < "2026-01-01") | (F.col("tpep_pickup_datetime") >= "2026-04-01")
).count()
satirlar.append(f"\nOcak-Mart 2026 disinda baslayan yolculuk: **{aralik_disi:,}**\n")

satirlar.append(f"\n_Script calisma suresi: {time.time() - baslangic:.1f} sn_\n")

metin = "\n".join(satirlar)
print(metin)
with open("docs/veri_profili.md", "w", encoding="utf-8") as f:
    f.write(metin)

spark.stop()
