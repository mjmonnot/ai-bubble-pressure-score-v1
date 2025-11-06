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
st.subheader("Composite (3-quarter rolling average)")
st.line_chart(df[["AIBPS_RA"]])

# ---- Latest metrics ----
st.subheader("Latest pillar readings")
cols = st.columns(5)
for i, p in enumerate(pillars):
    latest = df[p].dropna().iloc[-1] if not df[p].dropna().empty else float("nan")
    cols[i].metric(p, f"{latest:.1f}" if pd.notna(latest) else "na")

# ---- Weighted contributions (latest) ----
st.subheader("Weighted contributions (latest)")
latest_vals = np.array([df[p].dropna().iloc[-1] if not df[p].dropna().empty else 0.0 for p in pillars])
contrib = latest_vals * weights
fig, ax = plt.subplots(figsize=(7, 3))
ax.barh(pillars, contrib)
ax.axvline(contrib.sum(), linestyle="--", color="gray", label=f"Composite = {contrib.sum():.1f}")
ax.set_xlabel("Weighted contribution")
ax.legend(loc="lower right")
st.pyplot(fig, clear_figure=True)

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
