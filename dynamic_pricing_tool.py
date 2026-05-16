import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Dinamik Fiyatlama Araci",
    page_icon="💹",
    layout="wide"
)

def init_session_state():
    if "funding_sources" not in st.session_state:
        st.session_state.funding_sources = [
            {"name": "Sukuk", "amount": 50000000, "currency": "USD", "fx_rate": 1.0, "annual_rate": 12.5},
            {"name": "Banka Kredisi", "amount": 30000000, "currency": "USD", "fx_rate": 1.0, "annual_rate": 15.0},
            {"name": "VDMK", "amount": 20000000, "currency": "USD", "fx_rate": 1.0, "annual_rate": 11.0},
        ]
    if "opex_monthly_margin" not in st.session_state:
        st.session_state.opex_monthly_margin = 0.17
    if "strategy" not in st.session_state:
        st.session_state.strategy = {
            "sales_target": 140000000,
            "avg_maturity_days": 120,
            "gross_profit_pct_new": 4.5,
            "gross_profit_pct_repeat": 3.5,
            "monthly_profit_pct": 1.2,
            "grace_days": 15,
            "collection_rate_pct": 92.0,
            "legal_npl_pct_new": 3.0,
            "legal_npl_pct_repeat": 1.5,
            "macro_mode": "Dengeli",
        }
    if "weights" not in st.session_state:
        st.session_state.weights = {
            "risk_low": -50, "risk_mid": 0, "risk_high": 200,
            "maturity_lt90": -50, "maturity_120": 0, "maturity_gt120_per30": 100,
            "payment_weekly": -50, "payment_monthly": 0, "payment_45d": 75,
            "stock_gt6": -75, "stock_4to6": -25, "stock_lt4": 0,
            "category_fmcg": -25, "category_standard": 0, "category_textile": 100,
            "grace_none": 0, "grace_15d": 30, "grace_30d": 75,
            "pipeline_low": -50, "pipeline_normal": 0, "pipeline_high": 100,
        }
    if "approved_deals" not in st.session_state:
        st.session_state.approved_deals = []

init_session_state()

def get_usd_amount(amount, currency, fx_rate):
    if currency == "TL":
        return amount / fx_rate if fx_rate > 0 else 0
    return amount

def calculate_wacc(sources):
    total_usd = sum(get_usd_amount(s["amount"], s["currency"], s["fx_rate"]) for s in sources)
    if total_usd == 0:
        return 0.0, 0.0
    wacc_annual = sum(
        (get_usd_amount(s["amount"], s["currency"], s["fx_rate"]) / total_usd) * s["annual_rate"]
        for s in sources
    )
    wacc_monthly = wacc_annual / 12
    return round(wacc_annual, 4), round(wacc_monthly, 4)

def calculate_base_cost(wacc_annual, opex_annual):
    return round(wacc_annual + opex_annual, 4)

def get_macro_bps(mode):
    mapping = {"Agresif Buyume": -75, "Dengeli": 0, "Defansif / Karlilik Odakli": 100}
    return mapping.get(mode, 0)

def calculate_risk_bps(params, weights):
    bps = 0
    breakdown = []

    risk_map = {"Dusuk": weights["risk_low"], "Orta": weights["risk_mid"], "Yuksek": weights["risk_high"]}
    v = risk_map[params["risk_grade"]]
    bps += v
    breakdown.append(("Risk Notu", params["risk_grade"], v))

    md = params["maturity_days"]
    if md < 90:
        v = weights["maturity_lt90"]
        label = f"<90 gun ({md} gun)"
    elif md == 120:
        v = weights["maturity_120"]
        label = "120 gun"
    else:
        extra = max(0, (md - 120) // 30)
        v = extra * weights["maturity_gt120_per30"]
        label = f"{md} gun (+{extra}x30g)"
    bps += v
    breakdown.append(("Vade", label, v))

    pf_map = {"Haftalik": weights["payment_weekly"], "Aylik": weights["payment_monthly"], "45 Gunluk": weights["payment_45d"]}
    v = pf_map[params["payment_freq"]]
    bps += v
    breakdown.append(("Odeme Sikligi", params["payment_freq"], v))

    sc = params["stock_turnover"]
    if sc > 6:
        v = weights["stock_gt6"]
        label = f">6 ({sc}x)"
    elif sc >= 4:
        v = weights["stock_4to6"]
        label = f"4-6 ({sc}x)"
    else:
        v = weights["stock_lt4"]
        label = f"<4 ({sc}x)"
    bps += v
    breakdown.append(("Stok Cevrim", label, v))

    cat_map = {"FMCG": weights["category_fmcg"], "Standart": weights["category_standard"], "Tekstil": weights["category_textile"]}
    v = cat_map[params["category"]]
    bps += v
    breakdown.append(("Kategori", params["category"], v))

    gr_map = {"Yok": weights["grace_none"], "15 Gun": weights["grace_15d"], "30 Gun": weights["grace_30d"]}
    v = gr_map[params["grace_period"]]
    bps += v
    breakdown.append(("Grace Suresi", params["grace_period"], v))

    pl_map = {"Dusuk": weights["pipeline_low"], "Normal": weights["pipeline_normal"], "Yuksek": weights["pipeline_high"]}
    v = pl_map[params["pipeline"]]
    bps += v
    breakdown.append(("Pipeline", params["pipeline"], v))

    return bps, breakdown

def bps_to_pct(bps):
    return round(bps / 100, 4)

tabs = st.tabs([
    "Finans Ekibi",
    "Strateji Ekibi",
    "Degerlendirme & Fiyatlama",
    "Ayarlar / Weights",
    "Onaylanan Islemler"
])

# ══════════════════════════════════════════════
# TAB 1: FINANS EKIBI
# ══════════════════════════════════════════════
with tabs[0]:
    st.header("Finans Ekibi - Borclanma Kaynaklari & WACC")
    st.caption("Sirketin fon kaynaklarini girin. TL borclanmalar icin kur bilgisi girin.")

    with st.expander("Yeni Kaynak Ekle", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        new_name = c1.text_input("Kaynak Adi", value="Ortak Borcu")
        new_currency = c2.selectbox("Para Birimi", ["USD", "TL"])
        new_amount = c3.number_input("Tutar", min_value=0, value=10000000, step=1000000)
        new_fx = c4.number_input("Kur (1 USD = ? TL)", min_value=0.01, value=32.0, step=0.1,
                                  disabled=(new_currency == "USD"))
        new_rate = c5.number_input("Yillik Maliyet (%)", min_value=0.0, max_value=200.0, value=13.0, step=0.1)
        if st.button("Ekle", type="primary"):
            st.session_state.funding_sources.append({
                "name": new_name,
                "amount": new_amount,
                "currency": new_currency,
                "fx_rate": new_fx if new_currency == "TL" else 1.0,
                "annual_rate": new_rate,
            })
            st.rerun()

    st.subheader("Mevcut Kaynaklar")
    sources = st.session_state.funding_sources
    updated_sources = []
    for i, src in enumerate(sources):
        c1, c2, c3, c4, c5, c6 = st.columns([2, 1.2, 2, 1.5, 1.8, 0.8])
        name = c1.text_input("Ad", value=src["name"], key=f"fn_{i}")
        currency = c2.selectbox("Birim", ["USD", "TL"], index=0 if src["currency"] == "USD" else 1, key=f"fc_{i}")
        amount = c3.number_input("Tutar", value=src["amount"], step=1000000, key=f"fa_{i}")
        fx_rate = c4.number_input("Kur (TL/USD)", value=src.get("fx_rate", 1.0), step=0.1, key=f"fx_{i}",
                                   disabled=(currency == "USD"))
        rate = c5.number_input("Yillik Maliyet (%)", value=src["annual_rate"], step=0.1, key=f"fr_{i}")
        delete = c6.button("Sil", key=f"fd_{i}")
        if not delete:
            updated_sources.append({
                "name": name,
                "amount": amount,
                "currency": currency,
                "fx_rate": fx_rate if currency == "TL" else 1.0,
                "annual_rate": rate,
            })
    st.session_state.funding_sources = updated_sources

    # Base Kaynak Maliyeti (WACC) - OPEX'ten once
    if st.session_state.funding_sources:
        wacc_a_pre, wacc_m_pre = calculate_wacc(st.session_state.funding_sources)
        total_usd_pre = sum(get_usd_amount(s["amount"], s["currency"], s["fx_rate"]) for s in st.session_state.funding_sources)

        st.divider()
        st.subheader("Base Kaynak Maliyeti (OPEX Haric)")
        bm1, bm2, bm3 = st.columns(3)
        bm1.metric("Toplam Fon (USD)", f"${total_usd_pre:,.0f}")
        bm2.metric("Base Yillik Kaynak Maliyeti (WACC)", f"%{wacc_a_pre:.2f}")
        bm3.metric("Base Aylik Kaynak Maliyeti", f"%{wacc_m_pre:.2f}")

        # Kaynak tablosu
        df_src = []
        for s in st.session_state.funding_sources:
            usd_val = get_usd_amount(s["amount"], s["currency"], s["fx_rate"])
            weight = (usd_val / total_usd_pre * 100) if total_usd_pre > 0 else 0
            df_src.append({
                "Kaynak": s["name"],
                "Tutar (Orijinal)": f"{s['currency']} {s['amount']:,.0f}",
                "Kur": f"{s['fx_rate']:.2f}" if s["currency"] == "TL" else "-",
                "USD Karsiligi": f"${usd_val:,.0f}",
                "Yillik Maliyet (%)": s["annual_rate"],
                "Agirlik (%)": round(weight, 2),
                "Agirlikli Maliyet (%)": round(weight / 100 * s["annual_rate"], 4),
            })
        st.dataframe(pd.DataFrame(df_src), use_container_width=True)

    st.divider()
    st.subheader("OPEX Aylik Marji")
    st.session_state.opex_monthly_margin = st.number_input(
        "Aylik OPEX Marji (%)",
        min_value=0.0, max_value=5.0,
        value=st.session_state.opex_monthly_margin,
        step=0.01,
        help="Aylik girilen deger 12 ile carpilarak yillik OPEX marjina donusturulur."
    )
    opex_annual = round(st.session_state.opex_monthly_margin * 12, 4)
    st.info(f"Aylik OPEX: **%{st.session_state.opex_monthly_margin:.2f}** → Yillik OPEX: **%{opex_annual:.2f}**")

    # Hesaplama Sonuclari
    wacc_a, wacc_m = calculate_wacc(st.session_state.funding_sources)
    base_cost_annual = calculate_base_cost(wacc_a, opex_annual)
    base_cost_monthly = round(base_cost_annual / 12, 4)

    st.divider()
    st.subheader("Hesaplama Sonuclari")
    m1, m2, m3 = st.columns(3)
    m1.metric("WACC (Yillik)", f"%{wacc_a:.2f}")
    m2.metric("Base Cost Yillik (WACC+OPEX)", f"%{base_cost_annual:.2f}", delta=f"+OPEX %{opex_annual:.2f}")
    m3.metric("Base Cost Aylik (WACC+OPEX)", f"%{base_cost_monthly:.2f}")

# ══════════════════════════════════════════════
# TAB 2: STRATEJI EKIBI
# ══════════════════════════════════════════════
with tabs[1]:
    st.header("Strateji Ekibi - KPI Hedefleri & Makro Mod")
    s = st.session_state.strategy

    st.subheader("Global Makro Parametre (Risk Appetite Mode)")
    macro_options = ["Agresif Buyume", "Dengeli", "Defansif / Karlilik Odakli"]
    macro_desc = {
        "Agresif Buyume": "Pazar payi oncelikli - Nihai orana -75 bps indirim uygulanir.",
        "Dengeli": "Standart mod - 0 bps degisiklik.",
        "Defansif / Karlilik Odakli": "Karlilik oncelikli - Nihai orana +100 bps prim eklenir."
    }
    s["macro_mode"] = st.selectbox("Strateji Modu", macro_options, index=macro_options.index(s["macro_mode"]))
    st.info(macro_desc[s["macro_mode"]])

    st.divider()
    st.subheader("Yillik Board KPI'lari")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Genel Hedefler**")
        s["sales_target"] = st.number_input("Satis Hedefi ($)", value=s["sales_target"], step=1000000)
        s["avg_maturity_days"] = st.number_input("Ortalama Vade (Gun)", value=s["avg_maturity_days"], step=10)
        s["monthly_profit_pct"] = st.number_input("Aylik Kar Hedefi (%)", value=s["monthly_profit_pct"], step=0.1)
        s["grace_days"] = st.number_input("Grace Suresi (Gun)", value=s["grace_days"], step=5)
        s["collection_rate_pct"] = st.number_input("Tahsilat Orani (%)", value=s["collection_rate_pct"], step=0.5)
    with c2:
        st.markdown("**Musteri Segmenti Hedefleri**")
        s["gross_profit_pct_new"] = st.number_input("Brut Kar % - Yeni Musteri", value=s["gross_profit_pct_new"], step=0.1)
        s["gross_profit_pct_repeat"] = st.number_input("Brut Kar % - Tekrar Musteri", value=s["gross_profit_pct_repeat"], step=0.1)
        s["legal_npl_pct_new"] = st.number_input("Legal/NPL % - Yeni Musteri", value=s["legal_npl_pct_new"], step=0.1)
        s["legal_npl_pct_repeat"] = st.number_input("Legal/NPL % - Tekrar Musteri", value=s["legal_npl_pct_repeat"], step=0.1)

    st.session_state.strategy = s
    st.success(f"Makro Mod: {s['macro_mode']} | Satis Hedefi: ${s['sales_target']:,.0f} | Ort. Vade: {s['avg_maturity_days']} gun")

# ══════════════════════════════════════════════
# TAB 3: DEGERLENDIRME & FIYATLAMA
# ══════════════════════════════════════════════
with tabs[2]:
    st.header("Degerlendirme Ekibi - Musteri Fiyatlama & Ic Onay")

    opex_annual_t3 = round(st.session_state.opex_monthly_margin * 12, 4)
    wacc_a, wacc_m = calculate_wacc(st.session_state.funding_sources)
    base_cost_annual = calculate_base_cost(wacc_a, opex_annual_t3)
    s = st.session_state.strategy
    w = st.session_state.weights
    macro_bps = get_macro_bps(s["macro_mode"])

    col_input, col_result = st.columns([1, 1])

    with col_input:
        st.subheader("Musteri Parametreleri")
        customer_name = st.text_input("Musteri Adi / Kodu", value="ABC Gida Ltd.")
        customer_type = st.selectbox("Musteri Tipi", ["Yeni Musteri", "Tekrar Musteri"])
        deal_amount = st.number_input("Islem Tutari ($)", min_value=10000, value=500000, step=10000)

        st.markdown("---")
        risk_grade = st.selectbox("Risk Notu", ["Dusuk", "Orta", "Yuksek"])
        maturity_days = st.number_input("Vade (Gun)", min_value=30, max_value=360, value=120, step=15)
        payment_freq = st.selectbox("Odeme Sikligi", ["Haftalik", "Aylik", "45 Gunluk"])
        stock_turnover = st.number_input("Stok Cevrim Hizi (x/yil)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
        category = st.selectbox("Urun Kategorisi", ["FMCG", "Standart", "Tekstil"])
        grace_period = st.selectbox("Grace Suresi", ["Yok", "15 Gun", "30 Gun"])
        pipeline = st.selectbox("Pipeline Durumu", ["Dusuk", "Normal", "Yuksek"])

    params = {
        "risk_grade": risk_grade, "maturity_days": maturity_days,
        "payment_freq": payment_freq, "stock_turnover": stock_turnover,
        "category": category, "grace_period": grace_period, "pipeline": pipeline
    }
    risk_bps, breakdown = calculate_risk_bps(params, w)
    target_margin = s["gross_profit_pct_new"] if customer_type == "Yeni Musteri" else s["gross_profit_pct_repeat"]
    risk_pct = bps_to_pct(risk_bps)
    macro_pct = bps_to_pct(macro_bps)
    system_rate = round(base_cost_annual + target_margin + risk_pct + macro_pct, 4)

    with col_result:
        st.subheader("Ic Onay Ekrani - Fiyatlama Selalesi")

        waterfall_data = [
            ("WACC (Agirlikli Sermaye Maliyeti)", wacc_a),
            ("OPEX Yillik Marji", opex_annual_t3),
            ("Hedef Brut Kar Marji", target_margin),
            ("Risk BPS Ayarlamalari", risk_pct),
            ("Makro Strateji Ayari", macro_pct),
        ]

        st.markdown("**Waterfall Breakdown:**")
        running = 0
        for label, val in waterfall_data:
            running += val
            sign = "+" if val >= 0 else ""
            st.markdown(f"**{label}:** `{sign}{val:.2f}%` → Kumulatif: `{running:.2f}%`")

        st.divider()
        st.metric("Sistem Onerilen Oran (Yillik)", f"%{system_rate:.2f}", delta=f"Risk BPS: {risk_bps:+d}")

        st.markdown("**Risk BPS Detayi:**")
        bps_df = pd.DataFrame(breakdown, columns=["Parametre", "Deger", "BPS"])
        bps_df["BPS"] = bps_df["BPS"].apply(lambda x: f"{x:+d}")
        st.dataframe(bps_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Manuel Mudahale (Override)")
        override_rate = st.number_input(
            "Nihai Karar Orani (%)",
            min_value=0.0,
            value=float(system_rate), step=0.05,
            help="Yetkili kisi bu orani manuel olarak revize edebilir."
        )
        override_note = st.text_area("Karar Notu / Gerekcesi", placeholder="Ornek: Musteri stratejik oneme sahip, indirim onaylandi.")

        if abs(override_rate - system_rate) > 0.01:
            diff = override_rate - system_rate
            st.warning(f"Manuel override: Sistem onerisinden {diff:+.2f}% sapma var.")

        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("Onayla ve Kaydet", type="primary", use_container_width=True):
                deal = {
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Musteri": customer_name,
                    "Tip": customer_type,
                    "Tutar ($)": deal_amount,
                    "Sistem Orani (%)": system_rate,
                    "Nihai Oran (%)": override_rate,
                    "Risk BPS": risk_bps,
                    "Makro Mod": s["macro_mode"],
                    "Durum": "Onaylandi",
                    "Not": override_note
                }
                st.session_state.approved_deals.append(deal)
                st.success(f"Islem onaylandi! Nihai Oran: %{override_rate:.2f}")
        with col_reject:
            if st.button("Reddet", use_container_width=True):
                deal = {
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Musteri": customer_name,
                    "Tip": customer_type,
                    "Tutar ($)": deal_amount,
                    "Sistem Orani (%)": system_rate,
                    "Nihai Oran (%)": override_rate,
                    "Risk BPS": risk_bps,
                    "Makro Mod": s["macro_mode"],
                    "Durum": "Reddedildi",
                    "Not": override_note
                }
                st.session_state.approved_deals.append(deal)
                st.error("Islem reddedildi ve kayit altina alindi.")

# ══════════════════════════════════════════════
# TAB 4: AYARLAR / WEIGHTS
# ══════════════════════════════════════════════
with tabs[3]:
    st.header("Ayarlar - BPS Agirliklari (Yonetici Paneli)")
    st.caption("Tum baz puan degerleri buradan yonetilebilir. 100 bps = %1")
    w = st.session_state.weights

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Risk Notu")
        w["risk_low"] = st.number_input("Dusuk Risk (bps)", value=w["risk_low"])
        w["risk_mid"] = st.number_input("Orta Risk (bps)", value=w["risk_mid"])
        w["risk_high"] = st.number_input("Yuksek Risk (bps)", value=w["risk_high"])

        st.subheader("Vade")
        w["maturity_lt90"] = st.number_input("<90 Gun (bps)", value=w["maturity_lt90"])
        w["maturity_120"] = st.number_input("120 Gun (bps)", value=w["maturity_120"])
        w["maturity_gt120_per30"] = st.number_input(">120 Gun, her 30g (bps)", value=w["maturity_gt120_per30"])

        st.subheader("Odeme Sikligi")
        w["payment_weekly"] = st.number_input("Haftalik (bps)", value=w["payment_weekly"])
        w["payment_monthly"] = st.number_input("Aylik (bps)", value=w["payment_monthly"])
        w["payment_45d"] = st.number_input("45 Gunluk (bps)", value=w["payment_45d"])

        st.subheader("Stok Cevrim")
        w["stock_gt6"] = st.number_input(">6x (bps)", value=w["stock_gt6"])
        w["stock_4to6"] = st.number_input("4-6x (bps)", value=w["stock_4to6"])
        w["stock_lt4"] = st.number_input("<4x (bps)", value=w["stock_lt4"])

    with col2:
        st.subheader("Kategori")
        w["category_fmcg"] = st.number_input("FMCG (bps)", value=w["category_fmcg"])
        w["category_standard"] = st.number_input("Standart (bps)", value=w["category_standard"])
        w["category_textile"] = st.number_input("Tekstil (bps)", value=w["category_textile"])

        st.subheader("Grace Suresi")
        w["grace_none"] = st.number_input("Grace Yok (bps)", value=w["grace_none"])
        w["grace_15d"] = st.number_input("Grace 15 Gun (bps)", value=w["grace_15d"])
        w["grace_30d"] = st.number_input("Grace 30 Gun (bps)", value=w["grace_30d"])

        st.subheader("Pipeline")
        w["pipeline_low"] = st.number_input("Pipeline Dusuk (bps)", value=w["pipeline_low"])
        w["pipeline_normal"] = st.number_input("Pipeline Normal (bps)", value=w["pipeline_normal"])
        w["pipeline_high"] = st.number_input("Pipeline Yuksek (bps)", value=w["pipeline_high"])

    st.session_state.weights = w
    if st.button("Agirliklari Kaydet", type="primary"):
        st.success("BPS agirliklari guncellendi!")

# ══════════════════════════════════════════════
# TAB 5: ONAYLANAN ISLEMLER
# ══════════════════════════════════════════════
with tabs[4]:
    st.header("Onaylanan / Reddedilen Islemler")
    deals = st.session_state.approved_deals
    if not deals:
        st.info("Henuz kayitli islem yok. Degerlendirme sekmesinden islem onaylayin.")
    else:
        df_deals = pd.DataFrame(deals)
        st.dataframe(df_deals, use_container_width=True, hide_index=True)
        approved = df_deals[df_deals["Durum"] == "Onaylandi"]
        if not approved.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Toplam Onaylanan Islem", len(approved))
            m2.metric("Toplam Hacim ($)", f"${approved['Tutar ($)'].sum():,.0f}")
            m3.metric("Ort. Nihai Oran (%)", f"%{approved['Nihai Oran (%)'].mean():.2f}")
        if st.button("Tum Kayitlari Temizle"):
            st.session_state.approved_deals = []
            st.rerun()
