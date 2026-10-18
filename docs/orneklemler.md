# Benchmark Veri Setleri

Temiz veriden aylar birikimli eklenerek olusturuldu. Kucuk set buyugun icinde (1ay, 2ay'in ilk kismi; 2ay, 3ay'in ilk kismi).

| Veri seti | Aylar | Satir | Parquet (MB) | CSV (MB) |
|---|---|---|---|---|
| 1ay | 2026-01 | 3,504,231 | 108.3 | 728.1 |
| 2ay | 2026-01 + 2026-02 | 6,703,593 | 206.9 | 1392.5 |
| 3ay | 2026-01 + 2026-02 + 2026-03 | 10,452,582 | 322.4 | 2174.1 |

Dosyalar: `data/samples/yellow_<1ay|2ay|3ay>.parquet` ve `.csv`
