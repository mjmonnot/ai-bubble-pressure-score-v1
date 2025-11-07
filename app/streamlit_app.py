# =========================
# AIBPS COMPOSITE PANEL — SINGLE SOURCE OF TRUTH
# Paste this block once into app/streamlit_app.py and REMOVE any other "Weights" code.
# =========================
import numpy as np
import pandas as pd
import altair as alt
import os, time
import streamlit as st

# ---- Load processed composite once (use existing df if already loaded above) ----
try:
    df  # type: ignore # if df already exists, keep it
except NameError:
    PROC_PATH = os.path.join("data", "processed", "aibps_monthly.csv")
    if not os.path.exists(PROC_PATH):
        st.error("Processed file not found: data/processed/aibps_monthly.csv")
        st.stop()
    df = pd.read_csv(PROC_PATH, index_col=0, parse_dates=True)

# ---- Pillars present & single weights section (keep only this) ----
DESIRED = ["Market", "Capex_Supply", "Infra", "Adoption", "Credit"]
present_pillars = [p for p in DESIRED if p in df.columns]

if not present_pillars:
    st.error("No pillar columns found in processed data. Check your workflow outputs.")
    st.stop()

st.sidebar.subheader("Weights")  # ← the ONLY weights UI in the entire app
default_w = {"Market":0.25,"Capex_Supply":0.25,"Infra":0.20,"Adoption":0.15,"Credit":0.15}
w_controls = [
    st.sidebar.slider(p, 0.0, 1.0, float(default_w.get(p, 0.2)), 0.05)
    for p in present_pillars
]
weights = np.array(w_controls, dtype=float)
weights = np.ones_like(weights) if weights.sum() == 0 else weights / weights.sum()

# ---- Compute custom composite & 3Q rolling average ----
df = df.sort_index()
df["AIBPS_custom"] = (df[present_pillars] * weights).sum(axis=1)
df["AIBPS_RA"] = df["AIBPS_custom"].rolling(3, min_periods=1).mean()

# ---- Provenance (optional but helpful) ----
try:
    mtime = os.path.getmtime(os.path.join("data","processed","aibps_monthly.csv"))
    st.caption(f"Data last updated (UTC): {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(mtime))} | "
               f"Pillars: {', '.join(present_pillars)}")
except Exception:
    pass

# ---- Composite chart (bands fixed: green→yellow→orange→red, horizontal legend) ----
st.subheader("Composite (3-quarter rolling average)")
df_plot = df.reset_index().rename(columns={df.index.name or "index": "Date"})
df_plot["Date"] = pd.to_datetime(df_plot["Date"])
df_plot = df_plot[["Date", "AIBPS_RA"]].dropna()

if df_plot.empty:
    st.warning("No composite data available.")
else:
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2.4])
    with c1: show_bands  = st.checkbox("Show risk bands", value=True)
    with c2: show_rules  = st.checkbox("Show thresholds", value=True)
    with c3: show_points = st.checkbox("Show points", value=True)
    with c4: band_opacity = st.slider("Band opacity", 0.00, 0.40, 0.18, 0.02)

    ymin, ymax = 0, 100
    start_date = df_plot["Date"].min()
    end_date   = df_plot["Date"].max()

    # Badge that matches zone color
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

    # 1) Optional risk bands (draw first so they stay behind)
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
                x="Date:T",
                y="AIBPS_RA:Q",
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
