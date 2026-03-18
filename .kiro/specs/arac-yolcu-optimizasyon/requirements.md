# Requirements Document

## Introduction

Bu uygulama, İstanbul'daki 259 kişilik bir topluluğun araç paylaşımını optimize etmek için geliştirilmiştir. Excel dosyasından yüklenen kişi listesinde yalnızca İsim Soyisim, Adres, İlçe ve Posta Kodu sütunları bulunmaktadır. Uygulama, bu listeden rastgele araç sahipleri seçer, posta kodunun ilk 4 hanesine göre bölge grupları oluşturur, Google Maps API ile koordinat ve mesafe hesabı yapar, OR-Tools ile global optimizasyon uygular ve sonuçları Streamlit arayüzünde görsel kartlar halinde sunar.

Mevcut veri: 259 kişi — sütunlar: İsim Soyisim, Adres, İlçe, Posta Kodu (5 haneli).

## Glossary

- **Sistem**: Araç-Yolcu Optimizasyon ve Planlama Uygulaması
- **Araç Sahibi**: Uygulama tarafından rastgele seçilen, yolcu taşıyabilecek kişi
- **Yolcu**: Araç sahibi olmayan, bir araç sahibine atanacak kişi
- **Bölge Grubu**: Posta kodunun ilk 4 hanesiyle tanımlanan coğrafi küme (örn: 34025 → 3402)
- **Maliyet Matrisi**: Araç sahipleri ile yolcular arasındaki sürüş mesafelerini içeren matris
- **Atama**: Bir yolcunun belirli bir araç sahibine bağlanması işlemi
- **Geocoding**: Metin adresinin enlem/boylam koordinatına dönüştürülmesi
- **OR-Tools**: Google'ın açık kaynaklı optimizasyon kütüphanesi
- **Kapasite Kısıtı**: Her araç sahibine en fazla 3 yolcu atanabilmesi kuralı

## Requirements

### Requirement 1

**User Story:** As a sistem yöneticisi, I want Excel dosyasını yükleyip kişi listesini görmek, so that veri doğruluğunu kontrol edebileyim.

#### Acceptance Criteria

1. WHEN kullanıcı geçerli bir .xlsx dosyası yüklediğinde, THE Sistem SHALL dosyayı okuyarak İsim Soyisim, Adres, İlçe ve Posta Kodu sütunlarını DataFrame'e yükler.
2. WHEN veri yükleme tamamlandığında, THE Sistem SHALL toplam kişi sayısını, araç sahibi sayısını ve yolcu sayısını ekranda gösterir.
3. IF yüklenen dosyada beklenen sütunlar eksikse, THEN THE Sistem SHALL kullanıcıya hangi sütunların eksik olduğunu belirten bir hata mesajı gösterir.
4. WHEN veri yüklendiğinde, THE Sistem SHALL Posta Kodu sütununun ilk 4 hanesini alarak her satıra bir Bölge Grubu değeri atar.

---

### Requirement 2

**User Story:** As a sistem yöneticisi, I want araç sahiplerinin rastgele belirlenmesini, so that demo ve test senaryolarını hızlıca çalıştırabileyim.

#### Acceptance Criteria

1. WHEN kullanıcı araç sahibi sayısını girip "Araç Sahiplerini Belirle" butonuna tıkladığında, THE Sistem SHALL girilen sayı kadar kişiyi listeden rastgele seçerek araç sahibi olarak işaretler; geri kalanları yolcu olarak işaretler.
2. WHEN araç sahibi seçimi tamamlandığında, THE Sistem SHALL araç sahiplerinin ve yolcuların isim ve ilçe bilgilerini ayrı tablolar halinde gösterir.
3. WHILE araç sahibi sayısı 0 veya toplam kişi sayısından büyükse, THE Sistem SHALL kullanıcıya geçerli bir sayı girmesini isteyen bir uyarı mesajı gösterir.
4. WHEN araç sahipleri farklı ilçelerden seçildiğinde, THE Sistem SHALL her kişinin Bölge Grubunu koruyarak bölge bazlı gruplama mantığını sürdürür.

---

### Requirement 3

**User Story:** As a sistem yöneticisi, I want adreslerin koordinatlara dönüştürülmesini, so that mesafe hesabı yapılabilsin.

#### Acceptance Criteria

1. WHEN geocoding işlemi başlatıldığında, THE Sistem SHALL her adres için Google Maps Geocoding API'ye istek gönderir ve enlem/boylam değerlerini saklar.
2. WHILE geocoding devam ederken, THE Sistem SHALL işlem ilerlemesini bir ilerleme çubuğu ile gösterir.
3. IF bir adres için geocoding başarısız olursa, THEN THE Sistem SHALL o kişiyi atama dışında bırakır ve kullanıcıya başarısız adres sayısını bildirir.
4. WHEN aynı oturum içinde geocoding tekrar çalıştırıldığında, THE Sistem SHALL daha önce çözümlenen koordinatları önbellekten kullanır ve tekrar API çağrısı yapmaz.

---

### Requirement 4

**User Story:** As a sistem yöneticisi, I want bölge bazlı mesafe matrisi oluşturulmasını, so that API maliyeti minimize edilsin ve optimizasyon doğru çalışsın.

#### Acceptance Criteria

1. WHEN mesafe matrisi hesaplanırken, THE Sistem SHALL yalnızca aynı Bölge Grubundaki araç sahipleri ile yolcular arasında Distance Matrix API çağrısı yapar.
2. WHEN bir Bölge Grubunda araç sahibi yoksa, THE Sistem SHALL o gruptaki yolcuları komşu bölge grubundaki en yakın araç sahibine atamak üzere işaretler.
3. THE Sistem SHALL tek bir Distance Matrix API çağrısında en fazla 10 origin ve 10 destination göndererek API limitlerini aşmaz.
4. WHEN mesafe matrisi tamamlandığında, THE Sistem SHALL her araç sahibi-yolcu çifti için metre cinsinden mesafe ve saniye cinsinden süreyi saklar.

---

### Requirement 5

**User Story:** As a sistem yöneticisi, I want global optimal atama algoritmasının çalışmasını, so that toplam sürüş mesafesi minimize edilsin.

#### Acceptance Criteria

1. WHEN optimizasyon başlatıldığında, THE Sistem SHALL OR-Tools CP-SAT veya Linear Sum Assignment kullanarak her araç sahibine en fazla 3 yolcu atar.
2. WHEN atama yapılırken, THE Sistem SHALL toplam sürüş mesafesini minimize eden global çözümü bulur; greedy (açgözlü) yaklaşım kullanmaz.
3. IF toplam yolcu sayısı (araç sayısı × 3) değerini aşarsa, THEN THE Sistem SHALL atanamamış yolcuları ayrı bir listede gösterir.
4. WHEN optimizasyon tamamlandığında, THE Sistem SHALL her araç sahibine atanan yolcuların listesini ve toplam mesafeyi döndürür.

---

### Requirement 6

**User Story:** As a sistem yöneticisi, I want sonuçların görsel kartlar halinde gösterilmesini, so that atamaları kolayca okuyabileyim.

#### Acceptance Criteria

1. WHEN optimizasyon sonuçları hazır olduğunda, THE Sistem SHALL her araç sahibi için ayrı bir kart (st.container) gösterir; kartta araç sahibinin adı ve ilçesi başlık olarak yer alır.
2. WHEN bir araç sahibi kartı görüntülendiğinde, THE Sistem SHALL atanan her yolcu için isim ve ilçe bilgisini alt satır olarak listeler.
3. WHEN sonuçlar listelendiğinde, THE Sistem SHALL her yolcunun yanına tıklanabilir bir "Haritada Gör" bağlantısı ekler; bu bağlantı `https://www.google.com/maps/dir/?api=1&origin={lat},{lng}&destination={lat},{lng}&travelmode=driving` formatında olur.
4. WHEN atanamamış yolcular varsa, THE Sistem SHALL bu yolcuları ayrı bir bölümde listeler.

---

### Requirement 7

**User Story:** As a geliştirici, I want kodun modüler ve test edilebilir olmasını, so that bakım ve genişletme kolaylaşsın.

#### Acceptance Criteria

1. THE Sistem SHALL uygulama mantığını en az iki modüle ayırır: `utils.py` (veri işleme, API, optimizasyon) ve `app.py` (Streamlit arayüzü).
2. THE Sistem SHALL Google Maps API anahtarını `.env` dosyasından `python-dotenv` kütüphanesi ile okur; kaynak kodda API anahtarı bulunmaz.
3. WHEN herhangi bir API çağrısı veya dosya işlemi başarısız olursa, THE Sistem SHALL try-except bloğu ile hatayı yakalar ve kullanıcıya anlaşılır bir hata mesajı gösterir.
4. THE Sistem SHALL `generate_sample_excel.py` adında bir yardımcı script içerir; bu script mevcut Excel verisini okuyarak sütun adlarını standartlaştırılmış formatta içeren örnek bir dosya üretir.
