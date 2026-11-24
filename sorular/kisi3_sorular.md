# 3. Kisi - Coktan Secmeli Sorular

Konu: Performans / olceklenebilirlik benchmark deneyleri ve makine ogrenmesi modeli

---

SORU 1: 10,5 milyon satirlik veriden yalnizca 3 sutun okundugunda Parquet, CSV'den 148 kat hizli. Tum sutunlar okundugunda ise fark sadece 16 kat. Birkac sutun okunurken fark neden bu kadar aciliyor?

A) Parquet dosyasi kucuk oldugu icin tamamen RAM'de tutulur.
B) pandas, CSV okurken yalnizca tek cekirdek kullanir.
C) CSV'de sutun adlari olmadigi icin sutunlar tek tek aranir.
D) Parquet okunurken gereksiz satirlar otomatik atlanir.
E) Parquet yalnizca istenen sutunlari diskten okur.

CEVAP: E

---

SORU 2: 100 bin satirda pandas 0,7 saniye, Spark 5,4 saniye surdu. Veri 62 milyon satira cikinca Spark'in suresi yalnizca 9,4 saniye oldu. Kucuk veride Spark neden yavastir?

A) Isi bolme, dagitma ve toplamanin sabit bir maliyeti vardir.
B) Spark, 1 milyon satirin altinda tek cekirdek kullanir.
C) Spark, kucuk veride hesaplamayi birkac kez tekrarlar.
D) pandas, kucuk verinin sonuclarini onbellekten okur.
E) Spark, kucuk veride sonuclari ayrica dogrulamak zorundadir.

CEVAP: A

---

SORU 3: 16 GB RAM'li bir bilgisayarda pandas 20,9 milyon satirda bellegi yetmedigi icin calisamadi. Spark ise 62,7 milyon satiri 2,8 GB RAM ile isledi. Bunun temel nedeni nedir?

A) Spark veriyi daha guclu sikistirdigi icin RAM'de daha az yer kaplar.
B) Spark hesaplamada verinin yalnizca bir ornegini kullanir.
C) Spark veriyi parca parca isler, tamamini ayni anda bellege almaz.
D) Spark veriyi RAM yerine ekran kartinin belleginde tutar.
E) pandas buyuk veride Spark'tan her zaman daha yavastir.

CEVAP: C

---

SORU 4: Yolculuk suresini tahmin eden bir modele, mesafenin sureye bolunmesiyle bulunan ortalama hiz sutunu da eklendi. Model test verisinde neredeyse kusursuz sonuc verdi. Bu durum icin dogru yorum hangisidir?

A) Ortalama hiz trafigi iyi temsil ettigi icin model cok iyi ogrenmistir.
B) Hiz sutunu sureden hesaplandigi icin veri sizintisi vardir.
C) Model asiri ogrenme yapmistir, agac sayisi azaltilmalidir.
D) Test verisi yanlis secilmistir, rastgele bolme yapilmalidir.
E) Bu sorun yalnizca dogrusal modellerde ortaya cikar.

CEVAP: B
