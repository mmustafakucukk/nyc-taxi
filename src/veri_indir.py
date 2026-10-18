# NYC TLC sitesinden projede kullandigimiz ham veriyi indirir.
# Kullanim: python src/veri_indir.py
# Dosya zaten data/raw icindeyse tekrar indirmez.

import os
import urllib.request

AYLAR = ["2026-01", "2026-02", "2026-03"]
TLC_URL = "https://d37ci6vzurychx.cloudfront.net"
HEDEF_KLASOR = "data/raw"


def indir(url, dosya_yolu):
    if os.path.exists(dosya_yolu):
        print("zaten var, atlandi:", dosya_yolu)
        return
    print("indiriliyor:", url)
    urllib.request.urlretrieve(url, dosya_yolu)
    boyut_mb = os.path.getsize(dosya_yolu) / (1024 * 1024)
    print(f"  tamam ({boyut_mb:.1f} MB)")


os.makedirs(HEDEF_KLASOR, exist_ok=True)

for ay in AYLAR:
    dosya_adi = f"yellow_tripdata_{ay}.parquet"
    indir(f"{TLC_URL}/trip-data/{dosya_adi}", os.path.join(HEDEF_KLASOR, dosya_adi))

# bolge kodlarini (1-265) isme ceviren tablo
indir(f"{TLC_URL}/misc/taxi_zone_lookup.csv", os.path.join(HEDEF_KLASOR, "taxi_zone_lookup.csv"))
