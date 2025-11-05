import os
import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(__file__))
PRO = os.path.join(ROOT, "data", "processed")
SAMPLE = os.path.join(ROOT, "data", "sample")

st.set_page_config(page_title="AIBPS v0.1", layout="wide")
st.title("AI Bubble Pressure Score (AIBPS) — v0.1 Dashboard")

# Load processed or sample
path = os.path.join(PRO, "aibps_monthly.csv")
if not os.path.exists(path):
    path = os.path.join(SAMPLE, "aibps_monthly_sample.csv")
df = pd.read_csv(path, index_col=0, parse_dates=True)

st.line_chart(df[["AIBPS"]].rolling(3).mean())

cols = st.columns(5)
for i, p in enumerate([c for c in df.columns if c != "AIBPS"]):
    cols[i % 5].metric(p, f"{df[p].iloc[-1]:.1f}")

st.caption("""Bands: 50 (watch), 70–85 (elevated), >85 (critical)""")
