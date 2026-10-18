# Veri Sozlugu - NYC Yellow Taxi (Ocak-Mart 2026)

Kaynak: NYC TLC, *Data Dictionary - Yellow Taxi Trip Records* (18 Mart 2025 surumu)
https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf

Sayilar `src/veri_profili.py` ile 3 ayin ham verisinden hesaplandi (ayrintisi `docs/veri_profili.md`).

## Genel bilgi

- **Toplam:** 11.077.206 satir, 20 sutun. Her satir bir taksi yolculugu.
- **Birimler:** mesafe **mil** (1 mil = 1,609 km), ucretler **ABD dolari**.
- **Saat:** zaman sutunlari New York yerel saatinde, saat dilimi bilgisi yok (`timestamp_ntz`).
- **Kaynak:** Kayitlar taksimetreden (TPEP) otomatik geliyor. Yani anket degil makine kaydi,
  bu yuzden makine kaynakli hatalar da var (0 mil, eksi sure gibi).

## Ana tablo: yellow_tripdata_2026-XX.parquet

| Sutun | Aciklama | Tip | Bos % |
|---|---|---|---|
| VendorID | Kaydi gonderen taksimetre firmasi (kodlar asagida) | int | 0 |
| tpep_pickup_datetime | Taksimetrenin acildigi an (binis zamani) | timestamp | 0 |
| tpep_dropoff_datetime | Taksimetrenin kapandigi an (inis zamani) | timestamp | 0 |
| passenger_count | Yolcu sayisi. Surucu elle giriyor, guvenilirligi dusuk | bigint | 27.6 |
| trip_distance | Taksimetrenin olctugu mesafe (mil) | double | 0 |
| RatecodeID | Uygulanan tarife (kodlar asagida) | bigint | 27.6 |
| store_and_fwd_flag | Y = arac o an baglanti kuramadi, kayit sonradan gonderildi. N = normal | string | 27.6 |
| PULocationID | Binis bolgesi kodu (1-265), zone tablosuyla eslesir | int | 0 |
| DOLocationID | Inis bolgesi kodu (1-265) | int | 0 |
| payment_type | Odeme sekli (kodlar asagida) | bigint | 0 |
| fare_amount | Taksimetre ucreti: sure + mesafe, ekler haric ($) | double | 0 |
| extra | Ek ucretler: gece ve yogun saat zammi ($) | double | 0 |
| mta_tax | MTA toplu tasima vergisi, normalde 0,50 $ | double | 0 |
| tip_amount | Bahsis. Sadece kartla verilenler kaydediliyor, nakit bahsis gorunmez ($) | double | 0 |
| tolls_amount | Kopru/tunel gecis ucretleri ($) | double | 0 |
| improvement_surcharge | Sabit iyilestirme ucreti, 1 $ | double | 0 |
| total_amount | Yolcudan alinan toplam tutar, nakit bahsis haric ($) | double | 0 |
| congestion_surcharge | Manhattan trafik yogunlugu ek ucreti, 2,50 $ | double | 27.6 |
| Airport_fee | JFK ve LaGuardia binislerinde havalimani ucreti ($) | double | 27.6 |
| cbd_congestion_fee | Ocak 2025'te baslayan Manhattan merkez "Congestion Pricing" ucreti, 0,75 $ | double | 0 |

## Kodlu sutunlar

Bu sutunlardaki sayilar miktar degil kategori. Ortalamalarini almak anlamsiz.

**payment_type**

| Kod | Anlami | Yolculuk | % |
|---|---|---|---|
| 0 | Flex Fare (ucreti onceden belirlenen yolculuk) | 3.057.123 | 27.6 |
| 1 | Kredi karti | 6.910.238 | 62.4 |
| 2 | Nakit | 941.200 | 8.5 |
| 3 | Ucretsiz | 41.867 | 0.4 |
| 4 | Itirazli | 126.778 | 1.1 |
| 5 / 6 | Bilinmiyor / iptal | 0 | 0 |

**RatecodeID**

| Kod | Anlami | Yolculuk |
|---|---|---|
| 1 | Standart tarife | 7.272.171 |
| 2 | JFK havalimani sabit ucret | 247.859 |
| 3 | Newark havalimani | 34.208 |
| 4 | Nassau / Westchester (sehir disi) | 23.676 |
| 5 | Pazarlikli ucret | 91.009 |
| 6 | Grup yolculugu | 8 |
| 99 | Bilinmiyor | 351.152 |
| bos | Flex Fare satirlari | 3.057.123 |

**VendorID**

| Kod | Firma | Yolculuk |
|---|---|---|
| 1 | Creative Mobile Technologies | 2.112.458 |
| 2 | Curb Mobility | 8.811.934 |
| 6 | Myle Technologies | 19.072 |
| 7 | Helix | 133.742 |

## Bolge tablosu: taxi_zone_lookup.csv

265 satir. Ana tablodaki `PULocationID` ve `DOLocationID` bu tablonun `LocationID` sutunuyla JOIN edilir.

| Sutun | Aciklama |
|---|---|
| LocationID | Bolge kodu (1-265) |
| Borough | Ilce: Manhattan, Queens, Brooklyn, Bronx, Staten Island, EWR |
| Zone | Semt adi (orn. 132 = JFK Airport) |
| service_zone | Yellow Zone (Manhattan merkezi), Boro Zone (dis ilceler), Airports |

264 = "Unknown" ve 265 = "Outside of NYC" gercek bir semt degil.

## Onemli notlar

1. **%27,6'lik bosluk rastgele degil.** 5 sutun (passenger_count, RatecodeID, store_and_fwd_flag,
   congestion_surcharge, Airport_fee) ayni 3.057.123 satirda birlikte bos ve bu sayi
   payment_type = 0 (Flex Fare) sayisiyla birebir ayni. Bu yolculuklarda taksimetre bu alanlari
   gondermiyor ama mesafe, sure, bolge ve ucret dolu. Bu yuzden temizlikte `dropna()` ile
   bos satirlari toptan silmeyecegiz, yoksa verinin dortte birini kaybederiz.
2. **Ucs degerler var.** Mesafe 328.522 mile, ucret -2.555 $ ile +2.555 $ arasina kadar gidiyor.
   Ama %99'luk dilim mesafede 19,5 mil, surede 73 dk, ucrette 81 $. Yani bu degerler cok az
   sayida hatali kayittan geliyor. Temizlik esiklerini bu dilimlere bakarak secegiz.
3. **Tarih disi kayitlar.** 2008-2009 tarihli ve Nisan 2026'ya tasan 10 kayit var (arac saati hatasi).

## Temizlikte turetilecek sutunlar

| Sutun | Hesap | Neden |
|---|---|---|
| trip_duration_min | (inis - binis) dakika | Sure analizi ve ML hedefi |
| pickup_hour | binis saati (0-23) | Saatlik analiz |
| pickup_dayofweek | binis gunu | Gunluk analiz |
| avg_speed_mph | mesafe / (sure / 60) | Imkansiz hizlari yakalamak |
