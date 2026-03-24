"""
Katılım durumu test dosyası oluşturur
"""
import pandas as pd

# Örnek katılım durumu verisi
data = {
    "Adı": [
        "Tuğçe Sızan",
        "Ömer Faruk Demir",
        "Olgun Dincer",
        "Damla Sözen",
        "Reyyan Özer",
        "Aliye Coşkunlar",
        "Burcu Muradoğlu",
        "Berk Aktaş",
        "Erdem Güneş",
        "Esengül Ergün",
        "Fatma Nur Acar",
    ],
    "Katılım": [
        "Toplantı Düzenleyicisi Kabul",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
        "İsteğe Bağlı Katılan",
    ],
    "Yanıt": [
        "Kabul",
        "Kabul",
        "Red",
        "Red",
        "Kabul",
        "Kabul",
        "Kabul",
        "Kabul",
        "Kabul",
        "Kabul",
        "Kabul",
    ]
}

df = pd.DataFrame(data)

# Excel'e kaydet
output_file = "katilim_durumu_test.xlsx"
df.to_excel(output_file, index=False)
print(f"✅ {output_file} oluşturuldu")
print(f"   Toplam: {len(df)} kişi")
print(f"   Red: {len(df[df['Yanıt'] == 'Red'])} kişi")
