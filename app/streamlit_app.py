# app/streamlit_app.py
# ============================================================
# AIBPS — Streamlit App (Full Replacement, Single Source of Truth)
# - Pillar-aware weights (only one weights section)
# - Robust composite calc with per-row weight renormalization
# - Composite chart with correct bands (green→yellow→orange→red),
#   horizontal legend, dynamic status badge, and tooltips
# - Weighted contributions bar for latest period
# - Debug expanders for quick sanity checks
# ============================================================

import os, time
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

# ---------- Page config ----------
st.set_page_config(
    page_title="AI Bubble Pressure Score (AIBPS)",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Load processed composite ----------
PROC_PATH = os.path.join("data", "processed", "aibps_monthly.csv")
if not os.path.exists(PROC_PATH):
    st.error("Processed file not found: data/processed/aibps_monthly.csv")
    st.stop()

df = pd.read_csv(PROC_PATH, index_col=0, parse_dates=True).sort_index()

# ---- Sidebar status panel (replaces any top-of-page badges) ----
with st.sidebar.expander("Dataset status", expanded=False):
    freshness_badge(PROC_PATH)
    gh_meta_badge(META_PATH)  # clickable build badge (link to Actions run)


# ---------- Identify pillars present ----------
DESIRED = ["Market", "Capex_Supply", "Infra", "Adoption", "Credit"]
present_pillars = [p for p in DESIRED if p in df.columns]

if not present_pillars:
    st.error("No pillar columns found in processed data. Check your workflow outputs.")
    st.stop()

# ---------- Sidebar: Weights (ONLY HERE) ----------
st.sidebar.title("AIBPS Controls")
st.sidebar.subheader("Weights")
default_w = {"Market":0.25,"Capex_Supply":0.25,"Infra":0.20,"Adoption":0.15,"Credit":0.15}
w_controls = [
    st.sidebar.slider(p, 0.0, 1.0, float(default_w.get(p, 0.2)), 0.05)
    for p in present_pillars
]
base_w = np.array(w_controls, dtype=float)
if base_w.sum() == 0:
    base_w[:] = 1.0  # avoid divide-by-zero; equal weights
# NOTE: We do per-row renormalization later (robust to NaNs / missing pillars)

# ---------- Compute Composite (Robust Weights) ----------
vals = df[present_pillars].copy()

# Build per-row weight matrix aligned to columns
w_series = pd.Series(base_w, index=present_pillars)                  # (P,)
W = pd.DataFrame(np.tile(w_series.values, (len(vals), 1)),           # (N,P)
                 index=vals.index, columns=present_pillars)

# Zero-out weights where data is missing on that row; renormalize per row
mask = vals.notna()
W_eff = W.where(mask, other=0.0)
row_sums = W_eff.sum(axis=1)
W_eff_norm = W_eff.div(row_sums.replace(0, np.nan), axis=0)

# Weighted average per row
df["AIBPS_custom"] = (vals * W_eff_norm).sum(axis=1)
# 3-quarter rolling average
df["AIBPS_RA"] = df["AIBPS_custom"].rolling(3, min_periods=1).mean()

# ---------- Provenance ----------
try:
    mtime = os.path.getmtime(PROC_PATH)
    st.caption(
        f"Data last updated (UTC): {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(mtime))} | "
        f"Pillars present: {', '.join(present_pillars)}"
    )
except Exception:
    pass

# ============================================================
# Composite Chart
# ============================================================
st.subheader("Composite (3-quarter rolling average)")

df_plot = df.reset_index().rename(columns={df.index.name or "index": "Date"})
df_plot["Date"] = pd.to_datetime(df_plot["Date"])
df_plot = df_plot[["Date", "AIBPS_RA"]].dropna()

if df_plot.empty:
    st.warning("No composite data available.")
else:
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2.4])
    with c1: show_bands   = st.checkbox("Show risk bands", value=True)
    with c2: show_rules   = st.checkbox("Show thresholds", value=True)
    with c3: show_points  = st.checkbox("Show points", value=True)
    with c4: band_opacity = st.slider("Band opacity", 0.00, 0.40, 0.18, 0.02)

    ymin, ymax = 0, 100
    start_date = df_plot["Date"].min()
    end_date   = df_plot["Date"].max()

    # Dynamic badge (color matches zone)
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

    # 1) Risk bands (green→yellow→orange→red), legend horizontal at bottom
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
                        title="Risk Zone",
                        orient="bottom",
                        direction="horizontal",
                        symbolSize=120,
                        titleAnchor="middle"
                    )
                )
            )
        )
        layers.append(bands)

    # 2) Main line (always)
    line = (
        alt.Chart(df_plot)
        .mark_line(point=False, strokeWidth=2, color="#e07b39")
        .encode(
            x=alt.X("Date:T", axis=alt.Axis(title="Date")),
            y=alt.Y("AIBPS_RA:Q", scale=alt.Scale(domain=[ymin, ymax]),
                    axis=alt.Axis(title="Composite Score (0–100)")),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                alt.Tooltip("AIBPS_RA:Q", title="AIBPS (3Q RA)", format=".1f")
            ],
        )
    )
    layers.append(line)

    # 3) Optional points
    if show_points:
        points = (
            alt.Chart(df_plot)
            .mark_circle(size=28, color="#e07b39", opacity=0.85)
            .encode(
                x="Date:T", y="AIBPS_RA:Q",
                tooltip=[
                    alt.Tooltip("Date:T", title="Date"),
                    alt.Tooltip("AIBPS_RA:Q", title="AIBPS (3Q RA)", format=".1f")
                ],
            )
        )
        layers.append(points)

    # 4) Optional threshold rules
    if show_rules:
        rules_df = pd.DataFrame({"y": [50, 70, 85]})
        rules = alt.Chart(rules_df).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")
        layers.append(rules)

    chart = alt.layer(*layers).resolve_scale(y="shared").interactive()
    st.altair_chart(chart, use_container_width=True)

# ============================================================
# Weighted Contributions (Latest Period)
# ============================================================
st.subheader("Weighted Contributions — Latest Period")

# Latest date with a composite value
if df["AIBPS_custom"].notna().any():
    latest_idx = df["AIBPS_custom"].last_valid_index()
    latest_row = df.loc[latest_idx, present_pillars]

    # Effective weights on that row (after NaN-aware renorm)
    eff_w_last = W_eff_norm.loc[latest_idx, present_pillars]

    contrib = (latest_row * eff_w_last).rename("Contribution")
    contrib_df = contrib.reset_index().rename(columns={"index":"Pillar"})
    contrib_df["Weight"] = eff_w_last.values
    contrib_df["Value"]  = latest_row.values

    bar = (
        alt.Chart(contrib_df)
        .mark_bar()
        .encode(
            x=alt.X("Pillar:N", sort=present_pillars),
            y=alt.Y("Contribution:Q", title="Weighted contribution"),
            tooltip=[
                alt.Tooltip("Pillar:N"),
                alt.Tooltip("Value:Q", format=".1f"),
                alt.Tooltip("Weight:Q", format=".2f"),
                alt.Tooltip("Contribution:Q", format=".1f"),
            ]
        )
    )
    st.altair_chart(bar, use_container_width=True)
    st.caption(f"Latest period: {latest_idx.date()} — AIBPS (raw) = {df.loc[latest_idx,'AIBPS_custom']:.1f}, "
               f"AIBPS (3Q RA) = {df.loc[latest_idx,'AIBPS_RA']:.1f}")
else:
    st.info("No composite values available to compute contributions.")

# ============================================================
# Debugging / Data peek (optional)
# ============================================================
with st.expander("Debug: last 6 rows & effective weights (last row)"):
    try:
        st.write(df[present_pillars + ["AIBPS_custom", "AIBPS_RA"]].tail(6))
        eff_last = W_eff_norm.tail(1).T
        eff_last.columns = ["effective_weight_last_row"]
        st.write(eff_last)
    except Exception as e:
        st.write(f"(debug failed: {e})")

# ============================================================
# Footer
# ============================================================
st.caption("AIBPS v0.2 — composite recalculates from pillar-aware weights; charts update live from processed CSVs.")
