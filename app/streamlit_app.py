import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

# ---------- Constants ----------
PROC_PATH = os.path.join("data", "processed", "aibps_monthly.csv")
PILLAR_CANDIDATES = ["Market", "Credit", "Capex_Supply", "Infra", "Adoption", "Sentiment"]

# ---------- Page config ----------
st.set_page_config(
    page_title="AI Bubble Pressure Score",
    layout="wide",
)

st.title("AI Bubble Pressure Score (AIBPS)")
st.caption(
    "Composite view of AI-related market, credit, capex, infrastructure, adoption, "
    "and sentiment conditions, normalized to a 0–100 'pressure' scale."
)

# ---------- Load composite ----------
if not os.path.exists(PROC_PATH):
    st.error(f"Composite file not found at `{PROC_PATH}`. Run the GitHub Action first.")
    st.stop()

df = pd.read_csv(PROC_PATH, index_col=0, parse_dates=True).sort_index()
if df.empty:
    st.error("Composite file is empty. Check workflows / processed inputs.")
    st.stop()

df.index.name = "date"

# Determine which pillars are actually present
available_pillars = [p for p in PILLAR_CANDIDATES if p in df.columns]
if not available_pillars:
    st.error("No known pillars found in composite file.")
    st.stop()

# Try to detect any pre-computed composite columns
precomp_cols = [c for c in df.columns if c.lower() in ["aibps", "aibps_ra", "composite", "aibps_ra_norm"]]


# ---------- Sidebar: weights & options ----------
with st.sidebar:
    st.header("Pillar Weights")

    st.markdown(
        "Adjust the relative importance of each pillar. "
        "Weights are rescaled to sum to 1 for the composite."
    )

    weight_inputs = {}
    for p in available_pillars:
        weight_inputs[p] = st.slider(
            label=f"{p} weight",
            min_value=0.0,
            max_value=3.0,
            value=1.0,
            step=0.1,
        )

    # Build normalized weight vector
    w_vec = np.array([weight_inputs[p] for p in available_pillars], dtype=float)
    if w_vec.sum() == 0:
        w_vec = np.ones_like(w_vec)
    w_vec = w_vec / w_vec.sum()
    weights = pd.Series(w_vec, index=available_pillars)

    st.markdown("**Effective weights (normalized):**")
    for p in available_pillars:
        st.write(f"- {p}: {weights[p]:.2f}")

    st.markdown("---")
    st.subheader("Display options")

    composite_source = st.selectbox(
        "Composite source",
        options=["In-app recomputed", "Precomputed (from CSV)"],
        index=0,
        help="Use either the recomputed composite based on slider weights or the precomputed AIBPS from the CSV.",
    )

    plot_series = st.selectbox(
        "Which composite line to show?",
        options=["Rolling average (AIBPS_RA)", "Raw composite"],
        index=0,
    )

# ---------- Prepare composite (in-app and/or precomputed) ----------

# Use pillars as 0–100 normalized inputs
pillars_df = df[available_pillars].copy()

# In-app composite (based on sidebar weights)
comp_in_app = (pillars_df * weights).sum(axis=1)
comp_in_app_ra = comp_in_app.rolling(3, min_periods=1).mean()

# Precomputed composite (if available)
precomp_raw = None
precomp_ra = None
if "AIBPS" in df.columns:
    precomp_raw = df["AIBPS"]
if "AIBPS_RA" in df.columns:
    precomp_ra = df["AIBPS_RA"]

# Decide which composite to plot
if composite_source == "In-app recomputed":
    comp_raw = comp_in_app
    comp_ra = comp_in_app_ra
    comp_label = "AIBPS (in-app composite)"
else:
    # fall back gracefully if no precomputed
    if precomp_ra is not None:
        comp_ra = precomp_ra
        comp_raw = precomp_raw if precomp_raw is not None else precomp_ra
        comp_label = "AIBPS (precomputed)"
    elif precomp_raw is not None:
        comp_raw = precomp_raw
        comp_ra = precomp_raw.rolling(3, min_periods=1).mean()
        comp_label = "AIBPS (precomputed)"
    else:
        comp_raw = comp_in_app
        comp_ra = comp_in_app_ra
        comp_label = "AIBPS (in-app composite)"

# Assemble plotting frame
comp_df = pd.DataFrame(
    {
        "Composite_raw": comp_raw,
        "Composite_RA": comp_ra,
    }
).dropna()

# Decide which series to show on the main line
if plot_series.startswith("Rolling"):
    comp_df["Composite"] = comp_df["Composite_RA"]
else:
    comp_df["Composite"] = comp_df["Composite_raw"]

# ---------- Top summary ----------
latest_date = comp_df.index.max()
latest_val = comp_df.loc[latest_date, "Composite"]
latest_str = latest_date.strftime("%Y-%m-%d")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Latest reading", f"{latest_val:.1f}")
with col_b:
    st.metric("As of", latest_str)
with col_c:
    st.write(f"Source: {composite_source}")

st.markdown("---")

# ---------- Composite chart with bands + historical event markers ----------

st.subheader("AI Bubble Pressure Score over time")

df_plot = comp_df.reset_index().rename(columns={"index": "date"})

# Regime bands (0–25, 25–50, 50–75, 75–100)
bands_df = pd.DataFrame(
    [
        {"ymin": 0, "ymax": 25, "label": "Low", "color": "#d9f0d3"},
        {"ymin": 25, "ymax": 50, "label": "Elevated", "color": "#ffffbf"},
        {"ymin": 50, "ymax": 75, "label": "High", "color": "#fee090"},
        {"ymin": 75, "ymax": 100, "label": "Extreme", "color": "#fc8d59"},
    ]
)

bands = (
    alt.Chart(bands_df)
    .mark_rect(opacity=0.25)
    .encode(
        y="ymin:Q",
        y2="ymax:Q",
        color=alt.Color("label:N", scale=alt.Scale(
            domain=["Low", "Elevated", "High", "Extreme"],
            range=["#d9f0d3", "#ffffbf", "#fee090", "#fc8d59"],
        ), legend=alt.Legend(title="Regime")),
    )
)

# Main AIBPS line
aibps_line = (
    alt.Chart(df_plot)
    .mark_line(strokeWidth=3)
    .encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("Composite:Q", title="AIBPS (0–100)", scale=alt.Scale(domain=[0, 100])),
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("Composite:Q", title=comp_label, format=".1f"),
        ],
    )
)

# Historical bubble event markers
event_data = pd.DataFrame(
    [
        {"date": pd.Timestamp("2000-03-01"), "label": "Dot-com peak"},
        {"date": pd.Timestamp("2006-07-01"), "label": "US housing peak"},
        {"date": pd.Timestamp("2007-10-01"), "label": "Pre-GFC peak"},
        {"date": pd.Timestamp("2008-09-15"), "label": "Lehman"},
        {"date": pd.Timestamp("2023-03-15"), "label": "AI boom"},
    ]
)

event_rules = (
    alt.Chart(event_data)
    .mark_rule(strokeDash=[4, 4], color="gray")
    .encode(
        x="date:T",
        tooltip=[
            alt.Tooltip("label:N", title="Event"),
            alt.Tooltip("date:T", title="Date"),
        ],
    )
)

event_labels = (
    alt.Chart(event_data)
    .mark_text(align="left", baseline="top", dx=3, dy=3, color="gray", fontSize=11)
    .encode(
        x="date:T",
        y=alt.value(5),
        text="label:N",
    )
)

composite_chart = (
    (bands + aibps_line + event_rules + event_labels)
    .properties(height=420)
    .interactive()
)

st.altair_chart(composite_chart, use_container_width=True)

# ---------- Pillar trajectories (mini-multiples) ----------

st.markdown("### Pillar trajectories")

pillars_long = (
    df[available_pillars]
    .reset_index()
    .melt(id_vars="date", var_name="Pillar", value_name="Value")
    .dropna()
)

pillars_chart = (
    alt.Chart(pillars_long)
    .mark_line()
    .encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("Value:Q", title="Normalized (0–100)", scale=alt.Scale(domain=[0, 100])),
        color="Pillar:N",
        facet=alt.Facet("Pillar:N", columns=3),
    )
    .properties(height=140)
    .resolve_scale(y="shared")
)

st.altair_chart(pillars_chart, use_container_width=True)

# ---------- Weighted contributions at latest date ----------

st.markdown("### Latest pillar contributions")

latest_row = df.loc[latest_date, available_pillars]
contrib = latest_row * weights
contrib_df = pd.DataFrame(
    {"Pillar": contrib.index, "Contribution": contrib.values}
)

contrib_chart = (
    alt.Chart(contrib_df)
    .mark_bar()
    .encode(
        x=alt.X("Contribution:Q", title="Weighted contribution (0–100 scale)"),
        y=alt.Y("Pillar:N", sort="-x"),
        tooltip=[
            alt.Tooltip("Pillar:N", title="Pillar"),
            alt.Tooltip("Contribution:Q", title="Contribution", format=".1f"),
        ],
    )
)

st.altair_chart(contrib_chart, use_container_width=True)

# ---------- Footer ----------
st.markdown("---")
updated_str = df.index.max().strftime("%Y-%m-%d")
st.caption(f"Data through {updated_str}. AIBPS is an experimental composite indicator and may be revised.")
