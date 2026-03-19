# 🚗 Araç-Yolcu Optimizasyon Uygulaması

Katılımcı listesi ve araç listesini kullanarak optimal araç-yolcu eşleştirmesi yapan Streamlit uygulaması.

## ✨ Özellikler

- 📊 Excel dosyalarından katılımcı ve araç listesi yükleme
- 🔍 Katılımcı arama ve filtreleme
- ✅ Gelmeyecek kişileri işaretleme
- 🚗 Otomatik araç sahibi eşleştirme
- 📍 Google Maps Geocoding API ile adres → koordinat dönüşümü
- 🗺️ Google Maps Distance Matrix API ile mesafe hesaplama
- 🧮 OR-Tools ile optimal atama (minimum toplam mesafe)
- 🎨 İnteraktif kart görünümü
- ✏️ Manuel düzenleme ve yeniden atama
- 📥 Excel ve PDF export

## 🚀 Hızlı Başlangıç

### Lokal Kurulum

1. **Bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

2. **API Key yapılandırması:**
`.env` dosyası oluşturun:
```bash
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
APP_PASSWORD=btc1234
```

3. **Uygulamayı çalıştırın:**
```bash
streamlit run app.py
```

### Streamlit Cloud'a Deploy

Detaylı deployment rehberi için [DEPLOYMENT.md](DEPLOYMENT.md) dosyasına bakın.

**Kısa özet:**
1. Repository'yi GitHub'a push edin
2. [share.streamlit.io](https://share.streamlit.io) → New app
3. Settings → Secrets bölümüne API key'inizi ekleyin
4. Deploy!

## 📋 Kullanım

### Sayfa 1: Katılımcı Listesi

1. Excel dosyasını yükleyin (İsim Soyisim, Adres, İlçe, Posta Kodu)
2. Gelmeyecek kişileri işaretleyin
3. "Sayfa 2'ye Geç" butonuna tıklayın

### Sayfa 2: Araç Sahibi & Atama

1. Araç listesi Excel'ini yükleyin (otomatik eşleştirme yapılır)
2. Araç sahiplerini onaylayın veya düzenleyin
3. "Geocoding + Optimizasyon Çalıştır" butonuna tıklayın
4. Sonuçları kartlarda görüntüleyin
5. Manuel düzenlemeler yapın (yolcu ekle/çıkar, yeni öneri)
6. Excel veya PDF olarak indirin

## 🔧 Teknik Detaylar

### Kullanılan Teknolojiler

- **Streamlit**: Web arayüzü
- **Pandas**: Veri işleme
- **Google Maps APIs**: Geocoding ve Distance Matrix
- **OR-Tools**: Constraint Programming ile optimizasyon
- **ReportLab**: PDF export
- **XlsxWriter**: Excel export

### Optimizasyon Algoritması

- **Model**: CP-SAT (Constraint Programming - Satisfiability)
- **Hedef**: Toplam mesafeyi minimize et
- **Kısıtlar**:
  - Her yolcu en fazla 1 araç sahibine atanır
  - Her araç sahibine en fazla 3 yolcu atanır
  - Bölge grubu bazında eşleştirme (aynı posta kodu ilk 4 hanesi)
- **Ceza sistemi**: Atanmayan yolcular için büyük ceza değeri

### Veri Formatları

**Katılımcı Listesi:**
- Format A (header yok): İsim Soyisim | Adres | İlçe | Posta Kodu
- Format B (header var): Ad Soyad | Ev Adresi | Posta Kodu | İl / İlçe

**Araç Listesi:**
- No | Plaka | Kullanan
- "Ortak Kullanım (X kullanıyor)" formatını destekler

## 🔒 Güvenlik

- ✅ Şifre korumalı giriş
- ✅ API key'ler environment variables'da
- ✅ `.env` ve `secrets.toml` dosyaları `.gitignore`'da
- ✅ Google Maps API key restrictions önerilir

## 📝 Lisans

Bu proje özel kullanım içindir.

## 🤝 Katkıda Bulunma

Sorun bildirmek veya öneride bulunmak için issue açabilirsiniz.

## 📞 Destek

Deployment sorunları için [DEPLOYMENT.md](DEPLOYMENT.md) dosyasındaki "Sorun Giderme" bölümüne bakın.
