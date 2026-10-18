# Ham taksi verisini temizler ve temiz veriyi hem Parquet hem CSV olarak kaydeder.
#
# Adimlar:
#   1) Ham veriyi Spark ile oku, yeni sutunlar turet (sure, saat, gun, hiz)
#   2) Her satira "neden silinecek" etiketi ver, her kuralin kac satir yakaladigini say
#   3) Kurala takilan satirlari ve birebir tekrar eden satirlari at
#   4) Bolge kodlarini isimlere cevir (zone tablosuyla join)
#   5) Ay ay pandas'a alip Parquet + CSV yaz (Windows'ta Spark dosya yazamiyor, README'ye bak)
#   6) Raporu docs/temizlik_raporu.md dosyasina yaz
#
# Kullanim: python src/temizle.py

import os
import time
from pyspark.sql import functions as F
from spark_baslat import spark_olustur, ham_dosyalar

# Esikler docs/veri_profili.md'deki yuzdelik dilimlere bakilarak secildi.
# Ornek: surenin %99.9'u 124 dk'nin altinda, 180 dk bunun da cok uzerinde.
ESIKLER = {
    "baslangic_tarihi": "2026-01-01",
    "bitis_tarihi": "2026-04-01",  # bu tarih dahil degil
    "min_sure_dk": 1,      # 1 dakikadan kisa yolculuk: taksimetre acilip hemen kapanmis
    "max_sure_dk": 180,    # p99.9 = 124 dk, 3 saatten uzunu taksimetre acik unutulmus
    "max_mesafe_mil": 100,  # p99.9 = 29.8 mil, max 328.522 mil (olcum hatasi)
    "max_ucret": 500,      # p99.9 = 142 $
    "max_hiz_mph": 80,     # sehir icinde 80 mil/saat (~130 km/s) fiziksel olarak imkansiz
}

CIKTI_PARQUET = "data/processed/parquet"
CIKTI_CSV = "data/processed/csv"

baslangic = time.time()
spark = spark_olustur("temizle")

# ---- 1) Okuma ve turetilen sutunlar ----
ham = spark.read.parquet(*ham_dosyalar())
ham_sayi = ham.count()
print("ham satir:", ham_sayi)

df = (
    ham
    .withColumn(
        "trip_duration_min",
        (F.unix_timestamp("tpep_dropoff_datetime") - F.unix_timestamp("tpep_pickup_datetime")) / 60,
    )
    .withColumn("pickup_date", F.to_date("tpep_pickup_datetime"))
    .withColumn("pickup_hour", F.hour("tpep_pickup_datetime"))
    .withColumn("pickup_dayofweek", F.dayofweek("tpep_pickup_datetime"))  # 1 = Pazar, 7 = Cumartesi
    .withColumn("pickup_month", F.date_format("tpep_pickup_datetime", "yyyy-MM"))
    # sure 0 ise bolme hatasi olmasin diye hizi sadece sure > 0 iken hesapliyoruz
    .withColumn(
        "avg_speed_mph",
        F.when(F.col("trip_duration_min") > 0, F.col("trip_distance") / (F.col("trip_duration_min") / 60)),
    )
)

# ---- 2) Kurallar ----
# Sira onemli: bir satir birden fazla kurala takilabilir, "silinme_sebebi" ilk takildigi kural olur.
kurallar = [
    ("tarih araligi disi",
     (F.col("tpep_pickup_datetime") < ESIKLER["baslangic_tarihi"])
     | (F.col("tpep_pickup_datetime") >= ESIKLER["bitis_tarihi"])),
    ("mesafe <= 0", F.col("trip_distance") <= 0),
    ("ucret veya toplam <= 0", (F.col("fare_amount") <= 0) | (F.col("total_amount") <= 0)),
    (f"sure < {ESIKLER['min_sure_dk']} dk", F.col("trip_duration_min") < ESIKLER["min_sure_dk"]),
    (f"sure > {ESIKLER['max_sure_dk']} dk", F.col("trip_duration_min") > ESIKLER["max_sure_dk"]),
    (f"mesafe > {ESIKLER['max_mesafe_mil']} mil", F.col("trip_distance") > ESIKLER["max_mesafe_mil"]),
    (f"ucret > {ESIKLER['max_ucret']} $", F.col("fare_amount") > ESIKLER["max_ucret"]),
    (f"hiz > {ESIKLER['max_hiz_mph']} mph", F.col("avg_speed_mph") > ESIKLER["max_hiz_mph"]),
]

# when().when()... zinciri: ilk saglanan kosulun adini yazar, hicbiri saglanmazsa null kalir
sebep = F.lit(None).cast("string")
for ad, kosul in reversed(kurallar):
    sebep = F.when(kosul, F.lit(ad)).otherwise(sebep)
df = df.withColumn("silinme_sebebi", sebep)

# Asagida veriyi birkac kez kullanacagiz, her seferinde diskten tekrar okumasin diye bellekte tut
df.cache()

# Her kural tek basina kac satiri yakalar? (bir satir birden fazla kurala sayilabilir)
tek_basina = df.agg(*[F.sum(kosul.cast("int")).alias(ad) for ad, kosul in kurallar]).collect()[0]
# Sirali uygulandiginda her kural kac satir sildi? (her satir sadece bir kez sayilir)
sirali = {r["silinme_sebebi"]: r["count"] for r in df.groupBy("silinme_sebebi").count().collect()}

# ---- 3) Filtreleme ----
temiz = df.filter(F.col("silinme_sebebi").isNull()).drop("silinme_sebebi")
filtre_sonrasi = sirali.get(None, 0)

# Birebir ayni satirlar (tum sutunlar ayni) muhtemelen ayni kaydin iki kez gonderilmesi
temiz = temiz.dropDuplicates()

# ---- passenger_count = 0 ----
# Yolculuk gecerli ama surucu yolcu sayisini girmemis. Satiri silmek yerine "bilinmiyor" (null) yapiyoruz.
yolcu_sifir = temiz.filter(F.col("passenger_count") == 0).count()
temiz = temiz.withColumn(
    "passenger_count",
    F.when(F.col("passenger_count") == 0, F.lit(None)).otherwise(F.col("passenger_count")),
)

# ---- 4) Bolge isimleri ----
# Zone tablosu sadece 265 satir. broadcast() ile her isciye kopyasini gonderiyoruz,
# boylece 11 milyonluk tablo shuffle edilmeden join yapiliyor (broadcast join).
zonlar = spark.read.csv("data/raw/taxi_zone_lookup.csv", header=True, inferSchema=True)
pu = zonlar.select(
    F.col("LocationID").alias("PULocationID"),
    F.col("Borough").alias("PU_Borough"),
    F.col("Zone").alias("PU_Zone"),
)
do = zonlar.select(
    F.col("LocationID").alias("DOLocationID"),
    F.col("Borough").alias("DO_Borough"),
    F.col("Zone").alias("DO_Zone"),
)
temiz = temiz.join(F.broadcast(pu), "PULocationID", "left").join(F.broadcast(do), "DOLocationID", "left")

temiz = temiz.cache()
temiz_sayi = temiz.count()
tekrar_sayi = filtre_sonrasi - temiz_sayi
bilinmeyen_bolge = temiz.filter(
    F.col("PULocationID").isin(264, 265) | F.col("DOLocationID").isin(264, 265)
).count()
flex_ham = df.filter(F.col("payment_type") == 0).count()
flex_temiz = temiz.filter(F.col("payment_type") == 0).count()

print("temiz satir:", temiz_sayi)

# ---- 5) Yazma ----
# Sutun sirasi: once ham sutunlar, sonra turettiklerimiz
sutunlar = ham.columns + [
    "trip_duration_min", "avg_speed_mph", "pickup_date", "pickup_hour", "pickup_dayofweek",
    "pickup_month", "PU_Borough", "PU_Zone", "DO_Borough", "DO_Zone",
]
temiz = temiz.select(sutunlar)

os.makedirs(CIKTI_PARQUET, exist_ok=True)
os.makedirs(CIKTI_CSV, exist_ok=True)

aylar = sorted(r["pickup_month"] for r in temiz.select("pickup_month").distinct().collect())
for ay in aylar:
    # Tum veriyi tek seferde pandas'a almak yerine ay ay aliyoruz, RAM'i doldurmasin
    pdf = temiz.filter(F.col("pickup_month") == ay).orderBy("tpep_pickup_datetime").toPandas()
    pdf.to_parquet(f"{CIKTI_PARQUET}/yellow_temiz_{ay}.parquet", index=False)
    pdf.to_csv(f"{CIKTI_CSV}/yellow_temiz_{ay}.csv", index=False)
    print(f"yazildi: {ay} ({len(pdf):,} satir)")
    del pdf

# ---- 6) Rapor ----
r = ["# Temizlik Raporu\n"]
r.append(f"Ham veri: **{ham_sayi:,}** satir -> Temiz veri: **{temiz_sayi:,}** satir "
         f"(%{(ham_sayi - temiz_sayi) / ham_sayi * 100:.2f} silindi)\n")

r.append("## Kurallar\n")
r.append("Kurallar asagidaki sirayla uygulandi. **Tek basina**: kural tek basina uygulansaydi kac satir "
         "yakalardi. **Sirali silinen**: onceki kurallardan gecen satirlardan kac tanesini bu kural sildi.\n")
r.append("| # | Kural | Tek basina | Sirali silinen | Kalan |")
r.append("|---|---|---|---|---|")
kalan = ham_sayi
for i, (ad, _) in enumerate(kurallar, 1):
    silinen = sirali.get(ad, 0)
    kalan -= silinen
    r.append(f"| {i} | {ad} | {tek_basina[ad]:,} | {silinen:,} | {kalan:,} |")
r.append(f"| {len(kurallar) + 1} | birebir tekrar eden satir | - | {tekrar_sayi:,} | {temiz_sayi:,} |")

r.append("\n## Silinmeyen ama duzeltilen / not edilen durumlar\n")
r.append(f"- **passenger_count = 0:** {yolcu_sifir:,} satir. Yolculuk gecerli, sadece yolcu sayisi "
         "girilmemis. Satir silinmedi, deger null (bilinmiyor) yapildi.")
r.append(f"- **Flex Fare (payment_type = 0):** ham veride {flex_ham:,}, temiz veride {flex_temiz:,} satir. "
         "Bu satirlarda passenger_count, RatecodeID, store_and_fwd_flag, congestion_surcharge ve "
         "Airport_fee bos ama bu bir hata degil (bkz. veri_sozlugu.md). Bos degerler doldurulmadi, "
         "dropna() kullanilmadi. ML'de kullanilacaksa congestion_surcharge ve Airport_fee 0 ile doldurulabilir.")
r.append(f"- **Bilinmeyen bolge (264 Unknown / 265 Outside of NYC):** {bilinmeyen_bolge:,} satir. "
         "Sure, mesafe ve ucret bilgisi gecerli oldugu icin silinmedi. Bolge analizinde filtrelenmeli.")

r.append("\n## Esikler\n")
for k, v in ESIKLER.items():
    r.append(f"- `{k}` = {v}")

r.append("\n## Eklenen sutunlar\n")
r.append("trip_duration_min, avg_speed_mph, pickup_date, pickup_hour, pickup_dayofweek (1 = Pazar), "
         "pickup_month, PU_Borough, PU_Zone, DO_Borough, DO_Zone\n")

r.append("## Ciktilar\n")
for ay in aylar:
    p = f"{CIKTI_PARQUET}/yellow_temiz_{ay}.parquet"
    c = f"{CIKTI_CSV}/yellow_temiz_{ay}.csv"
    r.append(f"- {ay}: Parquet {os.path.getsize(p) / 1024 ** 2:.0f} MB, CSV {os.path.getsize(c) / 1024 ** 2:.0f} MB")

r.append(f"\n_Calisma suresi: {time.time() - baslangic:.0f} sn_\n")

rapor = "\n".join(r)
print(rapor)
with open("docs/temizlik_raporu.md", "w", encoding="utf-8") as f:
    f.write(rapor)

spark.stop()
