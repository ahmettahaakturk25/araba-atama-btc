"""
generate_sample_excel.py — Örnek Excel dosyası üretici
Mevcut arac_planlama_adresler.xlsx dosyasını okur,
sütun adlarını standartlaştırır ve sample_data.xlsx olarak kaydeder.

Kullanım:
    python generate_sample_excel.py
    python generate_sample_excel.py --input baska_dosya.xlsx --output cikti.xlsx
"""

import argparse
import sys
import pandas as pd


def generate_sample(input_path: str, output_path: str) -> None:
    """
    Excel dosyasını okur, sütun adlarını standartlaştırır ve kaydeder.

    Args:
        input_path: Kaynak Excel dosyası yolu
        output_path: Çıktı Excel dosyası yolu
    """
    try:
        df = pd.read_excel(input_path, header=None)
    except FileNotFoundError:
        print(f"HATA: Dosya bulunamadı: {input_path}")
        sys.exit(1)
    except Exception as e:
        print(f"HATA: Dosya okunamadı: {e}")
        sys.exit(1)

    if df.shape[1] < 4:
        print(f"HATA: Dosyada en az 4 sütun bekleniyor, {df.shape[1]} bulundu.")
        sys.exit(1)

    # İlk 4 sütunu al ve standart adları ver
    df = df.iloc[:, :4].copy()
    df.columns = ["İsim Soyisim", "Adres", "İlçe", "Posta Kodu"]

    # Boş satırları temizle
    df = df.dropna(subset=["İsim Soyisim", "Adres"]).reset_index(drop=True)

    # Posta Kodu'nu string'e çevir
    df["Posta Kodu"] = df["Posta Kodu"].astype(str).str.strip()

    try:
        df.to_excel(output_path, index=False)
        print(f"✅ {len(df)} kişi → {output_path} dosyasına kaydedildi.")
    except Exception as e:
        print(f"HATA: Dosya kaydedilemedi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Örnek Excel dosyası üretici")
    parser.add_argument(
        "--input",
        default="arac_planlama_adresler.xlsx",
        help="Kaynak Excel dosyası (varsayılan: arac_planlama_adresler.xlsx)",
    )
    parser.add_argument(
        "--output",
        default="sample_data.xlsx",
        help="Çıktı Excel dosyası (varsayılan: sample_data.xlsx)",
    )
    args = parser.parse_args()
    generate_sample(args.input, args.output)
