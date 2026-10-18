# 1. Kisi - Coktan Secmeli Sorular

Konu: Veri temini, veri kalitesi, temizleme pipeline'i ve veri formatlari

---

SORU 1: NYC Yellow Taxi verisinde (Ocak-Mart 2026) passenger_count, RatecodeID, store_and_fwd_flag,
congestion_surcharge ve Airport_fee sutunlari ayni 3.057.123 satirda birlikte bostur ve bu satirlarin
tamaminda payment_type = 0 (Flex Fare) degeri bulunmaktadir. Bu satirlarda mesafe, sure, bolge ve
ucret bilgileri ise doludur. Temizleme pipeline'inda bu durum icin en dogru yaklasim hangisidir?

A) Bos deger iceren tum satirlar dropna() ile silinmelidir, cunku eksik veri analiz sonuclarini bozar.
B) Bos degerler ilgili sutunlarin ortalamasi ile doldurulmalidir.
C) Bosluk rastgele degil, odeme turune bagli oldugu icin satirlar korunmali; bos alanlar analize gore ayrica ele alinmalidir.
D) payment_type = 0 olan satirlar hatali kabul edilip tamamen veri setinden cikarilmalidir.
E) Bos sutunlar veri setinden tamamen silinmelidir, cunku hicbir analizde kullanilamazlar.

CEVAP: C

---

SORU 2: Ayni 11 milyon satirlik taksi verisi diskte Parquet formatinda 182 MB, CSV formatinda ise
1.141 MB yer kaplamaktadir. Bu farkin temel nedeni asagidakilerden hangisidir?

A) Parquet dosyasi verinin yalnizca bir kismini sakladigi icin daha kucuktur.
B) Parquet veriyi sutun bazli (columnar) saklar; ayni sutundaki benzer degerler yan yana durdugu icin sikistirma cok daha verimli calisir ve sayilar ikili (binary) formatta tutulur.
C) CSV dosyalari her satiri iki kez yazdigi icin daha fazla yer kaplar.
D) Parquet yalnizca sayisal sutunlari saklayabildigi icin metin sutunlari dosyaya yazilmaz.
E) CSV formati verileri otomatik olarak sifreledigi icin dosya boyutu buyur.

CEVAP: B

---

SORU 3: Bir temizleme pipeline'inda "sure < 1 dakika" kurali tek basina uygulandiginda 246.542 satiri
yakalamakta, ancak kurallar sirayla uygulandiginda (once "mesafe <= 0" ve "ucret <= 0" kurallari)
yalnizca 162.338 satiri silmektedir. Bu durumun aciklamasi asagidakilerden hangisidir?

A) Spark'in approxQuantile fonksiyonu yaklasik sonuc verdigi icin sayilar farklidir.
B) Kurallar sirayla uygulandiginda Spark verinin bir kismini okumayi atlar.
C) Sure kurali yanlis yazilmistir; iki sayi her zaman esit olmalidir.
D) Bir satir birden fazla kurala takilabilir; kisa sureli satirlarin bir kismi zaten onceki kurallarla (orn. sifir mesafe) silinmistir.
E) Sirali uygulamada tekrar eden satirlar otomatik olarak silindigi icin sayi azalir.

CEVAP: D
