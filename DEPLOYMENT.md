# 🚀 Streamlit Cloud Deployment Rehberi

Bu doküman, Araç-Yolcu Optimizasyon uygulamasını Streamlit Cloud'a deploy etmek için gereken adımları içerir.

## 📋 Ön Gereksinimler

1. **Google Maps API Key**: Google Cloud Console'dan aktif bir API key'iniz olmalı
2. **Streamlit Cloud Hesabı**: [share.streamlit.io](https://share.streamlit.io) üzerinden GitHub hesabınızla giriş yapın

## 🔑 Google Maps API Key Yapılandırması

### 1. API Key Oluşturma (Eğer yoksa)

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. "Create Credentials" → "API Key"
3. Aşağıdaki API'leri aktif edin:
   - Geocoding API
   - Distance Matrix API

### 2. API Key Kısıtlamalarını Ayarlama

**ÖNEMLİ**: API key'inizi güvenli hale getirmek için:

1. Google Cloud Console → Credentials → API Key'inizi seçin
2. "Application restrictions" bölümünde:
   - **Geliştirme için**: "None" seçebilirsiniz (geçici)
   - **Production için**: "HTTP referrers" seçin ve şunları ekleyin:
     ```
     localhost:*
     *.streamlit.app/*
     ```

## 🌐 Streamlit Cloud'a Deploy

### Adım 1: Repository'yi GitHub'a Push Edin

```bash
git add .
git commit -m "Deploy için hazır"
git push origin main
```

### Adım 2: Streamlit Cloud'da Uygulama Oluşturun

1. [share.streamlit.io](https://share.streamlit.io) → "New app"
2. Repository, branch ve main file path'i seçin:
   - **Repository**: `your-username/your-repo`
   - **Branch**: `main`
   - **Main file path**: `app.py`

### Adım 3: Secrets Yapılandırması

**ÇOK ÖNEMLİ**: Bu adımı atlamayın, aksi halde uygulama çalışmaz!

1. Streamlit Cloud dashboard'unda uygulamanızın yanındaki **"⋮" (3 nokta)** → **Settings**
2. Sol menüden **"Secrets"** sekmesini açın
3. Aşağıdaki içeriği yapıştırın ve kendi değerlerinizle doldurun:

```toml
GOOGLE_MAPS_API_KEY = "AIzaSyAHOHTKZIayBk7HelPnnAxir3_zCVpbGV4"
APP_PASSWORD = "btc1234"
```

4. **"Save"** butonuna tıklayın
5. Uygulama otomatik olarak yeniden başlayacak

### Adım 4: Deploy'u Başlatın

"Deploy!" butonuna tıklayın. İlk deploy 2-3 dakika sürebilir.

## ✅ Deployment Kontrolü

Deploy tamamlandıktan sonra:

1. Uygulamanın açılış sayfasında şifre girişi yapın
2. Sol sidebar'da "✅ API Key yüklendi" mesajını görmelisiniz
3. Bir test Excel dosyası yükleyip geocoding işlemini test edin

## 🐛 Sorun Giderme

### "API Key eksik" Hatası

**Neden**: Streamlit Secrets'a key eklenmemiş veya yanlış yazılmış

**Çözüm**:
1. Settings → Secrets bölümünü açın
2. `GOOGLE_MAPS_API_KEY` satırının tam olarak bu şekilde yazıldığından emin olun
3. Key'in başında/sonunda boşluk olmadığından emin olun
4. Save'e tıklayıp uygulamayı yeniden başlatın

### "Geocoding API Error" Hatası

**Neden**: API key geçersiz veya kısıtlamalar yanlış yapılandırılmış

**Çözüm**:
1. Google Cloud Console'da API key'in aktif olduğunu kontrol edin
2. Geocoding API ve Distance Matrix API'nin enabled olduğunu kontrol edin
3. Application restrictions'da `*.streamlit.app` domain'inin ekli olduğunu kontrol edin
4. Geçici olarak restrictions'ı "None" yapıp test edin

### Uygulama Yavaş Çalışıyor

**Neden**: Streamlit Cloud free tier sınırlamaları

**Çözüm**:
- Büyük Excel dosyaları için geocoding cache kullanılıyor (otomatik)
- Eğer çok yavaşsa, Streamlit Cloud'un ücretli planlarına geçmeyi düşünün

## 📝 Lokal Geliştirme

Lokal ortamda çalıştırmak için:

1. `.env` dosyasını oluşturun:
```bash
GOOGLE_MAPS_API_KEY=your_key_here
APP_PASSWORD=btc1234
```

2. Bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

3. Uygulamayı çalıştırın:
```bash
streamlit run app.py
```

## 🔒 Güvenlik Notları

- ✅ `.env` ve `.streamlit/secrets.toml` dosyaları `.gitignore`'da
- ✅ API key'ler asla GitHub'a push edilmemeli
- ✅ Production'da API key restrictions mutlaka aktif olmalı
- ✅ Uygulama şifre korumalı

## 📞 Destek

Sorun yaşarsanız:
1. Streamlit Cloud logs'ları kontrol edin (Settings → Logs)
2. Google Cloud Console'da API kullanım istatistiklerini kontrol edin
3. Bu dokümanın "Sorun Giderme" bölümüne bakın
