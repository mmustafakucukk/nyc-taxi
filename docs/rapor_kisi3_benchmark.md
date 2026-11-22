# Ölçeklenebilirlik Deneyleri ve Yolculuk Süresi Tahmini (3. Kişi)

Bu bölüm projenin araştırma sorusunu deneysel olarak cevaplar:

> **Veri büyüdükçe klasik analiz yaklaşımı ne zaman yetersiz kalıyor?**

Bunun için üç çalışma yapıldı:
1. CSV ve Parquet formatlarının karşılaştırılması
2. pandas ve PySpark ile aynı analizlerin farklı veri boyutlarında çalıştırılması
3. Yolculuk süresini tahmin eden bir makine öğrenmesi modeli

Bütün sonuçlar repodaki scriptlerle yeniden üretilebilir (`src/benchmark_format.py`, `src/benchmark_pandas_spark.py`, `src/model_egit.py`).

---

## 1. Deney Düzeni

### 1.1 Donanım ve yazılım

| | |
|---|---|
| İşlemci | AMD Ryzen 7 7735HS (8 çekirdek, 16 iş parçacığı) |
| Bellek | 16 GB RAM (işletim sistemine ayrılan sonrası ~15 GB kullanılabilir) |
| Disk | NVMe SSD |
| İşletim sistemi | Windows 11 |
| Yazılım | Python 3.12, pandas 2.3, PySpark 4.2 (`local[*]`, sürücü belleği 6 GB), scikit-learn 1.9, Java 17 |

Bütün deneyler **tek bir dizüstü bilgisayarda** yapıldı. Spark gerçek bir küme (cluster) yerine bilgisayarın 16 iş parçacığını kullanan yerel modda çalıştı.

### 1.2 Veri setleri

1. Kişinin hazırladığı temiz veriden (Ocak–Mart 2026, 10,45 milyon yolculuk) farklı boyutlarda setler oluşturuldu:

| Set | Satır | Nasıl oluşturuldu |
|---|---|---|
| 100k | 100.000 | Ocak verisinden rastgele örneklem (`random_state=42`) |
| 1m | 1.000.000 | Ocak verisinden rastgele örneklem |
| 1ay | 3.504.231 | Ocak |
| 2ay | 6.703.593 | Ocak + Şubat |
| 3ay | 10.452.582 | Ocak + Şubat + Mart |
| 20m | 20.905.164 | 3ay verisinin 2 kopyası |
| 30m | 31.357.746 | 3ay verisinin 3 kopyası |
| 60m | 62.715.492 | 3ay verisinin 6 kopyası |

20m, 30m ve 60m setleri, bellek sınırına ulaşmak için **kopyalama** ile üretildi. Kopya satırlar performans ölçümünü etkilemez (programlar satırların kopya olduğunu bilmez), ancak bu setlerden analiz sonucu çıkarılmamıştır.

### 1.3 Ölçüm yöntemi

- **Tekrar:** Her ölçüm 3 kez yapıldı, **medyan** (ortanca) değer raporlandı. Medyan, arka plandaki işlemlerin yol açtığı tek seferlik aykırı ölçümlerden etkilenmez.
- **Yalıtım:** pandas ve Spark ölçümlerinin her biri **ayrı bir Python sürecinde** çalıştırıldı. Böylece bir ölçümün bellekte bıraktıkları diğerini etkilemedi. Bellek yetmeyip çöken bir ölçüm de deneyin geri kalanını durdurmadı.
- **Bellek ölçümü:** Süreç çalışırken her 0,2 saniyede bir RAM kullanımı okundu ve **tepe değer** kaydedildi. Spark'ta asıl işi Java (JVM) yaptığı için Java sürecinin belleği de dahil edildi.
- **"Bellek yetmedi" tanımı:** Bilgisayardaki boş RAM 1 GB'ın altına düştüğü anda ölçüm durduruldu ve başarısız sayıldı. Windows RAM dolunca diski bellek gibi kullanmaya başlar (swap) ve sistem kilitlenir. Bu nokta, pratikte "bu makinede çalıştırılamaz" anlamına gelir.
- **Spark'ın tembel çalışması:** Spark, sonuç istenmeden (`collect()`) hiçbir hesaplama yapmaz (lazy evaluation). Bu nedenle her sorgu `collect()` ile bitirildi. Aksi halde ölçülen süre sıfıra yakın çıkardı.
- **Doğruluk kontrolü:** Her yöntemin işlediği satır sayısı dosyadaki satır sayısıyla karşılaştırıldı. Böylece eksik veri işleyerek "hızlı görünen" bir ölçüm olmadığı doğrulandı.

---

## 2. CSV ve Parquet Karşılaştırması

Aynı veri, pandas ile hem CSV hem Parquet olarak yazıldı ve okundu. Okuma iki şekilde ölçüldü: tüm sütunlar (30 sütun) ve yalnızca 3 sütun (`trip_distance`, `fare_amount`, `pickup_hour`).

![CSV vs Parquet](../results/format_benchmark.png)

| Satır | Disk CSV / Parquet (MB) | Yazma CSV / Parquet (sn) | Okuma, tüm sütunlar CSV / Parquet (sn) | Okuma, 3 sütun CSV / Parquet (sn) |
|---|---|---|---|---|
| 100.000 | 20,8 / 3,9 | 1,96 / 0,26 | 0,48 / 0,05 | 0,20 / 0,005 |
| 1.000.000 | 207,8 / 33,5 | 20,15 / 1,85 | 5,48 / 0,35 | 1,51 / 0,02 |
| 3.504.231 | 728,1 / 108,3 | 39,67 / 4,07 | 10,79 / 0,81 | 3,71 / 0,03 |
| 6.703.593 | 1.392,5 / 206,9 | 120,24 / 11,86 | 36,91 / 2,29 | 10,97 / 0,09 |
| 10.452.582 | 2.174,1 / 322,4 | 188,72 / 18,68 | 57,74 / 3,64 | 18,77 / 0,13 |

**10,5 milyon satırda Parquet:**
- diskte **6,7 kat** daha az yer kaplıyor,
- **10 kat** daha hızlı yazılıyor,
- **16 kat** daha hızlı okunuyor (tüm sütunlar),
- yalnızca 3 sütun okunurken **148 kat** daha hızlı.

### Yorum

- **Boyut farkı:** Parquet veriyi sütun sütun saklar. Aynı sütundaki benzer değerler yan yana durduğu için sıkıştırma çok daha verimli çalışır. Sayılar metin olarak değil ikili (binary) biçimde tutulur.
- **Okuma hızı:** CSV düz metindir. Okunurken her karakterin ayrıştırılması (sayı mı, tarih mi, ayraç mı?) ve tiplere çevrilmesi gerekir. Parquet ise veri tiplerini dosyanın içinde saklar, veri doğrudan belleğe aktarılır.
- **3 sütundaki 148 katlık fark:** CSV'de sütunlar satırların içine gömülüdür. 3 sütun için bile dosyanın tamamının taranması gerekir. Nitekim CSV'de 3 sütun okumak, tüm sütunları okumanın üçte biri kadar sürdü. Parquet ise yalnızca istenen sütunların bulunduğu bölümleri diskten okur (*column pruning*), diğer 27 sütuna hiç dokunmaz. Analizlerin büyük çoğunluğu birkaç sütunla çalıştığı için büyük veride bu fark belirleyicidir.
- **Ölçeklenme:** Fark veri büyüdükçe açılıyor. 100 bin satırda CSV okuması yarım saniye sürüyor, kullanıcı farkı hissetmez. 10,5 milyon satırda bir dakikaya yaklaşıyor. 1 yıllık veride (~44 milyon satır) bu süre birkaç dakikaya çıkacaktır. Büyük veride format seçimi bir tercih değil, gerekliliktir.

---

## 3. pandas ve PySpark Karşılaştırması

### 3.1 Yöntemler ve iş yükü

Üç yöntem aynı işi yaptı:

| Yöntem | Açıklama |
|---|---|
| `pandas_tum` | Klasik yaklaşım: Parquet dosyasının tamamı (30 sütun) RAM'e yüklenir |
| `pandas_secili` | Optimize edilmiş pandas: yalnızca analizde gereken 10 sütun okunur |
| `spark` | PySpark, yerel modda 16 iş parçacığı |

`pandas_secili`, karşılaştırmanın adil olması için eklendi. Böylece "pandas iyi kullanılmadığı için yenildi" itirazının önüne geçildi.

İş yükü, dosyayı okuyup aynı 4 analiz sorgusunu çalıştırmaktı:
1. Saate göre yolculuk sayısı ve ortalama ücret
2. İlçe ve ödeme türüne göre ortalama bahşiş
3. 10 milden uzun yolculukların en çok başladığı 10 bölge
4. Haftanın gününe göre ortalama hız ve süre

### 3.2 Sonuçlar

![pandas vs Spark](../results/pandas_spark_benchmark.png)

| Satır | pandas_tum süre / RAM | pandas_secili süre / RAM | Spark süre / RAM |
|---|---|---|---|
| 100.000 | 0,70 sn / 0,08 GB | 0,68 sn / 0,08 GB | 5,43 sn / 0,68 GB |
| 1.000.000 | 1,08 sn / 0,61 GB | 0,84 sn / 0,26 GB | 6,38 sn / 0,85 GB |
| 3.504.231 | 1,83 sn / 1,85 GB | 1,18 sn / 0,66 GB | 6,92 sn / 1,22 GB |
| 6.703.593 | 2,92 sn / 3,35 GB | 1,60 sn / 1,28 GB | 7,41 sn / 1,29 GB |
| 10.452.582 | 4,51 sn / 5,36 GB | 2,11 sn / 1,97 GB | 7,66 sn / 1,66 GB |
| 20.905.164 | ❌ bellek yetmedi | 3,62 sn / 3,61 GB | 8,47 sn / 2,04 GB |
| 31.357.746 | ❌ | 5,16 sn / 5,51 GB | 8,71 sn / 2,40 GB |
| 62.715.492 | ❌ | ❌ bellek yetmedi | **9,35 sn / 2,78 GB** |

Spark süreleri oturum açılışını içermez. Spark oturumunun açılması her ölçümde ayrıca yaklaşık **6,4 saniye** sürdü.

### 3.3 Yorum

**1. Küçük veride pandas açık ara önde.**
100 bin satırda pandas 0,7 saniyede bitirirken Spark 5,4 saniye sürdü. Açılış da eklenince Spark yaklaşık 17 kat yavaş. Bunun sebebi Spark'ın veri boyutundan bağımsız, **sabit bir koordinasyon maliyeti** olmasıdır: Java sanal makinesini başlatmak, sorguyu bir çalışma planına çevirmek, işi görevlere (task) bölüp çekirdeklere dağıtmak ve sonuçları toplamak. Veri küçükken bu hazırlık, asıl hesaplamadan çok daha uzun sürer.

**2. Spark'ın süresi veriyle neredeyse artmıyor.**
Veri 627 kat büyüdü (100 bin → 62,7 milyon), Spark'ın süresi ise yalnızca 5,4 saniyeden 9,4 saniyeye çıktı. Sürenin büyük kısmı sabit maliyet. Değişken kısım (asıl hesaplama) 16 iş parçacığına dağıtıldığı için yavaş büyüyor.

**3. Klasik pandas 20 milyon satırda çalışamadı.**
`pandas_tum` 10,5 milyon satırda 5,4 GB RAM kullandı. Satır başına yaklaşık 550 bayt, büyük kısmı bölge ve ilçe isimleri gibi metin sütunlarından geliyor. 20,9 milyon satırda bellek ihtiyacı 8,5 GB'ı geçince bilgisayarın boş belleği tükendi.

**4. Optimize pandas sınırı ileri itti ama kaldıramadı.**
Yalnızca gereken sütunları okumak bellek ihtiyacını yaklaşık üçte bire indirdi ve pandas'ı 31 milyon satıra kadar taşıdı. Ancak bellek ihtiyacı yine veriyle **doğrusal** büyüdü ve 62,7 milyon satırda bu yöntem de çalışamadı.

**5. Spark'ın bellek kullanımı sınırlı kaldı.**
Spark 62,7 milyon satırı 2,8 GB ile işledi. Bu, pandas'ın 10 milyon satırda kullandığından bile az. Temel fark şu:
- **pandas** veri setinin tamamını aynı anda bellekte tutar. Bellek ihtiyacı veri boyutuyla orantılıdır.
- **Spark** veriyi parçalara (partition) böler. Her parçayı okuyup sorguya katkısını hesaplar (örneğin grup bazında ara toplamlar), sonucu biriktirir ve parçayı bellekten bırakır. Ayrıca Parquet'in sütun yapısından yararlanarak sorguda geçmeyen sütunları hiç okumaz. Bellekte veri setinin tamamı değil, yalnızca o an işlenen parçalar ve küçük ara sonuçlar bulunur.

---

## 4. Yolculuk Süresi Tahmin Modeli

### 4.1 Problem tanımı

**Soru:** Yolcu taksiye bindiği anda bilinen bilgilerle yolculuğun kaç dakika süreceği tahmin edilebilir mi?

- **Hedef değişken:** `trip_duration_min` (dakika), regresyon problemi
- **Özellikler:** mesafe, biniş ve iniş bölgesi, biniş ve iniş ilçesi, biniş saati, haftanın günü, tarife kodu, taksimetre firması
- **Eğitim:** Ocak + Şubat 2026 (6.703.593 yolculuk)
- **Test:** Mart 2026 (3.748.989 yolculuk)

Eğitim ve test verisi rastgele değil, **zamana göre** ayrıldı. Model geçmiş aylardan öğrenip hiç görmediği bir ayda sınandı. Bu düzen, modelin gerçek kullanımını (geçmişten öğren, geleceği tahmin et) taklit eder.

### 4.2 Veri sızıntısının önlenmesi

Yalnızca yolculuk başlarken bilinen bilgiler kullanıldı. Aşağıdaki sütunlar bilinçli olarak dışarıda bırakıldı:

| Sütun | Neden kullanılmadı |
|---|---|
| `tpep_dropoff_datetime` | İniş − biniş zamanı, doğrudan hedef değişkenin kendisi |
| `avg_speed_mph` | Mesafe ÷ süre ile hesaplandı, hedefi içinde barındırır |
| `fare_amount`, `total_amount`, `tip_amount` | Taksimetre süreye göre işler ve yolculuk bitince belli olur |

Bu sütunlar kullanılsaydı model yapay olarak çok başarılı görünür, ancak gerçek kullanımda bu bilgiler henüz mevcut olmazdı.

263 farklı bölge kodu **target encoding** ile sayıya çevrildi: Her bölge, eğitim verisinde o bölgeden başlayan (veya biten) yolculukların ortalama süresiyle temsil edildi. Bir satırın kodu hesaplanırken o satırın kendi süresi kullanılmasın diye kodlar 5 katlı çapraz doğrulama ile (cross fitting) üretildi.

### 4.3 Modeller ve sonuçlar

| Model | Açıklama | MAE (dk) | RMSE (dk) | R² | Eğitim süresi |
|---|---|---|---|---|---|
| Baseline | Her yolculuk için eğitim ortalamasını söyler | 9,80 | 14,44 | 0,000 | – |
| Linear Regression | Mesafe + saat/gün/ilçe (one-hot) | 5,38 | 8,38 | 0,663 | 5 sn |
| **HistGradientBoosting** | 300 karar ağacından oluşan gradient boosting | **3,49** | **5,81** | **0,838** | 50 sn |

![Model sonuçları](../results/model_grafik.png)

### 4.4 Yorum

- **En iyi model** Mart yolculuklarının süresini **ortalama 3,5 dakika** hatayla tahmin etti. Baseline'a göre hata %64 azaldı. R² = 0,84, yani yolculuk sürelerindeki değişkenliğin %84'ü açıklanabildi.
- **Ağaç modelinin üstünlüğü:** Doğrusal model her özelliğin etkisini sabit ve birbirinden bağımsız varsayar ("her mil X dakika ekler"). Gerçekte etkiler birbirine bağlıdır: Aynı mesafe akşam saatinde Manhattan'da gece Queens'tekinden çok daha uzun sürer. Karar ağaçları bu **etkileşimleri** yakalayabildiği için hatayı 5,4 dakikadan 3,5 dakikaya indirdi.
- **Özellik önemi:** Belirleyici özellik açık ara **mesafe**. Onu **biniş saati** (trafik yoğunluğu) ve **biniş bölgesi** izliyor. Taksimetre firmasının (VendorID) etkisi sıfıra yakın. Bu da beklenen bir sonuç ve modelin anlamsız ilişkiler öğrenmediğini gösteriyor.
- **Kısıt: uzun yolculuklar.** Hata yolculuk uzadıkça artıyor:

| Gerçek süre | Yolculuk sayısı | MAE (dk) |
|---|---|---|
| 0–10 dk | 1.267.414 | 1,99 |
| 10–20 dk | 1.420.533 | 2,75 |
| 20–40 dk | 812.927 | 4,60 |
| 40–60 dk | 161.360 | 8,74 |
| 60+ dk | 86.755 | 17,32 |

Uzun yolculuklar hem verinin küçük bir kısmını oluşturuyor (%2) hem de trafik sıkışıklığı, kaza ve hava durumu gibi verimizde bulunmayan etkenlere daha açık. Anlık trafik ve hava durumu verisi eklenmesi bu hatayı azaltabilir.

---

## 5. Neden-Sonuç Değerlendirmesi: Araştırma Sorusunun Cevabı

> **Veri büyüdükçe klasik analiz yaklaşımı ne zaman yetersiz kalıyor?**

Deneylerin ortak sonucu: **Sınırı belirleyen hız değil, bellek.**

1. **Tek makine yaklaşımı, veri RAM'e sığdığı sürece hem yeterli hem daha hızlı.** Denenen her boyutta, belleğe sığdığı sürece pandas Spark'tan hızlıydı. Küçük ve orta ölçekli veride (bizim ölçümlerimizde ~10 milyon satıra kadar) Spark kullanmak, sabit koordinasyon maliyeti yüzünden işi yavaşlatır.

2. **Klasik yaklaşım, veri tek makinenin belleğine sığmadığı anda tamamen çalışamaz hale geliyor.** Bu bir yavaşlama değil, bir duvar. 16 GB RAM'li makinemizde:
   - Veriyi olduğu gibi yükleyen klasik pandas **~20 milyon satırda**,
   - Sütun seçimiyle optimize edilen pandas **~60 milyon satırda**

   çalışamadı. pandas'ın bellek ihtiyacı veri boyutuyla doğrusal büyüdüğü için bu sınır her makine için hesaplanabilir. Bu deney için kabaca *kullanılabilir RAM ÷ satır başına bellek* formülü geçerli.

3. **Spark'ın bellek ihtiyacı veri boyutuna bağlı değil.** Veriyi parça parça işlediği için 62,7 milyon satırı 2,8 GB ile işledi. Tek makinede bile pandas'ın erişemediği boyutlara ulaşıyor. Gerçek bir kümede makine sayısı arttırılarak ölçeklenmeye devam edebilir.

4. **Format seçimi de ölçekle birlikte kritikleşiyor.** CSV ile Parquet arasındaki fark 100 bin satırda hissedilmezken 10 milyon satırda tek bir okuma için yaklaşık 1 dakika kayıp demek. Spark'ın düşük bellekle çalışabilmesinin bir sebebi de Parquet'in yalnızca gereken sütunları okumaya izin vermesi.

**Sonuç:** Klasik yaklaşım, veri tek bir makinenin belleğini aşana kadar daha basit ve daha hızlıdır. Bu eşik aşıldığında dağıtık işleme bir tercih olmaktan çıkıp zorunluluk haline gelir. Bizim donanımımızda eşik 20–60 milyon satır arasında; ayda ~3,5 milyon temiz yolculukla bu, NYC Yellow Taxi'nin yaklaşık 6–17 aylık verisine karşılık geliyor. 1 yıllık veri (~44 milyon satır, 1. Kişi boyut analizi) klasik pandas'ın sınırını açıkça aşıyor. Optimize pandas'ın sınırına ise çok yaklaşıyor: Sorgulara yeni sütunlar eklendikçe ya da birkaç yıllık veriye geçildiğinde bu yöntem de yetersiz kalacak.

---

## 6. Kısıtlar

- **Tek makine:** Spark yerel modda tek bilgisayarda çalıştırıldı. Gerçek bir kümede ağ iletişimi ek maliyet getirir, buna karşılık bellek ve işlemci kapasitesi makine sayısıyla artar. Sonuçlar dağıtık ortama doğrudan genellenemez.
- **Kopya veri:** 20m, 30m ve 60m setleri gerçek veri yerine kopyalama ile üretildi. Performans ölçümü için yeterli olsa da gerçek veride değer dağılımı ve sıkıştırma oranı biraz farklı olabilir.
- **Ölçüm gürültüsü:** Ölçümler kişisel bir bilgisayarda yapıldı. İşletim sistemi önbelleği ve arka plan işlemleri bazı ölçümleri etkiledi (örneğin CSV yazma süresi tam doğrusal artmadı). Bu etki 3 tekrar ve medyan kullanılarak azaltıldı.
- **Windows kısıtı:** Windows'ta Hadoop yardımcı programı (winutils) olmadığından Spark diske yazamadı. Bu yüzden format karşılaştırmasındaki yazma ölçümleri yalnızca pandas ile yapıldı.
- **Model:** Yalnızca 3 aylık veri kullanıldı. Mevsimsel etkiler (yaz, tatil dönemleri) modele yansımamıştır.
