# Temizlik Raporu

Ham veri: **11,077,206** satir -> Temiz veri: **10,452,582** satir (%5.64 silindi)

## Kurallar

Kurallar asagidaki sirayla uygulandi. **Tek basina**: kural tek basina uygulansaydi kac satir yakalardi. **Sirali silinen**: onceki kurallardan gecen satirlardan kac tanesini bu kural sildi.

| # | Kural | Tek basina | Sirali silinen | Kalan |
|---|---|---|---|---|
| 1 | tarih araligi disi | 10 | 10 | 11,077,196 |
| 2 | mesafe <= 0 | 370,198 | 370,198 | 10,706,998 |
| 3 | ucret veya toplam <= 0 | 94,565 | 86,287 | 10,620,711 |
| 4 | sure < 1 dk | 246,542 | 162,338 | 10,458,373 |
| 5 | sure > 180 dk | 4,464 | 4,055 | 10,454,318 |
| 6 | mesafe > 100 mil | 495 | 441 | 10,453,877 |
| 7 | ucret > 500 $ | 162 | 42 | 10,453,835 |
| 8 | hiz > 80 mph | 2,762 | 1,253 | 10,452,582 |
| 9 | birebir tekrar eden satir | - | 0 | 10,452,582 |

## Silinmeyen ama duzeltilen / not edilen durumlar

- **passenger_count = 0:** 38,470 satir. Yolculuk gecerli, sadece yolcu sayisi girilmemis. Satir silinmedi, deger null (bilinmiyor) yapildi.
- **Flex Fare (payment_type = 0):** ham veride 3,057,123, temiz veride 2,778,143 satir. Bu satirlarda passenger_count, RatecodeID, store_and_fwd_flag, congestion_surcharge ve Airport_fee bos ama bu bir hata degil (bkz. veri_sozlugu.md). Bos degerler doldurulmadi, dropna() kullanilmadi. ML'de kullanilacaksa congestion_surcharge ve Airport_fee 0 ile doldurulabilir.
- **Bilinmeyen bolge (264 Unknown / 265 Outside of NYC):** 63,081 satir. Sure, mesafe ve ucret bilgisi gecerli oldugu icin silinmedi. Bolge analizinde filtrelenmeli.

## Esikler

- `baslangic_tarihi` = 2026-01-01
- `bitis_tarihi` = 2026-04-01
- `min_sure_dk` = 1
- `max_sure_dk` = 180
- `max_mesafe_mil` = 100
- `max_ucret` = 500
- `max_hiz_mph` = 80

## Eklenen sutunlar

trip_duration_min, avg_speed_mph, pickup_date, pickup_hour, pickup_dayofweek (1 = Pazar), pickup_month, PU_Borough, PU_Zone, DO_Borough, DO_Zone

## Ciktilar

- 2026-01: Parquet 108 MB, CSV 728 MB
- 2026-02: Parquet 99 MB, CSV 664 MB
- 2026-03: Parquet 116 MB, CSV 782 MB

_Calisma suresi: 246 sn_
