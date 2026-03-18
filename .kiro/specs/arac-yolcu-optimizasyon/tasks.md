# Implementation Plan

- [x] 1. Proje yapısını ve bağımlılıkları kur


  - `requirements.txt` oluştur: streamlit, pandas, openpyxl, python-dotenv, googlemaps, ortools
  - `.env.example` dosyası oluştur: `GOOGLE_MAPS_API_KEY=your_key_here`
  - `.gitignore` oluştur: `.env`, `__pycache__`, `*.pyc` girişleri
  - _Requirements: 7.2_

- [x] 2. Veri yükleme ve ön işleme modülünü yaz

- [x] 2.1 `utils.py` dosyasını oluştur ve `load_and_preprocess` fonksiyonunu yaz


  - Excel'i `header=None` ile oku, sütunları `['İsim Soyisim', 'Adres', 'İlçe', 'Posta Kodu']` olarak ata
  - `Bölge Grubu` sütununu `Posta Kodu.astype(str).str[:4]` ile oluştur
  - Eksik sütun kontrolü ve `ValueError` fırlat
  - _Requirements: 1.1, 1.3, 1.4_

- [x] 2.2 `select_drivers` fonksiyonunu `utils.py`'a ekle

  - `n` parametresi kadar rastgele satır seç, `Rol` sütununa `'Araç Sahibi'` yaz
  - Geri kalanları `'Yolcu'` olarak işaretle
  - `seed` parametresi ile tekrarlanabilir seçim sağla
  - Geçersiz `n` için `ValueError` fırlat
  - _Requirements: 2.1, 2.3_

- [x] 2.3 `test_utils.py` oluştur: `load_and_preprocess` ve `select_drivers` için unit testler yaz


  - Bölge Grubu doğruluğunu, Rol sütunu varlığını ve hata durumlarını test et
  - _Requirements: 1.1, 1.4, 2.1, 2.3_

- [x] 3. Google Maps Geocoding entegrasyonunu yaz

- [x] 3.1 `geocode_addresses` fonksiyonunu `utils.py`'a ekle


  - `googlemaps.Client` ile her adres için `geocode()` çağrısı yap
  - Sonuçları `Lat` ve `Lng` sütunlarına yaz
  - Başarısız geocoding'lerde satırı `NaN` bırak, sayacı artır
  - `cache` dict parametresi ile önbellekleme desteği ekle (aynı adres tekrar çağrılmaz)
  - _Requirements: 3.1, 3.3, 3.4_

- [x] 3.2 `build_cost_matrix` fonksiyonunu `utils.py`'a ekle


  - DataFrame'i `Bölge Grubu` bazında grupla
  - Her grup için araç sahiplerini `origins`, yolcuları `destinations` olarak ayır
  - `googlemaps.Client.distance_matrix()` ile max 10×10 batch çağrısı yap
  - Sonuçları `{(driver_idx, passenger_idx): distance_meters}` dict olarak döndür
  - Bölgesinde araç sahibi olmayan yolcuları `unassigned` listesine ekle
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 3.3 `test_utils.py`'a geocoding ve maliyet matrisi testleri ekle



  - `unittest.mock.patch` ile API çağrılarını mock'la
  - Batch boyutu kısıtını ve bölge grubu filtrelemesini doğrula
  - _Requirements: 4.1, 4.3_

- [x] 4. OR-Tools optimizasyon algoritmasını yaz

- [x] 4.1 `optimize_assignments` fonksiyonunu `utils.py`'a ekle


  - `ortools.sat.python.cp_model` ile CP-SAT model kur
  - `x[i,j]` boolean değişkenlerini tanımla (sadece cost_matrix'te olan çiftler için)
  - Kısıt 1: her yolcu en fazla 1 araç sahibine atanır
  - Kısıt 2: her araç sahibine en fazla `max_capacity` (varsayılan 3) yolcu atanır
  - Hedef: `sum(cost_matrix[i,j] * x[i,j])` minimize et
  - `INFEASIBLE` ve `UNKNOWN` durumlarını yakala, boş dict döndür
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 4.2 `test_utils.py`'a optimizasyon testleri ekle


  - Kapasite kısıtının aşılmadığını doğrula
  - Her yolcunun en fazla 1 araç sahibine atandığını doğrula
  - _Requirements: 5.1, 5.2_

- [x] 5. Streamlit arayüzünü yaz

- [x] 5.1 `app.py` iskeletini oluştur: sayfa başlığı, sidebar ve 5 adımlı akış


  - `st.set_page_config`, başlık ve sidebar (API key durumu)
  - `st.session_state` ile `df`, `cost_matrix`, `assignments` durumlarını yönet
  - _Requirements: 7.1_

- [x] 5.2 Adım 1 — Dosya yükleme bölümünü yaz


  - `st.file_uploader` ile `.xlsx` kabul et
  - `load_and_preprocess` çağır, hata mesajlarını `st.error` ile göster
  - Toplam kişi, araç sahibi (henüz 0), yolcu metriklerini `st.metric` ile göster
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 5.3 Adım 2 — Araç sahibi seçim bölümünü yaz


  - `st.number_input` ile araç sahibi sayısı al (min=1, max=len(df))
  - "Araç Sahiplerini Belirle" butonu ile `select_drivers` çağır
  - Araç sahipleri ve yolcuları ayrı `st.dataframe` tablolarında göster
  - Metrikleri güncelle
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 5.4 Adım 3 — Geocoding bölümünü yaz


  - "Koordinatları Hesapla" butonu ile `geocode_addresses` çağır
  - `st.progress` ile ilerleme çubuğu göster
  - Başarısız geocoding sayısını `st.warning` ile bildir
  - Koordinatları `st.session_state['geocode_cache']`'e kaydet
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 5.5 Adım 4 — Mesafe matrisi ve optimizasyon bölümünü yaz


  - "Optimizasyonu Çalıştır" butonu ile `build_cost_matrix` ve `optimize_assignments` çağır
  - `st.spinner` ile bekleme göstergesi ekle
  - Toplam atanan yolcu sayısını ve toplam mesafeyi göster
  - _Requirements: 4.1, 5.1, 5.4_

- [x] 5.6 Adım 5 — Sonuç kartlarını yaz


  - Her araç sahibi için `st.container` ile kart oluştur
  - Kart başlığı: araç sahibinin adı ve ilçesi
  - Her atanan yolcu için: isim, ilçe, adres ve `st.markdown` ile "Haritada Gör" linki
  - Link formatı: `https://www.google.com/maps/dir/?api=1&origin={lat},{lng}&destination={lat},{lng}&travelmode=driving`
  - Atanamamış yolcuları ayrı `st.expander` içinde listele
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 6. Yardımcı araçları yaz


- [x] 6.1 `generate_sample_excel.py` scriptini yaz


  - Mevcut `arac_planlama_adresler.xlsx` dosyasını oku
  - Sütun adlarını standartlaştır, `sample_data.xlsx` olarak kaydet
  - Komut satırından çalıştırılabilir olsun (`python generate_sample_excel.py`)
  - _Requirements: 7.4_

- [x] 6.2 Uygulamayı uçtan uca bağla ve doğrula


  - `sample_data.xlsx` ile tüm akışı çalıştır: yükleme → seçim → geocoding (mock) → optimizasyon → sonuçlar
  - Harita linklerinin doğru formatlandığını kontrol et
  - Atanamamış yolcu listesinin doğru göründüğünü doğrula
  - _Requirements: 6.3, 6.4, 7.3_
