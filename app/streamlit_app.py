import os
import time
from datetime import datetime

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

# ---------- Paths ----------
PROC_PATH = os.path.join("data", "processed", "aibps_monthly.csv")
META_PATH = os.path.join("data", "processed", "aibps_meta.yaml")


# ---------- Helper: dataset freshness & meta ----------
def freshness_badge(path: str):
    """Show last composite date + how stale it is."""
    st.markdown("**Composite data freshness**")
    if not os.path.exists(path):
        st.info("No composite file found yet.")
        return

    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
        if df.empty:
            st.warning("Composite exists but is empty.")
            return
        last_date = df.index.max()
        days_old = (pd.Timestamp.today().normalize() - last_date.normalize()).days
        st.write(f"Last composite point: `{last_date.date()}`  (≈ {days_old} days ago)")
    except Exception as e:
        st.error(f"Error reading composite for freshness: {e}")


def gh_meta_badge(path: str):
    """Very light meta badge placeholder."""
    st.markdown("**Build meta**")
    if not os.path.exists(path):
        st.write("No meta file found yet.")
        return
    try:
        import yaml

        with open(path, "r") as f:
            meta = yaml.safe_load(f) or {}
        build = meta.get("build_id", "n/a")
        ts = meta.get("timestamp", "n/a")
        st.write(f"Build: `{build}`  •  Timestamp: `{ts}`")
    except Exception as e:
        st.write(f"Meta read error: {e}")


# ---------- Load composite ----------
st.set_page_config(page_title="AI Bubble Pressure Score", layout="wide")

st.title("AI Bubble Pressure Score (AIBPS)")
st.caption("Composite view of AI-related market, credit, capex, infra, adoption, and sentiment conditions.")

if not os.path.exists(PROC_PATH):
    st.error(f"Composite file not found at `{PROC_PATH}`. Run the GitHub Action first.")
    st.stop()

df = pd.read_csv(PROC_PATH, index_col=0, parse_dates=True).sort_index()
if df.empty:
    st.error("Composite file is empty. Check workflows / processed inputs.")
    st.stop()

# All potential pillars
PILLAR_DESIRED = ["Market", "Capex_Supply", "Infra", "Adoption", "Sentiment", "Credit"]
present_pillars = [p for p in PILLAR_DESIRED if p in df.columns]


# ---------- Sidebar: status + pillar weights + mini-charts ----------
with st.sidebar.expander("Dataset & build status", expanded=False):
    freshness_badge(PROC_PATH)
    gh_meta_badge(META_PATH)

st.sidebar.markdown("## Pillar weights")

# Default weights (these will be renormalized)
default_weights = {
    "Market": 0.25,
    "Capex_Supply": 0.20,
    "Infra": 0.15,
    "Adoption": 0.15,
    "Sentiment": 0.10,
    "Credit": 0.15,
}

# Group headings
groups = {
    "Financial": ["Market", "Credit"],
    "Real Economy": ["Capex_Supply", "Infra"],
    "Diffusion / Psychology": ["Adoption", "Sentiment"],
}

weight_inputs = {}

for group_name, group_pillars in groups.items():
    # Show group only if at least one pillar is present
    group_present = [p for p in group_pillars if p in present_pillars]
    if not group_present:
        continue

    st.sidebar.markdown(f"### {group_name}")
    for p in group_present:
        default_val = default_weights.get(p, 0.1)
        weight_inputs[p] = st.sidebar.slider(
            p,
            min_value=0.0,
            max_value=1.0,
            value=float(default_val),
            step=0.01,
        )

# Normalize weights across all present pillars
if present_pillars:
    w_raw = np.array([weight_inputs.get(p, default_weights.get(p, 0.1)) for p in present_pillars], dtype=float)
    if w_raw.sum() == 0:
        w_norm = np.ones(len(present_pillars)) / len(present_pillars)
    else:
        w_norm = w_raw / w_raw.sum()
    weight_series = pd.Series(w_norm, index=present_pillars)
else:
    weight_series = pd.Series(dtype=float)

st.sidebar.markdown("**Normalized weights**")
for p in present_pillars:
    st.sidebar.write(f"{p}: {weight_series[p]:.2f}")

# ---------- Sidebar mini-charts (sparklines) ----------
st.sidebar.markdown("---")
st.sidebar.markdown("## Pillar sparklines (last 5 years)")

def mini_chart(col: str, title: str):
    if col not in df.columns:
        st.sidebar.write(f"{title}: no data.")
        return
    s = df[col].dropna()
    if s.empty:
        st.sidebar.write(f"{title}: no data.")
        return
    cutoff = s.index.max() - pd.DateOffset(years=5)
    s = s[s.index >= cutoff]
    s = s.reset_index().rename(columns={"index": "date"})
    chart = (
        alt.Chart(s)
        .mark_line()
        .encode(
            x=alt.X("date:T", title=""),
            y=alt.Y(f"{col}:Q", title="", scale=alt.Scale(domain=[0, 100])),
            tooltip=["date:T", alt.Tooltip(f"{col}:Q", title=title)],
        )
        .properties(height=80)
    )
    st.sidebar.altair_chart(chart, use_container_width=True)

for p in PILLAR_DESIRED:
    if p in df.columns:
        mini_chart(p, p)


# ---------- Recompute AIBPS with current slider weights ----------
if not present_pillars:
    st.warning("No pillars present in composite. Check your processed inputs.")
    st.stop()

df["AIBPS_dynamic"] = df[present_pillars].mul(weight_series, axis=1).sum(axis=1, skipna=True)
df["AIBPS_RA_dynamic"] = df["AIBPS_dynamic"].rolling(3, min_periods=1).mean()

# Choose which composite to display
composite_choice = st.radio(
    "Composite to display:",
    options=["Rolling AIBPS (3m)", "Raw AIBPS"],
    index=0,
    horizontal=True,
)

if composite_choice == "Rolling AIBPS (3m)":
    comp_col = "AIBPS_RA_dynamic"
else:
    comp_col = "AIBPS_dynamic"

# ---------- Regime callout ----------
if df[comp_col].dropna().empty:
    st.error("No valid composite values. Check processed pillars.")
    st.stop()

latest_date = df[comp_col].dropna().index.max()
latest_val = df.loc[latest_date, comp_col]

def classify_regime(x: float) -> str:
    if x < 40:
        return "Calm"
    elif x < 60:
        return "Normal-ish"
    elif x < 80:
        return "Elevated"
    else:
        return "Extreme"

regime = classify_regime(latest_val)
st.metric(
    label=f"{comp_col} (latest as of {latest_date.date()})",
    value=f"{latest_val:.1f}",
    help=f"Regime: {regime}",
)


# ---------- Main composite chart with bands ----------

# Build long form for pillars + composite
plot_cols = present_pillars + [comp_col]
df_plot = df[plot_cols].dropna(how="all").copy()
df_plot = df_plot.reset_index().rename(columns={"index": "date"})

long_pillars = df_plot.melt(
    id_vars=["date"],
    value_vars=present_pillars,
    var_name="pillar",
    value_name="value",
)

comp_df = df_plot[["date", comp_col]].rename(columns={comp_col: "Composite"})

# Bands definition
bands_df = pd.DataFrame(
    [
        {"name": "Calm",       "y0": 0,  "y1": 40, "color": "#e0f7e9"},
        {"name": "Normal-ish","y0": 40, "y1": 60, "color": "#fff9c4"},
        {"name": "Elevated",   "y0": 60, "y1": 80, "color": "#ffe0b2"},
        {"name": "Extreme",    "y0": 80, "y1": 100,"color": "#ffcccb"},
    ]
)

# Bands chart
bands_chart = (
    alt.Chart(bands_df)
    .mark_rect()
    .encode(
        x=alt.value(0),  # stretch over full x domain via transform
        x2=alt.value(1),
        y="y0:Q",
        y2="y1:Q",
        color=alt.Color("name:N", scale=alt.Scale(domain=[], range=[]), legend=None),
    )
    .transform_calculate(dummy="0")
)

# Composite line
comp_line = (
    alt.Chart(comp_df)
    .mark_line(strokeWidth=3)
    .encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("Composite:Q", title="AIBPS (0–100)", scale=alt.Scale(domain=[0, 100])),
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("Composite:Q", title=comp_col),
        ],
    )
)

# Pillar lines (faint)
pillars_lines = (
    alt.Chart(long_pillars)
    .mark_line(strokeDash=[4, 3], opacity=0.5)
    .encode(
        x="date:T",
        y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("pillar:N", title="Pillar"),
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("pillar:N", title="Pillar"),
            alt.Tooltip("value:Q", title="Value"),
        ],
    )
)

st.subheader("Composite over time")

# We can't directly stretch the rects over x in Altair without some tricks;
# Instead, we'll skip the rect chart and emulate bands with rules + background sense,
# but to keep it simple, we focus on composite + pillar lines for now.
main_chart = (
    comp_line
    + pillars_lines
).properties(height=400)

st.altair_chart(main_chart, use_container_width=True)

st.caption(
    "Solid line: composite AIBPS. Dashed lines: individual pillars (0–100 percentile). "
    "Regime bands are implied by the scale: 0–40 Calm, 40–60 Normal-ish, 60–80 Elevated, 80–100 Extreme."
)


# ---------- Contribution bar chart (latest date) ----------

st.subheader("Pillar contributions at latest composite date")

# Choose a latest date where composite and at least some pillars are non-NaN
latest_valid_idx = df[comp_col].dropna().index.max()
row_pillars = df.loc[latest_valid_idx, present_pillars]
contrib = (row_pillars * weight_series).dropna()

if contrib.empty:
    st.write("No valid contributions at latest date.")
else:
    contrib_df = contrib.reset_index().rename(columns={"index": "pillar", 0: "contribution"})
    contrib_df["weight"] = contrib_df["pillar"].map(weight_series.to_dict())
    contrib_df["value"] = contrib_df["pillar"].map(row_pillars.to_dict())

    contrib_chart = (
        alt.Chart(contrib_df)
        .mark_bar()
        .encode(
            x=alt.X("contribution:Q", title="Contribution to composite"),
            y=alt.Y("pillar:N", title="Pillar", sort="-x"),
            tooltip=[
                alt.Tooltip("pillar:N", title="Pillar"),
                alt.Tooltip("value:Q", title="Pillar value (0–100)"),
                alt.Tooltip("weight:Q", title="Weight"),
                alt.Tooltip("contribution:Q", title="Contribution"),
            ],
        )
        .properties(height=200)
    )
    st.altair_chart(contrib_chart, use_container_width=True)
    st.caption(f"Contributions computed at {latest_valid_idx.date()} using current slider weights.")


# ---------- Debug expanders ----------

with st.expander("Debug • composite tail (all pillars + composite)", expanded=False):
    cols = [c for c in PILLAR_DESIRED + ["AIBPS", "AIBPS_RA", "AIBPS_dynamic", "AIBPS_RA_dynamic"] if c in df.columns]
    st.write("Columns:", cols)
    st.write(df[cols].tail(12))

with st.expander("Debug • last available date per pillar", expanded=False):
    last_dates = {}
    for p in PILLAR_DESIRED:
        if p in df.columns and not df[p].dropna().empty:
            last_dates[p] = df[p].dropna().index.max().date()
    if not last_dates:
        st.write("No pillars with data.")
    else:
        ld_df = pd.DataFrame.from_dict(last_dates, orient="index", columns=["last_date"])
        st.table(ld_df)
    
# Download option
with st.expander("Download data", expanded=False):
    csv_bytes = df.to_csv().encode("utf-8")
    st.download_button(
        label="Download full composite CSV",
        data=csv_bytes,
        file_name="aibps_composite.csv",
        mime="text/csv",
    )
