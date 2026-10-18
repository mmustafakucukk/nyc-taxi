# Ayni verinin uc farkli halde ne kadar yer kapladigini olcer:
#   1) Parquet dosyasi (diskte, sikistirilmis, sutun tabanli)
#   2) CSV dosyasi (diskte, duz metin, satir tabanli)
#   3) Pandas DataFrame (RAM'de)
# Sonuclar docs/boyut_analizi.md dosyasina yazilir.
# Kullanim: python src/boyut_analizi.py

import glob
import os
import pandas as pd
import pyarrow.parquet as pq

CSV_KLASOR = "data/raw/csv"  # ham verinin CSV kopyasi, .gitignore sayesinde GitHub'a gitmez
MB = 1024 * 1024

os.makedirs(CSV_KLASOR, exist_ok=True)

sonuclar = []
for parquet_yolu in sorted(glob.glob("data/raw/yellow_tripdata_*.parquet")):
    dosya_adi = os.path.basename(parquet_yolu)
    print("isleniyor:", dosya_adi)

    # Parquet dosyasinin icinde satir sayisi ve sikistirma bilgisi hazir duruyor (metadata),
    # bunlari ogrenmek icin veriyi okumaya gerek yok.
    meta = pq.ParquetFile(parquet_yolu).metadata
    sikistirma = meta.row_group(0).column(0).compression

    df = pd.read_parquet(parquet_yolu)
    # deep=True: metin sutunlarindaki Python nesnelerinin gercek boyutunu da sayar
    ram_mb = df.memory_usage(deep=True).sum() / MB

    csv_yolu = os.path.join(CSV_KLASOR, dosya_adi.replace(".parquet", ".csv"))
    if not os.path.exists(csv_yolu):
        df.to_csv(csv_yolu, index=False)

    sonuclar.append({
        "dosya": dosya_adi,
        "satir": meta.num_rows,
        "row_group": meta.num_row_groups,
        "sikistirma": sikistirma,
        "parquet_mb": os.path.getsize(parquet_yolu) / MB,
        "csv_mb": os.path.getsize(csv_yolu) / MB,
        "ram_mb": ram_mb,
    })
    del df  # bir sonraki aya gecmeden bellegi bosalt

tablo = pd.DataFrame(sonuclar)
toplam = tablo[["satir", "parquet_mb", "csv_mb", "ram_mb"]].sum()

satirlar = ["# Veri Buyuklugu Analizi\n"]
satirlar.append("Ayni ham veri uc farkli halde olculdu. 1 MB = 1024 x 1024 bayt alindi.\n")
satirlar.append("| Dosya | Satir | Parquet (MB) | CSV (MB) | Pandas RAM (MB) | CSV / Parquet | RAM / Parquet |")
satirlar.append("|---|---|---|---|---|---|---|")
for _, r in tablo.iterrows():
    satirlar.append(
        f"| {r['dosya']} | {r['satir']:,} | {r['parquet_mb']:.0f} | {r['csv_mb']:.0f} | {r['ram_mb']:.0f} "
        f"| {r['csv_mb'] / r['parquet_mb']:.1f}x | {r['ram_mb'] / r['parquet_mb']:.1f}x |"
    )
satirlar.append(
    f"| **Toplam** | **{int(toplam['satir']):,}** | **{toplam['parquet_mb']:.0f}** | **{toplam['csv_mb']:.0f}** "
    f"| **{toplam['ram_mb']:.0f}** | **{toplam['csv_mb'] / toplam['parquet_mb']:.1f}x** "
    f"| **{toplam['ram_mb'] / toplam['parquet_mb']:.1f}x** |"
)

satirlar.append("\nParquet dosya bilgisi:\n")
for _, r in tablo.iterrows():
    satirlar.append(f"- {r['dosya']}: {r['row_group']} row group, sikistirma {r['sikistirma']}")

# Bir satirin RAM'de ortalama kac bayt tuttugunu bulup daha buyuk veri icin kaba tahmin yapiyoruz.
bayt_satir = toplam["ram_mb"] * MB / toplam["satir"]
satirlar.append(f"\nPandas'ta bir satir ortalama **{bayt_satir:.0f} bayt** RAM tutuyor. Buna gore tahmini RAM ihtiyaci:\n")
satirlar.append("| Veri | Satir (yaklasik) | Pandas RAM |")
satirlar.append("|---|---|---|")
aylik_satir = toplam["satir"] / len(tablo)
for etiket, ay in [("1 ay", 1), ("3 ay (bizim veri)", 3), ("1 yil", 12), ("5 yil", 60)]:
    satir_sayisi = aylik_satir * ay
    satirlar.append(f"| {etiket} | {satir_sayisi / 1e6:.1f} milyon | {satir_sayisi * bayt_satir / (1024 ** 3):.1f} GB |")

metin = "\n".join(satirlar) + "\n"
print(metin)
with open("docs/boyut_analizi.md", "w", encoding="utf-8") as f:
    f.write(metin)
