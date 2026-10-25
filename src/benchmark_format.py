# CSV ve Parquet formatlarini farkli veri boyutlarinda karsilastirir.
#
# Her veri boyutu icin olculenler:
#   - Disk boyutu (MB)
#   - Yazma suresi (pandas ile diske yazmak)
#   - Okuma suresi, tum sutunlar
#   - Okuma suresi, sadece 3 sutun (Parquet'in sutun bazli okuma avantajini gormek icin)
#
# Veri boyutlari: 100 bin, 1 milyon, 3,5M (1ay), 6,7M (2ay), 10,5M (3ay) satir.
# 100 bin ve 1 milyonluk setler 1ay verisinden rastgele ornekleme ile olusturulur.
#
# Ciktilar:
#   results/format_benchmark.csv      ham olcumler (her tekrar ayri satir)
#   results/format_benchmark.png      grafikler
#   docs/benchmark_format.md          rapor
#
# Kullanim: python src/benchmark_format.py  (once src/orneklem_olustur.py calismis olmali)

import gc
import os
import shutil
import statistics
import time

import matplotlib
matplotlib.use("Agg")  # pencere acmadan dogrudan dosyaya ciz
import matplotlib.pyplot as plt
import pandas as pd

ORNEKLEM = "data/samples"
GECICI = "data/samples/_benchmark_gecici"  # yazma testinde olusan dosyalar, sonda silinir
SONUC_CSV = "results/format_benchmark.csv"
SONUC_PNG = "results/format_benchmark.png"
RAPOR = "docs/benchmark_format.md"

TEKRAR = 3  # her olcum 3 kez yapilir, ortanca (medyan) deger alinir
SECILI_SUTUNLAR = ["trip_distance", "fare_amount", "pickup_hour"]

# CSV duz metin oldugu icin tarih sutunlari okununca yazi (string) olarak gelir.
# Adil bir karsilastirma icin CSV okurken tarihleri tekrar tarihe ceviriyoruz,
# cunku Parquet bu tipleri zaten dosyanin icinde sakliyor.
TARIH_SUTUNLARI = ["tpep_pickup_datetime", "tpep_dropoff_datetime"]

VERI_SETLERI = [
    # (ad, satir sayisi; None = dosyanin tamami)
    ("100k", 100_000),
    ("1m", 1_000_000),
    ("1ay", None),
    ("2ay", None),
    ("3ay", None),
]


def mb(yol):
    return os.path.getsize(yol) / 1024 ** 2


def sure_olc(islem):
    # Islemi TEKRAR kez calistirip her birinin suresini saniye olarak dondurur.
    # gc.collect(): bir onceki turdan kalan veriyi bellekten temizle ki olcumu etkilemesin.
    sureler = []
    for _ in range(TEKRAR):
        gc.collect()
        bas = time.perf_counter()
        sonuc = islem()
        sureler.append(time.perf_counter() - bas)
        del sonuc
    return sureler


def kucuk_setleri_hazirla():
    # 100 bin ve 1 milyon satirlik setleri 1ay verisinden rastgele secerek olustur.
    # random_state sabit: her calistirmada ayni satirlar secilsin (tekrarlanabilirlik).
    eksik = [(ad, n) for ad, n in VERI_SETLERI
             if n is not None and not os.path.exists(f"{ORNEKLEM}/yellow_{ad}.parquet")]
    if not eksik:
        return
    kaynak = pd.read_parquet(f"{ORNEKLEM}/yellow_1ay.parquet")
    for ad, n in eksik:
        parca = kaynak.sample(n=n, random_state=42).sort_values("tpep_pickup_datetime")
        parca.to_parquet(f"{ORNEKLEM}/yellow_{ad}.parquet", index=False)
        parca.to_csv(f"{ORNEKLEM}/yellow_{ad}.csv", index=False)
        print(f"olusturuldu: yellow_{ad} ({n:,} satir)")
    del kaynak


def veri_setini_olc(ad):
    parquet_yolu = f"{ORNEKLEM}/yellow_{ad}.parquet"
    csv_yolu = f"{ORNEKLEM}/yellow_{ad}.csv"

    # Yazma testi icin veriyi bir kez bellege al
    df = pd.read_parquet(parquet_yolu)
    satir = len(df)
    print(f"\n== {ad}: {satir:,} satir ==")

    olcumler = {
        "csv_yaz": sure_olc(lambda: df.to_csv(f"{GECICI}/test.csv", index=False)),
        "parquet_yaz": sure_olc(lambda: df.to_parquet(f"{GECICI}/test.parquet", index=False)),
    }
    del df

    olcumler["csv_oku_tum"] = sure_olc(lambda: pd.read_csv(csv_yolu, parse_dates=TARIH_SUTUNLARI))
    olcumler["parquet_oku_tum"] = sure_olc(lambda: pd.read_parquet(parquet_yolu))
    # CSV'de usecols olsa bile dosyanin tamami satir satir taranir, sadece istenmeyen sutunlar atilir.
    # Parquet'te ise diger sutunlarin bulundugu kisimlara hic dokunulmaz.
    olcumler["csv_oku_3sutun"] = sure_olc(lambda: pd.read_csv(csv_yolu, usecols=SECILI_SUTUNLAR))
    olcumler["parquet_oku_3sutun"] = sure_olc(lambda: pd.read_parquet(parquet_yolu, columns=SECILI_SUTUNLAR))

    satirlar = []
    for islem, sureler in olcumler.items():
        for i, s in enumerate(sureler, 1):
            satirlar.append({"veri_seti": ad, "satir": satir, "islem": islem, "tekrar": i, "sure_sn": s})
        print(f"  {islem:<20} medyan {statistics.median(sureler):7.2f} sn")

    boyut = {"veri_seti": ad, "satir": satir, "csv_mb": mb(csv_yolu), "parquet_mb": mb(parquet_yolu)}
    return satirlar, boyut


def grafik_ciz(ozet, boyutlar):
    fig, eksen = plt.subplots(1, 3, figsize=(16, 4.5))
    x = ozet.index / 1e6  # milyon satir

    eksen[0].plot(x, boyutlar["csv_mb"], "o-", label="CSV")
    eksen[0].plot(x, boyutlar["parquet_mb"], "o-", label="Parquet")
    eksen[0].set_title("Disk boyutu")
    eksen[0].set_ylabel("MB")

    eksen[1].plot(x, ozet["csv_oku_tum"], "o-", label="CSV - tum sutunlar")
    eksen[1].plot(x, ozet["parquet_oku_tum"], "o-", label="Parquet - tum sutunlar")
    eksen[1].plot(x, ozet["csv_oku_3sutun"], "s--", label="CSV - 3 sutun")
    eksen[1].plot(x, ozet["parquet_oku_3sutun"], "s--", label="Parquet - 3 sutun")
    eksen[1].set_title("Okuma suresi (pandas)")
    eksen[1].set_ylabel("saniye")

    eksen[2].plot(x, ozet["csv_yaz"], "o-", label="CSV")
    eksen[2].plot(x, ozet["parquet_yaz"], "o-", label="Parquet")
    eksen[2].set_title("Yazma suresi (pandas)")
    eksen[2].set_ylabel("saniye")

    for e in eksen:
        e.set_xlabel("milyon satir")
        e.grid(alpha=0.3)
        e.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(SONUC_PNG, dpi=120)


def rapor_yaz(ozet, boyutlar):
    r = ["# CSV vs Parquet Benchmark\n"]
    r.append(f"Her olcum {TEKRAR} kez yapildi, tabloda ortanca (medyan) sure var. Okuma ve yazma pandas ile yapildi. "
             f"3 sutun: `{', '.join(SECILI_SUTUNLAR)}`.\n")

    r.append("## Disk boyutu\n")
    r.append("| Veri seti | Satir | CSV (MB) | Parquet (MB) | CSV / Parquet |")
    r.append("|---|---|---|---|---|")
    for satir, b in boyutlar.iterrows():
        r.append(f"| {b['veri_seti']} | {satir:,} | {b['csv_mb']:.1f} | {b['parquet_mb']:.1f} | "
                 f"{b['csv_mb'] / b['parquet_mb']:.1f}x |")

    r.append("\n## Sureler (saniye)\n")
    r.append("| Satir | CSV yaz | Parquet yaz | CSV oku (tum) | Parquet oku (tum) | Hiz farki | "
             "CSV oku (3 sutun) | Parquet oku (3 sutun) | Hiz farki |")
    r.append("|---|---|---|---|---|---|---|---|---|")
    for satir, o in ozet.iterrows():
        r.append(f"| {satir:,} | {o['csv_yaz']:.2f} | {o['parquet_yaz']:.2f} | "
                 f"{o['csv_oku_tum']:.2f} | {o['parquet_oku_tum']:.2f} | "
                 f"{o['csv_oku_tum'] / o['parquet_oku_tum']:.1f}x | "
                 f"{o['csv_oku_3sutun']:.2f} | {o['parquet_oku_3sutun']:.2f} | "
                 f"{o['csv_oku_3sutun'] / o['parquet_oku_3sutun']:.1f}x |")

    r.append("\n![grafikler](../results/format_benchmark.png)\n")

    with open(RAPOR, "w", encoding="utf-8") as f:
        f.write("\n".join(r))


if __name__ == "__main__":
    os.makedirs(GECICI, exist_ok=True)
    os.makedirs("results", exist_ok=True)
    baslangic = time.time()

    kucuk_setleri_hazirla()

    tum_olcumler, boyutlar = [], []
    for ad, _ in VERI_SETLERI:
        satirlar, boyut = veri_setini_olc(ad)
        tum_olcumler += satirlar
        boyutlar.append(boyut)

    shutil.rmtree(GECICI)

    olcum_df = pd.DataFrame(tum_olcumler)
    olcum_df.to_csv(SONUC_CSV, index=False)

    # Her veri boyutu ve islem icin 3 tekrarin ortancasi: satirlar = veri boyutu, sutunlar = islem
    ozet = olcum_df.pivot_table(index="satir", columns="islem", values="sure_sn", aggfunc="median")
    boyut_df = pd.DataFrame(boyutlar).set_index("satir")

    grafik_ciz(ozet, boyut_df)
    rapor_yaz(ozet, boyut_df)
    print(f"\nbitti, toplam {time.time() - baslangic:.0f} sn. Rapor: {RAPOR}")
