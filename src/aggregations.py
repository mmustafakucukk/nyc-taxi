# 2. Kisi - PySpark ile sehir ici hareket oruntuleri analizi
#
# Temiz veriden (data/processed/parquet) saat, gun, bolge ve odeme turune gore
# toplulastirma (aggregation) analizleri yapar. Ayrica:
#   - JOIN   : zone tablosundan service_zone bilgisini ekler
#   - WINDOW : her saatin en yogun 5 bolgesi, 7 gunluk hareketli ortalama,
#              bolgenin kendi ilcesi icindeki payi
#   - SQL    : odeme turu analizi Spark SQL ile yazildi (ayni isin SQL hali)
#
# Her sonuc kucuk bir tablo oldugu icin toPandas() ile alinip results/agg/ klasorune CSV yazilir
# (Windows'ta Spark dosya yazamiyor, README'ye bak). Dashboard bu CSV'leri okur.
# Her analizin suresi results/agg/_sure_olcumleri.csv dosyasina kaydedilir.
#
# Kullanim (proje ana klasorunden): python src/aggregations.py
# Once src/temizle.py calismis olmali.

import glob
import numbers
import os
import time

import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_baslat import spark_olustur

KAYNAK = "data/processed/parquet"
ZONE_CSV = "data/raw/taxi_zone_lookup.csv"
CIKTI = "results/agg"

BILINMEYEN_BOLGE = [264, 265]  # 264 = Unknown, 265 = Outside of NYC (gercek semt degil)
HAVALIMANLARI = [1, 132, 138]  # 1 = Newark (EWR), 132 = JFK, 138 = LaGuardia

ODEME_ADLARI = {0: "Flex Fare", 1: "Kredi karti", 2: "Nakit", 3: "Ucretsiz", 4: "Itirazli"}
GUN_ADLARI = {1: "Pazar", 2: "Pazartesi", 3: "Sali", 4: "Carsamba", 5: "Persembe", 6: "Cuma", 7: "Cumartesi"}

os.makedirs(CIKTI, exist_ok=True)
sureler = []  # her analizin ne kadar surdugu


def kaydet(ad, sdf, aciklama):
    """Spark DataFrame'ini hesaplatip CSV'ye yazar ve suresini kaydeder."""
    bas = time.time()
    # toPandas() bir "action": Spark tembel calistigi icin hesaplama tam burada yapilir.
    pdf = sdf.toPandas()
    sure = time.time() - bas
    pdf.to_csv(f"{CIKTI}/{ad}.csv", index=False)
    sureler.append({"analiz": ad, "aciklama": aciklama, "satir": len(pdf), "sure_sn": round(sure, 2)})
    print(f"  {ad:<22} {len(pdf):>6} satir  {sure:6.2f} sn  -> {aciklama}")
    return pdf


toplam_bas = time.time()
spark = spark_olustur("aggregations")
# Temiz veri pandas ile yazildi; pandas tarih sutunlarini nanosaniye (TIMESTAMP(NANOS)) olarak sakliyor.
# Spark bu tipi dogrudan okuyamiyor, bu ayarla o sutunlari sayi (long) olarak okuyor.
# Bizim kullandigimiz sutunlarda (pickup_date, pickup_hour...) tarih-saat yok, analiz etkilenmez.
spark.conf.set("spark.sql.legacy.parquet.nanosAsLong", "true")

# ---- 1) Veriyi oku ----
# Sadece kullanacagimiz sutunlari seciyoruz. Parquet sutun bazli oldugu icin
# geri kalan sutunlar diskten hic okunmaz (column pruning).
dosyalar = sorted(glob.glob(f"{KAYNAK}/*.parquet"))
if not dosyalar:
    raise SystemExit(f"{KAYNAK} bos. Once 'python src/temizle.py' calistirin.")

sutunlar = [
    "pickup_date", "pickup_hour", "pickup_dayofweek",
    "PULocationID", "DOLocationID", "PU_Borough", "PU_Zone", "DO_Borough", "DO_Zone",
    "payment_type", "fare_amount", "tip_amount", "total_amount",
    "trip_distance", "trip_duration_min", "avg_speed_mph",
]
df = (
    spark.read.parquet(*dosyalar)
    .select(*sutunlar)
    # 1 = Pazar, 7 = Cumartesi
    .withColumn("gun_tipi", F.when(F.col("pickup_dayofweek").isin(1, 7), "Hafta sonu").otherwise("Hafta ici"))
)

# Ayni veri uzerinde 10'dan fazla analiz yapacagiz. cache() ile ilk okumadan sonra bellekte
# tutuluyor, her analizde diskten bastan okunmuyor.
df.cache()
bas = time.time()
toplam_satir = df.count()  # cache'i dolduran action
okuma_suresi = time.time() - bas
sureler.append({"analiz": "_okuma_ve_cache", "aciklama": "Parquet okuma + bellege alma",
                "satir": toplam_satir, "sure_sn": round(okuma_suresi, 2)})
print(f"Okunan satir: {toplam_satir:,} ({len(dosyalar)} dosya, {okuma_suresi:.1f} sn)\n")

# Bolge analizlerinde Unknown / Outside of NYC satirlarini disarida birakiyoruz
bolge_df = df.filter(~F.col("PULocationID").isin(BILINMEYEN_BOLGE) & ~F.col("DOLocationID").isin(BILINMEYEN_BOLGE))

print("Aggregation analizleri:")

# ---- 2) Zaman oruntuleri ----

# 2a) Saatlik profil, hafta ici ve hafta sonu ayri.
# Gun sayisina bolerek "o saatte ortalama gunde kac yolculuk" buluyoruz, boylece
# hafta ici (5 gun) ile hafta sonu (2 gun) adil karsilastirilir.
saatlik = (
    df.groupBy("gun_tipi", "pickup_hour")
    .agg(
        F.count("*").alias("yolculuk"),
        F.countDistinct("pickup_date").alias("gun_sayisi"),
        F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
        F.round(F.avg("trip_distance"), 2).alias("ort_mesafe_mil"),
        F.round(F.avg("trip_duration_min"), 2).alias("ort_sure_dk"),
        F.round(F.avg("avg_speed_mph"), 2).alias("ort_hiz_mph"),
    )
    .withColumn("gunluk_ort_yolculuk", F.round(F.col("yolculuk") / F.col("gun_sayisi"), 0))
    .orderBy("gun_tipi", "pickup_hour")
)
kaydet("saatlik", saatlik, "saat x hafta ici/sonu: sayi, ucret, mesafe, sure, hiz")

# 2b) Gun x saat isi haritasi. Ocak-Mart'ta her gunden ayni sayida yok (12 veya 13),
# bu yuzden yine gun sayisina bolup ortalama aliyoruz.
gun_saat = (
    df.groupBy("pickup_dayofweek", "pickup_hour")
    .agg(
        F.count("*").alias("yolculuk"),
        F.countDistinct("pickup_date").alias("gun_sayisi"),
        F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
        F.round(F.avg("trip_distance"), 2).alias("ort_mesafe_mil"),
        F.round(F.avg("trip_duration_min"), 2).alias("ort_sure_dk"),
        F.round(F.avg("avg_speed_mph"), 2).alias("ort_hiz_mph"),
    )
    .withColumn("gunluk_ort_yolculuk", F.round(F.col("yolculuk") / F.col("gun_sayisi"), 0))
    .orderBy("pickup_dayofweek", "pickup_hour")
)
pdf = kaydet("gun_saat", gun_saat, "haftanin gunu x saat: sayi, ucret, mesafe, sure, hiz")

# 2c) Gunluk trend + WINDOW: 7 gunluk hareketli ortalama ve bir onceki gune gore degisim.
# Window.orderBy tek bir siralama oldugu icin Spark tum veriyi tek parcaya toplar;
# burada sorun degil cunku gunluk tabloda sadece ~90 satir var.
gunluk = df.groupBy("pickup_date").agg(
    F.count("*").alias("yolculuk"),
    F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
)
w_tarih = Window.orderBy("pickup_date")
gunluk = (
    gunluk
    .withColumn("ort_7gun", F.round(F.avg("yolculuk").over(w_tarih.rowsBetween(-6, 0)), 0))
    .withColumn("onceki_gun", F.lag("yolculuk", 1).over(w_tarih))
    .withColumn("degisim_yuzde", F.round((F.col("yolculuk") - F.col("onceki_gun")) / F.col("onceki_gun") * 100, 1))
    .orderBy("pickup_date")
)
kaydet("gunluk", gunluk, "gunluk sayi + 7 gunluk hareketli ortalama (window)")

# ---- 3) Bolge analizleri ----

# 3a) En yogun binis bolgeleri
binis = (
    bolge_df.groupBy("PULocationID", "PU_Borough", "PU_Zone")
    .agg(
        F.count("*").alias("yolculuk"),
        F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
        F.round(F.avg("trip_distance"), 2).alias("ort_mesafe_mil"),
    )
    .orderBy(F.desc("yolculuk"))
)
# WINDOW: bolgenin kendi ilcesindeki toplam yolculuk icindeki payi
w_ilce = Window.partitionBy("PU_Borough")
binis = binis.withColumn(
    "ilce_ici_pay_yuzde", F.round(F.col("yolculuk") / F.sum("yolculuk").over(w_ilce) * 100, 2)
)
kaydet("binis_bolgeleri", binis.orderBy(F.desc("yolculuk")), "bolge bazinda binis + ilce ici pay (window)")

# 3a-2) En yogun inis bolgeleri (dashboard'da binis / inis secimi icin)
inis = (
    bolge_df.groupBy("DOLocationID", "DO_Borough", "DO_Zone")
    .agg(
        F.count("*").alias("yolculuk"),
        F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
        F.round(F.avg("trip_distance"), 2).alias("ort_mesafe_mil"),
    )
    .orderBy(F.desc("yolculuk"))
)
kaydet("inis_bolgeleri", inis, "bolge bazinda inis")

# 3b) Ilceden ilceye hareket matrisi
ilce_matrisi = bolge_df.groupBy("PU_Borough", "DO_Borough").count().withColumnRenamed("count", "yolculuk")
kaydet("ilce_matrisi", ilce_matrisi, "binis ilcesi x inis ilcesi")

# 3c) En sik 20 rota (bolgeden bolgeye)
rotalar = (
    bolge_df.groupBy("PU_Zone", "DO_Zone")
    .agg(
        F.count("*").alias("yolculuk"),
        F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
        F.round(F.avg("trip_duration_min"), 1).alias("ort_sure_dk"),
    )
    .orderBy(F.desc("yolculuk"))
    .limit(20)
)
kaydet("top_rotalar", rotalar, "en sik 20 bolge-bolge rotasi")

# 3d) WINDOW: her saatin en yogun 5 binis bolgesi.
# groupBy her (saat, bolge) icin tek satir verir; rank() ise her saati kendi icinde siralar.
saat_bolge = bolge_df.groupBy("pickup_hour", "PU_Zone").count().withColumnRenamed("count", "yolculuk")
w_saat = Window.partitionBy("pickup_hour").orderBy(F.desc("yolculuk"))
saatlik_top5 = (
    saat_bolge.withColumn("sira", F.rank().over(w_saat))
    .filter(F.col("sira") <= 5)
    .orderBy("pickup_hour", "sira")
)
kaydet("saatlik_top5_bolge", saatlik_top5, "her saatin en yogun 5 bolgesi (window rank)")

# 3e) JOIN: temiz veride service_zone yok. Zone tablosundan ekleyip
# Yellow Zone (Manhattan merkezi) / Boro Zone (dis ilceler) / Airports karsilastirmasi yapiyoruz.
# Zone tablosu 265 satir, broadcast ile her isciye kopyasi gonderilir, buyuk tablo shuffle edilmez.
zonlar = spark.read.csv(ZONE_CSV, header=True, inferSchema=True).select(
    F.col("LocationID").alias("PULocationID"), F.col("service_zone")
)
servis = (
    bolge_df.join(F.broadcast(zonlar), "PULocationID", "left")
    .groupBy("service_zone")
    .agg(
        F.count("*").alias("yolculuk"),
        F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
        F.round(F.avg("trip_distance"), 2).alias("ort_mesafe_mil"),
        F.round(F.avg("trip_duration_min"), 1).alias("ort_sure_dk"),
    )
    .orderBy(F.desc("yolculuk"))
)
kaydet("servis_bolgesi", servis, "service_zone bazinda ozet (broadcast join)")

# ---- 4) Odeme turu: Spark SQL ile ----
# Ayni analiz DataFrame API ile de yazilabilirdi. SQL hali, Spark'in iki yolu da
# ayni plana cevirdigini gostermek icin burada.
# Bahsis orani = toplam bahsis / toplam ucret (yolculuk basina oranlarin ortalamasi
# kucuk ucretli yolculuklarda asiri buyudugu icin toplamlarin orani alindi).
df.createOrReplaceTempView("yolculuklar")
odeme = spark.sql("""
    SELECT payment_type,
           COUNT(*)                                       AS yolculuk,
           ROUND(AVG(fare_amount), 2)                     AS ort_ucret,
           ROUND(AVG(tip_amount), 2)                      AS ort_bahsis,
           ROUND(SUM(tip_amount) / SUM(fare_amount) * 100, 2) AS bahsis_orani_yuzde,
           ROUND(AVG(CASE WHEN tip_amount > 0 THEN 1 ELSE 0 END) * 100, 1) AS bahsis_veren_yuzde
    FROM yolculuklar
    GROUP BY payment_type
    ORDER BY yolculuk DESC
""")
pdf = kaydet("odeme_turu", odeme, "odeme turune gore ucret ve bahsis (Spark SQL)")

# 4b) Odeme turu ayrintilari: dashboard'da bir odeme turu secilince acilan grafikler icin.
# Ayni toplulastirma uc farkli kirilimda: saat, mesafe dilimi ve binis ilcesi.
odeme_ozet = [
    F.count("*").alias("yolculuk"),
    F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
    F.round(F.sum("tip_amount") / F.sum("fare_amount") * 100, 2).alias("bahsis_orani_yuzde"),
    F.round(F.avg(F.when(F.col("tip_amount") > 0, 1).otherwise(0)) * 100, 1).alias("bahsis_veren_yuzde"),
]
kaydet("odeme_saat", df.groupBy("payment_type", "pickup_hour").agg(*odeme_ozet).orderBy("payment_type", "pickup_hour"),
       "odeme turu x saat")
mesafe_dilimi = (
    F.when(F.col("trip_distance") < 1, "0-1 mil").when(F.col("trip_distance") < 2, "1-2 mil")
    .when(F.col("trip_distance") < 5, "2-5 mil").when(F.col("trip_distance") < 10, "5-10 mil")
    .otherwise("10+ mil")
)
kaydet("odeme_mesafe", df.withColumn("mesafe_dilimi", mesafe_dilimi)
       .groupBy("payment_type", "mesafe_dilimi").agg(*odeme_ozet), "odeme turu x mesafe dilimi")
kaydet("odeme_ilce", bolge_df.groupBy("payment_type", "PU_Borough").agg(*odeme_ozet), "odeme turu x binis ilcesi")

# ---- 5) Havalimani ve sehir ici ----
yolculuk_tipi = (
    F.when(F.col("PULocationID").isin(HAVALIMANLARI), "Havalimanindan binis")
    .when(F.col("DOLocationID").isin(HAVALIMANLARI), "Havalimanina gidis")
    .otherwise("Sehir ici")
)
havalimani = (
    df.withColumn("yolculuk_tipi", yolculuk_tipi)
    .groupBy("yolculuk_tipi")
    .agg(
        F.count("*").alias("yolculuk"),
        F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
        F.round(F.avg("total_amount"), 2).alias("ort_toplam"),
        F.round(F.avg("trip_distance"), 2).alias("ort_mesafe_mil"),
        F.round(F.avg("trip_duration_min"), 1).alias("ort_sure_dk"),
        F.round(F.avg("avg_speed_mph"), 1).alias("ort_hiz_mph"),
    )
    .orderBy(F.desc("yolculuk"))
)
kaydet("havalimani", havalimani, "havalimani / sehir ici karsilastirma")

# ---- 6) Genel ozet (dashboard'daki buyuk sayilar) ----
genel = df.agg(
    F.count("*").alias("toplam_yolculuk"),
    F.countDistinct("pickup_date").alias("gun_sayisi"),
    F.round(F.avg("fare_amount"), 2).alias("ort_ucret"),
    F.round(F.avg("trip_distance"), 2).alias("ort_mesafe_mil"),
    F.round(F.avg("trip_duration_min"), 1).alias("ort_sure_dk"),
    F.round(F.sum("total_amount"), 0).alias("toplam_ciro"),
)
kaydet("genel_ozet", genel, "genel toplamlar")

df.unpersist()
spark.stop()

toplam_sure = time.time() - toplam_bas
sureler.append({"analiz": "_toplam", "aciklama": "script toplam (Spark acilisi dahil)",
                "satir": toplam_satir, "sure_sn": round(toplam_sure, 2)})
pd.DataFrame(sureler).to_csv(f"{CIKTI}/_sure_olcumleri.csv", index=False)

# ---- 7) Kisa rapor ----
# Sayilari CSV'lerden okuyup ana bulgulari markdown'a yaziyoruz. "Neden" yorumlari elle eklenecek.
s = pd.read_csv(f"{CIKTI}/saatlik.csv")
gs = pd.read_csv(f"{CIKTI}/gun_saat.csv")
b = pd.read_csv(f"{CIKTI}/binis_bolgeleri.csv")
r = pd.read_csv(f"{CIKTI}/top_rotalar.csv")
o = pd.read_csv(f"{CIKTI}/odeme_turu.csv")
h = pd.read_csv(f"{CIKTI}/havalimani.csv")
sv = pd.read_csv(f"{CIKTI}/servis_bolgesi.csv")
g = pd.read_csv(f"{CIKTI}/gunluk.csv")
sur = pd.DataFrame(sureler)

hi = s[s["gun_tipi"] == "Hafta ici"]
hs = s[s["gun_tipi"] == "Hafta sonu"]
zirve_hi = hi.loc[hi["gunluk_ort_yolculuk"].idxmax()]
zirve_hs = hs.loc[hs["gunluk_ort_yolculuk"].idxmax()]
en_dusuk = hi.loc[hi["gunluk_ort_yolculuk"].idxmin()]
en_yavas = hi.loc[hi["ort_hiz_mph"].idxmin()]
en_hizli = hi.loc[hi["ort_hiz_mph"].idxmax()]
en_yogun_hucre = gs.loc[gs["gunluk_ort_yolculuk"].idxmax()]
manhattan_pay = b.loc[b["PU_Borough"] == "Manhattan", "yolculuk"].sum() / b["yolculuk"].sum() * 100
o["odeme"] = o["payment_type"].map(ODEME_ADLARI)
en_yogun_gun = g.loc[g["yolculuk"].idxmax()]
en_sakin_gun = g.loc[g["yolculuk"].idxmin()]


def tablo(pdf_, sutunlar_):
    satirlar_ = ["| " + " | ".join(sutunlar_) + " |", "|" + "---|" * len(sutunlar_)]
    for _, satir in pdf_[sutunlar_].iterrows():
        satirlar_.append("| " + " | ".join(f"{v:,}" if isinstance(v, numbers.Integral) else str(v) for v in satir) + " |")
    return satirlar_


m = ["# Aggregation Sonuclari (2. Kisi)\n"]
m.append(f"Veri: temiz veri, **{toplam_satir:,}** yolculuk (Ocak-Mart 2026). "
         "Uretici script: `src/aggregations.py`. Tum tablolar `results/agg/` klasorunde.\n")
m.append("## Ana bulgular\n")
m.append(f"- Hafta ici en yogun saat **{int(zirve_hi['pickup_hour'])}:00** (gunde ort. {int(zirve_hi['gunluk_ort_yolculuk']):,} yolculuk), "
         f"en sakin saat **{int(en_dusuk['pickup_hour'])}:00** ({int(en_dusuk['gunluk_ort_yolculuk']):,}).")
m.append(f"- Hafta sonu en yogun saat **{int(zirve_hs['pickup_hour'])}:00** (gunde ort. {int(zirve_hs['gunluk_ort_yolculuk']):,}).")
m.append(f"- Hafta ici ortalama hiz en dusuk **{int(en_yavas['pickup_hour'])}:00**'de ({en_yavas['ort_hiz_mph']} mph), "
         f"en yuksek **{int(en_hizli['pickup_hour'])}:00**'de ({en_hizli['ort_hiz_mph']} mph).")
m.append(f"- Haftanin en yogun gun-saat hucresi: **{GUN_ADLARI[int(en_yogun_hucre['pickup_dayofweek'])]} "
         f"{int(en_yogun_hucre['pickup_hour'])}:00**.")
m.append(f"- Binislerin **%{manhattan_pay:.1f}**'i Manhattan'da. En yogun bolge: **{b.iloc[0]['PU_Zone']}** "
         f"({int(b.iloc[0]['yolculuk']):,} binis).")
m.append(f"- En sik rota: **{r.iloc[0]['PU_Zone']} -> {r.iloc[0]['DO_Zone']}** ({int(r.iloc[0]['yolculuk']):,} yolculuk).")
m.append(f"- En yogun gun {en_yogun_gun['pickup_date']} ({int(en_yogun_gun['yolculuk']):,}), "
         f"en sakin gun {en_sakin_gun['pickup_date']} ({int(en_sakin_gun['yolculuk']):,}).")

m.append("\n## Odeme turu\n")
m += tablo(o, ["odeme", "yolculuk", "ort_ucret", "ort_bahsis", "bahsis_orani_yuzde", "bahsis_veren_yuzde"])
m.append("\n## Havalimani / sehir ici\n")
m += tablo(h, ["yolculuk_tipi", "yolculuk", "ort_ucret", "ort_mesafe_mil", "ort_sure_dk", "ort_hiz_mph"])
m.append("\n## Servis bolgesi (join ile eklendi)\n")
m += tablo(sv, ["service_zone", "yolculuk", "ort_ucret", "ort_mesafe_mil", "ort_sure_dk"])
m.append("\n## Islem sureleri\n")
m.append("Veri `cache()` ile bellege alindiktan sonra olculdu. Ilk satir okuma + cache suresidir.\n")
m += tablo(sur, ["analiz", "aciklama", "sure_sn"])
m.append("\n## Yorumlar\n")
m.append("Bu sayilarin yorumu (neden boyle cikti?) `docs/rapor_kisi2_aggregation.md` dosyasinda. "
         "Etkilesimli grafikler icin: `streamlit run dashboard/app.py`")

metin = "\n".join(m) + "\n"
with open("docs/aggregation_sonuclari.md", "w", encoding="utf-8") as f:
    f.write(metin)

print(f"\nToplam sure: {toplam_sure:.1f} sn")
print("Rapor: docs/aggregation_sonuclari.md")
