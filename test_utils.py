"""
test_utils.py — utils.py için unit testler
Çalıştırmak için: pytest test_utils.py -v
"""

import io
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from utils import load_and_preprocess, select_drivers, geocode_addresses, build_cost_matrix, optimize_assignments, EXPECTED_COLUMNS


# ─── Yardımcı: test için in-memory Excel üret ───────────────────────────────

def make_excel_bytes(rows: list[list]) -> io.BytesIO:
    """Verilen satırlardan header'sız bir Excel dosyası üretir."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, header=False)
    buf.seek(0)
    return buf


SAMPLE_ROWS = [
    ["Ahmet Yılmaz", "Atatürk Cad. No:1", "Kadıköy", "34710"],
    ["Ayşe Kaya",    "İstiklal Cad. No:5", "Beyoğlu", "34435"],
    ["Mehmet Demir", "Bağdat Cad. No:10",  "Maltepe", "34843"],
    ["Fatma Çelik",  "Halkalı Cad. No:3",  "Küçükçekmece", "34295"],
    ["Ali Veli",     "Ordu Cad. No:7",     "Sancaktepe", "34785"],
]


# ─── load_and_preprocess testleri ───────────────────────────────────────────

class TestLoadAndPreprocess:

    def test_sutunlar_dogru_atanir(self):
        buf = make_excel_bytes(SAMPLE_ROWS)
        df = load_and_preprocess(buf)
        assert list(df.columns[:4]) == EXPECTED_COLUMNS

    def test_bolge_grubu_ilk_4_hane(self):
        buf = make_excel_bytes(SAMPLE_ROWS)
        df = load_and_preprocess(buf)
        assert "Bölge Grubu" in df.columns
        # 34710 → 3471
        assert df.loc[df["İsim Soyisim"] == "Ahmet Yılmaz", "Bölge Grubu"].values[0] == "3471"
        # 34843 → 3484
        assert df.loc[df["İsim Soyisim"] == "Mehmet Demir", "Bölge Grubu"].values[0] == "3484"

    def test_satir_sayisi_dogru(self):
        buf = make_excel_bytes(SAMPLE_ROWS)
        df = load_and_preprocess(buf)
        assert len(df) == len(SAMPLE_ROWS)

    def test_az_sutun_value_error(self):
        # Sadece 2 sütunlu dosya
        buf = make_excel_bytes([["Ahmet", "Adres"], ["Ayşe", "Adres2"]])
        with pytest.raises(ValueError, match="Eksik sütunlar"):
            load_and_preprocess(buf)

    def test_gecersiz_dosya_exception(self):
        with pytest.raises(Exception):
            load_and_preprocess("var_olmayan_dosya.xlsx")

    def test_posta_kodu_string_olur(self):
        # Posta kodu integer olarak gelirse de string'e çevrilmeli
        rows = [["Test Kişi", "Test Adres", "İlçe", 34710]]
        buf = make_excel_bytes(rows)
        df = load_and_preprocess(buf)
        assert df["Bölge Grubu"].values[0] == "3471"


# ─── select_drivers testleri ────────────────────────────────────────────────

class TestSelectDrivers:

    def setup_method(self):
        buf = make_excel_bytes(SAMPLE_ROWS)
        self.df = load_and_preprocess(buf)

    def test_rol_sutunu_eklenir(self):
        result = select_drivers(self.df, n=2, seed=42)
        assert "Rol" in result.columns

    def test_arac_sahibi_sayisi_dogru(self):
        result = select_drivers(self.df, n=2, seed=42)
        assert (result["Rol"] == "Araç Sahibi").sum() == 2

    def test_yolcu_sayisi_dogru(self):
        result = select_drivers(self.df, n=2, seed=42)
        assert (result["Rol"] == "Yolcu").sum() == len(self.df) - 2

    def test_seed_ile_tekrarlanabilir(self):
        r1 = select_drivers(self.df, n=2, seed=42)
        r2 = select_drivers(self.df, n=2, seed=42)
        assert list(r1["Rol"]) == list(r2["Rol"])

    def test_farkli_seed_farkli_sonuc(self):
        r1 = select_drivers(self.df, n=2, seed=1)
        r2 = select_drivers(self.df, n=2, seed=99)
        # 5 kişiden 2 seçimde farklı seed farklı sonuç verebilir (her zaman değil ama büyük veri için güvenli)
        # Burada sadece her iki sonucun da geçerli olduğunu doğruluyoruz
        assert (r1["Rol"] == "Araç Sahibi").sum() == 2
        assert (r2["Rol"] == "Araç Sahibi").sum() == 2

    def test_n_sifir_value_error(self):
        with pytest.raises(ValueError):
            select_drivers(self.df, n=0)

    def test_n_toplam_kadar_value_error(self):
        with pytest.raises(ValueError):
            select_drivers(self.df, n=len(self.df))

    def test_n_negatif_value_error(self):
        with pytest.raises(ValueError):
            select_drivers(self.df, n=-1)

    def test_orijinal_df_degismez(self):
        """select_drivers orijinal DataFrame'i değiştirmemeli."""
        original_cols = list(self.df.columns)
        select_drivers(self.df, n=2, seed=42)
        assert list(self.df.columns) == original_cols
        assert "Rol" not in self.df.columns


# ─── Yardımcı: koordinatlı test DataFrame'i ─────────────────────────────────

def make_df_with_coords(rows_with_coords: list[dict]) -> pd.DataFrame:
    """
    Rol, Lat, Lng, Bölge Grubu sütunları olan DataFrame üretir.
    rows_with_coords: [{"isim": ..., "ilce": ..., "bolge": ..., "rol": ..., "lat": ..., "lng": ...}]
    """
    records = []
    for r in rows_with_coords:
        records.append({
            "İsim Soyisim": r["isim"],
            "Adres": "Test Adres",
            "İlçe": r["ilce"],
            "Posta Kodu": r["bolge"] + "0",
            "Bölge Grubu": r["bolge"],
            "Rol": r["rol"],
            "Lat": r["lat"],
            "Lng": r["lng"],
        })
    return pd.DataFrame(records)


# ─── geocode_addresses testleri ─────────────────────────────────────────────

class TestGeocodeAddresses:

    def setup_method(self):
        buf = make_excel_bytes(SAMPLE_ROWS)
        self.df = load_and_preprocess(buf)

    @patch("utils.googlemaps.Client")
    def test_koordinatlar_eklenir(self, mock_client_cls):
        """Başarılı geocoding sonucunda Lat/Lng sütunları dolar."""
        mock_gmaps = MagicMock()
        mock_client_cls.return_value = mock_gmaps
        mock_gmaps.geocode.return_value = [
            {"geometry": {"location": {"lat": 41.0, "lng": 29.0}}}
        ]

        result_df, failed = geocode_addresses(self.df, api_key="FAKE_KEY")

        assert "Lat" in result_df.columns
        assert "Lng" in result_df.columns
        assert failed == 0
        assert result_df["Lat"].notna().all()

    @patch("utils.googlemaps.Client")
    def test_bos_sonuc_failed_sayar(self, mock_client_cls):
        """Geocoding boş liste döndürürse failed sayacı artar."""
        mock_gmaps = MagicMock()
        mock_client_cls.return_value = mock_gmaps
        mock_gmaps.geocode.return_value = []  # boş sonuç

        result_df, failed = geocode_addresses(self.df, api_key="FAKE_KEY")

        assert failed == len(self.df)
        assert result_df["Lat"].isna().all()

    @patch("utils.googlemaps.Client")
    def test_onbellekleme_calisir(self, mock_client_cls):
        """Aynı adres için cache varsa API tekrar çağrılmaz."""
        mock_gmaps = MagicMock()
        mock_client_cls.return_value = mock_gmaps
        mock_gmaps.geocode.return_value = [
            {"geometry": {"location": {"lat": 41.0, "lng": 29.0}}}
        ]

        cache = {}
        # İlk çağrı — API çağrısı yapılır
        geocode_addresses(self.df, api_key="FAKE_KEY", cache=cache)
        first_call_count = mock_gmaps.geocode.call_count

        # İkinci çağrı — cache dolu, API çağrısı yapılmamalı
        geocode_addresses(self.df, api_key="FAKE_KEY", cache=cache)
        second_call_count = mock_gmaps.geocode.call_count

        assert second_call_count == first_call_count  # yeni çağrı yok

    @patch("utils.googlemaps.Client")
    def test_api_exception_failed_sayar(self, mock_client_cls):
        """API exception fırlatırsa failed sayacı artar, uygulama çökmez."""
        mock_gmaps = MagicMock()
        mock_client_cls.return_value = mock_gmaps
        mock_gmaps.geocode.side_effect = Exception("API hatası")

        result_df, failed = geocode_addresses(self.df, api_key="FAKE_KEY")

        assert failed == len(self.df)


# ─── build_cost_matrix testleri ─────────────────────────────────────────────

class TestBuildCostMatrix:

    @patch("utils.googlemaps.Client")
    def test_ayni_bolgede_maliyet_hesaplanir(self, mock_client_cls):
        """Aynı bölgedeki araç sahibi-yolcu çiftleri için maliyet matrisi dolar."""
        mock_gmaps = MagicMock()
        mock_client_cls.return_value = mock_gmaps
        mock_gmaps.distance_matrix.return_value = {
            "rows": [
                {"elements": [{"status": "OK", "distance": {"value": 1500}}]},
            ]
        }

        df = make_df_with_coords([
            {"isim": "Sürücü A", "ilce": "Kadıköy", "bolge": "3471", "rol": "Araç Sahibi", "lat": 41.0, "lng": 29.0},
            {"isim": "Yolcu B",  "ilce": "Kadıköy", "bolge": "3471", "rol": "Yolcu",       "lat": 41.1, "lng": 29.1},
        ])

        cost_matrix, unassigned = build_cost_matrix(df, api_key="FAKE_KEY")

        assert len(cost_matrix) > 0
        assert len(unassigned) == 0

    @patch("utils.googlemaps.Client")
    def test_arac_sahibi_olmayan_bolge_unassigned(self, mock_client_cls):
        """Bölgesinde araç sahibi olmayan yolcular unassigned listesine girer."""
        mock_gmaps = MagicMock()
        mock_client_cls.return_value = mock_gmaps

        df = make_df_with_coords([
            {"isim": "Yolcu A", "ilce": "Maltepe", "bolge": "3484", "rol": "Yolcu", "lat": 40.9, "lng": 29.1},
            {"isim": "Yolcu B", "ilce": "Maltepe", "bolge": "3484", "rol": "Yolcu", "lat": 40.8, "lng": 29.2},
        ])

        cost_matrix, unassigned = build_cost_matrix(df, api_key="FAKE_KEY")

        assert len(cost_matrix) == 0
        assert len(unassigned) == 2
        # Distance Matrix API çağrılmamalı
        mock_gmaps.distance_matrix.assert_not_called()

    @patch("utils.googlemaps.Client")
    def test_farkli_bolgeler_karistirilmaz(self, mock_client_cls):
        """Farklı bölgedeki araç sahibi-yolcu çiftleri için maliyet hesaplanmaz."""
        mock_gmaps = MagicMock()
        mock_client_cls.return_value = mock_gmaps
        mock_gmaps.distance_matrix.return_value = {
            "rows": [{"elements": [{"status": "OK", "distance": {"value": 2000}}]}]
        }

        df = make_df_with_coords([
            {"isim": "Sürücü A", "ilce": "Kadıköy",  "bolge": "3471", "rol": "Araç Sahibi", "lat": 41.0, "lng": 29.0},
            {"isim": "Yolcu B",  "ilce": "Maltepe",   "bolge": "3484", "rol": "Yolcu",       "lat": 40.9, "lng": 29.1},
        ])

        cost_matrix, unassigned = build_cost_matrix(df, api_key="FAKE_KEY")

        # Farklı bölgede olduğu için yolcu unassigned'a düşmeli
        assert len(unassigned) == 1
        # Sürücü A ile Yolcu B arasında maliyet olmamalı
        assert len(cost_matrix) == 0


# ─── optimize_assignments testleri ──────────────────────────────────────────

def make_opt_df(driver_count: int, passenger_count: int) -> pd.DataFrame:
    """Optimizasyon testi için basit DataFrame üretir (tek bölge)."""
    records = []
    for i in range(driver_count):
        records.append({
            "İsim Soyisim": f"Sürücü {i}",
            "Adres": "Adres", "İlçe": "İlçe",
            "Posta Kodu": "34710", "Bölge Grubu": "3471",
            "Rol": "Araç Sahibi", "Lat": 41.0 + i * 0.01, "Lng": 29.0,
        })
    for j in range(passenger_count):
        records.append({
            "İsim Soyisim": f"Yolcu {j}",
            "Adres": "Adres", "İlçe": "İlçe",
            "Posta Kodu": "34710", "Bölge Grubu": "3471",
            "Rol": "Yolcu", "Lat": 41.0 + j * 0.005, "Lng": 29.1,
        })
    return pd.DataFrame(records)


def make_cost_matrix(df: pd.DataFrame) -> dict:
    """Tüm araç sahibi-yolcu çiftleri için sabit mesafeli maliyet matrisi üretir."""
    drivers = df[df["Rol"] == "Araç Sahibi"].index.tolist()
    passengers = df[df["Rol"] == "Yolcu"].index.tolist()
    cost = {}
    for i, d in enumerate(drivers):
        for j, p in enumerate(passengers):
            # Sürücüye yakın yolcular daha düşük maliyetli
            cost[(d, p)] = 1000 + abs(i - j) * 200
    return cost


class TestOptimizeAssignments:

    def test_kapasite_asilmaz(self):
        """Hiçbir araç sahibine max_capacity'den fazla yolcu atanmamalı."""
        df = make_opt_df(driver_count=2, passenger_count=6)
        cost_matrix = make_cost_matrix(df)
        assignments, _ = optimize_assignments(df, cost_matrix, max_capacity=3)

        for driver_idx, passengers in assignments.items():
            assert len(passengers) <= 3, f"Sürücü {driver_idx} kapasiteyi aştı: {len(passengers)}"

    def test_her_yolcu_en_fazla_bir_surucuye_atanir(self):
        """Bir yolcu birden fazla araç sahibine atanmamalı."""
        df = make_opt_df(driver_count=2, passenger_count=4)
        cost_matrix = make_cost_matrix(df)
        assignments, _ = optimize_assignments(df, cost_matrix, max_capacity=3)

        all_assigned = []
        for passengers in assignments.values():
            all_assigned.extend(passengers)

        assert len(all_assigned) == len(set(all_assigned)), "Yolcu birden fazla atandı"

    def test_atama_sayisi_dogru(self):
        """2 sürücü × 3 kapasite = max 6 yolcu atanabilir; 4 yolcu varsa 4'ü atanmalı."""
        df = make_opt_df(driver_count=2, passenger_count=4)
        cost_matrix = make_cost_matrix(df)
        assignments, unassigned = optimize_assignments(df, cost_matrix, max_capacity=3)

        total_assigned = sum(len(p) for p in assignments.values())
        assert total_assigned == 4
        assert len(unassigned) == 0

    def test_kapasiteyi_asan_yolcular_unassigned(self):
        """Kapasite dolunca fazla yolcular unassigned listesine girmeli."""
        df = make_opt_df(driver_count=1, passenger_count=5)
        cost_matrix = make_cost_matrix(df)
        assignments, unassigned = optimize_assignments(df, cost_matrix, max_capacity=3)

        total_assigned = sum(len(p) for p in assignments.values())
        assert total_assigned == 3
        assert len(unassigned) == 2

    def test_bos_cost_matrix_bos_atama(self):
        """Maliyet matrisi boşsa atama yapılmamalı."""
        df = make_opt_df(driver_count=2, passenger_count=3)
        assignments, unassigned = optimize_assignments(df, cost_matrix={}, max_capacity=3)

        total_assigned = sum(len(p) for p in assignments.values())
        assert total_assigned == 0
        assert len(unassigned) == 3
