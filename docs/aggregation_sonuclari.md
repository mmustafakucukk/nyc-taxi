# Aggregation Sonuclari (2. Kisi)

Veri: temiz veri, **10,452,582** yolculuk (Ocak-Mart 2026). Uretici script: `src/aggregations.py`. Tum tablolar `results/agg/` klasorunde.

## Ana bulgular

- Hafta ici en yogun saat **18:00** (gunde ort. 7,752 yolculuk), en sakin saat **3:00** (511).
- Hafta sonu en yogun saat **18:00** (gunde ort. 7,606).
- Hafta ici ortalama hiz en dusuk **15:00**'de (8.48 mph), en yuksek **4:00**'de (18.69 mph).
- Haftanin en yogun gun-saat hucresi: **Cumartesi 18:00**.
- Binislerin **%86.1**'i Manhattan'da. En yogun bolge: **Upper East Side South** (456,049 binis).
- En sik rota: **Upper East Side South -> Upper East Side North** (68,416 yolculuk).
- En yogun gun 2026-02-07 (149,590), en sakin gun 2026-02-23 (22,736).

## Odeme turu

| odeme | yolculuk | ort_ucret | ort_bahsis | bahsis_orani_yuzde | bahsis_veren_yuzde |
|---|---|---|---|---|---|
| Kredi karti | 6,721,029 | 19.45 | 4.12 | 21.19 | 90.5 |
| Flex Fare | 2,778,143 | 26.5 | 0.42 | 1.58 | 8.9 |
| Nakit | 872,038 | 19.46 | 0.0 | 0.0 | 0.0 |
| Itirazli | 59,478 | 23.1 | 0.0 | 0.01 | 0.0 |
| Ucretsiz | 21,894 | 19.16 | 0.0 | 0.0 | 0.0 |

## Havalimani / sehir ici

| yolculuk_tipi | yolculuk | ort_ucret | ort_mesafe_mil | ort_sure_dk | ort_hiz_mph |
|---|---|---|---|---|---|
| Sehir ici | 9,656,858 | 18.46 | 2.68 | 15.9 | 9.9 |
| Havalimanindan binis | 646,908 | 55.2 | 13.13 | 36.1 | 23.6 |
| Havalimanina gidis | 148,816 | 61.28 | 13.46 | 39.0 | 22.9 |

## Servis bolgesi (join ile eklendi)

| service_zone | yolculuk | ort_ucret | ort_mesafe_mil | ort_sure_dk |
|---|---|---|---|---|
| Yellow Zone | 8,576,628 | 17.51 | 2.43 | 14.7 |
| Boro Zone | 1,189,661 | 29.72 | 5.68 | 27.0 |
| Airports | 623,161 | 53.42 | 12.87 | 36.0 |
| EWR | 51 | 92.12 | 8.05 | 21.2 |

## Islem sureleri

Veri `cache()` ile bellege alindiktan sonra olculdu. Ilk satir okuma + cache suresidir.

| analiz | aciklama | sure_sn |
|---|---|---|
| _okuma_ve_cache | Parquet okuma + bellege alma | 7.75 |
| saatlik | saat x hafta ici/sonu: sayi, ucret, mesafe, sure, hiz | 1.77 |
| gun_saat | haftanin gunu x saat: sayi, ucret, mesafe, sure, hiz | 0.99 |
| gunluk | gunluk sayi + 7 gunluk hareketli ortalama (window) | 0.52 |
| binis_bolgeleri | bolge bazinda binis + ilce ici pay (window) | 1.58 |
| inis_bolgeleri | bolge bazinda inis | 1.44 |
| ilce_matrisi | binis ilcesi x inis ilcesi | 0.85 |
| top_rotalar | en sik 20 bolge-bolge rotasi | 1.69 |
| saatlik_top5_bolge | her saatin en yogun 5 bolgesi (window rank) | 1.05 |
| servis_bolgesi | service_zone bazinda ozet (broadcast join) | 0.9 |
| odeme_turu | odeme turune gore ucret ve bahsis (Spark SQL) | 0.84 |
| odeme_saat | odeme turu x saat | 0.75 |
| odeme_mesafe | odeme turu x mesafe dilimi | 0.89 |
| odeme_ilce | odeme turu x binis ilcesi | 1.0 |
| havalimani | havalimani / sehir ici karsilastirma | 1.03 |
| genel_ozet | genel toplamlar | 0.46 |
| _toplam | script toplam (Spark acilisi dahil) | 28.91 |

## Yorumlar

Bu sayilarin yorumu (neden boyle cikti?) `docs/rapor_kisi2_aggregation.md` dosyasinda. Etkilesimli grafikler icin: `streamlit run dashboard/app.py`
