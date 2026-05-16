# dynamic_pricing_tool.py

# Gereksinimler: pip install streamlit pandas

import streamlit as st\
import pandas as pd\
from datetime import datetime

st.set_page_config(\
page_title="Dinamik Fiyatlama Aracı",\
page_icon="💹",\
layout="wide"\
)

# ─────────────────────────────────────────────

# SESSION STATE BAŞLATMA (Varsayılan Değerler)

# ─────────────────────────────────────────────

def init_session_state():\
if "funding_sources" not in st.session_state:\
st.session_state.funding_sources = \[\
{"name": "Sukuk", "amount": 50_000_000, "annual_rate": 12.5, "frequency": "Yıllık"},\
{"name": "Banka Kredisi", "amount": 30_000_000, "annual_rate": 15.0, "frequency": "Aylık"},\
{"name": "VDMK", "amount": 20_000_000, "annual_rate": 11.0, "frequency": "Yıllık"},\
\]\
if "opex_margin" not in st.session_state:\
st.session_state.opex_margin = 2.0\
if "strategy" not in st.session_state:\
st.session_state.strategy = {\
"sales_target": 140_000_000,\
"avg_maturity_days": 120,\
"gross_profit_pct_new": 4.5,\
"gross_profit_pct_repeat": 3.5,\
"monthly_profit_pct": 1.2,\
"grace_days": 15,\
"collection_rate_pct": 92.0,\
"legal_npl_pct_new": 3.0,\
"legal_npl_pct_repeat": 1.5,\
"macro_mode": "Dengeli",\
}\
if "weights" not in st.session_state:\
st.session_state.weights = {\
"risk_low": -50, "risk_mid": 0, "risk_high": 200,\
"maturity_lt90": -50, "maturity_120": 0, "maturity_gt120_per30": 100,\
"payment_weekly": -50, "payment_monthly": 0, "payment_45d": 75,\
"stock_gt6": -75, "stock_4to6": -25, "stock_lt4": 0,\
"category_fmcg": -25, "category_standard": 0, "category_textile": 100,\
"grace_none": 0, "grace_15d": 30, "grace_30d": 75,\
"pipeline_low": -50, "pipeline_normal": 0, "pipeline_high": 100,\
}\
if "approved_deals" not in st.session_state:\
st.session_state.approved_deals = \[\]

init_session_state()

# ─────────────────────────────────────────────

# HESAPLAMA FONKSİYONLARI (Modüler - Google Sheets API'ye bağlanabilir)

# ─────────────────────────────────────────────

def calculate_wacc(sources):\
total = sum(s\["amount"\] for s in sources)\
if total == 0:\
return 0.0, 0.0\
wacc_annual = sum((s\["amount"\] / total) \* s\["annual_rate"\] for s in sources)\
wacc_monthly = wacc_annual / 12\
return round(wacc_annual, 4), round(wacc_monthly, 4)

def calculate_base_cost(wacc_annual, opex_margin):\
return round(wacc_annual + opex_margin, 4)

def get_macro_bps(mode):\
mapping = {"Agresif Büyüme": -75, "Dengeli": 0, "Defansif / Karlılık Odaklı": 100}\
return mapping.get(mode, 0)

def calculate_risk_bps(params, weights):\
bps = 0\
breakdown = \[\]

```
# Risk Notu
risk_map = {"Düşük": weights["risk_low"], "Orta": weights["risk_mid"], "Yüksek": weights["risk_high"]}
v = risk_map[params["risk_grade"]]
bps += v; breakdown.append(("Risk Notu", params["risk_grade"], v))

# Vade
md = params["maturity_days"]
if md < 90:
    v = weights["maturity_lt90"]
    label = f"<90 gün ({md} gün)"
elif md == 120:
    v = weights["maturity_120"]
    label = "120 gün"
else:
    extra = max(0, (md - 120) // 30)
    v = extra * weights["maturity_gt120_per30"]
    label = f"{md} gün (+{extra}×30g)"
bps += v; breakdown.append(("Vade", label, v))

# Ödeme Sıklığı
pf_map = {"Haftalık": weights["payment_weekly"], "Aylık": weights["payment_monthly"], "45 Günlük": weights["payment_45d"]}
v = pf_map[params["payment_freq"]]
bps += v; breakdown.append(("Ödeme Sıklığı", params["payment_freq"], v))

# Stok Çevrim
sc = params["stock_turnover"]
if sc > 6:
    v = weights["stock_gt6"]; label = f">6 ({sc}x)"
elif sc >= 4:
    v = weights["stock_4to6"]; label = f"4-6 ({sc}x)"
else:
    v = weights["stock_lt4"]; label = f"<4 ({sc}x)"
bps += v; breakdown.append(("Stok Çevrim", label, v))

# Kategori
cat_map = {"FMCG": weights["category_fmcg"], "Standart": weights["category_standard"], "Tekstil": weights["category_textile"]}
v = cat_map[params["category"]]
bps += v; breakdown.append(("Kategori", params["category"], v))

# Grace Süresi
gr_map = {"Yok": weights["grace_none"], "15 Gün": weights["grace_15d"], "30 Gün": weights["grace_30d"]}
v = gr_map[params["grace_period"]]
bps += v; breakdown.append(("Grace Süresi", params["grace_period"], v))

# Pipeline
pl_map = {"Düşük": weights["pipeline_low"], "Normal": weights["pipeline_normal"], "Yüksek": weights["pipeline_high"]}
v = pl_map[params["pipeline"]]
bps += v; breakdown.append(("Pipeline", params["pipeline"], v))

return bps, breakdown
```

def bps_to_pct(bps):\
return round(bps / 100, 4)

# ─────────────────────────────────────────────

# SEKMELER

# ─────────────────────────────────────────────

tabs = st.tabs(\[\
"💰 Finans Ekibi",\
"🎯 Strateji Ekibi",\
"🔍 Değerlendirme & Fiyatlama",\
"⚙️ Ayarlar / Weights",\
"📋 Onaylanan İşlemler"\
\])

# ══════════════════════════════════════════════

# TAB 1: FİNANS EKİBİ

# ══════════════════════════════════════════════

with tabs\[0\]:\
st.header("💰 Finans Ekibi — Borçlanma Kaynakları & WACC")\
st.caption("Şirketin fon kaynaklarını girin. Sistem WACC'ı otomatik hesaplar.")

```
col_add, col_space = st.columns([3, 1])
with col_add:
    with st.expander("➕ Yeni Kaynak Ekle", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        new_name = c1.text_input("Kaynak Adı", value="Ortak Borcu")
        new_amount = c2.number_input("Tutar ($)", min_value=0, value=10_000_000, step=1_000_000)
        new_rate = c3.number_input("Yıllık Maliyet (%)", min_value=0.0, max_value=100.0, value=13.0, step=0.1)
        new_freq = c4.selectbox("Ödeme Sıklığı", ["Aylık", "Yıllık", "Çeyreklik"])
        if st.button("Ekle", type="primary"):
            st.session_state.funding_sources.append({
                "name": new_name, "amount": new_amount,
                "annual_rate": new_rate, "frequency": new_freq
            })
            st.rerun()

st.subheader("Mevcut Kaynaklar")
sources = st.session_state.funding_sources
updated_sources = []
for i, src in enumerate(sources):
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
    name = c1.text_input("Ad", value=src["name"], key=f"fn_{i}")
    amount = c2.number_input("Tutar ($)", value=src["amount"], step=1_000_000, key=f"fa_{i}")
    rate = c3.number_input("Yıllık Maliyet (%)", value=src["annual_rate"], step=0.1, key=f"fr_{i}")
    freq = c4.selectbox("Sıklık", ["Aylık", "Yıllık", "Çeyreklik"], index=["Aylık", "Yıllık", "Çeyreklik"].index(src["frequency"]), key=f"ff_{i}")
    delete = c5.button("🗑️", key=f"fd_{i}")
    if not delete:
        updated_sources.append({"name": name, "amount": amount, "annual_rate": rate, "frequency": freq})
st.session_state.funding_sources = updated_sources

st.divider()
st.subheader("OPEX Marjı")
st.session_state.opex_margin = st.slider(
    "Operasyonel Gider Marjı (%)", min_value=1.0, max_value=5.0,
    value=st.session_state.opex_margin, step=0.1
)

# WACC Hesaplama
wacc_a, wacc_m = calculate_wacc(st.session_state.funding_sources)
base_cost = calculate_base_cost(wacc_a, st.session_state.opex_margin)
total_funds = sum(s["amount"] for s in st.session_state.funding_sources)

st.divider()
st.subheader("📊 Hesaplama Sonuçları")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Toplam Fon", f"${total_funds:,.0f}")
m2.metric("WACC (Yıllık)", f"%{wacc_a:.2f}")
m3.metric("WACC (Aylık)", f"%{wacc_m:.2f}")
m4.metric("Base Cost (WACC+OPEX)", f"%{base_cost:.2f}", delta=f"+OPEX %{st.session_state.opex_margin:.1f}")

if st.session_state.funding_sources:
    df_src = pd.DataFrame(st.session_state.funding_sources)
    df_src["Ağırlık (%)"] = (df_src["amount"] / total_funds * 100).round(2)
    df_src["Ağırlıklı Maliyet (%)"] = (df_src["Ağırlık (%)"] / 100 * df_src["annual_rate"]).round(4)
    df_src.columns = ["Kaynak", "Tutar ($)", "Yıllık Maliyet (%)", "Sıklık", "Ağırlık (%)", "Ağırlıklı Maliyet (%)"]
    st.dataframe(df_src, use_container_width=True)
```

# ══════════════════════════════════════════════

# TAB 2: STRATEJİ EKİBİ

# ══════════════════════════════════════════════

with tabs\[1\]:\
st.header("🎯 Strateji Ekibi — KPI Hedefleri & Makro Mod")\
s = st.session_state.strategy

```
st.subheader("🌐 Global Makro Parametre (Risk Appetite Mode)")
macro_options = ["Agresif Büyüme", "Dengeli", "Defansif / Karlılık Odaklı"]
macro_desc = {
    "Agresif Büyüme": "🟢 Pazar payı öncelikli — Nihai orana **-75 bps** indirim uygulanır.",
    "Dengeli": "🟡 Standart mod — **0 bps** değişiklik.",
    "Defansif / Karlılık Odaklı": "🔴 Karlılık öncelikli — Nihai orana **+100 bps** prim eklenir."
}
s["macro_mode"] = st.selectbox("Strateji Modu", macro_options, index=macro_options.index(s["macro_mode"]))
st.info(macro_desc[s["macro_mode"]])

st.divider()
st.subheader("📌 Yıllık Board KPI'ları")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Genel Hedefler**")
    s["sales_target"] = st.number_input("Satış Hedefi ($)", value=s["sales_target"], step=1_000_000)
    s["avg_maturity_days"] = st.number_input("Ortalama Vade (Gün)", value=s["avg_maturity_days"], step=10)
    s["monthly_profit_pct"] = st.number_input("Aylık Kar Hedefi (%)", value=s["monthly_profit_pct"], step=0.1)
    s["grace_days"] = st.number_input("Grace Süresi (Gün)", value=s["grace_days"], step=5)
    s["collection_rate_pct"] = st.number_input("Tahsilat Oranı (%)", value=s["collection_rate_pct"], step=0.5)
with c2:
    st.markdown("**Müşteri Segmenti Hedefleri**")
    s["gross_profit_pct_new"] = st.number_input("Brüt Kar % — Yeni Müşteri", value=s["gross_profit_pct_new"], step=0.1)
    s["gross_profit_pct_repeat"] = st.number_input("Brüt Kar % — Tekrar Müşteri", value=s["gross_profit_pct_repeat"], step=0.1)
    s["legal_npl_pct_new"] = st.number_input("Legal/NPL % — Yeni Müşteri", value=s["legal_npl_pct_new"], step=0.1)
    s["legal_npl_pct_repeat"] = st.number_input("Legal/NPL % — Tekrar Müşteri", value=s["legal_npl_pct_repeat"], step=0.1)

st.session_state.strategy = s
st.success(f"✅ Makro Mod: **{s['macro_mode']}** | Satış Hedefi: **${s['sales_target']:,.0f}** | Ort. Vade: **{s['avg_maturity_days']} gün**")
```

# ══════════════════════════════════════════════

# TAB 3: DEĞERLENDİRME & FİYATLAMA

# ══════════════════════════════════════════════

with tabs\[2\]:\
st.header("🔍 Değerlendirme Ekibi — Müşteri Fiyatlama & İç Onay")

```
wacc_a, wacc_m = calculate_wacc(st.session_state.funding_sources)
base_cost = calculate_base_cost(wacc_a, st.session_state.opex_margin)
s = st.session_state.strategy
w = st.session_state.weights
macro_bps = get_macro_bps(s["macro_mode"])

col_input, col_result = st.columns([1, 1])

with col_input:
    st.subheader("📝 Müşteri Parametreleri")
    customer_name = st.text_input("Müşteri Adı / Kodu", value="ABC Gıda Ltd.")
    customer_type = st.selectbox("Müşteri Tipi", ["Yeni Müşteri", "Tekrar Müşteri"])
    deal_amount = st.number_input("İşlem Tutarı ($)", min_value=10_000, value=500_000, step=10_000)

    st.markdown("---")
    risk_grade = st.selectbox("Risk Notu", ["Düşük", "Orta", "Yüksek"])
    maturity_days = st.number_input("Vade (Gün)", min_value=30, max_value=360, value=120, step=15)
    payment_freq = st.selectbox("Ödeme Sıklığı", ["Haftalık", "Aylık", "45 Günlük"])
    stock_turnover = st.number_input("Stok Çevrim Hızı (x/yıl)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
    category = st.selectbox("Ürün Kategorisi", ["FMCG", "Standart", "Tekstil"])
    grace_period = st.selectbox("Grace Süresi", ["Yok", "15 Gün", "30 Gün"])
    pipeline = st.selectbox("Pipeline Durumu", ["Düşük", "Normal", "Yüksek"])

params = {
    "risk_grade": risk_grade, "maturity_days": maturity_days,
    "payment_freq": payment_freq, "stock_turnover": stock_turnover,
    "category": category, "grace_period": grace_period, "pipeline": pipeline
}
risk_bps, breakdown = calculate_risk_bps(params, w)
target_margin = s["gross_profit_pct_new"] if customer_type == "Yeni Müşteri" else s["gross_profit_pct_repeat"]
risk_pct = bps_to_pct(risk_bps)
macro_pct = bps_to_pct(macro_bps)
system_rate = round(base_cost + target_margin + risk_pct + macro_pct, 4)

with col_result:
    st.subheader("📊 İç Onay Ekranı — Fiyatlama Şelalesi")

    waterfall_data = [
        ("WACC (Ağırlıklı Sermaye Maliyeti)", wacc_a, "maliyet"),
        ("OPEX Marjı", st.session_state.opex_margin, "maliyet"),
        ("Hedef Brüt Kar Marjı", target_margin, "hedef"),
        ("Risk BPS Ayarlamaları", risk_pct, "risk"),
        ("Makro Strateji Ayarı", macro_pct, "makro"),
    ]

    st.markdown("**Waterfall Breakdown:**")
    running = 0
    for label, val, typ in waterfall_data:
        running += val
        color = "🟢" if val < 0 else ("🔵" if val == 0 else "🔴")
        sign = "+" if val >= 0 else ""
        st.markdown(f"{color} **{label}:** `{sign}{val:.2f}%` → Kümülatif: `{running:.2f}%`")

    st.divider()
    st.metric("🎯 Sistem Önerilen Oran", f"%{system_rate:.2f}", delta=f"Risk BPS: {risk_bps:+d}")

    st.markdown("**Risk BPS Detayı:**")
    bps_df = pd.DataFrame(breakdown, columns=["Parametre", "Değer", "BPS"])
    bps_df["BPS"] = bps_df["BPS"].apply(lambda x: f"{x:+d}")
    st.dataframe(bps_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("✏️ Manuel Müdahale (Override)")
    override_rate = st.number_input(
        "Nihai Karar Oranı (%)",
        min_value=0.0, max_value=50.0,
        value=float(system_rate), step=0.05,
        help="Yetkili kişi bu oranı manuel olarak revize edebilir."
    )
    override_note = st.text_area("Karar Notu / Gerekçe", placeholder="Örn: Müşteri stratejik öneme sahip, indirim onaylandı.")

    if abs(override_rate - system_rate) > 0.01:
        diff = override_rate - system_rate
        st.warning(f"⚠️ Manuel override: Sistem önerisinden **{diff:+.2f}%** sapma var.")

    col_approve, col_reject = st.columns(2)
    with col_approve:
        if st.button("✅ Onayla ve Kaydet", type="primary", use_container_width=True):
            deal = {
                "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Müşteri": customer_name,
                "Tip": customer_type,
                "Tutar ($)": deal_amount,
                "Sistem Oranı (%)": system_rate,
                "Nihai Oran (%)": override_rate,
                "Risk BPS": risk_bps,
                "Makro Mod": s["macro_mode"],
                "Durum": "✅ Onaylandı",
                "Not": override_note
            }
            st.session_state.approved_deals.append(deal)
            st.success(f"✅ İşlem onaylandı! Nihai Oran: **%{override_rate:.2f}**")
    with col_reject:
        if st.button("❌ Reddet", use_container_width=True):
            deal = {
                "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Müşteri": customer_name,
                "Tip": customer_type,
                "Tutar ($)": deal_amount,
                "Sistem Oranı (%)": system_rate,
                "Nihai Oran (%)": override_rate,
                "Risk BPS": risk_bps,
                "Makro Mod": s["macro_mode"],
                "Durum": "❌ Reddedildi",
                "Not": override_note
            }
            st.session_state.approved_deals.append(deal)
            st.error("❌ İşlem reddedildi ve kayıt altına alındı.")
```

# ══════════════════════════════════════════════

# TAB 4: AYARLAR / WEIGHTS

# ══════════════════════════════════════════════

with tabs\[3\]:\
st.header("⚙️ Ayarlar — BPS Ağırlıkları (Yönetici Paneli)")\
st.caption("Tüm baz puan değerleri buradan yönetilebilir. 100 bps = %1")\
w = st.session_state.weights

```
col1, col2 = st.columns(2)
with col1:
    st.subheader("Risk Notu")
    w["risk_low"] = st.number_input("Düşük Risk (bps)", value=w["risk_low"])
    w["risk_mid"] = st.number_input("Orta Risk (bps)", value=w["risk_mid"])
    w["risk_high"] = st.number_input("Yüksek Risk (bps)", value=w["risk_high"])

    st.subheader("Vade")
    w["maturity_lt90"] = st.number_input("<90 Gün (bps)", value=w["maturity_lt90"])
    w["maturity_120"] = st.number_input("120 Gün (bps)", value=w["maturity_120"])
    w["maturity_gt120_per30"] = st.number_input(">120 Gün, her 30g (bps)", value=w["maturity_gt120_per30"])

    st.subheader("Ödeme Sıklığı")
    w["payment_weekly"] = st.number_input("Haftalık (bps)", value=w["payment_weekly"])
    w["payment_monthly"] = st.number_input("Aylık (bps)", value=w["payment_monthly"])
    w["payment_45d"] = st.number_input("45 Günlük (bps)", value=w["payment_45d"])

    st.subheader("Stok Çevrim")
    w["stock_gt6"] = st.number_input(">6x (bps)", value=w["stock_gt6"])
    w["stock_4to6"] = st.number_input("4-6x (bps)", value=w["stock_4to6"])
    w["stock_lt4"] = st.number_input("<4x (bps)", value=w["stock_lt4"])

with col2:
    st.subheader("Kategori")
    w["category_fmcg"] = st.number_input("FMCG (bps)", value=w["category_fmcg"])
    w["category_standard"] = st.number_input("Standart (bps)", value=w["category_standard"])
    w["category_textile"] = st.number_input("Tekstil (bps)", value=w["category_textile"])

    st.subheader("Grace Süresi")
    w["grace_none"] = st.number_input("Grace Yok (bps)", value=w["grace_none"])
    w["grace_15d"] = st.number_input("Grace 15 Gün (bps)", value=w["grace_15d"])
    w["grace_30d"] = st.number_input("Grace 30 Gün (bps)", value=w["grace_30d"])

    st.subheader("Pipeline")
    w["pipeline_low"] = st.number_input("Pipeline Düşük (bps)", value=w["pipeline_low"])
    w["pipeline_normal"] = st.number_input("Pipeline Normal (bps)", value=w["pipeline_normal"])
    w["pipeline_high"] = st.number_input("Pipeline Yüksek (bps)", value=w["pipeline_high"])

st.session_state.weights = w
if st.button("💾 Ağırlıkları Kaydet", type="primary"):
    st.success("✅ BPS ağırlıkları güncellendi!")
```

# ══════════════════════════════════════════════

# TAB 5: ONAYLANAN İŞLEMLER

# ══════════════════════════════════════════════

with tabs\[4\]:\
st.header("📋 Onaylanan / Reddedilen İşlemler")\
deals = st.session_state.approved_deals\
if not deals:\
[st.info](http://st.info)("Henüz kayıtlı işlem yok. Değerlendirme sekmesinden işlem onaylayın.")\
else:\
df_deals = pd.DataFrame(deals)\
st.dataframe(df_deals, use_container_width=True, hide_index=True)\
approved = df_deals\[df_deals\["Durum"\] == "✅ Onaylandı"\]\
if not approved.empty:\
m1, m2, m3 = st.columns(3)\
m1.metric("Toplam Onaylanan İşlem", len(approved))\
m2.metric("Toplam Hacim ($$)'\].sum():,.0f}")\
m3.metric("Ort. Nihai Oran (%)", f"%{approved\['Nihai Oran (%)'\].mean():.2f}")\
if st.button("🗑️ Tüm Kayıtları Temizle"):\
st.session_state.approved_deals = \[\]\
st.rerun()