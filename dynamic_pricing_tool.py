code = '''import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Dinamik Fiyatlama Araci",
    page_icon="💹",
    layout="wide"
)

# ══════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════
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
            "target_portfolio_gross_pct": 25.0,
            "monthly_profit_pct": 1.2,
            "grace_days": 15,
            "collection_rate_pct": 92.0,
            "funds_in_legal_threshold_pct": 3.0,
            "funds_in_legal_pct_new": 3.0,
            "funds_in_legal_pct_repeat": 1.5,
            "macro_mode": "Dengeli",
        }
    if "weights" not in st.session_state:
        st.session_state.weights = {
            "risk_low": -50, "risk_mid": 0, "risk_high": 200,
            "maturity_lt90": -50, "maturity_120": 0, "maturity_gt120_per30": 100,
            "payment_weekly": -50, "payment_monthly": 0, "payment_45d": 75,
            "stock_gt6": -75, "stock_4to6": -25, "stock_lt4": 0,
            # Trendyol kategori BPS - dusuk komisyon = ince marj = fiyati dusuk tut (negatif bps)
            # Supermarket/FMCG: dusuk komisyon (%8-17) = ince marjli = indirim (-75 bps)
            # Giyim/Moda: yuksek komisyon (%21+) = yuksek marjli = prim tasiyabilir (+100 bps)
            "cat_supermarket": -75,       # Supermarket / FMCG (%8-17 komisyon) - en karli
            "cat_kozmetik": -50,          # Kozmetik & Kisisel Bakim (%12-17) - karli
            "cat_elektronik": -25,        # Elektronik & Aksesuar (%7-15) - orta-karli
            "cat_ev_yasam": 0,            # Ev & Yasam (%10-21) - standart
            "cat_spor": 0,                # Spor & Outdoor (%10-15) - standart
            "cat_cocuk_bebek": 25,        # Cocuk & Bebek (%16) - orta
            "cat_kirtasiye": 25,          # Kirtasiye & Ofis (%8-19) - orta
            "cat_giyim_moda": 100,        # Giyim & Moda (%21+) - en az karli = prim
            "cat_ayakkabi_canta": 100,    # Ayakkabi & Canta (%21-23) - en az karli = prim
            "grace_none": 0, "grace_15d": 30, "grace_30d": 75,
            "pipeline_low": -50, "pipeline_normal": 0, "pipeline_high": 100,
            "funds_in_legal_multiplier": 0.5,
            "funds_in_legal_cap_bps": 200,
        }
    if "approved_deals" not in st.session_state:
        st.session_state.approved_deals = []

init_session_state()

# Trendyol kategori listesi ve aciklamalari
# Mantik: Yuksek komisyon = Yuksek marjli kategori = Satici prim tasiyabilir (+bps)
#          Dusuk komisyon  = Ince marjli kategori   = Fiyati dusuk tut (-bps)
TRENDYOL_CATEGORIES = {
    "Supermarket / FMCG": {"key": "cat_supermarket", "komisyon": "%8-17", "karlilik": "⭐ Ince Marj - Dusuk"},
    "Kozmetik & Kisisel Bakim": {"key": "cat_kozmetik", "komisyon": "%12-17", "karlilik": "⭐⭐ Orta-Dusuk"},
    "Elektronik & Aksesuar": {"key": "cat_elektronik", "komisyon": "%7-15", "karlilik": "⭐⭐ Orta-Dusuk"},
    "Ev & Yasam": {"key": "cat_ev_yasam", "komisyon": "%10-21", "karlilik": "⭐⭐⭐ Standart"},
    "Spor & Outdoor": {"key": "cat_spor", "komisyon": "%10-15", "karlilik": "⭐⭐⭐ Standart"},
    "Cocuk & Bebek": {"key": "cat_cocuk_bebek", "komisyon": "%16", "karlilik": "⭐⭐⭐ Orta"},
    "Kirtasiye & Ofis": {"key": "cat_kirtasiye", "komisyon": "%8-19", "karlilik": "⭐⭐⭐ Orta"},
    "Giyim & Moda": {"key": "cat_giyim_moda", "komisyon": "%21+", "karlilik": "⭐⭐⭐⭐ Yuksek Marj"},
    "Ayakkabi & Canta": {"key": "cat_ayakkabi_canta", "komisyon": "%21-23", "karlilik": "⭐⭐⭐⭐⭐ En Yuksek Marj"},
}

# ══════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════
def get_usd_amount(amount, currency, fx_rate):
    if currency == "TL":
        return amount / fx_rate if fx_rate > 0 else 0
    elif currency == "EUR":
        return amount * fx_rate if fx_rate > 0 else 0
    return amount

def calculate_wacc(sources):
    total_usd = sum(get_usd_amount(s["amount"], s["currency"], s["fx_rate"]) for s in sources)
    if total_usd == 0:
        return 0.0, 0.0
    wacc_annual = sum(
        (get_usd_amount(s["amount"], s["currency"], s["fx_rate"]) / total_usd) * s["annual_rate"]
        for s in sources
    )
    return round(wacc_annual, 4), round(wacc_annual / 12, 4)

def calculate_legal_premium_bps(legal_pct, threshold, multiplier, cap_bps):
    if legal_pct <= threshold:
        return 0
    raw = (legal_pct - threshold) * multiplier * 100
    return int(min(raw, cap_bps))

def get_macro_bps(mode):
    return {"Agresif Buyume": -75, "Dengeli": 0, "Defansif / Karlilik Odakli": 100}.get(mode, 0)

def calculate_risk_bps(params, weights):
    bps = 0
    breakdown = []

    risk_map = {"Dusuk": weights["risk_low"], "Orta": weights["risk_mid"], "Yuksek": weights["risk_high"]}
    v = risk_map[params["risk_grade"]]
    bps += v; breakdown.append(("Risk Notu", params["risk_grade"], v))

    md = params["maturity_days"]
    if md < 90:
        v = weights["maturity_lt90"]; label = f"<90 gun ({md}g)"
    elif md <= 120:
        v = weights["maturity_120"]; label = "120 gun"
    else:
        extra = max(0, (md - 120) // 30)
        v = extra * weights["maturity_gt120_per30"]; label = f"{md}g (+{extra}x30g)"
    bps += v; breakdown.append(("Vade", label, v))

    pf_map = {"Haftalik": weights["payment_weekly"], "Aylik": weights["payment_monthly"], "45 Gunluk": weights["payment_45d"]}
    v = pf_map[params["payment_freq"]]
    bps += v; breakdown.append(("Odeme Sikligi", params["payment_freq"], v))

    sc = params["stock_turnover"]
    if sc > 6:
        v = weights["stock_gt6"]; label = f">6 ({sc}x)"
    elif sc >= 4:
        v = weights["stock_4to6"]; label = f"4-6 ({sc}x)"
    else:
        v = weights["stock_lt4"]; label = f"<4 ({sc}x)"
    bps += v; breakdown.append(("Stok Cevrim", label, v))

    cat_key = TRENDYOL_CATEGORIES[params["category"]]["key"]
    v = weights[cat_key]
    komisyon = TRENDYOL_CATEGORIES[params["category"]]["komisyon"]
    bps += v; breakdown.append(("Kategori", f"{params['category']} ({komisyon})", v))

    gr_map = {"Yok": weights["grace_none"], "15 Gun": weights["grace_15d"], "30 Gun": weights["grace_30d"]}
    v = gr_map[params["grace_period"]]
    bps += v; breakdown.append(("Grace Suresi", params["grace_period"], v))

    pl_map = {"Dusuk": weights["pipeline_low"], "Normal": weights["pipeline_normal"], "Yuksek": weights["pipeline_high"]}
    v = pl_map[params["pipeline"]]
    bps += v; breakdown.append(("Pipeline", params["pipeline"], v))

    return bps, breakdown

def bps_to_pct(bps):
    return round(bps / 100, 4)

# ══════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════
tabs = st.tabs([
    "Borclanma Kaynaklari & WACC",
    "Stratejik Hedefler",
    "Degerlendirme & Fiyatlama",
    "Portfoy Takip",
    "Ayarlar / Weights",
])

# ══════════════════════════════════════════════
# TAB 1: BORCLANMA KAYNAKLARI & WACC
# ══════════════════════════════════════════════
with tabs[0]:
    st.header("Borclanma Kaynaklari & WACC")

    with st.expander("Yeni Kaynak Ekle", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        new_name = c1.text_input("Kaynak Adi", value="Ortak Borcu")
        new_currency = c2.selectbox("Para Birimi", ["USD", "EUR", "TL"])
        new_amount = c3.number_input("Tutar", min_value=0, value=10000000, step=1000000)
        if new_currency == "TL":
            fx_label = "Kur (1 USD = ? TL)"
            fx_default = 32.0
        elif new_currency == "EUR":
            fx_label = "Kur (1 EUR = ? USD)"
            fx_default = 1.08
        else:
            fx_label = "Kur (N/A)"
            fx_default = 1.0
        new_fx = c4.number_input(fx_label, min_value=0.01, value=fx_default, step=0.01,
                                  disabled=(new_currency == "USD"))
        new_rate = c5.number_input("Yillik Maliyet (%)", min_value=0.0, max_value=200.0, value=13.0, step=0.1)
        if st.button("Ekle", type="primary"):
            st.session_state.funding_sources.append({
                "name": new_name, "amount": new_amount, "currency": new_currency,
                "fx_rate": new_fx if new_currency != "USD" else 1.0, "annual_rate": new_rate,
            })
            st.rerun()

    st.subheader("Mevcut Kaynaklar")
    updated_sources = []
    for i, src in enumerate(st.session_state.funding_sources):
        c1, c2, c3, c4, c5, c6 = st.columns([2, 1.2, 2, 1.8, 1.8, 0.8])
        name = c1.text_input("Ad", value=src["name"], key=f"fn_{i}")
        currency = c2.selectbox("Birim", ["USD", "EUR", "TL"],
                                 index=["USD", "EUR", "TL"].index(src["currency"]) if src["currency"] in ["USD", "EUR", "TL"] else 0,
                                 key=f"fc_{i}")
        amount = c3.number_input("Tutar", value=src["amount"], step=1000000, key=f"fa_{i}")
        if currency == "TL":
            fx_lbl = "Kur (TL/USD)"
            fx_def = src.get("fx_rate", 32.0)
        elif currency == "EUR":
            fx_lbl = "Kur (EUR/USD)"
            fx_def = src.get("fx_rate", 1.08)
        else:
            fx_lbl = "Kur (N/A)"
            fx_def = 1.0
        fx_rate = c4.number_input(fx_lbl, value=float(fx_def), step=0.01, key=f"fx_{i}",
                                   disabled=(currency == "USD"))
        rate = c5.number_input("Yillik Maliyet (%)", value=src["annual_rate"], step=0.1, key=f"fr_{i}")
        delete = c6.button("Sil", key=f"fd_{i}")
        if not delete:
            updated_sources.append({
                "name": name, "amount": amount, "currency": currency,
                "fx_rate": fx_rate if currency != "USD" else 1.0, "annual_rate": rate,
            })
    st.session_state.funding_sources = updated_sources

    if st.session_state.funding_sources:
        wacc_a_pre, wacc_m_pre = calculate_wacc(st.session_state.funding_sources)
        total_usd_pre = sum(get_usd_amount(s["amount"], s["currency"], s["fx_rate"]) for s in st.session_state.funding_sources)

        st.divider()
        st.subheader("Base Kaynak Maliyeti (OPEX Haric)")
        bm1, bm2, bm3 = st.columns(3)
        bm1.metric("Toplam Fon (USD Karsiligi)", f"${total_usd_pre:,.0f}")
        bm2.metric("Base Yillik Kaynak Maliyeti (WACC)", f"%{wacc_a_pre:.2f}")
        bm3.metric("Base Aylik Kaynak Maliyeti", f"%{wacc_m_pre:.2f}")

        df_src = []
        for s in st.session_state.funding_sources:
            usd_val = get_usd_amount(s["amount"], s["currency"], s["fx_rate"])
            weight = (usd_val / total_usd_pre * 100) if total_usd_pre > 0 else 0
            if s["currency"] == "TL":
                kur_str = f"1 USD = {s['fx_rate']:.2f} TL"
            elif s["currency"] == "EUR":
                kur_str = f"1 EUR = {s['fx_rate']:.2f} USD"
            else:
                kur_str = "-"
            df_src.append({
                "Kaynak": s["name"],
                "Tutar (Orijinal)": f"{s['currency']} {s['amount']:,.0f}",
                "Kur": kur_str,
                "USD Karsiligi": f"${usd_val:,.0f}",
                "Yillik Maliyet (%)": s["annual_rate"],
                "Agirlik (%)": round(weight, 2),
                "Agirlikli Maliyet (%)": round(weight / 100 * s["annual_rate"], 4),
            })
        st.dataframe(pd.DataFrame(df_src), use_container_width=True)

    st.divider()
    st.subheader("OPEX Aylik Marji")
    st.session_state.opex_monthly_margin = st.number_input(
        "Aylik OPEX Marji (%)", min_value=0.0, max_value=5.0,
        value=st.session_state.opex_monthly_margin, step=0.01,
        help="Aylik girilen deger 12 ile carpilarak yillik OPEX marjina donusturulur."
    )
    opex_annual = round(st.session_state.opex_monthly_margin * 12, 4)
    st.info(f"Aylik OPEX: **%{st.session_state.opex_monthly_margin:.2f}** → Yillik OPEX: **%{opex_annual:.2f}**")

    wacc_a, wacc_m = calculate_wacc(st.session_state.funding_sources)
    base_cost_annual = round(wacc_a + opex_annual, 4)
    base_cost_monthly = round(base_cost_annual / 12, 4)

    st.divider()
    st.subheader("Hesaplama Sonuclari")
    m1, m2, m3 = st.columns(3)
    m1.metric("WACC (Yillik)", f"%{wacc_a:.2f}")
    m2.metric("Base Cost Yillik (WACC+OPEX)", f"%{base_cost_annual:.2f}", delta=f"+OPEX %{opex_annual:.2f}")
    m3.metric("Base Cost Aylik (WACC+OPEX)", f"%{base_cost_monthly:.2f}")

# ══════════════════════════════════════════════
# TAB 2: STRATEJIK HEDEFLER
# ══════════════════════════════════════════════
with tabs[1]:
    st.header("Stratejik Hedefler")
    s = st.session_state.strategy
    w = st.session_state.weights

    wacc_a2, _ = calculate_wacc(st.session_state.funding_sources)
    opex_annual2 = round(st.session_state.opex_monthly_margin * 12, 4)
    base_cost_annual2 = round(wacc_a2 + opex_annual2, 4)

    st.subheader("Global Makro Parametre")
    macro_options = ["Agresif Buyume", "Dengeli", "Defansif / Karlilik Odakli"]
    macro_desc = {
        "Agresif Buyume": "Pazar payi oncelikli — Nihai orana -75 bps indirim.",
        "Dengeli": "Standart mod — 0 bps degisiklik.",
        "Defansif / Karlilik Odakli": "Karlilik oncelikli — Nihai orana +100 bps prim."
    }
    s["macro_mode"] = st.selectbox("Strateji Modu", macro_options, index=macro_options.index(s["macro_mode"]))
    st.info(macro_desc[s["macro_mode"]])

    st.divider()
    st.subheader("Yillik Board KPI Hedefleri")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Hacim & Vade**")
        s["sales_target"] = st.number_input("Yillik Satis Hedefi ($)", value=s["sales_target"], step=1000000)
        s["avg_maturity_days"] = st.number_input("Hedef Ortalama Vade (Gun)", value=s["avg_maturity_days"], step=10)
        s["collection_rate_pct"] = st.number_input("Hedef Tahsilat Orani (%)", value=s["collection_rate_pct"], step=0.5)
        s["grace_days"] = st.number_input("Standart Grace Suresi (Gun)", value=s["grace_days"], step=5)

    with c2:
        st.markdown("**Karlilik & Risk**")
        s["target_portfolio_gross_pct"] = st.number_input(
            "Hedef Portfoy Brut Kar % (Yillik)",
            value=s["target_portfolio_gross_pct"], step=0.5,
        )
        s["funds_in_legal_threshold_pct"] = st.number_input(
            "Funds in Legal - Fiyatlamaya Yansima Esigi (%)",
            value=s["funds_in_legal_threshold_pct"], step=0.5,
            help="Bu esigi gecen Funds in Legal orani fiyata prim olarak yansir."
        )
        s["funds_in_legal_pct_new"] = st.number_input(
            "Funds in Legal % - Yeni Musteri",
            value=s["funds_in_legal_pct_new"], step=0.1
        )
        s["funds_in_legal_pct_repeat"] = st.number_input(
            "Funds in Legal % - Tekrar Musteri",
            value=s["funds_in_legal_pct_repeat"], step=0.1
        )

    st.session_state.strategy = s

    st.divider()
    st.subheader("Strateji Hesaplama Ozeti")

    avg_maturity_months = s["avg_maturity_days"] / 30
    target_monthly_rate = round(s["target_portfolio_gross_pct"] / avg_maturity_months, 4) if avg_maturity_months > 0 else 0
    base_cost_monthly2 = round(base_cost_annual2 / 12, 4)
    macro_bps2 = get_macro_bps(s["macro_mode"])
    macro_pct2 = bps_to_pct(macro_bps2)
    adjusted_monthly_rate = round(target_monthly_rate + macro_pct2 / avg_maturity_months, 4) if avg_maturity_months > 0 else target_monthly_rate

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hedef Portfoy Brut Kar (Yillik)", f"%{s['target_portfolio_gross_pct']:.1f}")
    col2.metric("Hedef Ortalama Vade", f"{s['avg_maturity_days']} gun ({avg_maturity_months:.1f} ay)")
    col3.metric("Hedef Aylik Oran", f"%{target_monthly_rate:.2f} / ay",
                help=f"= {s['target_portfolio_gross_pct']}% / {avg_maturity_months:.1f} ay")
    col4.metric("Makro Duzeltmeli Aylik Oran", f"%{adjusted_monthly_rate:.2f} / ay",
                delta=f"Makro: {macro_bps2:+d} bps")

    st.divider()
    st.subheader("Vade-Brut Kar Simulasyonu")
    sim_data = []
    for days in [30, 60, 90, 120, 150, 180]:
        months = days / 30
        gross = round(target_monthly_rate * months, 2)
        gross_adj = round(adjusted_monthly_rate * months, 2)
        sim_data.append({
            "Vade (Gun)": days,
            "Vade (Ay)": months,
            "Brut Kar % (Hedef Oran)": gross,
            "Brut Kar % (Makro Duzeltmeli)": gross_adj,
            "Hedef Vade mi?": "✅" if days == s["avg_maturity_days"] else ""
        })
    st.dataframe(pd.DataFrame(sim_data), use_container_width=True, hide_index=True)

    legal_new_bps = calculate_legal_premium_bps(s["funds_in_legal_pct_new"], s["funds_in_legal_threshold_pct"],
                                                 w["funds_in_legal_multiplier"], w["funds_in_legal_cap_bps"])
    legal_rep_bps = calculate_legal_premium_bps(s["funds_in_legal_pct_repeat"], s["funds_in_legal_threshold_pct"],
                                                  w["funds_in_legal_multiplier"], w["funds_in_legal_cap_bps"])
    if legal_new_bps > 0 or legal_rep_bps > 0:
        st.warning(f"Funds in Legal Primi Aktif — Yeni Musteri: +{legal_new_bps} bps | Tekrar Musteri: +{legal_rep_bps} bps")
    else:
        st.success(f"Funds in Legal esik altinda — Fiyatlamaya prim yansimaz (Esik: %{s['funds_in_legal_threshold_pct']})")

# ══════════════════════════════════════════════
# TAB 3: DEGERLENDIRME & FIYATLAMA
# ══════════════════════════════════════════════
with tabs[2]:
    st.header("Degerlendirme & Fiyatlama")

    opex_annual_t3 = round(st.session_state.opex_monthly_margin * 12, 4)
    wacc_a3, _ = calculate_wacc(st.session_state.funding_sources)
    base_cost_annual3 = round(wacc_a3 + opex_annual_t3, 4)
    base_cost_monthly3 = round(base_cost_annual3 / 12, 4)
    s3 = st.session_state.strategy
    w3 = st.session_state.weights
    macro_bps3 = get_macro_bps(s3["macro_mode"])

    avg_maturity_months3 = s3["avg_maturity_days"] / 30
    target_monthly_rate3 = round(s3["target_portfolio_gross_pct"] / avg_maturity_months3, 4) if avg_maturity_months3 > 0 else 0

    col_input, col_result = st.columns([1, 1])

    with col_input:
        st.subheader("Musteri Parametreleri")
        customer_name = st.text_input("Musteri Adi / Kodu", value="ABC Gida Ltd.")
        customer_type = st.selectbox("Musteri Tipi", ["Yeni Musteri", "Tekrar Musteri"])
        deal_amount = st.number_input("Islem Tutari ($)", min_value=10000, value=500000, step=10000)
        maturity_days = st.number_input("Vade (Gun)", min_value=30, max_value=360, value=120, step=15)

        st.markdown("---")
        risk_grade = st.selectbox("Risk Notu", ["Dusuk", "Orta", "Yuksek"])
        payment_freq = st.selectbox("Odeme Sikligi", ["Haftalik", "Aylik", "45 Gunluk"])
        stock_turnover = st.number_input("Stok Cevrim Hizi (x/yil)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)

        st.markdown("**Urun Kategorisi (Trendyol)**")
        category = st.selectbox(
            "Kategori Sec",
            list(TRENDYOL_CATEGORIES.keys()),
            help="Trendyol komisyon oranina gore karlilik bazli BPS ayarlamasi yapilir."
        )
        cat_info = TRENDYOL_CATEGORIES[category]
        cat_bps = w3[cat_info["key"]]
        st.caption(f"Komisyon: {cat_info['komisyon']} | Karlilik: {cat_info['karlilik']} | BPS: {cat_bps:+d}")

        grace_period = st.selectbox("Grace Suresi", ["Yok", "15 Gun", "30 Gun"])
        pipeline = st.selectbox("Pipeline Durumu", ["Dusuk", "Normal", "Yuksek"])

        legal_pct = s3["funds_in_legal_pct_new"] if customer_type == "Yeni Musteri" else s3["funds_in_legal_pct_repeat"]
        legal_bps = calculate_legal_premium_bps(legal_pct, s3["funds_in_legal_threshold_pct"],
                                                 w3["funds_in_legal_multiplier"], w3["funds_in_legal_cap_bps"])
        st.markdown("---")
        st.caption(f"Funds in Legal ({customer_type}): **%{legal_pct}** → Prim: **+{legal_bps} bps**")

    params = {
        "risk_grade": risk_grade, "maturity_days": maturity_days,
        "payment_freq": payment_freq, "stock_turnover": stock_turnover,
        "category": category, "grace_period": grace_period, "pipeline": pipeline
    }
    risk_bps, breakdown = calculate_risk_bps(params, w3)
    macro_pct3 = bps_to_pct(macro_bps3)
    legal_pct_val = bps_to_pct(legal_bps)
    risk_pct3 = bps_to_pct(risk_bps)

    maturity_months = maturity_days / 30
    risk_monthly_adj = round(risk_pct3 / maturity_months, 4) if maturity_months > 0 else 0
    legal_monthly_adj = round(legal_pct_val / maturity_months, 4) if maturity_months > 0 else 0
    macro_monthly_adj = round(macro_pct3 / maturity_months, 4) if maturity_months > 0 else 0

    final_monthly_rate = round(base_cost_monthly3 + target_monthly_rate3 + risk_monthly_adj + legal_monthly_adj + macro_monthly_adj, 4)
    final_annual_rate = round(final_monthly_rate * 12, 4)
    vade_gross_pct = round(final_monthly_rate * maturity_months, 4)

    with col_result:
        st.subheader("Fiyatlama Selalesi (Waterfall)")

        waterfall = [
            ("Base Cost Aylik (WACC+OPEX)", base_cost_monthly3, "maliyet"),
            ("Hedef Brut Kar Aylik Payi", target_monthly_rate3, "hedef"),
            ("Risk BPS Aylik Etkisi", risk_monthly_adj, "risk"),
            ("Funds in Legal Primi Aylik", legal_monthly_adj, "legal"),
            ("Makro Strateji Aylik Etkisi", macro_monthly_adj, "makro"),
        ]

        running = 0
        for label, val, kind in waterfall:
            running += val
            sign = "+" if val >= 0 else ""
            icons = {"maliyet": "🔵", "hedef": "🟢", "risk": "🔴" if val > 0 else "🟢",
                     "legal": "🔴" if val > 0 else "⚪", "makro": "🟡"}
            extra = ""
            if kind == "risk":
                extra = f" ({risk_bps:+d} bps / {maturity_months:.1f} ay)"
            elif kind == "legal":
                extra = f" ({legal_bps:+d} bps)"
            elif kind == "makro":
                extra = f" ({macro_bps3:+d} bps)"
            st.markdown(f"{icons[kind]} **{label}:** `{sign}{val:.3f}%`{extra}")

        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Nihai Aylik Oran", f"%{final_monthly_rate:.3f} / ay")
        r2.metric(f"Vade Bazli Brut Kar ({maturity_days}g)", f"%{vade_gross_pct:.2f}",
                  delta=f"Hedef: %{s3['target_portfolio_gross_pct']:.1f}")
        r3.metric("Yillik Esdeger Oran", f"%{final_annual_rate:.2f}")

        diff_from_target = round(vade_gross_pct - s3["target_portfolio_gross_pct"], 2)
        if diff_from_target >= 0:
            st.success(f"Bu islem portfoy hedefini **{diff_from_target:+.2f}%** asiyor.")
        else:
            st.warning(f"Bu islem portfoy hedefinin **{diff_from_target:.2f}%** altinda.")

        st.markdown("**Risk BPS Detayi:**")
        bps_df = pd.DataFrame(breakdown, columns=["Parametre", "Deger", "BPS"])
        bps_df["BPS"] = bps_df["BPS"].apply(lambda x: f"{x:+d}")
        st.dataframe(bps_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Manuel Override & Onay")
        override_monthly = st.number_input(
            "Nihai Aylik Oran - Manuel Duzeltme (%)",
            min_value=0.0,
            value=float(final_monthly_rate), step=0.01,
        )
        override_annual = round(override_monthly * 12, 4)
        override_gross = round(override_monthly * maturity_months, 4)

        if abs(override_monthly - final_monthly_rate) > 0.001:
            st.warning(f"Override: {override_monthly - final_monthly_rate:+.3f}%/ay sapma | Vade brut kar: %{override_gross:.2f}")

        override_note = st.text_area("Karar Notu", placeholder="Ornek: Stratejik musteri, indirim onaylandi.")

        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("Onayla ve Kaydet", type="primary", use_container_width=True):
                deal = {
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Musteri": customer_name, "Tip": customer_type,
                    "Tutar ($)": deal_amount, "Vade (Gun)": maturity_days,
                    "Vade (Ay)": round(maturity_months, 2),
                    "Kategori": category,
                    "Sistem Aylik Oran (%)": final_monthly_rate,
                    "Nihai Aylik Oran (%)": override_monthly,
                    "Nihai Yillik Oran (%)": override_annual,
                    "Vade Brut Kar (%)": override_gross,
                    "Risk BPS": risk_bps, "Legal BPS": legal_bps,
                    "Makro Mod": s3["macro_mode"], "Durum": "Onaylandi", "Not": override_note
                }
                st.session_state.approved_deals.append(deal)
                st.success(f"Onaylandi! Aylik: %{override_monthly:.3f} | Vade Brut Kar: %{override_gross:.2f}")
        with col_reject:
            if st.button("Reddet", use_container_width=True):
                deal = {
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Musteri": customer_name, "Tip": customer_type,
                    "Tutar ($)": deal_amount, "Vade (Gun)": maturity_days,
                    "Vade (Ay)": round(maturity_months, 2),
                    "Kategori": category,
                    "Sistem Aylik Oran (%)": final_monthly_rate,
                    "Nihai Aylik Oran (%)": override_monthly,
                    "Nihai Yillik Oran (%)": override_annual,
                    "Vade Brut Kar (%)": override_gross,
                    "Risk BPS": risk_bps, "Legal BPS": legal_bps,
                    "Makro Mod": s3["macro_mode"], "Durum": "Reddedildi", "Not": override_note
                }
                st.session_state.approved_deals.append(deal)
                st.error("Islem reddedildi ve kayit altina alindi.")

# ══════════════════════════════════════════════
# TAB 4: PORTFOY TAKIP
# ══════════════════════════════════════════════
with tabs[3]:
    st.header("Portfoy Takip - Yillik Hedeflere Gore Neredeyiz?")
    s4 = st.session_state.strategy
    approved = [d for d in st.session_state.approved_deals if d["Durum"] == "Onaylandi"]

    st.subheader("Hedef Gostergeler")
    g1, g2, g3 = st.columns(3)

    total_volume = sum(d["Tutar ($)"] for d in approved) if approved else 0
    sales_progress = (total_volume / s4["sales_target"] * 100) if s4["sales_target"] > 0 else 0

    if approved:
        df_ap = pd.DataFrame(approved)
        weighted_maturity = (df_ap["Tutar ($)"] * df_ap["Vade (Gun)"]).sum() / df_ap["Tutar ($)"].sum()
        weighted_gross = (df_ap["Tutar ($)"] * df_ap["Vade Brut Kar (%)"]).sum() / df_ap["Tutar ($)"].sum()
        weighted_monthly = (df_ap["Tutar ($)"] * df_ap["Nihai Aylik Oran (%)"]).sum() / df_ap["Tutar ($)"].sum()
    else:
        weighted_maturity = weighted_gross = weighted_monthly = 0

    with g1:
        st.metric("Toplam Onaylanan Hacim", f"${total_volume:,.0f}",
                  delta=f"%{sales_progress:.1f} / Hedef ${s4['sales_target']:,.0f}")
        st.progress(min(sales_progress / 100, 1.0))
        if sales_progress >= 100: st.success("Satis hedefi asildi!")
        elif sales_progress >= 75: st.warning(f"Hedefe %{100-sales_progress:.1f} kaldi")
        else: st.error(f"Hedefe %{100-sales_progress:.1f} kaldi")

    with g2:
        maturity_diff = weighted_maturity - s4["avg_maturity_days"]
        st.metric("Portfoy Agirlikli Ort. Vade",
                  f"{weighted_maturity:.0f} gun" if approved else "- gun",
                  delta=f"{maturity_diff:+.0f}g / Hedef {s4['avg_maturity_days']}g" if approved else "Veri yok")
        if approved:
            st.progress(min(weighted_maturity / s4["avg_maturity_days"], 1.0))
            if abs(maturity_diff) <= 10: st.success("Vade hedefinde!")
            elif maturity_diff > 10: st.warning(f"Hedefin {maturity_diff:.0f}g uzeri")
            else: st.info(f"Hedefin {abs(maturity_diff):.0f}g alti")

    with g3:
        gross_diff = weighted_gross - s4["target_portfolio_gross_pct"]
        st.metric("Portfoy Agirlikli Brut Kar %",
                  f"%{weighted_gross:.2f}" if approved else "-%",
                  delta=f"{gross_diff:+.2f}% / Hedef %{s4['target_portfolio_gross_pct']:.1f}" if approved else "Veri yok")
        if approved:
            st.progress(min(weighted_gross / s4["target_portfolio_gross_pct"], 1.0))
            if gross_diff >= 0: st.success(f"Brut kar hedefi asildi! (+{gross_diff:.2f}%)")
            elif gross_diff >= -2: st.warning(f"Hedefe yakin ({gross_diff:.2f}%)")
            else: st.error(f"Hedefin altinda ({gross_diff:.2f}%)")

    if approved:
        st.divider()
        st.subheader("Islem Bazli Detay")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Onaylanan Islem", len(approved))
        m2.metric("Reddedilen Islem", len([d for d in st.session_state.approved_deals if d["Durum"] == "Reddedildi"]))
        m3.metric("Ort. Aylik Oran (Agirlikli)", f"%{weighted_monthly:.3f}")
        m4.metric("Ort. Yillik Esdeger", f"%{weighted_monthly*12:.2f}")
        st.dataframe(pd.DataFrame(approved), use_container_width=True, hide_index=True)
        if st.button("Tum Kayitlari Temizle"):
            st.session_state.approved_deals = []
            st.rerun()
    else:
        st.info("Henuz onaylanan islem yok.")

# ══════════════════════════════════════════════
# TAB 5: AYARLAR / WEIGHTS
# ══════════════════════════════════════════════
with tabs[4]:
    st.header("Ayarlar - BPS Agirliklari & Parametreler")
    w5 = st.session_state.weights

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Risk Notu")
        w5["risk_low"] = st.number_input("Dusuk Risk (bps)", value=w5["risk_low"])
        w5["risk_mid"] = st.number_input("Orta Risk (bps)", value=w5["risk_mid"])
        w5["risk_high"] = st.number_input("Yuksek Risk (bps)", value=w5["risk_high"])

        st.subheader("Vade")
        w5["maturity_lt90"] = st.number_input("<90 Gun (bps)", value=w5["maturity_lt90"])
        w5["maturity_120"] = st.number_input("120 Gun (bps)", value=w5["maturity_120"])
        w5["maturity_gt120_per30"] = st.number_input(">120 Gun, her 30g (bps)", value=w5["maturity_gt120_per30"])

        st.subheader("Odeme Sikligi")
        w5["payment_weekly"] = st.number_input("Haftalik (bps)", value=w5["payment_weekly"])
        w5["payment_monthly"] = st.number_input("Aylik (bps)", value=w5["payment_monthly"])
        w5["payment_45d"] = st.number_input("45 Gunluk (bps)", value=w5["payment_45d"])

        st.subheader("Stok Cevrim")
        w5["stock_gt6"] = st.number_input(">6x (bps)", value=w5["stock_gt6"])
        w5["stock_4to6"] = st.number_input("4-6x (bps)", value=w5["stock_4to6"])
        w5["stock_lt4"] = st.number_input("<4x (bps)", value=w5["stock_lt4"])

    with col2:
        st.subheader("Trendyol Kategori BPS (Karlilik Bazli)")
        st.caption("Dusuk komisyon = Ince marj = Fiyati dusuk tut (negatif bps) | Yuksek komisyon = Yuksek marj = Prim uygula (pozitif bps)")
        cat_table = []
        for cat_name, cat_data in TRENDYOL_CATEGORIES.items():
            key = cat_data["key"]
            w5[key] = st.number_input(
                f"{cat_name} ({cat_data['komisyon']})",
                value=w5[key], step=25, key=f"w_{key}"
            )
            cat_table.append({"Kategori": cat_name, "Komisyon": cat_data["komisyon"],
                               "Karlilik": cat_data["karlilik"], "BPS": w5[key]})

        st.subheader("Grace Suresi")
        w5["grace_none"] = st.number_input("Grace Yok (bps)", value=w5["grace_none"])
        w5["grace_15d"] = st.number_input("Grace 15 Gun (bps)", value=w5["grace_15d"])
        w5["grace_30d"] = st.number_input("Grace 30 Gun (bps)", value=w5["grace_30d"])

        st.subheader("Pipeline")
        w5["pipeline_low"] = st.number_input("Pipeline Dusuk (bps)", value=w5["pipeline_low"])
        w5["pipeline_normal"] = st.number_input("Pipeline Normal (bps)", value=w5["pipeline_normal"])
        w5["pipeline_high"] = st.number_input("Pipeline Yuksek (bps)", value=w5["pipeline_high"])

        st.subheader("Funds in Legal Prim Parametreleri")
        w5["funds_in_legal_multiplier"] = st.number_input(
            "Katsayi", value=float(w5["funds_in_legal_multiplier"]), step=0.1,
            help="(Legal% - Esik%) x Katsayi x 100 = BPS"
        )
        w5["funds_in_legal_cap_bps"] = st.number_input(
            "Prim Tavani (bps)", value=int(w5["funds_in_legal_cap_bps"]), step=25
        )

    st.session_state.weights = w5

    st.divider()
    st.subheader("Kategori Ozet Tablosu")
    st.dataframe(pd.DataFrame(cat_table), use_container_width=True, hide_index=True)

    if st.button("Agirliklari Kaydet", type="primary"):
        st.success("Tum parametreler guncellendi!")
'''

with open("dynamic_pricing_tool.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Dosya olusturuldu!")
print(f"Satir sayisi: {len(code.splitlines())}")