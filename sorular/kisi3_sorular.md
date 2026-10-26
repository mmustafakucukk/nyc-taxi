# 3. Kisi - Coktan Secmeli Sorular

Konu: Performans / olceklenebilirlik benchmark deneyleri ve makine ogrenmesi modeli

---

SORU 1: 10,5 milyon satirlik ve 30 sutunlu taksi verisinden yalnizca 3 sutun (trip_distance, fare_amount,
pickup_hour) pandas ile okunmak istenmektedir. Olcumlerde bu islem CSV dosyasindan 18,8 saniye, Parquet
dosyasindan ise 0,13 saniye surmustur (yaklasik 148 kat fark). Tum sutunlar okundugunda ise fark yalnizca
16 kattir. Sadece birkac sutun okunurken farkin bu kadar acilmasinin temel nedeni hangisidir?

A) Parquet dosyasi diskte daha az yer kapladigi icin bilgisayar onu otomatik olarak RAM'de tutar.
B) pandas, CSV dosyalarini okurken sadece tek bir islemci cekirdegi kullanabilir.
C) CSV dosyalarinda sutun isimleri olmadigi icin istenen sutunlar tahmin edilerek bulunur.
D) Parquet dosyasi okunurken istenmeyen satirlar otomatik olarak atlanir.
E) Parquet veriyi sutun bazli sakladigi icin yalnizca istenen sutunlarin bulundugu kisimlar diskten okunur; CSV'de ise 3 sutun icin bile tum satirlar bastan sona taranmak zorundadir.

CEVAP: E

---

SORU 2: Ayni analiz sorgulari (groupBy + ortalama) 100 bin satirlik veri uzerinde calistirildiginda
pandas 0,7 saniyede, PySpark ise 5,4 saniyede bitirmistir (Spark oturumunun acilma suresi haric).
Veri 62 milyon satira cikarildiginda ise Spark'in suresi yalnizca 9,4 saniyeye yukselmistir.
Kucuk veride Spark'in pandas'tan yavas olmasinin en dogru aciklamasi hangisidir?

A) Spark, isi gorevlere bolme, cekirdeklere dagitma ve sonuclari toplama gibi sabit bir koordinasyon maliyetine sahiptir; veri kucukken bu maliyet asil hesaplama suresinden buyuktur.
B) Spark yalnizca 1 milyon satirdan buyuk verilerde tum islemci cekirdeklerini kullanir.
C) Spark kucuk verilerde hesaplamayi tekrar tekrar yaptigi icin yavaslar.
D) pandas kucuk verilerde sonuclari onceden hesaplanmis bir tablodan okur.
E) Spark'in kucuk veride verdigi sonuclar yaklasik oldugu icin dogrulama adimi zaman alir.

CEVAP: A

---

SORU 3: 16 GB RAM'li bir bilgisayarda yapilan deneyde, Parquet dosyasini tamamen bellege yukleyen
pandas 10,5 milyon satirda 5,4 GB RAM kullanmis ve 20,9 milyon satirda bellek yetersizligi nedeniyle
calisamamistir. Ayni bilgisayarda PySpark 62,7 milyon satiri yaklasik 2,8 GB RAM ile islemistir.
Bu sonuca gore asagidaki ifadelerden hangisi dogrudur?

A) Spark veriyi daha guclu sikistirdigi icin tum veriyi pandas'tan daha az yer kaplayacak sekilde RAM'e yukler.
B) pandas her durumda Spark'tan yavas oldugu icin buyuk veride kullanilmamalidir.
C) pandas tum veriyi ayni anda RAM'de tuttugu icin bellek ihtiyaci veriyle dogrusal buyur; Spark ise veriyi parcalar (partition) halinde isleyip ara sonuclari biriktirdigi icin tum veriyi ayni anda bellekte tutmak zorunda kalmaz.
D) Spark islem sirasinda verinin bir kismini ornekleyerek (sampling) kullandigi icin daha az bellek harcar.
E) Spark verileri bilgisayarin RAM'i yerine her zaman ekran kartinin (GPU) belleginde tutar.

CEVAP: C

---

SORU 4: Bir yolculuk suresi (trip_duration_min) tahmin modeli gelistirilirken, mesafe, binis saati ve
binis bolgesi ile birlikte avg_speed_mph (ortalama hiz = mesafe / sure) sutunu da ozellik olarak
kullanilirsa model test verisinde neredeyse kusursuz bir sonuc (R2 degeri 1'e cok yakin) verir. Bu
yaklasimla ilgili en dogru degerlendirme hangisidir?

A) Model cok iyi ogrenmistir; ortalama hiz trafik durumunu temsil eden degerli bir ozelliktir.
B) Ortalama hiz hedef degiskenin (sure) kendisinden hesaplandigi ve yolculuk bitmeden bilinemedigi icin veri sizintisi (data leakage) vardir; model gercek kullanimda bu basariyi gosteremez.
C) Model asiri ogrenme (overfitting) yapmistir; bunu cozmek icin agac sayisi azaltilmalidir.
D) R2 degeri 1'e cok yakin oldugu icin test verisi yanlis secilmistir; rastgele bolme yapilmalidir.
E) Ortalama hiz sutunu yalnizca dogrusal modellerde sorun olusturur, agac tabanli modellerde kullanilabilir.

CEVAP: B
