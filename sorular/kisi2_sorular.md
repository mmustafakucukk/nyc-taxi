# 2. Kisi - Coktan Secmeli Sorular

Konu: PySpark aggregation, join, window fonksiyonlari, sehir ici hareket oruntuleri ve dashboard

---

SORU 1: Taksi verisinde odeme turune gore bahsis analizi yapilmistir. Kredi karti ile odenen
yolculuklarda ortalama bahsis ucretin %21'i iken, nakit odenen yolculuklarda bahsis orani %0,00
cikmistir. Iki grubun ortalama ucreti ise neredeyse aynidir (19,45 $ ve 19,46 $). Bu sonuc icin
en dogru yorum hangisidir?

A) Nakit odeyen yolcular bahsis vermez; bu nedenle nakit odeme taksiciler icin dezavantajlidir.
B) Nakit odenen yolculuklar daha kisa oldugu icin bahsis verilmesine gerek kalmamaktadir.
C) Spark'ta groupBy islemi sirasinda nakit odemelerin bahsis degerleri kaybolmustur.
D) tip_amount sutunu yalnizca kartla verilen bahsisleri kaydeder; nakit bahsis taksimetreye girilmez. Bu bir davranis farki degil, veri toplama yonteminden kaynaklanan bir yanilgidir.
E) Nakit odemelerde bahsis ayri bir sutunda tutuldugu icin tip_amount degeri bos kalmistir.

CEVAP: D

---

SORU 2: PySpark ile "gunun her saati icin en cok binis yapilan 5 bolgeyi" bulmak isteniyor.
Once groupBy("pickup_hour", "PU_Zone").count() ile her saat-bolge cifti icin yolculuk sayisi
hesaplaniyor. Bir sonraki adimda kullanilmasi gereken en uygun islem hangisidir?

A) Window.partitionBy("pickup_hour").orderBy(desc("count")) uzerinde rank() ile her saati kendi icinde siralayip sira <= 5 olanlari filtrelemek.
B) Tum tabloyu count sutununa gore siralayip limit(5) ile ilk 5 satiri almak.
C) groupBy("pickup_hour").max("count") ile her saatin en buyuk degerini bulmak.
D) Tabloyu zone tablosuyla join edip LocationID'si 5'ten kucuk bolgeleri secmek.
E) Veriyi toPandas() ile pandas'a alip her saat icin ayri bir dongu ile siralamak; Spark'ta bu islem yapilamaz.

CEVAP: A

---

SORU 3: 10,45 milyon satirlik taksi verisi uzerinde PySpark ile 11 farkli aggregation analizi
yapilmistir. Veri once cache() ile bellege alinmis (6,3 sn), ardindan her analiz 0,4 - 1,6 saniyede
tamamlanmistir. Sonuclar Streamlit dashboard'una aktarilirken dashboard'un ham veriyi degil, analiz
sonucunda olusan kucuk CSV dosyalarini okumasi tercih edilmistir. Bu tasarimla ilgili asagidakilerden
hangisi YANLISTIR?

A) cache() kullanilmasaydi her analiz Parquet dosyalarini diskten bastan okuyacakti.
B) Dashboard her acildiginda veya kullanici bir ayari degistirdiginde 10 milyon satiri yeniden islemek zorunda kalmaz.
C) Dashboard'un calismasi icin bilgisayarda Spark ve Java kurulu olmasi gerekmez.
D) Spark tembel (lazy) calistigi icin hesaplama groupBy() satirinda degil, toPandas() gibi bir action cagrildiginda yapilir.
E) Analiz sonuclari onceden hesaplandigi icin veri kumesine yeni aylar eklense bile dashboard otomatik olarak guncel kalir; analiz scriptinin tekrar calistirilmasina gerek yoktur.

CEVAP: E
