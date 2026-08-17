"""
app.py — Step 4. The live discovery engine (Streamlit).

Reads ONLY the precomputed CSVs (classified_data.csv, opportunities.csv).
NO Gemini call at runtime -> the deployed app needs no API key.

Run:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

# color-blind-safe qualitative palette (Plotly "Safe" ~ Okabe-Ito)
SAFE = px.colors.qualitative.Safe
PLOT_FONT = dict(family="system-ui, sans-serif", size=14)

st.set_page_config(page_title="Myntra Wishlist→Purchase Discovery Engine",
                   page_icon="🛍️", layout="wide")

# min ~14pt-equivalent text everywhere
st.markdown("""
<style>
  html, body, [class*="css"] { font-size: 16px; }
  .stMetric label { font-size: 15px !important; }
  .stMetric [data-testid="stMetricValue"] { font-size: 30px !important; }
  .insight { border:1px solid #d0d0d0; border-radius:10px; padding:14px 18px;
             margin-bottom:14px; background:rgba(127,127,127,0.05); }
  .quote { border-left:3px solid #888; padding-left:10px; margin:6px 0;
           color:#444; font-style:italic; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load():
    cls = pd.read_csv("classified_data.csv", dtype=str).fillna("")
    cls["is_relevant"] = cls["is_relevant"].str.lower().isin({"true", "1", "yes"})
    try:
        opp = pd.read_csv("opportunities.csv").fillna("")
    except FileNotFoundError:
        opp = pd.DataFrame()
    return cls, opp


def explode_barriers(df):
    s = df["barriers"].fillna("none").str.split("|").explode().str.strip()
    return s[s != ""]


try:
    cls, opp = load()
except FileNotFoundError:
    st.error("Missing classified_data.csv / opportunities.csv. "
             "Run collect.py → classify.py → analyze.py first.")
    st.stop()

st.title("🛍️ Myntra Wishlist→Purchase — Discovery Engine")
st.caption("Mines public user text to find **non-price** reasons people save fashion items but don't buy. "
           "A hypothesis generator, not proof — reach = complaint-share, not true prevalence.")

# ------------------------------------------------------------------ filters
rel_all = cls[cls["is_relevant"]].copy()
with st.sidebar:
    st.header("Filters")
    src = st.multiselect("Source", sorted(rel_all["source"].unique()),
                         default=sorted(rel_all["source"].unique()))
    stg = st.multiselect("Journey stage", sorted(rel_all["journey_stage"].unique()))
    itn = st.multiselect("Intent", sorted(rel_all["intent"].unique()))
    st.caption("Filters apply to the charts & cards below (not the corpus-level KPIs).")

rel = rel_all[rel_all["source"].isin(src)] if src else rel_all
if stg:
    rel = rel[rel["journey_stage"].isin(stg)]
if itn:
    rel = rel[rel["intent"].isin(itn)]

# ------------------------------------------------------------------ KPIs (corpus-level)
n_rel = len(rel_all)
price_mask = (rel_all["intent"] == "price_waiter") | rel_all["barriers"].str.contains("price_value")
price_share = price_mask.mean() if n_rel else 0
latent_share = (rel_all["intent"] == "latent_intent").mean() if n_rel else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Texts (total)", f"{len(cls):,}")
k2.metric("Relevant", f"{n_rel:,}")
k3.metric("Sources", cls["source"].nunique())
k4.metric("Non-price blockers", f"{(1-price_share)*100:.0f}%",
          help="KILL-SWITCH: share of relevant texts NOT blocked by price. Higher = more headroom for a no-discount strategy.")
k5.metric("Latent purchase intent", f"{latent_share*100:.0f}%")

st.divider()

# ------------------------------------------------------------------ kill-switch banner
if price_share < 0.5:
    st.success(f"**Kill-switch:** {price_share*100:.1f}% price vs **{(1-price_share)*100:.1f}% non-price**. "
               "Non-monetary strategy has headroom.")
else:
    st.warning(f"**Kill-switch:** {price_share*100:.1f}% of blockers are PRICE. "
               "The non-monetary strategy has a low ceiling — re-scope before investing.")

# ------------------------------------------------------------------ barrier chart
st.subheader("Barrier distribution")
bc = explode_barriers(rel).value_counts().reset_index()
bc.columns = ["barrier", "count"]
bc = bc[~bc["barrier"].isin(["none"])]
fig = px.bar(bc, x="count", y="barrier", orientation="h",
             color="barrier", color_discrete_sequence=SAFE,
             title=f"Voiced barriers among {len(rel):,} filtered relevant texts")
fig.update_layout(showlegend=False, font=PLOT_FONT, yaxis={"categoryorder": "total ascending"},
                  height=460, margin=dict(l=10, r=10, t=50, b=10))
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ intent + journey
c1, c2 = st.columns(2)
with c1:
    st.subheader("Intent mix")
    im = rel["intent"].value_counts().reset_index()
    im.columns = ["intent", "count"]
    f = px.pie(im, names="intent", values="count", color_discrete_sequence=SAFE, hole=0.45)
    f.update_layout(font=PLOT_FONT, height=360, margin=dict(t=10, b=10))
    st.plotly_chart(f, use_container_width=True)
with c2:
    st.subheader("Journey stage")
    jm = rel["journey_stage"].value_counts().reset_index()
    jm.columns = ["stage", "count"]
    f = px.bar(jm, x="stage", y="count", color="stage", color_discrete_sequence=SAFE)
    f.update_layout(showlegend=False, font=PLOT_FONT, height=360, margin=dict(t=10, b=10))
    st.plotly_chart(f, use_container_width=True)

st.divider()

# ------------------------------------------------------------------ opportunities
st.subheader("🎯 Ranked opportunities (gated, non-monetary)")
if opp.empty:
    st.info("No opportunities.csv — run analyze.py.")
else:
    show = opp[["rank", "barrier", "funnel_level", "score", "reach_band",
                "severity_band", "metric_relevance_band", "evidence_confidence", "n_texts"]]
    st.dataframe(show, use_container_width=True, hide_index=True,
                 column_config={"score": st.column_config.ProgressColumn(
                     "score", min_value=0, max_value=float(opp["score"].max()), format="%.2f")})
    st.caption("score = 2·MetricRelevance + 1.5·Severity + 1·Reach, × evidence discount (1.0/0.7/0.4). "
               "Reach = complaint-share (not true prevalence). MetricRelevance = hypothesised link to conversion.")

    st.subheader("Insight cards")
    for _, r in opp.head(6).iterrows():
        with st.container():
            st.markdown(
                f"<div class='insight'><b>#{int(r['rank'])} · {r['barrier']}</b> "
                f"— <i>{r['funnel_level']}</i> · score <b>{r['score']}</b> "
                f"(R/S/M = {r['reach_band']}/{r['severity_band']}/{r['metric_relevance_band']}, "
                f"evidence {r['evidence_confidence']}, n={int(r['n_texts'])})<br>"
                f"<b>Opportunity:</b> {r['opportunity']}<br>"
                f"<b>Top sub-theme:</b> {r['top_subtheme']}</div>",
                unsafe_allow_html=True)
            ev = rel_all[rel_all["barriers"].str.contains(str(r["barrier"]), regex=False)]
            ev = ev[ev["evidence_span"].str.len() > 0].head(3)
            for _, e in ev.iterrows():
                st.markdown(f"<div class='quote'>“{e['evidence_span']}” "
                            f"<a href='{e['url']}' target='_blank'>[{e['source']}]</a></div>",
                            unsafe_allow_html=True)

# ------------------------------------------------------------------ method
with st.expander("Method & limitations"):
    st.markdown("""
**Pipeline:** public text (Google Play / YouTube / Reddit) → Gemini labels (barrier, intent,
journey stage, emotion, verbatim evidence span) → TF-IDF sub-theme clustering → gated opportunity scoring.

**Gate:** only non-monetary, funnel-linked barriers survive; `price_value`, `none`, `other` are logged out.

**Honesty:**
- **Complaint-skewed** — reviews over-represent the frustrated. Reach = complaint-share, *not* true prevalence.
- **English-skewed** — `lang=en` only.
- **Proxy funnel** — app-review text ≠ the wishlist funnel. Every wishlist→purchase link is a *hypothesis*.
- Every relevant row carries a verbatim `evidence_span`, so labels are hand-auditable against source quotes.
- **No Gemini at runtime** — this app only reads precomputed CSVs.
""")
