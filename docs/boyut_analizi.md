# Veri Buyuklugu Analizi

Ayni ham veri uc farkli halde olculdu. 1 MB = 1024 x 1024 bayt alindi.

| Dosya | Satir | Parquet (MB) | CSV (MB) | Pandas RAM (MB) | CSV / Parquet | RAM / Parquet |
|---|---|---|---|---|---|---|
| yellow_tripdata_2026-01.parquet | 3,724,889 | 61 | 383 | 648 | 6.3x | 10.6x |
| yellow_tripdata_2026-02.parquet | 3,399,866 | 56 | 349 | 591 | 6.2x | 10.6x |
| yellow_tripdata_2026-03.parquet | 3,952,451 | 65 | 409 | 693 | 6.3x | 10.7x |
| **Toplam** | **11,077,206** | **182** | **1141** | **1931** | **6.3x** | **10.6x** |

Parquet dosya bilgisi:

- yellow_tripdata_2026-01.parquet: 4 row group, sikistirma ZSTD
- yellow_tripdata_2026-02.parquet: 4 row group, sikistirma ZSTD
- yellow_tripdata_2026-03.parquet: 4 row group, sikistirma ZSTD

Pandas'ta bir satir ortalama **183 bayt** RAM tutuyor. Buna gore tahmini RAM ihtiyaci:

| Veri | Satir (yaklasik) | Pandas RAM |
|---|---|---|
| 1 ay | 3.7 milyon | 0.6 GB |
| 3 ay (bizim veri) | 11.1 milyon | 1.9 GB |
| 1 yil | 44.3 milyon | 7.5 GB |
| 5 yil | 221.5 milyon | 37.7 GB |
