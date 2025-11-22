import os

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

# ---------- Paths & constants ----------
PROC_PATH = os.path.join("data", "processed", "aibps_monthly.csv")

# The pillars we conceptually care about
PILLAR_CANDIDATES = [
    "Market",
    "Credit",
    "Capex_Supply",
    "Infra",
    "Adoption",
    "Sentiment",
]

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

# Force all visualizations to start from 1980
MIN_DATE = pd.Timestamp("1980-01-01")
df = df[df.index >= MIN_DATE]
if df.empty:
    st.error("No composite data available from 1980 onward.")
    st.stop()


df.index.name = "date"

# Figure out which of our six conceptual pillars actually exist
available_pillars = [p for p in PILLAR_CANDIDATES if p in df.columns]

if not available_pillars:
    st.error("None of the expected pillars are present in the composite file.")
    st.stop()

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

pillars_df = df[available_pillars].copy()

# In-app composite from pillar weights
comp_in_app_raw = (pillars_df * weights).sum(axis=1)
comp_in_app_ra = comp_in_app_raw.rolling(3, min_periods=1).mean()

# Precomputed composite from CSV (if present)
precomp_raw = df["AIBPS"] if "AIBPS" in df.columns else None
precomp_ra = df["AIBPS_RA"] if "AIBPS_RA" in df.columns else None

if composite_source == "In-app recomputed":
    comp_raw = comp_in_app_raw
    comp_ra = comp_in_app_ra
    comp_label = "AIBPS (in-app composite)"
else:
    if precomp_ra is not None:
        comp_ra = precomp_ra
        comp_raw = precomp_raw if precomp_raw is not None else precomp_ra
        comp_label = "AIBPS (precomputed)"
    elif precomp_raw is not None:
        comp_raw = precomp_raw
        comp_ra = precomp_raw.rolling(3, min_periods=1).mean()
        comp_label = "AIBPS (precomputed)"
    else:
        comp_raw = comp_in_app_raw
        comp_ra = comp_in_app_ra
        comp_label = "AIBPS (in-app composite)"

comp_df = pd.DataFrame(
    {
        "Composite_raw": comp_raw,
        "Composite_RA": comp_ra,
    }
).dropna(how="all")

if comp_df.empty:
    st.error("Composite series is empty after combining. Check inputs.")
    st.stop()

if plot_series.startswith("Rolling"):
    comp_df["Composite"] = comp_df["Composite_RA"]
else:
    comp_df["Composite"] = comp_df["Composite_raw"]

# ---------- Top summary ----------
latest_comp_date = comp_df.index.max()
latest_val = comp_df.loc[latest_comp_date, "Composite"]
latest_str = latest_comp_date.strftime("%Y-%m-%d")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Latest reading", f"{latest_val:.1f}")
with col_b:
    st.metric("As of", latest_str)
with col_c:
    st.write(f"Source: {composite_source}")

st.markdown("---")

# ---------- Composite chart: bands + regime lines + bubble markers ----------

st.subheader("AI Bubble Pressure Score over time")

df_plot = comp_df.reset_index().rename(columns={"index": "date"})

x_min = df_plot["date"].min()
x_max = df_plot["date"].max()

bands_df = pd.DataFrame(
    [
        {"date_start": x_min, "date_end": x_max, "ymin": 0, "ymax": 25, "label": "Low"},
        {"date_start": x_min, "date_end": x_max, "ymin": 25, "ymax": 50, "label": "Elevated"},
        {"date_start": x_min, "date_end": x_max, "ymin": 50, "ymax": 75, "label": "High"},
        {"date_start": x_min, "date_end": x_max, "ymin": 75, "ymax": 100, "label": "Extreme"},
    ]
)

band_colors = {
    "Low": "#d9f0d3",
    "Elevated": "#ffffbf",
    "High": "#fee090",
    "Extreme": "#fc8d59",
}

bands = (
    alt.Chart(bands_df)
    .mark_rect(opacity=0.35)
    .encode(
        x=alt.X("date_start:T", title="Date"),
        x2="date_end:T",
        y="ymin:Q",
        y2="ymax:Q",
        color=alt.Color(
            "label:N",
            scale=alt.Scale(
                domain=list(band_colors.keys()),
                range=list(band_colors.values()),
            ),
            legend=alt.Legend(title="Regime"),
        ),
    )
)

# Horizontal regime threshold lines at 25/50/75
thresholds_df = pd.DataFrame({"y": [25, 50, 75]})

regime_rules = (
    alt.Chart(thresholds_df)
    .mark_rule(strokeDash=[3, 3], color="black", opacity=0.5)
    .encode(
        y="y:Q",
    )
)

aibps_line = (
    alt.Chart(df_plot)
    .mark_line(strokeWidth=3)
    .encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(
            "Composite:Q",
            title="AIBPS (0–100)",
            scale=alt.Scale(domain=[0, 100]),
        ),
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("Composite:Q", title=comp_label, format=".1f"),
        ],
    )
)

event_data = pd.DataFrame(
    [
        {"date": pd.Timestamp("2000-03-01"), "label": "Dot-com peak", "ypos": 12},
        {"date": pd.Timestamp("2006-07-01"), "label": "US housing peak", "ypos": 26},
        {"date": pd.Timestamp("2007-10-01"), "label": "Pre-GFC peak", "ypos": 40},
        {"date": pd.Timestamp("2008-09-15"), "label": "Lehman", "ypos": 54},
        {"date": pd.Timestamp("2023-03-15"), "label": "AI boom", "ypos": 68},
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
    .mark_text(
        align="left",
        baseline="middle",
        dx=5,
        dy=0,
        color="gray",
        fontSize=11,
    )
    .encode(
        x="date:T",
        y=alt.Y("ypos:Q", scale=alt.Scale(domain=[0, 100])),
        text="label:N",
    )
)

composite_chart = (
    (bands + regime_rules + aibps_line + event_rules + event_labels)
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
    .dropna(subset=["Value"])
)

if pillars_long.empty:
    st.info("No non-missing pillar data to plot.")
else:
    pillars_chart = (
        alt.Chart(pillars_long)
        .mark_line()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y(
                "Value:Q",
                title="Normalized (0–100)",
                scale=alt.Scale(domain=[0, 100]),
            ),
            color="Pillar:N",
            facet=alt.Facet("Pillar:N", columns=3),
        )
        .properties(height=140)
        .resolve_scale(y="shared")
    )

    st.altair_chart(pillars_chart, use_container_width=True)

import os  # ensure this is at the top of the file once, not repeated

# --- Capex supply trajectory from macro_capex_processed (raw index) ---

st.subheader("Capex supply trajectory (raw index, baseline = 100)")

macro_capex_path = "data/processed/macro_capex_processed.csv"

if not os.path.exists(macro_capex_path):
    st.info(f"`{macro_capex_path}` not found. Run the update-data workflow first.")
else:
    try:
        capex_df = (
            pd.read_csv(macro_capex_path, parse_dates=["Date"])
            .set_index("Date")
            .sort_index()
        )
    except Exception as e:
        st.error(f"Failed to read `{macro_capex_path}`: {e}")
        capex_df = None

    if capex_df is not None and not capex_df.empty:
        # Prefer Capex_Supply if present, otherwise fall back to a macro composite
        capex_col = None
        for candidate in ["Capex_Supply", "Capex_Macro_Comp"]:
            if candidate in capex_df.columns:
                capex_col = candidate
                break

        if capex_col is None:
            st.info("No Capex_Supply or Capex_Macro_Comp column found in macro_capex_processed.csv.")
        else:
            capex_series = capex_df[capex_col].dropna()
            if capex_series.empty:
                st.info(f"{capex_col} has no valid values.")
            else:
                capex_vis = (
                    capex_series.reset_index(name="Value")
                    .rename(columns={"Date": "date"})
                )

                capex_line = (
                    alt.Chart(capex_vis)
                    .mark_line()
                    .encode(
                        x=alt.X("date:T", title="Date"),
                        y=alt.Y("Value:Q", title="Capex index (baseline = 100)"),
                        tooltip=[
                            alt.Tooltip("date:T", title="Date"),
                            alt.Tooltip("Value:Q", title="Index", format=".1f"),
                        ],
                    )
                    .properties(
                        height=260,
                        title=f"{capex_col} over time (raw capex index from macro_capex_processed.csv)",
                    )
                )

                st.altair_chart(capex_line, use_container_width=True)

                # Quick numeric tail for sanity
                st.caption("Latest 12 observations for capex index")
                st.dataframe(capex_series.tail(12))
    else:
        st.info("macro_capex_processed.csv is empty.")


# ---------- Latest pillar contributions ----------

st.markdown("### Latest pillar contributions")

valid_rows = df[available_pillars].dropna(how="all")
if valid_rows.empty:
    st.info("No rows with pillar data found for contributions.")
else:
    # Last date where at least 2 pillars have data
    mask_at_least_two = valid_rows.notna().sum(axis=1) >= 2
    if not mask_at_least_two.any():
        st.info("Not enough non-missing pillars at any date to compute contributions.")
    else:
        contrib_date = valid_rows.index[mask_at_least_two].max()
        latest_row = df.loc[contrib_date, available_pillars]

        contrib = latest_row * weights.reindex(available_pillars)
        contrib = contrib.dropna()

        contrib_df = pd.DataFrame(
            {"Pillar": contrib.index, "Contribution": contrib.values}
        )

        st.caption(f"Contributions as of {contrib_date.strftime('%Y-%m-%d')}")

        contrib_chart = (
            alt.Chart(contrib_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Contribution:Q",
                    title="Weighted contribution (0–100 scale)",
                ),
                y=alt.Y("Pillar:N", sort="-x"),
                tooltip=[
                    alt.Tooltip("Pillar:N", title="Pillar"),
                    alt.Tooltip("Contribution:Q", title="Contribution", format=".1f"),
                ],
            )
        )

        st.altair_chart(contrib_chart, use_container_width=True)

# ---------- Pillar-by-pillar debug: Market ----------

st.markdown("### Pillar debug")

with st.expander("Market pillar debug"):
    mkt_path = os.path.join("data", "processed", "market_processed.csv")
    if not os.path.exists(mkt_path):
        st.info("market_processed.csv not found. Run the update-data workflow first.")
    else:
        mkt = pd.read_csv(mkt_path, index_col=0, parse_dates=True).sort_index()
        mkt.index.name = "date"

        # Identify component columns (everything except the main Market composite)
        comp_cols = [c for c in mkt.columns if c.startswith("Mkt_")]
        show_cols = ["Market"] + comp_cols if "Market" in mkt.columns else comp_cols

        if not show_cols:
            st.info("No Market component series found to debug.")
        else:
            # Melt to long format for Altair
            mkt_long = (
                mkt[show_cols]
                .reset_index()
                .melt(id_vars="date", var_name="Series", value_name="Value")
                .dropna(subset=["Value"])
            )

            st.write("Underlying Market components (rebased to 100 at first valid point):")

            mkt_chart = (
                alt.Chart(mkt_long)
                .mark_line()
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("Value:Q", title="Index (rebased to 100)"),
                    color="Series:N",
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("Series:N", title="Series"),
                        alt.Tooltip("Value:Q", title="Value", format=".1f"),
                    ],
                )
                .properties(height=260)
                .interactive()
            )

            st.altair_chart(mkt_chart, use_container_width=True)

            st.write("Tail of market_processed.csv:")
            st.dataframe(mkt.tail(10))

# ---------- Pillar-by-pillar debug: Credit ----------

with st.expander("Credit pillar debug"):
    credit_path = os.path.join("data", "processed", "credit_fred_processed.csv")
    if not os.path.exists(credit_path):
        st.info("credit_fred_processed.csv not found. Run the update-data workflow first.")
    else:
        credit = pd.read_csv(credit_path, index_col=0, parse_dates=True).sort_index()
        credit.index.name = "date"

        st.write("Underlying credit series (FRED):")
        st.dataframe(credit.tail(10))

        # Long format for Altair
        credit_long = (
            credit.reset_index()
            .melt(id_vars="date", var_name="Series", value_name="Value")
            .dropna(subset=["Value"])
        )

        credit_chart = (
            alt.Chart(credit_long)
            .mark_line()
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("Value:Q", title="Level (native units)"),
                color="Series:N",
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("Series:N", title="Series"),
                    alt.Tooltip("Value:Q", title="Value", format=".2f"),
                ],
            )
            .properties(height=260)
            .interactive()
        )

        st.altair_chart(credit_chart, use_container_width=True)

# ---------- Pillar-by-pillar debug: Capex ----------

# -----------------------------
# CAPEX / SUPPLY PILLAR DEBUG
# -----------------------------



with st.expander("Capex pillar debug", expanded=False):
    st.markdown("### Capex subcomponents (diagnostic view)")

    macro_capex_path = "data/processed/macro_capex_processed.csv"

    if not os.path.exists(macro_capex_path):
        st.warning(f"`{macro_capex_path}` not found. Run the update-data workflow first.")
    else:
        try:
            capex_df = (
                pd.read_csv(macro_capex_path, parse_dates=["Date"])
                .set_index("Date")
                .sort_index()
            )
        except Exception as e:
            st.error(f"Failed to read `{macro_capex_path}`: {e}")
            capex_df = None

        if capex_df is None or capex_df.empty:
            st.info("macro_capex_processed.csv is empty.")
        else:
            # 1) Identify all Capex-related columns in the macro capex file
            capex_cols = [c for c in capex_df.columns if c.startswith("Capex_")]
            if not capex_cols:
                st.info("No Capex_* columns found in macro_capex_processed.csv.")
            else:
                # 2) Let user choose which components to visualize
                default_selection = [c for c in capex_cols if c != "Capex_Supply"] or capex_cols
                selected_cols = st.multiselect(
                    "Select Capex components to display",
                    options=capex_cols,
                    default=default_selection,
                    help=(
                        "Includes Capex_Macro_Comp, Capex_Semi_Activity, Capex_IT_Equip, "
                        "Capex_Constr, Capex_Hyperscaler, Capex_Fab_Index, "
                        "Capex_DC_Cost_Index, Capex_Supply (composite)."
                    ),
                )

                if not selected_cols:
                    st.warning("Select at least one Capex component to view.")
                else:
                    # 3) Show raw tail (true index values, baseline ~100 but can go >>100)
                    st.markdown("**Latest 12 months — raw capex indices (baseline ≈ 100)**")
                    st.dataframe(capex_df[selected_cols].tail(12))

                    # 4) Build visually normalized copy (0–100 per component) for charts
                    vis_df = capex_df[selected_cols].copy()
                    for col in vis_df.columns:
                        col_min = vis_df[col].min()
                        col_max = vis_df[col].max()
                        if pd.isna(col_min) or pd.isna(col_max) or col_min == col_max:
                            # If no variation, park it at midline so it's visible but flat
                            vis_df[col] = 50.0
                        else:
                            vis_df[col] = 100.0 * (vis_df[col] - col_min) / (col_max - col_min)

                    # 5) Time-series chart (visually normalized 0–100 so all lines "alive")
                    vis_long = (
                        vis_df
                        .reset_index(names="date")
                        .melt(id_vars="date", var_name="Component", value_name="Value")
                    )

                    capex_ts = (
                        alt.Chart(vis_long)
                        .mark_line()
                        .encode(
                            x=alt.X("date:T", title="Date"),
                            y=alt.Y(
                                "Value:Q",
                                title="Visual index (0–100 per component)",
                                scale=alt.Scale(domain=[0, 100]),
                            ),
                            color=alt.Color("Component:N", title="Capex Component"),
                            tooltip=[
                                alt.Tooltip("date:T", title="Date"),
                                alt.Tooltip("Component:N", title="Component"),
                                alt.Tooltip(
                                    "Value:Q",
                                    title="Visual index (0–100)",
                                    format=".1f"
                                ),
                            ],
                        )
                        .properties(
                            height=260,
                            title="Capex components over time (visually normalized per series)",
                        )
                    )
                    st.altair_chart(capex_ts, use_container_width=True)

                    # 6) Current-date contribution snapshot (visually normalized bar)
                    latest_idx = vis_df.dropna(how="all").index.max()
                    if pd.isna(latest_idx):
                        st.info("No valid recent data to compute current Capex contributions.")
                    else:
                        latest_vis = vis_df.loc[latest_idx, selected_cols].dropna()
                        if latest_vis.empty:
                            st.info("Latest row has no non-missing Capex values (visual).")
                        else:
                            contrib_df = (
                                latest_vis.reset_index()
                                .rename(columns={"index": "Component", latest_idx: "Value"})
                            )
                            contrib_df["Component"] = contrib_df["Component"].astype(str)

                            st.markdown(
                                f"**Current Capex contributions (visual scale)** "
                                f"(as of `{latest_idx.date()}`, 0–100 per component)"
                            )

                            capex_bar = (
                                alt.Chart(contrib_df)
                                .mark_bar()
                                .encode(
                                    x=alt.X(
                                        "Component:N",
                                        title="Capex Component",
                                        sort="-y",
                                    ),
                                    y=alt.Y(
                                        "Value:Q",
                                        title="Visual index (0–100)",
                                        scale=alt.Scale(domain=[0, 100]),
                                    ),
                                    tooltip=[
                                        alt.Tooltip("Component:N", title="Component"),
                                        alt.Tooltip(
                                            "Value:Q",
                                            title="Visual index (0–100)",
                                            format=".1f",
                                        ),
                                    ],
                                )
                                .properties(height=260)
                            )

                            st.altair_chart(capex_bar, use_container_width=True)

                            top_comp = contrib_df.sort_values("Value", ascending=False).iloc[0]
                            st.caption(
                                "Visual-only: each component is rescaled to 0–100 over its own history. "
                                f"At the latest date, the relatively strongest component (within this visual scale) "
                                f"is **{top_comp['Component']}** (~{top_comp['Value']:.1f}/100)."
                            )


# -----------------------------
# INFRASTRUCTURE PILLAR DEBUG
# -----------------------------
with st.expander("Infrastructure (Infra) Pillar Debug"):
    infra_candidates = [
        os.path.join("data", "processed", "infra_processed.csv"),
        os.path.join("data", "processed", "infra_macro_processed.csv"),
    ]

    infra_path = None
    for p in infra_candidates:
        if os.path.exists(p):
            infra_path = p
            break

    if infra_path is None:
        st.info("No infra_processed.csv or infra_macro_processed.csv found.")
    else:
        st.write(f"Using file: `{infra_path}`")

        infra = pd.read_csv(infra_path, index_col=0, parse_dates=True).sort_index()
        infra.index.name = "date"

        st.write("Tail of Infra processed data:")
        st.dataframe(infra.tail(10))

        # Identify columns related to Infra
        infra_cols = [c for c in infra.columns if "Infra" in c]

        # Fallback: plot all numeric columns
        if not infra_cols:
            infra_cols = infra.select_dtypes(include="number").columns.tolist()

        if infra_cols:
            infra_long = (
                infra[infra_cols]
                .reset_index()
                .melt(id_vars="date", var_name="Series", value_name="Value")
                .dropna(subset=["Value"])
            )

            infra_chart = (
                alt.Chart(infra_long)
                .mark_line()
                .encode(
                    x="date:T",
                    y="Value:Q",
                    color="Series:N",
                    tooltip=["date:T", "Series:N", "Value:Q"]
                )
                .properties(height=260)
                .interactive()
            )

            st.altair_chart(infra_chart, use_container_width=True)
        else:
            st.info("No numeric Infra columns to plot.")

# -----------------------------
# ADOPTION PILLAR DEBUG
# -----------------------------
with st.expander("Adoption Pillar Debug"):
    adoption_candidates = [
        os.path.join("data", "processed", "adoption_processed.csv"),
        os.path.join("data", "processed", "adoption_macro_processed.csv"),
    ]

    adoption_path = None
    for p in adoption_candidates:
        if os.path.exists(p):
            adoption_path = p
            break

    if adoption_path is None:
        st.info("No adoption_processed.csv or adoption_macro_processed.csv found.")
    else:
        st.write(f"Using file: `{adoption_path}`")

        ad = pd.read_csv(adoption_path, index_col=0, parse_dates=True).sort_index()
        ad.index.name = "date"

        st.write("Tail of Adoption processed data:")
        st.dataframe(ad.tail(10))

        # Try to identify adoption-related columns
        ad_cols = [c for c in ad.columns if "Adoption" in c or c.lower().startswith("adopt")]
        if not ad_cols:
            ad_cols = ad.select_dtypes(include="number").columns.tolist()

        if ad_cols:
            ad_long = (
                ad[ad_cols]
                .reset_index()
                .melt(id_vars="date", var_name="Series", value_name="Value")
                .dropna(subset=["Value"])
            )

            ad_chart = (
                alt.Chart(ad_long)
                .mark_line()
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("Value:Q", title="Value (mixed units / indexes)"),
                    color="Series:N",
                    tooltip=["date:T", "Series:N", "Value:Q"],
                )
                .properties(height=260)
                .interactive()
            )

            st.altair_chart(ad_chart, use_container_width=True)
        else:
            st.info("No numeric Adoption columns to plot.")

# -----------------------------
# SENTIMENT PILLAR DEBUG
# -----------------------------
with st.expander("Sentiment Pillar Debug"):
    sentiment_candidates = [
        os.path.join("data", "processed", "sentiment_processed.csv"),
        os.path.join("data", "processed", "sentiment_trends_processed.csv"),
    ]

    sentiment_path = None
    for p in sentiment_candidates:
        if os.path.exists(p):
            sentiment_path = p
            break

    if sentiment_path is None:
        st.info("No sentiment_processed.csv or sentiment_trends_processed.csv found.")
    else:
        st.write(f"Using file: `{sentiment_path}`")

        sent = pd.read_csv(sentiment_path, index_col=0, parse_dates=True).sort_index()
        sent.index.name = "date"

        st.write("Tail of Sentiment processed data:")
        st.dataframe(sent.tail(10))

        # Try to identify sentiment-related columns
        sent_cols = [c for c in sent.columns if "Sentiment" in c or "Hype" in c]
        if not sent_cols:
            sent_cols = sent.select_dtypes(include="number").columns.tolist()

        if sent_cols:
            sent_long = (
                sent[sent_cols]
                .reset_index()
                .melt(id_vars="date", var_name="Series", value_name="Value")
                .dropna(subset=["Value"])
            )

            sent_chart = (
                alt.Chart(sent_long)
                .mark_line()
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("Value:Q", title="Value (mixed units / indexes)"),
                    color="Series:N",
                    tooltip=["date:T", "Series:N", "Value:Q"],
                )
                .properties(height=260)
                .interactive()
            )

            st.altair_chart(sent_chart, use_container_width=True)
        else:
            st.info("No numeric Sentiment columns to plot.")



# ---------- Footer ----------
st.markdown("---")
updated_str = df.index.max().strftime("%Y-%m-%d")
st.caption(f"Data through {updated_str}. AIBPS is an experimental composite indicator and may be revised.")
