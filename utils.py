"""
utils.py — Araç-Yolcu Optimizasyon Uygulaması
Veri işleme, Google Maps API entegrasyonu ve OR-Tools optimizasyon fonksiyonları.
"""

import os
import math
import random
import logging
from typing import Optional

import pandas as pd
import googlemaps
from ortools.sat.python import cp_model
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Beklenen sütun adları (Excel'de header yok, sırayla atanır)
EXPECTED_COLUMNS = ["İsim Soyisim", "Adres", "İlçe", "Posta Kodu"]


def load_and_preprocess(file) -> pd.DataFrame:
    """
    Excel dosyasını okur. İki format desteklenir:
    Format A (header yok): İsim Soyisim | Adres | İlçe | Posta Kodu
    Format B (header var): Ad Soyad | Ev Adresi | Posta Kodu | İl / İlçe
    Bölge Grubu sütunu Posta Kodu'nun ilk 4 hanesinden oluşturulur.
    """
    try:
        # Önce header'lı okumayı dene
        df_h = pd.read_excel(file, header=0)
    except Exception as e:
        raise Exception(f"Excel dosyası okunamadı: {e}")

    cols = [str(c).strip() for c in df_h.columns]

    # Format B: header var, "Ad Soyad" veya "Posta Kodu" sütunu içeriyor
    if any(c in cols for c in ["Ad Soyad", "Posta Kodu", "İl / İlçe"]):
        df = df_h.copy()
        df.columns = [str(c).strip() for c in df.columns]

        # Sütun adlarını normalize et
        rename_map = {}
        for c in df.columns:
            cl = c.lower()
            if "ad" in cl and "soyad" in cl:
                rename_map[c] = "İsim Soyisim"
            elif "adres" in cl or "ev adresi" in cl:
                rename_map[c] = "Adres"
            elif "posta" in cl:
                rename_map[c] = "Posta Kodu"
            elif "il" in cl and "ilçe" in cl:
                rename_map[c] = "İlçe"
        df = df.rename(columns=rename_map)

        # "İstanbul / Maltepe" → "Maltepe"
        if "İlçe" in df.columns:
            df["İlçe"] = df["İlçe"].astype(str).str.split("/").str[-1].str.strip()
        elif "İl / İlçe" in df.columns:
            df["İlçe"] = df["İl / İlçe"].astype(str).str.split("/").str[-1].str.strip()

    else:
        # Format A: header yok, dosyayı tekrar header=None ile oku
        try:
            import io
            # file pointer'ı başa sar
            if hasattr(file, "seek"):
                file.seek(0)
            df = pd.read_excel(file, header=None)
        except Exception as e:
            raise Exception(f"Excel dosyası okunamadı: {e}")

        if df.shape[1] < len(EXPECTED_COLUMNS):
            eksik = EXPECTED_COLUMNS[df.shape[1]:]
            raise ValueError(f"Eksik sütunlar: {eksik}. Dosyada {df.shape[1]} sütun bulundu.")

        df = df.iloc[:, :4].copy()
        df.columns = EXPECTED_COLUMNS

    # Ortak işlemler
    df["Posta Kodu"] = df["Posta Kodu"].astype(str).str.strip().str.split(".").str[0]
    df["Bölge Grubu"] = df["Posta Kodu"].str[:4]
    df = df.dropna(subset=["İsim Soyisim", "Adres"]).reset_index(drop=True)

    # Boş / "nan" satırları temizle
    df = df[df["İsim Soyisim"].astype(str).str.strip().str.lower() != "nan"]
    df = df[df["İsim Soyisim"].astype(str).str.strip() != ""].reset_index(drop=True)

    logger.info(f"Yüklendi: {len(df)} kişi, {df['Bölge Grubu'].nunique()} bölge grubu")
    return df


def select_drivers(df: pd.DataFrame, n: int, seed: Optional[int] = None) -> pd.DataFrame:
    """
    DataFrame'den rastgele n kişiyi araç sahibi olarak seçer. (Test/eski akış için)
    """
    if n <= 0 or n >= len(df):
        raise ValueError(f"Araç sahibi sayısı 1 ile {len(df) - 1} arasında olmalıdır. Girilen: {n}")

    df = df.copy()
    rng = random.Random(seed)
    driver_indices = rng.sample(range(len(df)), n)
    df["Rol"] = "Yolcu"
    df.loc[driver_indices, "Rol"] = "Araç Sahibi"
    logger.info(f"Seçildi: {n} araç sahibi, {len(df) - n} yolcu")
    return df


def assign_roles_manual(
    df: pd.DataFrame,
    driver_indices: list[int],
) -> pd.DataFrame:
    """
    Kullanıcının elle seçtiği kişileri araç sahibi, geri kalanları yolcu yapar.

    Args:
        df: İşlenmiş DataFrame (aktif katılımcılar — gelmeyenler çıkarılmış)
        driver_indices: Araç sahibi olarak seçilen satır index'leri

    Returns:
        pd.DataFrame: 'Rol' sütunu eklenmiş DataFrame
    """
    if not driver_indices:
        raise ValueError("En az 1 araç sahibi seçilmelidir.")

    df = df.copy()
    df["Rol"] = "Yolcu"
    df.loc[driver_indices, "Rol"] = "Araç Sahibi"
    n = len(driver_indices)
    logger.info(f"Manuel atama: {n} araç sahibi, {len(df) - n} yolcu")
    return df


def geocode_addresses(
    df: pd.DataFrame,
    api_key: str,
    cache: Optional[dict] = None,
    progress_callback=None,
) -> tuple[pd.DataFrame, int]:
    """
    Her satırdaki adresi Google Maps Geocoding API ile koordinata çevirir.

    Args:
        df: İşlenmiş DataFrame (İsim Soyisim, Adres, İlçe sütunları içermeli)
        api_key: Google Maps API anahtarı
        cache: Adres → (lat, lng) önbellek dict'i. None ise yeni dict oluşturulur.
        progress_callback: Her adres işlendiğinde çağrılan fonksiyon (i, total) → None

    Returns:
        (DataFrame, başarısız_sayı): Lat ve Lng sütunları eklenmiş DataFrame
    """
    if cache is None:
        cache = {}

    try:
        gmaps = googlemaps.Client(key=api_key)
    except Exception as e:
        raise ValueError(f"Google Maps istemcisi oluşturulamadı: {e}")

    df = df.copy()
    df["Lat"] = float("nan")
    df["Lng"] = float("nan")
    failed = 0
    total = len(df)

    for i, row in df.iterrows():
        # Adres + İlçe + "İstanbul" birleştirerek daha doğru sonuç al
        address_str = f"{row['Adres']}, {row['İlçe']}, İstanbul, Türkiye"

        if address_str in cache:
            lat, lng = cache[address_str]
            df.at[i, "Lat"] = lat
            df.at[i, "Lng"] = lng
        else:
            try:
                result = gmaps.geocode(address_str)
                if result:
                    loc = result[0]["geometry"]["location"]
                    df.at[i, "Lat"] = loc["lat"]
                    df.at[i, "Lng"] = loc["lng"]
                    cache[address_str] = (loc["lat"], loc["lng"])
                else:
                    logger.warning(f"Geocoding sonuç yok: {address_str}")
                    failed += 1
            except Exception as e:
                logger.error(f"Geocoding hatası [{row['İsim Soyisim']}]: {e}")
                failed += 1

        if progress_callback:
            progress_callback(i + 1, total)

    logger.info(f"Geocoding tamamlandı: {total - failed}/{total} başarılı")
    return df, failed


def _batch_distance_matrix(
    gmaps: googlemaps.Client,
    origins: list[tuple[float, float]],
    destinations: list[tuple[float, float]],
    origin_indices: list[int],
    destination_indices: list[int],
    cost_matrix: dict,
    batch_size: int = 10,
) -> None:
    """
    Distance Matrix API'yi max batch_size×batch_size boyutunda çağırır.
    Sonuçları cost_matrix dict'ine yazar (in-place).
    """
    for o_start in range(0, len(origins), batch_size):
        o_batch = origins[o_start: o_start + batch_size]
        o_idx_batch = origin_indices[o_start: o_start + batch_size]

        for d_start in range(0, len(destinations), batch_size):
            d_batch = destinations[d_start: d_start + batch_size]
            d_idx_batch = destination_indices[d_start: d_start + batch_size]

            try:
                result = gmaps.distance_matrix(
                    origins=o_batch,
                    destinations=d_batch,
                    mode="driving",
                    language="tr",
                )
                rows = result.get("rows", [])
                for r_i, row in enumerate(rows):
                    if r_i >= len(o_idx_batch):
                        break
                    elements = row.get("elements", [])
                    for r_j, element in enumerate(elements):
                        if r_j >= len(d_idx_batch):
                            break
                        if element.get("status") == "OK":
                            dist = element["distance"]["value"]  # metre
                            cost_matrix[(o_idx_batch[r_i], d_idx_batch[r_j])] = dist
            except Exception as e:
                logger.error(f"Distance Matrix API hatası: {e}")


def build_cost_matrix(
    df: pd.DataFrame,
    api_key: str,
) -> tuple[dict, list[int]]:
    """
    Bölge Grubu bazında araç sahipleri ile yolcular arasındaki mesafe matrisini oluşturur.

    Args:
        df: Rol, Lat, Lng ve Bölge Grubu sütunları içeren DataFrame
        api_key: Google Maps API anahtarı

    Returns:
        (cost_matrix, unassigned_passenger_indices):
            cost_matrix: {(driver_idx, passenger_idx): distance_meters}
            unassigned_passenger_indices: bölgesinde araç sahibi olmayan yolcuların index listesi
    """
    try:
        gmaps = googlemaps.Client(key=api_key)
    except Exception as e:
        raise ValueError(f"Google Maps istemcisi oluşturulamadı: {e}")

    cost_matrix: dict = {}
    unassigned: list[int] = []

    # Koordinatı olmayan satırları atla
    valid_df = df.dropna(subset=["Lat", "Lng"])

    for bolge, group in valid_df.groupby("Bölge Grubu"):
        drivers = group[group["Rol"] == "Araç Sahibi"]
        passengers = group[group["Rol"] == "Yolcu"]

        if drivers.empty:
            # Bu bölgede araç sahibi yok → yolcular atanamamış listesine
            unassigned.extend(passengers.index.tolist())
            logger.info(f"Bölge {bolge}: araç sahibi yok, {len(passengers)} yolcu atanamamış")
            continue

        if passengers.empty:
            logger.info(f"Bölge {bolge}: yolcu yok, atlanıyor")
            continue

        origins = list(zip(drivers["Lat"], drivers["Lng"]))
        destinations = list(zip(passengers["Lat"], passengers["Lng"]))
        origin_indices = drivers.index.tolist()
        destination_indices = passengers.index.tolist()

        _batch_distance_matrix(
            gmaps, origins, destinations,
            origin_indices, destination_indices,
            cost_matrix,
        )
        logger.info(f"Bölge {bolge}: {len(drivers)} araç sahibi × {len(passengers)} yolcu işlendi")

    logger.info(f"Maliyet matrisi: {len(cost_matrix)} çift, {len(unassigned)} atanamamış yolcu")
    return cost_matrix, unassigned


def optimize_assignments(
    df: pd.DataFrame,
    cost_matrix: dict,
    max_capacity: int = 3,
) -> tuple[dict, list[int]]:
    """
    OR-Tools CP-SAT Solver ile global optimal araç-yolcu ataması yapar.

    Args:
        df: Rol sütunu içeren DataFrame
        cost_matrix: {(driver_idx, passenger_idx): distance_meters}
        max_capacity: Her araç sahibine atanabilecek maksimum yolcu sayısı

    Returns:
        (assignments, unassigned_passengers):
            assignments: {driver_idx: [passenger_idx, ...]}
            unassigned_passengers: atanamamış yolcuların index listesi
    """
    driver_indices = df[df["Rol"] == "Araç Sahibi"].index.tolist()
    passenger_indices = df[df["Rol"] == "Yolcu"].index.tolist()

    if not driver_indices or not passenger_indices:
        return {}, passenger_indices

    model = cp_model.CpModel()

    # x[i, j] = 1 ise driver i, passenger j'yi taşır
    x = {}
    for i in driver_indices:
        for j in passenger_indices:
            if (i, j) in cost_matrix:
                x[i, j] = model.NewBoolVar(f"x_{i}_{j}")

    if not x:
        # Hiç geçerli çift yok
        return {d: [] for d in driver_indices}, passenger_indices

    # Kısıt 1: Her yolcu en fazla 1 araç sahibine atanır
    for j in passenger_indices:
        pairs = [x[i, j] for i in driver_indices if (i, j) in x]
        if pairs:
            model.Add(sum(pairs) <= 1)

    # Kısıt 2: Her araç sahibine en fazla max_capacity yolcu
    for i in driver_indices:
        pairs = [x[i, j] for j in passenger_indices if (i, j) in x]
        if pairs:
            model.Add(sum(pairs) <= max_capacity)

    # Maksimum mesafe — ceza hesabı için üst sınır
    max_dist = max(cost_matrix.values()) if cost_matrix else 1
    # Atanmayan yolcuya büyük ceza: tüm mesafelerin toplamından büyük bir değer
    penalty = max_dist * (len(driver_indices) * max_capacity + 1)

    # Hedef: atanan yolcuların mesafesini minimize et + atanmayan yolcuları cezalandır
    assigned_terms = [cost_matrix[i, j] * x[i, j] for (i, j) in x]
    unassigned_penalty = []
    for j in passenger_indices:
        pairs = [x[i, j] for i in driver_indices if (i, j) in x]
        if pairs:
            # assigned_j = 1 ise yolcu atandı, 0 ise atanmadı → ceza = penalty * (1 - assigned_j)
            assigned_j = model.NewBoolVar(f"assigned_{j}")
            model.Add(sum(pairs) == assigned_j)
            unassigned_penalty.append(penalty * (1 - assigned_j))

    model.Minimize(sum(assigned_terms) + sum(unassigned_penalty))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0  # zaman aşımı
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logger.warning(f"OR-Tools çözüm bulunamadı. Durum: {solver.StatusName(status)}")
        return {d: [] for d in driver_indices}, passenger_indices

    # Sonuçları topla
    assignments: dict = {d: [] for d in driver_indices}
    assigned_set = set()

    for (i, j), var in x.items():
        if solver.Value(var) == 1:
            assignments[i].append(j)
            assigned_set.add(j)

    unassigned = [j for j in passenger_indices if j not in assigned_set]

    total_dist = sum(
        cost_matrix[i, j]
        for i, passengers in assignments.items()
        for j in passengers
        if (i, j) in cost_matrix
    )
    logger.info(
        f"Optimizasyon tamamlandı: {len(assigned_set)} yolcu atandı, "
        f"{len(unassigned)} atanamamadı, toplam mesafe: {total_dist}m"
    )
    return assignments, unassigned


def load_arac_listesi(file) -> pd.DataFrame:
    """
    Araç listesi Excel'ini okur ve temizler.
    Sütunlar: No, Plaka, Kullanan
    'Ortak Kullanım (X kullanıyor)' satırlarından gerçek kullananı çıkarır.

    Returns:
        DataFrame: Plaka, Kullanan, GercekKullanan sütunları
    """
    try:
        df = pd.read_excel(file, header=None)
    except Exception as e:
        raise Exception(f"Araç listesi okunamadı: {e}")

    # İlk 3 sütunu al
    df = df.iloc[:, :3].copy()
    df.columns = ["No", "Plaka", "Kullanan"]

    # Boş plaka satırlarını at
    df = df.dropna(subset=["Plaka"]).copy()
    df["Plaka"] = df["Plaka"].astype(str).str.strip()
    df["Kullanan"] = df["Kullanan"].fillna("").astype(str).str.strip()

    # Gerçek kullananı çıkar:
    # "Ortak Kullanım (Furkan Şentürk kullanıyor)" → "Furkan Şentürk"
    # "Ortak Kullanım (Plan için müsait)" → None
    # "Ortak Kullanım" → None
    # "Mehmet Tükel (GM)" → "Mehmet Tükel"
    import re

    def extract_name(kullanan: str) -> str:
        kullanan = kullanan.strip()
        if not kullanan or kullanan.lower() in ("bekliyor", ""):
            return ""

        # "Ortak Kullanım (X kullanıyor)" → X
        m = re.search(r"Ortak [Kk]ullan[ıi]m\s*\((.+?)\s*kullan[ıi]yor\)", kullanan, re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # "Ortak Kullanım (Plan için müsait)" veya sadece "Ortak Kullanım" → boş
        if re.match(r"Ortak [Kk]ullan[ıi]m", kullanan, re.IGNORECASE):
            return ""

        # "Mehmet Tükel (GM)" → "Mehmet Tükel"
        m2 = re.match(r"^(.+?)\s*\(", kullanan)
        if m2:
            return m2.group(1).strip()

        return kullanan

    df["GercekKullanan"] = df["Kullanan"].apply(extract_name)

    # Sadece gerçek kullananı olan satırları döndür (boş olanlar araç sahibi değil)
    logger.info(f"Araç listesi: {len(df)} araç, {(df['GercekKullanan'] != '').sum()} kişiye atanmış")
    return df.reset_index(drop=True)


def eslesir_mi(isim1: str, isim2: str) -> bool:
    """
    İki ismin eşleşip eşleşmediğini kontrol eder.
    Büyük/küçük harf ve Türkçe karakter normalizasyonu yapar.
    """
    def normalize(s: str) -> str:
        s = s.lower().strip()
        tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        return s.translate(tr_map)

    n1 = normalize(isim1)
    n2 = normalize(isim2)
    return n1 == n2 or n1 in n2 or n2 in n1


def eslesenleri_bul(katilimci_df: pd.DataFrame, arac_df: pd.DataFrame) -> list[int]:
    """
    Araç listesindeki GercekKullanan isimlerini katılımcı listesiyle eşleştirir.

    Returns:
        Katılımcı DataFrame'indeki araç sahibi index listesi
    """
    arac_sahipleri = arac_df[arac_df["GercekKullanan"] != ""]["GercekKullanan"].tolist()
    driver_indices = []

    for idx, row in katilimci_df.iterrows():
        katilimci_isim = str(row["İsim Soyisim"])
        for arac_isim in arac_sahipleri:
            if eslesir_mi(katilimci_isim, arac_isim):
                driver_indices.append(idx)
                break

    logger.info(f"Eşleşme: {len(driver_indices)} araç sahibi katılımcı listesinde bulundu")
    return driver_indices


def build_export_df(assignments_edit: dict, df_geo: pd.DataFrame, cost_matrix: dict) -> pd.DataFrame:
    """
    Atama sonuçlarını düz tablo formatına çevirir.
    Her satır: Araç Sahibi | Plaka | Araç Sahibi İlçe | Yolcu | Yolcu İlçe | Mesafe (km)
    """
    rows = []
    for driver_idx, passenger_list in assignments_edit.items():
        driver = df_geo.loc[driver_idx]
        d_name = driver["İsim Soyisim"]
        d_ilce = driver["İlçe"]
        if not passenger_list:
            rows.append({
                "Araç Sahibi": d_name,
                "Araç Sahibi İlçe": d_ilce,
                "Yolcu": "—",
                "Yolcu İlçe": "—",
                "Mesafe (km)": "—",
            })
        for p_idx in passenger_list:
            p = df_geo.loc[p_idx]
            dist_km = cost_matrix.get((driver_idx, p_idx), 0) / 1000
            rows.append({
                "Araç Sahibi": d_name,
                "Araç Sahibi İlçe": d_ilce,
                "Yolcu": p["İsim Soyisim"],
                "Yolcu İlçe": p["İlçe"],
                "Mesafe (km)": round(dist_km, 1),
            })
    return pd.DataFrame(rows)


def export_to_excel(df_export: pd.DataFrame) -> bytes:
    """DataFrame'i Excel (xlsx) formatında bytes olarak döndürür."""
    import io
    import xlsxwriter

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Atamalar")
        wb = writer.book
        ws = writer.sheets["Atamalar"]

        # Başlık formatı
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#4472C4", "font_color": "white",
            "border": 1, "align": "center",
        })
        driver_fmt = wb.add_format({"bg_color": "#D9E1F2", "border": 1})
        normal_fmt = wb.add_format({"border": 1})

        # Sütun genişlikleri
        ws.set_column("A:A", 28)
        ws.set_column("B:B", 18)
        ws.set_column("C:C", 28)
        ws.set_column("D:D", 18)
        ws.set_column("E:E", 14)

        # Başlıkları yeniden yaz
        for col_num, col_name in enumerate(df_export.columns):
            ws.write(0, col_num, col_name, header_fmt)

        # Satırları formatla
        prev_driver = None
        for row_num, row in enumerate(df_export.itertuples(index=False), start=1):
            fmt = driver_fmt if row[0] != prev_driver else normal_fmt
            prev_driver = row[0]
            for col_num, val in enumerate(row):
                ws.write(row_num, col_num, val, fmt)

    return buf.getvalue()


def export_to_pdf(df_export: pd.DataFrame) -> bytes:
    """DataFrame'i PDF formatında bytes olarak döndürür."""
    import io
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Heading1"],
        fontSize=14, spaceAfter=12, alignment=1,
    )

    elements = []
    elements.append(Paragraph("Araç-Yolcu Atama Listesi", title_style))
    elements.append(Spacer(1, 0.3*cm))

    # Tablo verisi
    header = list(df_export.columns)
    data = [header] + [list(row) for row in df_export.itertuples(index=False)]

    col_widths = [6*cm, 4*cm, 6*cm, 4*cm, 3*cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Renk bloklarını belirle (araç sahibi değişince renk değişsin)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#D9E1F2"), colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    table.setStyle(TableStyle(style_cmds))
    elements.append(table)

    doc.build(elements)
    return buf.getvalue()
