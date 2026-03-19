"""
app.py — Araç-Yolcu Optimizasyon ve Planlama Uygulaması
Sayfa 1: Katılımcı listesi + search + gelmeyenleri işaretle
Sayfa 2: Araç listesi yükle, otomatik eşleştir, optimizasyon, sonuç kartları
"""

import os
import pandas as pd
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

from utils import (
    load_and_preprocess,
    load_arac_listesi,
    eslesenleri_bul,
    eslesir_mi,
    assign_roles_manual,
    geocode_addresses,
    build_cost_matrix,
    optimize_assignments,
)

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

# API key: önce Streamlit Secrets, yoksa .env
def get_api_key() -> str:
    """
    Google Maps API key'ini önce Streamlit Secrets'tan, 
    yoksa .env dosyasından okur.
    
    Streamlit Cloud'da çalışırken mutlaka Secrets kullanılmalıdır.
    """
    try:
        key = st.secrets["GOOGLE_MAPS_API_KEY"]
        if key and key.strip():
            return key.strip()
    except (KeyError, FileNotFoundError):
        pass
    
    # Fallback: .env dosyasından oku (lokal geliştirme için)
    env_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    return env_key.strip() if env_key else ""

st.set_page_config(page_title="Araç-Yolcu Optimizasyon", page_icon="🚗", layout="wide")


def init_state():
    defaults = {
        "df_raw": None, "df_active": None, "df_arac": None,
        "df_with_roles": None, "df_geocoded": None,
        "cost_matrix": None, "unassigned_cm": [],
        "assignments": None, "unassigned_final": [],
        "geocode_cache": {}, "page": 1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()

# api_key her rerun'da taze alınır
api_key = get_api_key().strip()

# ─── Şifre koruması ──────────────────────────────────────────────────────────
def check_password() -> bool:
    """Basit şifre ekranı. Şifre Streamlit Secrets'tan veya sabit değerden alınır."""
    try:
        correct = st.secrets.get("APP_PASSWORD", "btc2024")
    except Exception:
        correct = os.getenv("APP_PASSWORD", "btc2024")

    if st.session_state.get("authenticated"):
        return True

    with st.form("login"):
        st.markdown("### 🔐 Giriş")
        pwd = st.text_input("Şifre", type="password")
        submitted = st.form_submit_button("Giriş Yap")
        if submitted:
            if pwd == correct:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Hatalı şifre")
    return False

if not check_password():
    st.stop()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🚗 Araç-Yolcu Optimizasyon")
    st.markdown("---")
    if api_key:
        st.success(f"✅ API Key yüklendi")
    else:
        st.error("❌ GOOGLE_MAPS_API_KEY eksik")
        st.info("💡 Streamlit Cloud'da Settings → Secrets bölümünden ekleyin")
    st.markdown("---")
    sayfa = st.radio(
        "Sayfa",
        ["📋 1 — Katılımcı Listesi", "🚗 2 — Araç Sahibi & Atama"],
        index=st.session_state["page"] - 1,
    )
    st.session_state["page"] = 1 if sayfa.startswith("📋") else 2


# ════════════════════════════════════════════════════════════════════════════
# SAYFA 1 — Katılımcı Listesi
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["page"] == 1:
    st.title("📋 Katılımcı Listesi")
    st.caption("Excel dosyasını yükleyin, gelmeyecek kişileri işaretleyin.")

    uploaded = st.file_uploader("Katılımcı listesi (.xlsx)", type=["xlsx"], key="uploader1")
    if uploaded:
        try:
            df = load_and_preprocess(uploaded)
            st.session_state["df_raw"] = df
            for k in ["df_active", "df_with_roles", "df_geocoded", "cost_matrix", "assignments"]:
                st.session_state[k] = None
            st.session_state["unassigned_cm"] = []
            st.session_state["unassigned_final"] = []
        except Exception as e:
            st.error(f"❌ {e}")

    if st.session_state["df_raw"] is None:
        st.info("Henüz dosya yüklenmedi.")
        st.stop()

    df = st.session_state["df_raw"].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("👥 Toplam", len(df))
    c2.metric("🗺️ Bölge Grubu", df["Bölge Grubu"].nunique())
    c3.metric("📍 İlçe", df["İlçe"].nunique())

    st.markdown("---")
    search = st.text_input("🔍 İsim veya ilçe ara", placeholder="Örn: Ahmet, Kadıköy...")

    if search:
        mask = (
            df["İsim Soyisim"].str.contains(search, case=False, na=False) |
            df["İlçe"].str.contains(search, case=False, na=False)
        )
        df_show = df[mask].copy()
    else:
        df_show = df.copy()

    st.caption(f"{len(df_show)} kişi gösteriliyor")

    df_edit = df_show[["İsim Soyisim", "İlçe", "Posta Kodu", "Bölge Grubu"]].copy()
    df_edit.insert(0, "Gelmiyor", False)

    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        height=550,
        column_config={
            "Gelmiyor": st.column_config.CheckboxColumn("Gelmiyor ✗", default=False)
        },
        disabled=["İsim Soyisim", "İlçe", "Posta Kodu", "Bölge Grubu"],
        hide_index=True,
        key="editor1",
    )

    gelmeyen_isimler = set(edited.loc[edited["Gelmiyor"], "İsim Soyisim"].tolist())
    df_active = df[~df["İsim Soyisim"].isin(gelmeyen_isimler)].reset_index(drop=True)

    c1, c2 = st.columns(2)
    c1.metric("❌ Gelmiyor", len(gelmeyen_isimler))
    c2.metric("✅ Katılıyor", len(df_active))

    st.markdown("---")
    if st.button("➡️ Sayfa 2'ye Geç", type="primary", use_container_width=True):
        if len(df_active) < 2:
            st.error("En az 2 katılımcı olmalı.")
        else:
            st.session_state["df_active"] = df_active
            st.session_state["page"] = 2
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# SAYFA 2 — Araç Sahibi Seçimi, Optimizasyon, Sonuçlar
# ════════════════════════════════════════════════════════════════════════════
else:
    st.title("🚗 Araç Sahibi Seçimi & Optimizasyon")

    if st.session_state["df_active"] is None:
        st.warning("Önce Sayfa 1'den katılımcı listesini onaylayın.")
        st.stop()

    df_active = st.session_state["df_active"]

    # ── Araç listesi yükleme ─────────────────────────────────────────────────
    st.subheader("1️⃣ Araç Listesini Yükle")
    uploaded_arac = st.file_uploader("Araç listesi (.xlsx)", type=["xlsx"], key="uploader2")
    if uploaded_arac:
        try:
            df_arac = load_arac_listesi(uploaded_arac)
            st.session_state["df_arac"] = df_arac
            st.success(f"✅ {len(df_arac)} araç yüklendi")
        except Exception as e:
            st.error(f"❌ {e}")

    # ── Otomatik eşleştirme ──────────────────────────────────────────────────
    auto_driver_indices = []
    if st.session_state["df_arac"] is not None:
        df_arac = st.session_state["df_arac"]
        auto_driver_indices = eslesenleri_bul(df_active, df_arac)

        if auto_driver_indices:
            rows = []
            for idx in auto_driver_indices:
                isim = df_active.loc[idx, "İsim Soyisim"]
                for _, ar in df_arac[df_arac["GercekKullanan"] != ""].iterrows():
                    if eslesir_mi(isim, ar["GercekKullanan"]):
                        rows.append({
                            "Katılımcı": isim,
                            "İlçe": df_active.loc[idx, "İlçe"],
                            "Plaka": ar["Plaka"],
                            "Araç Listesindeki İsim": ar["GercekKullanan"],
                        })
                        break
            with st.expander(f"✅ {len(auto_driver_indices)} araç sahibi otomatik eşleştirildi", expanded=True):
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.warning("Araç listesindeki isimler katılımcı listesiyle eşleşmedi.")

    st.markdown("---")

    # ── Manuel araç sahibi seçimi ────────────────────────────────────────────
    st.subheader("2️⃣ Araç Sahiplerini Onayla / Düzenle")
    auto_isimler = [df_active.loc[i, "İsim Soyisim"] for i in auto_driver_indices]
    tum_isimler = df_active["İsim Soyisim"].tolist()

    secilen_isimler = st.multiselect(
        "Araç sahipleri",
        options=tum_isimler,
        default=auto_isimler,
        placeholder="İsim arayın veya listeden seçin...",
    )

    if not secilen_isimler:
        st.info("En az 1 araç sahibi seçin.")
        st.stop()

    driver_indices = df_active[df_active["İsim Soyisim"].isin(secilen_isimler)].index.tolist()
    c1, c2, c3 = st.columns(3)
    c1.metric("🚗 Araç Sahibi", len(driver_indices))
    c2.metric("🧍 Yolcu", len(df_active) - len(driver_indices))
    c3.metric("📦 Max Kapasite", len(driver_indices) * 3)

    st.markdown("---")

    # ── Optimizasyon ─────────────────────────────────────────────────────────
    st.subheader("3️⃣ Optimizasyonu Çalıştır")
    if not api_key:
        st.error("❌ GOOGLE_MAPS_API_KEY eksik.")
        st.info("""
        **Streamlit Cloud'da çalışıyorsanız:**
        1. Sağ üstteki "⋮" (3 nokta) → Settings → Secrets
        2. Aşağıdaki satırı ekleyin:
        ```
        GOOGLE_MAPS_API_KEY = "your_api_key_here"
        ```
        3. Save'e tıklayın
        
        **Lokal'de çalışıyorsanız:**
        - `.env` dosyasına `GOOGLE_MAPS_API_KEY=your_key` ekleyin
        """)
        st.stop()

    if st.button("🚀 Geocoding + Optimizasyon Çalıştır", type="primary"):
        try:
            df_roles = assign_roles_manual(df_active, driver_indices)
            st.session_state["df_with_roles"] = df_roles
        except ValueError as e:
            st.error(f"❌ {e}")
            st.stop()

        progress_bar = st.progress(0, text="📍 Adresler koordinata çevriliyor...")
        def upd(cur, tot):
            progress_bar.progress(cur / tot, text=f"📍 {cur}/{tot} adres işlendi")

        try:
            df_geo, failed = geocode_addresses(
                df_roles, api_key=api_key,
                cache=st.session_state["geocode_cache"],
                progress_callback=upd,
            )
            st.session_state["df_geocoded"] = df_geo
            progress_bar.progress(1.0, text="✅ Geocoding tamamlandı")
            if failed:
                st.warning(f"⚠️ {failed} adres koordinata çevrilemedi.")
        except Exception as e:
            st.error(f"❌ Geocoding hatası: {e}")
            st.stop()

        with st.spinner("📡 Mesafe matrisi hesaplanıyor..."):
            try:
                cost_matrix, unassigned_cm = build_cost_matrix(df_geo, api_key=api_key)
                st.session_state["cost_matrix"] = cost_matrix
                st.session_state["unassigned_cm"] = unassigned_cm
            except Exception as e:
                st.error(f"❌ Mesafe matrisi hatası: {e}")
                st.stop()

        with st.spinner("🧮 Optimal atama hesaplanıyor..."):
            try:
                assignments, unassigned_opt = optimize_assignments(
                    df_geo, cost_matrix=cost_matrix, max_capacity=3
                )
                all_unassigned = list(set(unassigned_cm + unassigned_opt))
                st.session_state["assignments"] = assignments
                st.session_state["unassigned_final"] = all_unassigned
            except Exception as e:
                st.error(f"❌ Optimizasyon hatası: {e}")
                st.stop()

        st.success("✅ Tamamlandı!")
        st.rerun()

    # ── Sonuçlar ─────────────────────────────────────────────────────────────
    if st.session_state["assignments"] is None:
        st.stop()

    st.markdown("---")
    st.subheader("4️⃣ Atama Sonuçları")

    assignments = st.session_state["assignments"]
    unassigned_final = st.session_state["unassigned_final"]
    cost_matrix = st.session_state["cost_matrix"]
    df_geo = st.session_state["df_geocoded"]
    df_arac = st.session_state.get("df_arac")

    # Düzenlenebilir atama — session state'te tut
    if "assignments_edit" not in st.session_state or st.session_state.get("assignments_edit_base") != id(assignments):
        st.session_state["assignments_edit"] = {k: list(v) for k, v in assignments.items()}
        st.session_state["assignments_edit_base"] = id(assignments)

    assignments_edit = st.session_state["assignments_edit"]

    # Atanmış yolcuların set'i (manuel ekleme için kullanılabilir havuz)
    tum_atananlar = {p for plist in assignments_edit.values() for p in plist}
    unassigned_havuz = [i for i in unassigned_final if i not in tum_atananlar]

    total_assigned = sum(len(p) for p in assignments_edit.values())
    total_dist_km = sum(
        cost_matrix.get((d, p), 0) for d, plist in assignments_edit.items() for p in plist
    ) / 1000

    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Atanan Yolcu", total_assigned)
    c2.metric("❌ Atanamamayan", len(unassigned_havuz))
    c3.metric("📏 Toplam Mesafe", f"{total_dist_km:.1f} km")
    st.markdown("---")

    # Kartlar — 3 kolon
    driver_list = list(assignments_edit.items())
    for row_start in range(0, len(driver_list), 3):
        row_drivers = driver_list[row_start: row_start + 3]
        cols = st.columns(len(row_drivers))

        for col, (driver_idx, passenger_list) in zip(cols, row_drivers):
            driver = df_geo.loc[driver_idx]
            d_lat, d_lng = driver["Lat"], driver["Lng"]
            d_name = driver["İsim Soyisim"]
            d_ilce = driver["İlçe"]
            d_bolge = driver["Bölge Grubu"]

            plaka = ""
            if df_arac is not None:
                for _, ar in df_arac[df_arac["GercekKullanan"] != ""].iterrows():
                    if eslesir_mi(d_name, ar["GercekKullanan"]):
                        plaka = ar["Plaka"]
                        break

            with col:
                with st.container(border=True):
                    plaka_str = f" · 🚘 {plaka}" if plaka else ""
                    st.markdown(f"### 🚗 {d_name}")
                    st.caption(f"📍 {d_ilce} · {d_bolge}{plaka_str}")

                    # Mevcut yolcular + çıkarma butonu
                    st.markdown("**Atanan Yolcular:**")
                    for p_idx in list(passenger_list):
                        p = df_geo.loc[p_idx]
                        dist_km = cost_matrix.get((driver_idx, p_idx), 0) / 1000
                        maps_url = (
                            f"https://www.google.com/maps/dir/?api=1"
                            f"&origin={d_lat},{d_lng}"
                            f"&destination={p['Lat']},{p['Lng']}"
                            f"&travelmode=driving"
                        )
                        p_col, btn_col = st.columns([5, 1])
                        with p_col:
                            st.markdown(
                                f'<a href="{maps_url}" target="_blank" style="text-decoration:none;">'
                                f'<div style="background:#f0f4ff;border:1px solid #c5d3f0;'
                                f'border-radius:8px;padding:6px 10px;margin:2px 0;cursor:pointer;">'
                                f'👤 <b>{p["İsim Soyisim"]}</b><br>'
                                f'<small style="color:#666">📍 {p["İlçe"]} · 🛣️ {dist_km:.1f} km &nbsp; 🗺️</small>'
                                f'</div></a>',
                                unsafe_allow_html=True,
                            )
                        with btn_col:
                            if st.button("✕", key=f"rm_{driver_idx}_{p_idx}", help="Yolcuyu çıkar"):
                                assignments_edit[driver_idx].remove(p_idx)
                                if p_idx not in unassigned_havuz:
                                    unassigned_havuz.append(p_idx)
                                st.session_state["assignments_edit"] = assignments_edit
                                st.rerun()

                    # Manuel ekleme + Yeni Öneri
                    bos_slot = 3 - len(passenger_list)
                    if bos_slot > 0 and unassigned_havuz:
                        st.markdown("**➕ Yolcu Ekle:**")
                        ekle_col, oneri_col = st.columns([3, 2])

                        with ekle_col:
                            ekle_options = {
                                f"{df_geo.loc[i, 'İsim Soyisim']} ({df_geo.loc[i, 'İlçe']})": i
                                for i in unassigned_havuz
                            }
                            secim = st.selectbox(
                                "Elle seç",
                                options=["—"] + list(ekle_options.keys()),
                                key=f"add_{driver_idx}",
                                label_visibility="collapsed",
                            )
                            if secim != "—":
                                p_idx_ekle = ekle_options[secim]
                                assignments_edit[driver_idx].append(p_idx_ekle)
                                unassigned_havuz.remove(p_idx_ekle)
                                st.session_state["assignments_edit"] = assignments_edit
                                st.rerun()

                        with oneri_col:
                            if st.button(
                                f"🔄 Yeni Öneri",
                                key=f"oneri_{driver_idx}",
                                help=f"{bos_slot} boş slot için en yakın yolcuları öner",
                            ):
                                # Havuzdaki yolcuları araç sahibine mesafeye göre sırala
                                # cost_matrix'te varsa onu kullan, yoksa Haversine
                                import math

                                def hav(lat1, lng1, lat2, lng2):
                                    R = 6371000
                                    p1 = math.radians(lat1)
                                    p2 = math.radians(lat2)
                                    dp = math.radians(lat2 - lat1)
                                    dl = math.radians(lng2 - lng1)
                                    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
                                    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

                                skorlar = []
                                for p_i in unassigned_havuz:
                                    if (driver_idx, p_i) in cost_matrix:
                                        dist = cost_matrix[(driver_idx, p_i)]
                                    else:
                                        p_row = df_geo.loc[p_i]
                                        dist = hav(d_lat, d_lng, p_row["Lat"], p_row["Lng"])
                                    skorlar.append((dist, p_i))

                                skorlar.sort()
                                eklenecekler = [p_i for _, p_i in skorlar[:bos_slot]]

                                for p_i in eklenecekler:
                                    assignments_edit[driver_idx].append(p_i)
                                    unassigned_havuz.remove(p_i)

                                st.session_state["assignments_edit"] = assignments_edit
                                st.rerun()

    if unassigned_havuz:
        st.markdown("---")
        with st.expander(f"❌ Atanamamış Yolcular ({len(unassigned_havuz)} kişi)"):
            ua_df = df_geo.loc[unassigned_havuz][
                ["İsim Soyisim", "İlçe", "Bölge Grubu"]
            ].reset_index(drop=True)
            st.dataframe(ua_df, use_container_width=True)

    # ── Tamamla & İndir ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("5️⃣ Tamamla & İndir")
    st.caption("Tüm düzenlemeler tamamlandıktan sonra listeyi indirin.")

    from utils import build_export_df, export_to_excel, export_to_pdf

    df_export = build_export_df(assignments_edit, df_geo, cost_matrix)

    with st.expander("📋 İndirilecek Tablo Önizlemesi", expanded=False):
        st.dataframe(df_export, use_container_width=True, hide_index=True)

    fmt_col, dl_col = st.columns([2, 3])
    with fmt_col:
        fmt = st.radio("Format seç", ["📊 Excel (.xlsx)", "📄 PDF (.pdf)"], horizontal=True)

    with dl_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if fmt == "📊 Excel (.xlsx)":
            try:
                excel_bytes = export_to_excel(df_export)
                st.download_button(
                    label="⬇️ Excel İndir",
                    data=excel_bytes,
                    file_name="arac_yolcu_atamalari.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )
            except Exception as e:
                st.error(f"Excel oluşturulamadı: {e}")
        else:
            try:
                pdf_bytes = export_to_pdf(df_export)
                st.download_button(
                    label="⬇️ PDF İndir",
                    data=pdf_bytes,
                    file_name="arac_yolcu_atamalari.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            except Exception as e:
                st.error(f"PDF oluşturulamadı: {e}")
