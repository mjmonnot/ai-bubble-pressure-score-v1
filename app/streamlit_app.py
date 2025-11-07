import os
import io
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# --- Page config: force the sidebar open so controls are visible on load ---
st.set_page_config(
    page_title="AIBPS v0.1",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("AI Bubble Pressure Score (AIBPS) — v0.1 Dashboard")

ROOT = os.path.dirname(os.path.dirname(__file__))
PRO = os.path.join(ROOT, "data", "processed")
SAMPLE = os.path.join(ROOT, "data", "sample")

# ---- Load data ----
path = os.path.join(PRO, "aibps_monthly.csv")
if not os.path.exists(path):
    path = os.path.join(SAMPLE, "aibps_monthly_sample.csv")
df = pd.read_csv(path, index_col=0, parse_dates=True)

pillars = ["Market", "Capex_Supply", "Infra", "Adoption", "Credit"]
for p in pillars:
    if p not in df.columns:
        df[p] = np.nan
df = df[pillars + [c for c in df.columns if c not in pillars]]

# --- Sidebar controls ---
st.sidebar.header("Weights (drag sliders)")
default_w = np.array([0.25, 0.25, 0.20, 0.15, 0.15])

# Reset button (uses session_state to reset sliders)
if "weights" not in st.session_state:
    st.session_state["weights"] = default_w.copy()

def reset_weights():
    st.session_state["weights"] = default_w.copy()

if st.sidebar.button("Reset to default (25/25/20/15/15)"):
    reset_weights()

w_market = st.sidebar.slider("Market", 0.0, 1.0, float(st.session_state["weights"][0]), 0.01)
w_capex  = st.sidebar.slider("Capex & Supply", 0.0, 1.0, float(st.session_state["weights"][1]), 0.01)
w_infra  = st.sidebar.slider("Infra (Power/DC)", 0.0, 1.0, float(st.session_state["weights"][2]), 0.01)
w_adopt  = st.sidebar.slider("Adoption", 0.0, 1.0, float(st.session_state["weights"][3]), 0.01)
w_credit = st.sidebar.slider("Credit", 0.0, 1.0, float(st.session_state["weights"][4]), 0.01)

weights = np.array([w_market, w_capex, w_infra, w_adopt, w_credit])
if weights.sum() == 0:
    weights = default_w.copy()
weights = weights / weights.sum()
st.sidebar.caption(f"Sum = {weights.sum():.2f} (auto-normalized)")

# --- Make interactivity obvious in the main pane ---
st.info(
    "Tip: Use the **weights** in the left sidebar to tune the composite. "
    "The chart and contributions update instantly. Click **Export** below to download a PDF chartbook.",
    icon="🧭",
)

# ---- Compute custom composite ----
df["AIBPS_custom"] = (df[pillars] * weights).sum(axis=1)
df["AIBPS_RA"] = df["AIBPS_custom"].rolling(3, min_periods=1).mean()


# ---- Composite chart ----
# ---- Composite chart ----
import altair as alt

st.subheader("Composite (3-quarter rolling average)")

# Pillar awareness + weights (normalize)
DESIRED = ["Market","Capex_Supply","Infra","Adoption","Credit"]
present_pillars = [p for p in DESIRED if p in df.columns]
if not present_pillars:
    st.error("No pillar columns found in processed data. Check pipeline outputs.")
    st.stop()

default_w = {"Market":0.25,"Capex_Supply":0.25,"Infra":0.20,"Adoption":0.15,"Credit":0.15}
w_controls = []
st.sidebar.subheader("Weights")
for p in present_pillars:
    w_controls.append(st.sidebar.slider(p, 0.0, 1.0, float(default_w.get(p,0.2)), 0.05))
weights = np.array(w_controls, dtype=float)
weights = np.ones_like(weights) if weights.sum() == 0 else weights/weights.sum()

# Compute custom composite
df["AIBPS_custom"] = (df[present_pillars] * weights).sum(axis=1)
df["AIBPS_RA"] = df["AIBPS_custom"].rolling(3, min_periods=1).mean()

df_plot = df.reset_index().rename(columns={df.index.name or "index": "Date"})
df_plot["Date"] = pd.to_datetime(df_plot["Date"])
df_plot = df_plot[["Date","AIBPS_RA"]].dropna()

if df_plot.empty:
    st.warning("No composite data available.")
else:
    c1,c2,c3,c4 = st.columns([1.2,1.2,1.2,2.4])
    with c1: show_bands  = st.checkbox("Show risk bands", value=True)
    with c2: show_rules  = st.checkbox("Show thresholds", value=True)
    with c3: show_points = st.checkbox("Show points", value=True)
    with c4: band_opacity = st.slider("Band opacity", 0.00, 0.40, 0.18, 0.02)

    ymin,ymax = 0,100
    start_date = df_plot["Date"].min(); end_date = df_plot["Date"].max()

    # Dynamic badge (palette matches bands)
    latest_val = float(df_plot["AIBPS_RA"].iloc[-1])
    def _zone(x):
        if x < 50: return "Watch (<50)", "#b7e3b1"
        if x < 70: return "Rising (50–70)", "#fde28a"
        if x < 85: return "Elevated (70–85)", "#f7b267"
        return "Critical (>85)", "#f08080"
    z_label, z_color = _zone(latest_val)
    st.markdown(
        f"""<div style="display:inline-block;padding:10px 14px;border-radius:12px;
                        background:{z_color};color:#222;font-weight:600;margin-bottom:6px;">
                AIBPS (3Q RA): {latest_val:.1f} — {z_label}
            </div>""",
        unsafe_allow_html=True
    )

    layers = []

    # Bands (green→yellow→orange→red) with horizontal legend at bottom
    if show_bands:
        bands_df = pd.DataFrame([
            {"label":"Critical (>85)",   "y_start":85, "y_end":100, "start":start_date, "end":end_date},
            {"label":"Elevated (70–85)", "y_start":70, "y_end":85,  "start":start_date, "end":end_date},
            {"label":"Rising (50–70)",   "y_start":50, "y_end":70,  "start":start_date, "end":end_date},
            {"label":"Watch (<50)",      "y_start":0,  "y_end":50,  "start":start_date, "end":end_date},
        ])
        bands = (
            alt.Chart(bands_df)
            .mark_rect(opacity=float(band_opacity))
            .encode(
                x="start:T", x2="end:T",
                y="y_start:Q", y2="y_end:Q",
                color=alt.Color(
                    "label:N",
                    scale=alt.Scale(
                        domain=["Watch (<50)","Rising (50–70)","Elevated (70–85)","Critical (>85)"],
                        range=["#b7e3b1","#fde28a","#f7b267","#f08080"]
                    ),
                    legend=alt.Legend(
                        title="Risk Zone", orient="bottom", direction="horizontal",
                        symbolSize=120, titleAnchor="middle"
                    )
                )
            )
        )
        layers.append(bands)

    # Main line (always)
    line = (
        alt.Chart(df_plot)
        .mark_line(point=False, strokeWidth=2, color="#e07b39")
        .encode(
            x=alt.X("Date:T", axis=alt.Axis(title="Date")),
            y=alt.Y("AIBPS_RA:Q", scale=alt.Scale(domain=[ymin,ymax]),
                    axis=alt.Axis(title="Composite Score (0–100)")),
            tooltip=[alt.Tooltip("Date:T", title="Date"),
                     alt.Tooltip("AIBPS_RA:Q", title="AIBPS (3Q RA)", format=".1f")]
        )
    )
    layers.append(line)

    if show_points:
        points = (
            alt.Chart(df_plot)
            .mark_circle(size=28, color="#e07b39", opacity=0.8)
            .encode(x="Date:T", y="AIBPS_RA:Q",
                    tooltip=[alt.Tooltip("Date:T", title="Date"),
                             alt.Tooltip("AIBPS_RA:Q", title="AIBPS (3Q RA)", format=".1f")])
        )
        layers.append(points)

    if show_rules:
        rules_df = pd.DataFrame({"y":[50,70,85]})
        rules = alt.Chart(rules_df).mark_rule(strokeDash=[4,4], color="gray").encode(y="y:Q")
        layers.append(rules)

    chart = alt.layer(*layers).resolve_scale(y="shared").interactive()
    st.altair_chart(chart, use_container_width=True)


# ---- Export to PDF ----
st.subheader("Export")
if st.button("Export current view as PDF"):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # Time-series page
        fig1, ax1 = plt.subplots(figsize=(9, 4.5))
        ax1.plot(df.index, df["AIBPS_RA"], linewidth=2)
        ax1.axhline(50, linestyle="--", linewidth=1)
        ax1.axhline(70, linestyle="--", linewidth=1)
        ax1.axhline(85, linestyle="--", linewidth=1)
        ax1.set_title("AIBPS — 3-Quarter Rolling Average")
        ax1.set_ylabel("Score (0–100)")
        fig1.tight_layout()
        pdf.savefig(fig1); plt.close(fig1)

        # Contributions page
        fig2, ax2 = plt.subplots(figsize=(7, 3))
        ax2.barh(pillars, contrib)
        ax2.axvline(contrib.sum(), linestyle="--", color="gray", label=f"Composite = {contrib.sum():.1f}")
        ax2.set_xlabel("Weighted contribution")
        ax2.set_title("Weighted Pillar Contributions — Latest")
        ax2.legend(loc="lower right")
        fig2.tight_layout()
        pdf.savefig(fig2); plt.close(fig2)

    st.download_button(
        "Download Chartbook PDF",
        data=buf.getvalue(),
        file_name="AIBPS_chartbook.pdf",
        mime="application/pdf",
    )

# --- Footer / version ---
st.caption("AIBPS v0.1 • sliders in sidebar • export available below")
st.markdown(
    """
    ---
    <div style="text-align: center; font-size: 0.9em;">
        <a href="https://streamlit.io/cloud" target="_blank">
            <img src="https://static.streamlit.io/badges/streamlit_badge_black_white.svg" 
                 alt="Streamlit Badge" width="100"/>
        </a>
        &nbsp;&nbsp;
        <a href="https://github.com/mjmonnot/aibps-v0-1" target="_blank">
            <img src="https://img.shields.io/badge/GitHub-Repository-black?logo=github" 
                 alt="GitHub Repo" height="25"/>
        </a>
        <br>
        <em>Deployed on Streamlit Cloud • View source on GitHub</em>
    </div>
    """,
    unsafe_allow_html=True,
)
