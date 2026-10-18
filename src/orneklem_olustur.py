# Temiz veriden benchmark deneyleri icin 3 farkli buyuklukte veri seti olusturur:
#   1ay: sadece Ocak
#   2ay: Ocak + Subat
#   3ay: Ocak + Subat + Mart
# Her biri hem Parquet hem CSV olarak data/samples/ klasorune yazilir.
# Kullanim: python src/orneklem_olustur.py  (once src/temizle.py calismis olmali)

import os
import pandas as pd

KAYNAK = "data/processed/parquet"
HEDEF = "data/samples"
AYLAR = ["2026-01", "2026-02", "2026-03"]

os.makedirs(HEDEF, exist_ok=True)
satirlar = ["# Benchmark Veri Setleri\n"]
satirlar.append("Temiz veriden aylar birikimli eklenerek olusturuldu. Kucuk set buyugun icinde "
                "(1ay, 2ay'in ilk kismi; 2ay, 3ay'in ilk kismi).\n")
satirlar.append("| Veri seti | Aylar | Satir | Parquet (MB) | CSV (MB) |")
satirlar.append("|---|---|---|---|---|")

parcalar = []
for i, ay in enumerate(AYLAR, 1):
    # Her turda bir ay daha ekliyoruz: 1. turda Ocak, 2. turda Ocak+Subat, 3. turda hepsi
    parcalar.append(pd.read_parquet(f"{KAYNAK}/yellow_temiz_{ay}.parquet"))
    veri = pd.concat(parcalar, ignore_index=True)

    ad = f"{i}ay"
    parquet_yolu = f"{HEDEF}/yellow_{ad}.parquet"
    csv_yolu = f"{HEDEF}/yellow_{ad}.csv"
    veri.to_parquet(parquet_yolu, index=False)
    veri.to_csv(csv_yolu, index=False)

    parquet_mb = os.path.getsize(parquet_yolu) / 1024 ** 2
    csv_mb = os.path.getsize(csv_yolu) / 1024 ** 2
    print(f"{ad} ({', '.join(AYLAR[:i])}): {len(veri):,} satir, parquet {parquet_mb:.1f} MB, csv {csv_mb:.1f} MB")
    satirlar.append(f"| {ad} | {' + '.join(AYLAR[:i])} | {len(veri):,} | {parquet_mb:.1f} | {csv_mb:.1f} |")
    del veri

satirlar.append("\nDosyalar: `data/samples/yellow_<1ay|2ay|3ay>.parquet` ve `.csv`\n")
with open("docs/orneklemler.md", "w", encoding="utf-8") as f:
    f.write("\n".join(satirlar))
