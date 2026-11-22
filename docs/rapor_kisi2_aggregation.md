# Şehir İçi Hareket Örüntüleri ve Dashboard (2. Kişi)

Bu bölüm, temizlenmiş 10,45 milyon yolculuk üzerinde PySpark ile yapılan toplulaştırma (aggregation) analizlerini ve projenin tüm sonuçlarını bir araya getiren dashboard'u anlatır.

Cevaplanan sorular:

1. New York'ta taksi talebi **ne zaman** ve **nerede** yoğunlaşıyor?
2. Yolculuklar saate, bölgeye ve ödeme türüne göre nasıl farklılaşıyor ve **neden**?
3. Bu analizler 10 milyon satırlık veride PySpark ile ne kadar sürüyor?

Bütün sonuçlar `src/aggregations.py` ile yeniden üretilebilir. Script sonuç tablolarını `results/agg/` klasörüne, kısa özeti `docs/aggregation_sonuclari.md` dosyasına yazar.

---

## 1. Yöntem

### 1.1 Veri ve ortam

- **Veri:** 1. Kişinin temizlediği Ocak–Mart 2026 Yellow Taxi verisi (`data/processed/parquet/`), **10.452.582** yolculuk.
- **Ortam:** PySpark 4.2, yerel mod (`local[*]`), Python 3.12, Java 17, macOS.
- **Spark ayarları:** `src/spark_baslat.py` (sürücü belleği 6 GB, saat dilimi America/New_York).

### 1.2 Hazırlık adımları

- **Sütun seçimi (column pruning):** 30 sütunun yalnızca 16'sı okundu. Parquet sütun bazlı olduğu için diğer sütunlar diskten hiç okunmaz.
- **Önbellek (`cache()`):** Aynı veri üzerinde 15 ayrı analiz yapıldı. Veri ilk okumada belleğe alındı, sonraki analizler diskten tekrar okumadı.
- **Bilinmeyen bölgeler:** Bölge analizlerinde 264 (*Unknown*) ve 265 (*Outside of NYC*) kodlu yolculuklar dışarıda bırakıldı. Bunlar gerçek semt değildir.
- **Gün başına ortalama:** Ocak–Mart döneminde her haftanın gününden eşit sayıda yok (12 veya 13). Hafta içinde 5, hafta sonunda 2 gün var. Bu yüzden saatlik sayılar **o gruptaki farklı gün sayısına bölündü** (`countDistinct("pickup_date")`). Böylece "o saatte ortalama bir günde kaç yolculuk" karşılaştırılabilir hâle geldi.
- **Spark ile pandas dosya uyumsuzluğu:** Temiz veri pandas ile yazıldığı için tarih-saat sütunları `TIMESTAMP(NANOS)` tipinde. Spark bu tipi doğrudan okuyamadı (`PARQUET_TYPE_ILLEGAL` hatası). `spark.sql.legacy.parquet.nanosAsLong=true` ayarıyla bu sütunlar sayı olarak okundu. Analizde tarih-saat sütunu değil, temizlikte türetilen `pickup_date` ve `pickup_hour` kullanıldığı için sonuç etkilenmedi.

### 1.3 Kullanılan Spark işlemleri

| İşlem | Nerede kullanıldı | Ne işe yaradı |
|---|---|---|
| **Aggregation** (`groupBy().agg()`) | Saatlik, gün × saat, biniş ve iniş bölgeleri, ilçe matrisi, rota, ödeme (tür × saat / mesafe dilimi / ilçe), havalimanı | Satırları gruplayıp sayı, ortalama, toplam çıkarmak |
| **Join** (broadcast) | Zone tablosundan `service_zone` eklemek | 265 satırlık küçük tablo her işçiye kopyalandı; 10 milyonluk tablo ağ üzerinde karıştırılmadı (shuffle yok) |
| **Window: `rank()`** | Her saatin en yoğun 5 bölgesi | Gruplamayı bozmadan her saatin kendi içinde sıralama |
| **Window: `avg() ... rowsBetween(-6, 0)`** | 7 günlük hareketli ortalama | Haftalık dalgalanmayı düzleştirip eğilimi göstermek |
| **Window: `lag()`** | Önceki güne göre % değişim | Bir satırın önceki satırla karşılaştırılması |
| **Window: `sum() over partitionBy`** | Bölgenin ilçesi içindeki payı | Toplamı ayrıca hesaplayıp tekrar join etmeye gerek kalmadan oran |
| **Spark SQL** | Ödeme türü analizi | Aynı işin SQL ile yazılması; Spark ikisini de aynı plana çevirir |

**Window neden gerekli?** `groupBy` her gruptan tek satır döndürür. "Her saatin en yoğun 5 bölgesi" sorusunda ise hem saat hem bölge bilgisi korunmalı ve sıralama her saatin kendi içinde yapılmalıdır. Window olmadan bu iş ancak ikinci bir `groupBy` ve ardından `join` ile yapılabilirdi.

---

## 2. Zaman Örüntüleri

### 2.1 Sonuçlar

| | Değer |
|---|---|
| Hafta içi en yoğun saat | **18:00**, günde ortalama 7.752 yolculuk |
| Hafta içi en sakin saat | **03:00**, günde ortalama 511 yolculuk |
| Hafta sonu en yoğun saat | **18:00**, günde ortalama 7.606 yolculuk |
| Haftanın en yoğun gün-saat hücresi | **Cumartesi 18:00** |
| Ortalama hızın en düşük olduğu saat (hafta içi) | **15:00**, 8,48 mph (~13,6 km/sa) |
| Ortalama hızın en yüksek olduğu saat (hafta içi) | **04:00**, 18,69 mph (~30,1 km/sa) |

### 2.2 Yorum

**Zirve neden 18:00?** Hafta içinde 18:00 hem iş çıkışına hem de akşam etkinliklerinin (yemek, tiyatro, buluşma) başlangıcına denk geliyor. En yoğun saat ile en sakin saat (03:00) arasında yaklaşık **15 kat** fark var; taksi talebi gün içinde çok dengesiz dağılıyor.

**Hafta sonu zirvesi de neden 18:00?** Hafta sonu iş dönüşü yok, ama akşam sosyal hayatı var. Haftanın en yoğun hücresinin **Cumartesi 18:00** olması, bu saatteki talebin işe gidip gelmeden çok eğlence ve sosyal hayattan beslendiğini gösteriyor.

**En yavaş saat neden en yoğun saat değil?** Taksi en çok 18:00'de kullanılıyor, ama yollar en çok 15:00'te tıkanıyor. Bunun sebebi, taksi talebi ile yol trafiğinin aynı şey olmaması. Öğleden sonra yollarda taksilerin yanında ticari araçlar, teslimat kamyonetleri ve okul çıkışı trafiği de bulunuyor. Bu veri yalnızca taksileri içerdiği için bu açıklama bir çıkarımdır; doğrulamak için genel trafik verisi gerekir.

**Gece neden iki kat hızlı?** 04:00'te yollar boş. Ayrıca gece yolculuklarının içinde havalimanı gibi uzun ve otoyol ağırlıklı yolculukların payı daha yüksek olabilir; bu da ortalamayı yukarı çeker (karışım etkisi).

---

## 3. Günlük Eğilim ve Window Fonksiyonu

| | Tarih | Yolculuk |
|---|---|---|
| En yoğun gün | 7 Şubat 2026, Cumartesi | **149.590** |
| En sakin gün | 23 Şubat 2026, Pazartesi | **22.736** |

En sakin gün normal bir günün yaklaşık **beşte biri** kadar yolculuk içeriyor. Bu bir veri hatası değil: 22–23 Şubat 2026'da New York'ta büyük bir kar fırtınası yaşandı. Central Park'ta 48 cm kar ölçüldü, şehirde acil durum ilan edildi, okullar tatil edildi ve havalimanlarında binlerce uçuş iptal oldu ([NPR, 23 Şubat 2026](https://www.npr.org/2026/02/23/g-s1-111202/winter-storm-northeast-travel-airport-flight-train-roads-new-york-boston)). Temizlik aşamasında bu gün silinmedi; gerçek bir olayın veride bıraktığı izdir.

**7 günlük hareketli ortalama ne gösteriyor?** Günlük seri hem hafta içi/hafta sonu döngüsü hem de fırtına gibi tek seferlik olaylar yüzünden çok dalgalı. 7 günlük pencere her noktada tam bir haftayı kapsadığı için haftalık döngüyü siler ve genel eğilimi gösterir. Fırtına günü ise bu düz çizginin altında belirgin bir çukur olarak öne çıkar. `lag()` ile hesaplanan "önceki güne göre değişim" de böyle ani düşüşleri sayısal olarak yakalar.

---

## 4. Bölge Analizleri

### 4.1 Sonuçlar

- Binişlerin **%86,1**'i Manhattan'da.
- En yoğun biniş bölgesi: **Upper East Side South**, 456.049 biniş.
- En sık rota: **Upper East Side South → Upper East Side North**, 68.416 yolculuk.

Servis bölgesine göre (zone tablosuyla **broadcast join** sonucu):

| Servis bölgesi | Yolculuk | Ort. ücret ($) | Ort. mesafe (mil) | Ort. süre (dk) |
|---|---|---|---|---|
| Yellow Zone (Manhattan merkezi) | 8.576.628 | 17,51 | 2,43 | 14,7 |
| Boro Zone (dış ilçeler) | 1.189.661 | 29,72 | 5,68 | 27,0 |
| Airports | 623.161 | 53,42 | 12,87 | 36,0 |
| EWR (Newark) | 51 | 92,12 | 8,05 | 21,2 |

### 4.2 Yorum

**Manhattan neden baskın?** Sarı taksinin çalışma modeli sokaktan el kaldırarak taksi çevirmeye dayanıyor. Bu model, yaya yoğunluğunun ve iş/eğlence merkezlerinin en yüksek olduğu Manhattan'da işliyor. Dış ilçelerde bu talebin büyük kısmını yeşil taksiler (Boro Taxi) ve uygulama tabanlı araçlar karşılıyor; bu veriler projemizin kapsamında değil. Yani %86, "New Yorkluların %86'sı Manhattan'da yolculuk yapıyor" anlamına gelmez; **sarı taksinin** Manhattan'a odaklı bir hizmet olduğunu gösterir.

**En sık rota neden bu kadar kısa?** Upper East Side, Manhattan'ın en yoğun yerleşim bölgelerinden biri. En sık rota aynı semtin güney ve kuzey parçaları arasında; yani taksi burada uzun yolculuktan çok, kısa mahalle içi yolculuklar için de kullanılıyor.

**Dış ilçe yolculukları neden daha uzun ve pahalı?** Boro Zone'dan binen yolculuklar ortalamada 2,3 kat daha uzun mesafeli. Dış ilçeler Manhattan'a göre çok daha seyrek yerleşimli; varış noktaları birbirinden uzak. Bu yolculukların nereye gittiği dashboard'daki ilçe matrisinde görülebilir.

**EWR neden sadece 51?** Newark Havalimanı New Jersey'de. Sarı taksiler yolcuyu oraya bırakabiliyor ama oradan yolcu almaları neredeyse yok. Bu yüzden EWR'den biniş sayısı çok düşük.

---

## 5. Havalimanı ve Şehir İçi

| Yolculuk tipi | Yolculuk | Ort. ücret ($) | Ort. mesafe (mil) | Ort. süre (dk) | Ort. hız (mph) |
|---|---|---|---|---|---|
| Şehir içi | 9.656.858 | 18,46 | 2,68 | 15,9 | 9,9 |
| Havalimanından biniş | 646.908 | 55,20 | 13,13 | 36,1 | 23,6 |
| Havalimanına gidiş | 148.816 | 61,28 | 13,46 | 39,0 | 22,9 |

**Daha pahalı ama mil başına daha ucuz.** Havalimanı yolculukları yaklaşık 3 kat pahalı. Ama mesafe 5 kat fazla olduğu için mil başına ücret daha düşük: şehir içinde 18,46 / 2,68 ≈ **6,9 $/mil**, havalimanından binişte 55,20 / 13,13 ≈ **4,2 $/mil**. Bunun bir sebebi taksimetrenin hem süreye hem mesafeye göre işlemesi: şehir içindeki yavaş trafikte süre ücreti mesafeye göre daha fazla birikiyor. Diğer sebebi JFK–Manhattan arasındaki sabit tarife (RatecodeID 2).

**Neden 2,4 kat daha hızlı?** Havalimanı yolculuklarının büyük kısmı otoyolda geçiyor (23,6 mph). Şehir içinde ise sinyalizasyon ve sıkışık trafik var (9,9 mph ≈ 16 km/sa).

---

## 6. Ödeme Türü (Spark SQL)

| Ödeme | Yolculuk | Ort. ücret ($) | Ort. bahşiş ($) | Bahşiş / ücret (%) | Bahşiş veren (%) |
|---|---|---|---|---|---|
| Kredi kartı | 6.721.029 | 19,45 | 4,12 | 21,19 | 90,5 |
| Flex Fare | 2.778.143 | 26,50 | 0,42 | 1,58 | 8,9 |
| Nakit | 872.038 | 19,46 | 0,00 | 0,00 | 0,0 |
| İtirazlı | 59.478 | 23,10 | 0,00 | 0,01 | 0,0 |
| Ücretsiz | 21.894 | 19,16 | 0,00 | 0,00 | 0,0 |

Bahşiş oranı, yolculuk başına oranların ortalaması olarak değil, **toplam bahşiş / toplam ücret** olarak hesaplandı. Yolculuk başına oran alınsaydı, 3 dolarlık bir yolculukta verilen 5 dolarlık bahşiş tek başına %167'lik bir değer üretip ortalamayı bozardı.

### Yorum: veri toplama yanılgısı

**Nakit ödemelerde bahşiş neden sıfır?** Nakit yolcuların bahşiş vermediği sonucu **yanlış** olur. Veri sözlüğüne göre `tip_amount` yalnızca kartla verilen bahşişleri kaydediyor; nakit bahşiş taksimetreye girilmiyor. Ücretler iki grupta neredeyse aynı (19,45 $ ve 19,46 $), yani nakit ödeyen yolcular farklı tür yolculuklar yapmıyor. Fark tamamen verinin nasıl toplandığından kaynaklanıyor.

**Sonuç:** Bahşiş davranışı analiz edilecekse **yalnızca kredi kartı yolculukları** kullanılmalı. Bu veriye göre kartla ödeyenlerin %90,5'i bahşiş veriyor ve ortalama bahşiş ücretin %21'i.

**Flex Fare'de bahşiş neden bu kadar düşük?** Flex Fare yolculuklarında ücret önceden belirleniyor ve bu yolculuklarda bazı alanlar (yolcu sayısı, tarife kodu vb.) hiç gönderilmiyor (bkz. `veri_sozlugu.md`). Bahşişin de bu kanalda kısmen kaydedilmemiş olması olası; ancak veri bunu kesin olarak söylemeye yetmiyor.

---

## 7. Performans

| Ölçüm | Süre |
|---|---|
| Parquet okuma + belleğe alma (10,45 M satır, 16 sütun) | **7,75 sn** |
| 15 analizin her biri | 0,46 – 1,77 sn |
| 15 analizin toplamı | 15,76 sn |
| Script toplam (Spark oturumunun açılması dahil) | **28,91 sn** |

### Yorum

- **Önbellekten sonra her analiz 2 saniyenin altında.** Veri bir kez okunup belleğe alındıktan sonra 10 milyon satır üzerindeki bir `groupBy` 1 saniye civarında bitiyor. `cache()` kullanılmasaydı 15 analizin her biri Parquet dosyalarını baştan okuyacaktı.
- **En uzun süren analizler** (`saatlik` 1,77 sn, `top_rotalar` 1,69 sn, `binis_bolgeleri` 1,58 sn) çok sayıda grup oluşturanlar ya da `countDistinct` ve window gibi ek sıralama gerektirenler.
- **Sabit maliyet büyük.** Toplam 29 saniyenin yaklaşık 5,4 saniyesi analiz değil; Spark'ın açılması ve rapor yazımı. 3. Kişinin ölçümüne göre Spark oturumunun açılması tek başına ~6 saniye sürüyor.

**Araştırma sorusuyla bağlantı.** 10 milyon satır bu bilgisayarda pandas'ın da işleyebileceği bir boyut. 3. Kişinin benchmark'ında pandas aynı boyutta 2,1 saniyede bitiriyor. Yani bu veri boyutunda Spark'ın avantajı hız değil. Avantaj, veri belleğe sığmayacak kadar büyüdüğünde ortaya çıkıyor: 3. Kişinin deneyinde pandas 20 milyon satırda bellek sınırına takıldı, Spark 62 milyon satırı 10 saniyenin altında işledi. Bu analizlerdeki kod aynen kalarak daha büyük veriye ve bir kümeye (cluster) taşınabilir.

---

## 8. Dashboard

`dashboard/app.py` (Streamlit + Plotly) projenin tamamını tek uygulamada toplar. Soldaki menüde dokuz bölüm var:

| Bölüm | İçerik | Etkileşim |
|---|---|---|
| Özet | Ana sayılar, iki temel grafik, öne çıkan bulgular, araştırma sorusunun cevabı | – |
| Veri ve temizlik | Temizlik kuralları, korunan durumlar, veri sözlüğü, dosya boyutları | Kural seçimi, sözlükte arama |
| Zaman analizi | Saatlik profil, gün × saat ısı haritası, günlük seyir | Ölçüt (sayı / ücret / mesafe / süre / hız), hafta içi-sonu ya da tek gün, tarih aralığı |
| Bölge analizi | En yoğun bölgeler, ilçe matrisi, rotalar, saate göre en yoğun bölgeler | Biniş / iniş, ilçe, sıralama ölçütü, adet, arama, CSV indirme |
| Ödeme analizi | Ödeme payları, ücret ve bahşiş karşılaştırması, saat / mesafe / ilçe kırılımları, havalimanı | Ödeme türü seçildikçe grafikler açılır |
| Performans | pandas / Spark, CSV / Parquet, analiz süreleri | Ölçüt, yöntem ve veri büyüklüğü seçimi |
| Süre tahmini | Model karşılaştırması, özellik önemi, hata dağılımı, kurulum | Ölçüt seçimi |
| Proje dokümanları | Ekibin tüm raporları ve mimari şema | Doküman seçimi, indirme |
| Sınav soruları | 10 çoktan seçmeli soru | Cevaplama ve puanlama |

**Tasarım kararları:**

- **Hesaplama ve görselleştirme ayrı.** Dashboard ham veriyi değil, analiz scriptlerinin ürettiği küçük sonuç dosyalarını (toplamı 1 MB'ın altında) okur. Bu yüzden anında açılır ve Spark kurulu olmayan bir bilgisayarda da çalışır. Ödeme türü ve iniş bölgesi gibi filtreler için gereken kırılımlar da `aggregations.py` içinde önceden hesaplanır.
- **Renk kuralı.** Seçilen ya da öne çıkan veri yeşil, geri kalanı gri; ikinci bir seri gerekiyorsa turuncu. Her renk bir varlığı temsil eder (ör. kredi kartı her grafikte yeşil, nakit turuncu). Palet renk körlüğü testinden geçirildi.
- **Metinler veriden.** Başlık altlarındaki ve yorumlardaki sayılar sonuç dosyalarından hesaplanır; bazı yorumlar yalnızca veri onları destekliyorsa gösterilir (ör. nakit bahşiş açıklaması yalnızca "Nakit" seçiliyken çıkar).
- **Görsel dil.** Grubun önceki projesi PatiPortal'ın tasarım sisteminden uyarlandı: krem zemin, petrol yeşili, Nunito başlıklar, Inter gövde metni, yuvarlak beyaz kartlar. Her bölümün başındaki küçük etiket (ör. "2. Kişi · Zaman analizi") o bölümün kime ait olduğunu gösterir.

Çalıştırmak için:

```bash
python src/aggregations.py
streamlit run dashboard/app.py
```

---

## 9. Kısıtlar

- **Dönem:** Veri yalnızca Ocak–Mart (kış) aylarını kapsıyor. Yaz aylarında turizm ve hava koşulları nedeniyle örüntüler farklı olabilir.
- **Kapsam:** Yalnızca sarı taksi verisi kullanıldı. Yeşil taksi ve uygulama tabanlı araçlar (Uber, Lyft) dahil olsaydı bölge dağılımı çok daha dengeli çıkardı.
- **Ortalama hız:** Her yolculuğun kendi hızının ortalaması alındı. Kısa yolculuklardaki ölçüm gürültüsü ortalamayı etkileyebilir.
- **Süre ölçümü:** Aggregation süreleri tek çalıştırmadan alındı. 3. Kişinin benchmark'ındaki gibi 3 tekrarın medyanı daha güvenilir olurdu.
- **Nedensellik:** Hız ve bölge yorumlarının bir kısmı (ör. öğleden sonra ticari trafik) veriden doğrudan ölçülmüyor, bilinen şehir dinamiklerinden çıkarım yapılıyor.

---

Kaynak: Kar fırtınası bilgisi için [NPR – Huge snowstorm in the Northeast forces millions to stay home (23 Şubat 2026)](https://www.npr.org/2026/02/23/g-s1-111202/winter-storm-northeast-travel-airport-flight-train-roads-new-york-boston).
