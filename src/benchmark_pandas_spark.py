# Ayni analiz islerini pandas ve PySpark ile farkli veri boyutlarinda calistirip
# sure ve bellek (RAM) kullanimini karsilastirir.
#
# Uc yontem yarisiyor:
#   pandas_tum    : klasik yaklasim, dosyanin tamami RAM'e yuklenir
#   pandas_secili : pandas, ama sadece analizde gereken sutunlar okunur
#   spark         : PySpark, local[*] (bilgisayarin tum cekirdekleri)
#
# Her olcum ayri bir Python sureci (subprocess) icinde calisir. Boylece:
#   - bir olcumun RAM'i digerine karismaz
#   - pandas bellek yetmeyip cokerse ana script cokmez, sonuc "bellek yetmedi" olarak kaydedilir
#
# Bellek yetmedi kurali: bilgisayarda bos RAM BOS_RAM_ALT_SINIR_GB'in altina inerse surec durdurulur.
# (Windows RAM bitince diske tasir ve bilgisayar kilitlenir, bunu beklemiyoruz.)
#
# Veri boyutlari: 100 bin, 1M, 3,5M, 6,7M, 10,5M ve 3ay verisi kopyalanarak olusturulan 20,9M, 31,4M ve 62,7M.
#
# Ciktilar:
#   results/pandas_spark_benchmark.csv
#   results/pandas_spark_benchmark.png
#   docs/benchmark_pandas_spark.md
#
# Kullanim: python src/benchmark_pandas_spark.py  (once src/benchmark_format.py calismis olmali,
#           100k ve 1m setlerini o olusturuyor)

import json
import os
import statistics
import subprocess
import sys
import threading
import time

ORNEKLEM = "data/samples"
SONUC_CSV = "results/pandas_spark_benchmark.csv"
SONUC_PNG = "results/pandas_spark_benchmark.png"
RAPOR = "docs/benchmark_pandas_spark.md"

TEKRAR = 3
ZAMAN_ASIMI_SN = 900
BOS_RAM_ALT_SINIR_GB = 1.0
YONTEMLER = ["pandas_tum", "pandas_secili", "spark"]
VERI_SETLERI = ["100k", "1m", "1ay", "2ay", "3ay", "20m", "30m", "60m"]
KOPYA_SAYISI = {"20m": 2, "30m": 3, "60m": 6}  # bu setler 3ay verisinin kac kopyasindan olusuyor

# Analizlerde kullanilan sutunlar (pandas_secili sadece bunlari okur)
GEREKLI_SUTUNLAR = [
    "pickup_hour", "pickup_dayofweek", "PU_Borough", "PULocationID", "payment_type",
    "fare_amount", "tip_amount", "trip_distance", "trip_duration_min", "avg_speed_mph",
]


# --------------------------------------------------------------------------------------
# Analiz isleri. Iki tarafta da AYNI 4 soru soruluyor:
#   1) Saat bazinda yolculuk sayisi ve ortalama ucret
#   2) Bolge ve odeme turune gore ortalama bahsis
#   3) 10 milden uzun yolculuklarin en cok basladigi 10 bolge
#   4) Haftanin gunune gore ortalama hiz ve sure
# Her fonksiyon toplam satir sayisini dondurur; iki yontemin ayni veriyi isledigini kontrol icin.
# --------------------------------------------------------------------------------------

def pandas_isleri(dosya, sutunlar):
    import pandas as pd

    df = pd.read_parquet(dosya, columns=sutunlar)

    saatlik = df.groupby("pickup_hour").agg(sayi=("fare_amount", "size"), ort_ucret=("fare_amount", "mean"))
    df.groupby(["PU_Borough", "payment_type"])["tip_amount"].mean()
    df[df["trip_distance"] > 10].groupby("PULocationID").size().nlargest(10)
    df.groupby("pickup_dayofweek")[["avg_speed_mph", "trip_duration_min"]].mean()

    return int(saatlik["sayi"].sum())


def spark_isleri(spark, dosya):
    from pyspark.sql import functions as F

    df = spark.read.parquet(dosya)

    # Spark "tembel" (lazy) calisir: collect() denene kadar hicbir hesap yapilmaz.
    # Bu yuzden her sorgunun sonunda collect() ile sonucu istiyoruz, yoksa sureyi olcemeyiz.
    saatlik = df.groupBy("pickup_hour").agg(F.count("*").alias("sayi"), F.avg("fare_amount")).collect()
    df.groupBy("PU_Borough", "payment_type").agg(F.avg("tip_amount")).collect()
    (df.filter(F.col("trip_distance") > 10).groupBy("PULocationID").count()
       .orderBy(F.desc("count")).limit(10).collect())
    df.groupBy("pickup_dayofweek").agg(F.avg("avg_speed_mph"), F.avg("trip_duration_min")).collect()

    return sum(r["sayi"] for r in saatlik)


def isci(yontem, dosya):
    # Alt surecte calisan kisim. Sonucu JSON olarak ekrana yazar, ana script okur.
    sonuc = {}
    if yontem == "spark":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        bas = time.perf_counter()
        from spark_baslat import spark_olustur
        spark = spark_olustur("benchmark")
        # Dosyalar pandas ile yazildi, pandas tarihleri nanosaniye (TIMESTAMP(NANOS)) olarak sakliyor.
        # Spark bu tipi okuyamiyor; bu ayarla tarih sutunlari sayi (long) olarak okunur.
        # Analizlerde tarih sutunu kullanmadigimiz icin sonucu etkilemiyor.
        spark.conf.set("spark.sql.legacy.parquet.nanosAsLong", "true")
        sonuc["baslatma_sn"] = time.perf_counter() - bas  # Spark'in ayaga kalkma suresi, ayrica raporlanir
        bas = time.perf_counter()
        sonuc["satir"] = spark_isleri(spark, dosya)
        sonuc["sure_sn"] = time.perf_counter() - bas
        spark.stop()
    else:
        sutunlar = GEREKLI_SUTUNLAR if yontem == "pandas_secili" else None
        bas = time.perf_counter()
        sonuc["satir"] = pandas_isleri(dosya, sutunlar)
        sonuc["sure_sn"] = time.perf_counter() - bas
    print("SONUC " + json.dumps(sonuc))


# --------------------------------------------------------------------------------------
# Ana script: veri setlerini hazirlar, her olcum icin bir alt surec acar ve izler
# --------------------------------------------------------------------------------------

def buyuk_setleri_hazirla():
    # 3ay verisini dosyaya birden fazla kez art arda yazarak 20M, 30M ve 60M satirlik setler olusturur.
    # Dosyayi parca parca (batch) okuyup yaziyoruz, boylece tamami hic RAM'e alinmiyor.
    import pyarrow.parquet as pq

    kaynak_yolu = f"{ORNEKLEM}/yellow_3ay.parquet"
    for ad, kopya in KOPYA_SAYISI.items():
        hedef = f"{ORNEKLEM}/yellow_{ad}.parquet"
        if os.path.exists(hedef):
            continue
        kaynak = pq.ParquetFile(kaynak_yolu)
        with pq.ParquetWriter(hedef, kaynak.schema_arrow) as yazici:
            for _ in range(kopya):
                for parca in kaynak.iter_batches(batch_size=1_000_000):
                    yazici.write_batch(parca)
        print(f"olusturuldu: yellow_{ad} ({pq.ParquetFile(hedef).metadata.num_rows:,} satir)")


def olcum_yap(yontem, dosya):
    # Alt sureci baslatir, calisirken her 0,2 saniyede bir RAM kullanimina bakar.
    # Spark'ta asil isi Java (JVM) yaptigi icin alt surecin cocuk sureclerini de topluyoruz.
    import psutil

    surec = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--isci", yontem, dosya],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    durum = {"tepe_ram_mb": 0.0, "bellek_yetmedi": False}

    def izle():
        p = psutil.Process(surec.pid)
        while surec.poll() is None:
            try:
                ram = p.memory_info().rss + sum(c.memory_info().rss for c in p.children(recursive=True))
            except psutil.Error:
                break
            durum["tepe_ram_mb"] = max(durum["tepe_ram_mb"], ram / 1024 ** 2)
            if psutil.virtual_memory().available / 1024 ** 3 < BOS_RAM_ALT_SINIR_GB:
                durum["bellek_yetmedi"] = True
                for c in p.children(recursive=True):
                    c.kill()
                p.kill()
                break
            time.sleep(0.2)

    izleyici = threading.Thread(target=izle)
    izleyici.start()
    try:
        cikti, _ = surec.communicate(timeout=ZAMAN_ASIMI_SN)
    except subprocess.TimeoutExpired:
        surec.kill()
        cikti, _ = surec.communicate()
        durum["durum"] = "zaman asimi"
    izleyici.join()

    sonuc_satiri = [s for s in cikti.splitlines() if s.startswith("SONUC ")]
    if durum["bellek_yetmedi"]:
        durum["durum"] = "bellek yetmedi"
    elif sonuc_satiri:
        durum.update(json.loads(sonuc_satiri[0][6:]))
        durum["durum"] = "tamam"
    elif "durum" not in durum:
        durum["durum"] = "hata"
    return durum


def grafik_ciz(df):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tamam = df[df["durum"] == "tamam"]
    ozet = tamam.groupby(["yontem", "satir"])[["sure_sn", "tepe_ram_mb"]].median().reset_index()

    fig, eksen = plt.subplots(1, 2, figsize=(13, 4.8))
    for yontem in YONTEMLER:
        y = ozet[ozet["yontem"] == yontem]
        eksen[0].plot(y["satir"] / 1e6, y["sure_sn"], "o-", label=yontem)
        cizgi, = eksen[1].plot(y["satir"] / 1e6, y["tepe_ram_mb"] / 1024, "o-", label=yontem)
        # Bellek yetmeyen noktayi, yontemin kendi renginde X ile isaretle
        basarisiz = df[(df["yontem"] == yontem) & (df["durum"] == "bellek yetmedi")]
        if len(basarisiz):
            x = basarisiz["satir"].min() / 1e6
            y_ram = basarisiz["tepe_ram_mb"].max() / 1024
            eksen[1].plot(x, y_ram, "x", color=cizgi.get_color(), markersize=12, mew=3)
            eksen[1].annotate("bellek yetmedi", (x, y_ram), textcoords="offset points", xytext=(-35, -20),
                              color=cizgi.get_color(), fontsize=8)

    eksen[0].set_title("Analiz suresi (okuma + 4 sorgu)")
    eksen[0].set_ylabel("saniye")
    eksen[1].set_title("Tepe RAM kullanimi")
    eksen[1].set_ylabel("GB")
    for e in eksen:
        e.set_xscale("log")
        e.set_yscale("log")
        e.set_xlabel("milyon satir (log olcek)")
        e.grid(alpha=0.3, which="both")
        e.legend()
    fig.tight_layout()
    fig.savefig(SONUC_PNG, dpi=120)


def rapor_yaz(df):
    import psutil

    r = ["# Pandas vs PySpark Benchmark\n"]
    r.append(f"Her olcum ayri bir Python surecinde {TEKRAR} kez yapildi, tabloda ortanca (medyan) deger var. "
             "Sure = dosyayi okuma + 4 analiz sorgusu. Spark icin ayrica oturum baslatma suresi verildi. "
             "Tepe RAM = olcum boyunca surecin (Spark'ta Java dahil) ulastigi en yuksek bellek.\n")
    r.append(f"Bilgisayar: {psutil.virtual_memory().total / 1024 ** 3:.0f} GB RAM, "
             f"{psutil.cpu_count()} mantiksal cekirdek. Bos RAM {BOS_RAM_ALT_SINIR_GB} GB'in altina "
             "inerse olcum durduruldu ve 'bellek yetmedi' yazildi. 20M, 30M ve 60M setleri "
             "3ay verisinin 2, 3 ve 6 kopyasidir; sadece performans olcumu icindir, analiz sonucu cikarilmaz.\n")

    r.append("| Satir | Yontem | Sure (sn) | Tepe RAM (GB) | Spark baslatma (sn) | Durum |")
    r.append("|---|---|---|---|---|---|")
    for (satir, yontem), g in df.groupby(["satir", "yontem"], sort=True):
        t = g[g["durum"] == "tamam"]
        if len(t):
            bas = f"{t['baslatma_sn'].median():.1f}" if yontem == "spark" else "-"
            r.append(f"| {satir:,} | {yontem} | {t['sure_sn'].median():.2f} | "
                     f"{t['tepe_ram_mb'].median() / 1024:.2f} | {bas} | tamam |")
        else:
            r.append(f"| {satir:,} | {yontem} | - | - | - | {g['durum'].iloc[0]} |")

    r.append("\n![grafikler](../results/pandas_spark_benchmark.png)\n")
    with open(RAPOR, "w", encoding="utf-8") as f:
        f.write("\n".join(r))


def ana():
    import pandas as pd
    import pyarrow.parquet as pq

    os.makedirs("results", exist_ok=True)
    baslangic = time.time()
    buyuk_setleri_hazirla()

    satirlar = []
    basarisiz_yontemler = set()  # bir boyutta bellegi yetmeyen yontem daha buyuk boyutta denenmez
    for ad in VERI_SETLERI:
        dosya = f"{ORNEKLEM}/yellow_{ad}.parquet"
        satir = pq.ParquetFile(dosya).metadata.num_rows
        print(f"\n== {ad}: {satir:,} satir ==")
        for yontem in YONTEMLER:
            if yontem in basarisiz_yontemler:
                satirlar.append({"veri_seti": ad, "satir": satir, "yontem": yontem, "tekrar": 1,
                                 "durum": "atlandi (kucuk boyutta basarisiz)"})
                print(f"  {yontem:<14} atlandi")
                continue
            for i in range(1, TEKRAR + 1):
                o = olcum_yap(yontem, dosya)
                satirlar.append({"veri_seti": ad, "satir": satir, "yontem": yontem, "tekrar": i, **o})
                if o["durum"] != "tamam":
                    print(f"  {yontem:<14} {o['durum']} (tepe RAM {o['tepe_ram_mb'] / 1024:.1f} GB)")
                    basarisiz_yontemler.add(yontem)
                    break
                # Kontrol: islenen satir sayisi dosyadaki satir sayisina esit olmali
                assert o["satir"] == satir, f"{yontem} {o['satir']} satir isledi, beklenen {satir}"
                print(f"  {yontem:<14} {o['sure_sn']:7.2f} sn, tepe RAM {o['tepe_ram_mb'] / 1024:5.2f} GB")

    df = pd.DataFrame(satirlar)
    df.to_csv(SONUC_CSV, index=False)
    grafik_ciz(df)
    rapor_yaz(df)
    print(f"\nbitti, toplam {time.time() - baslangic:.0f} sn. Rapor: {RAPOR}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--isci":
        isci(sys.argv[2], sys.argv[3])
    else:
        ana()
