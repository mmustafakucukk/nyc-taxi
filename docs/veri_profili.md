# Ham Veri Profili (Ocak-Mart 2026)

Toplam satir: **11,077,206**, sutun sayisi: **20**

## Sutunlar

| Sutun | Tip | Bos | Bos % | Min | Max |
|---|---|---|---|---|---|
| VendorID | int | 0 | 0.0 | 1 | 7 |
| tpep_pickup_datetime | timestamp_ntz | 0 | 0.0 | 2008-12-31 23:03:20 | 2026-04-01 00:06:25 |
| tpep_dropoff_datetime | timestamp_ntz | 0 | 0.0 | 2009-01-01 00:07:36 | 2026-04-02 16:03:47 |
| passenger_count | bigint | 3,057,123 | 27.6 | 0 | 9 |
| trip_distance | double | 0 | 0.0 | 0.0 | 328522.2 |
| RatecodeID | bigint | 3,057,123 | 27.6 | 1 | 99 |
| store_and_fwd_flag | string | 3,057,123 | 27.6 | N | Y |
| PULocationID | int | 0 | 0.0 | 1 | 265 |
| DOLocationID | int | 0 | 0.0 | 1 | 265 |
| payment_type | bigint | 0 | 0.0 | 0 | 4 |
| fare_amount | double | 0 | 0.0 | -2555.2 | 2555.2 |
| extra | double | 0 | 0.0 | -7.5 | 20.71 |
| mta_tax | double | 0 | 0.0 | -0.5 | 4.75 |
| tip_amount | double | 0 | 0.0 | -88.88 | 766.0 |
| tolls_amount | double | 0 | 0.0 | -111.79 | 1400.0 |
| improvement_surcharge | double | 0 | 0.0 | -1.0 | 1.0 |
| total_amount | double | 0 | 0.0 | -2560.2 | 2560.2 |
| congestion_surcharge | double | 3,057,123 | 27.6 | -2.5 | 2.5 |
| Airport_fee | double | 3,057,123 | 27.6 | -2.0 | 27.0 |
| cbd_congestion_fee | double | 0 | 0.0 | -0.75 | 0.75 |

## VendorID dagilimi

| Deger | Yolculuk | % |
|---|---|---|
| 2 | 8,811,934 | 79.6 |
| 1 | 2,112,458 | 19.1 |
| 7 | 133,742 | 1.2 |
| 6 | 19,072 | 0.2 |

## payment_type dagilimi

| Deger | Yolculuk | % |
|---|---|---|
| 1 | 6,910,238 | 62.4 |
| 0 | 3,057,123 | 27.6 |
| 2 | 941,200 | 8.5 |
| 4 | 126,778 | 1.1 |
| 3 | 41,867 | 0.4 |

## RatecodeID dagilimi

| Deger | Yolculuk | % |
|---|---|---|
| 1 | 7,272,171 | 65.6 |
| None | 3,057,123 | 27.6 |
| 99 | 351,152 | 3.2 |
| 2 | 247,859 | 2.2 |
| 5 | 91,009 | 0.8 |
| 3 | 34,208 | 0.3 |
| 4 | 23,676 | 0.2 |
| 6 | 8 | 0.0 |

## Yuzdelik dilimler

| Sutun | p1 | p25 | p50 | p75 | p99 | p99.9 |
|---|---|---|---|---|---|---|
| trip_distance | 0.00 | 1.00 | 1.80 | 3.70 | 19.51 | 29.79 |
| sure_dk | 0.00 | 8.15 | 13.53 | 21.53 | 73.17 | 124.35 |
| fare_amount | 3.00 | 10.00 | 15.60 | 26.80 | 81.10 | 142.30 |
| total_amount | 7.00 | 17.25 | 23.55 | 34.71 | 104.95 | 172.45 |
| passenger_count | 1.00 | 1.00 | 1.00 | 1.00 | 4.00 | 6.00 |

Ocak-Mart 2026 disinda baslayan yolculuk: **10**


_Script calisma suresi: 36.4 sn_
