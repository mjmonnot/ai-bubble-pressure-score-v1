import os

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

# ---------- Paths & constants ----------
PROC_PATH = os.path.join("data", "processed", "aibps_monthly.csv")

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

MIN_DATE = pd.Timestamp("1980-01-01")
df = df[df.index >= MIN_DATE]

if df.empty:
    st.error("No composite data available from 1980 onward.")
    st.stop()

df.index.name = "date"

available_pillars = [p for p in PILLAR_CANDIDATES if p in df.columns]

if not available_pillars:
    st.error("None of the expected pillars are present in the composite file.")
    st.stop()

# ---------- Sidebar ----------
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

# ---------- Prepare composite ----------
# Match compute.py: ≥2 pillars historically; ≥5 only on the live edge
MIN_PILLARS_HISTORICAL = 2
MIN_PILLARS_LIVE_EDGE = 5
LIVE_EDGE_MONTHS = 4

pillars_df = df[available_pillars].copy()
pillars_reporting = pillars_df.notna().sum(axis=1)

end_m = pd.Timestamp(pillars_df.index.max()).to_period("M").to_timestamp("M")
live_start = (end_m.to_period("M") - (LIVE_EDGE_MONTHS - 1)).to_timestamp("M")
min_required = pd.Series(MIN_PILLARS_HISTORICAL, index=pillars_df.index, dtype=int)
min_required.loc[pillars_df.index >= live_start] = MIN_PILLARS_LIVE_EDGE
publish_mask = pillars_reporting >= min_required

# Renormalize slider weights over available pillars, then apply live-edge freeze
w_matrix = pd.DataFrame(
    {p: float(weights[p]) for p in available_pillars},
    index=pillars_df.index,
)
w_eff = w_matrix.where(pillars_df.notna())
w_sum = w_eff.sum(axis=1).replace(0, np.nan)
comp_in_app_raw = (pillars_df * w_eff).sum(axis=1, skipna=True) / w_sum
comp_in_app_raw = comp_in_app_raw.where(publish_mask)
comp_in_app_ra = comp_in_app_raw.rolling(6, min_periods=1).mean()
comp_in_app_ra = comp_in_app_ra.where(publish_mask)

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

# Drop blank composite points so the chart domain matches the visible series
comp_df = comp_df.dropna(subset=["Composite"])

if comp_df.empty:
    st.error("Composite series is empty after applying the publication rule.")
    st.stop()

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

latest_raw_date = df.index.max()
latest_raw_n = int(pillars_reporting.loc[latest_raw_date]) if latest_raw_date in pillars_reporting.index else 0
if latest_raw_date > latest_comp_date and latest_raw_n < MIN_PILLARS_LIVE_EDGE:
    st.caption(
        f"Live edge frozen: newest month {latest_raw_date.strftime('%Y-%m')} has "
        f"{latest_raw_n}/6 pillars (need ≥{MIN_PILLARS_LIVE_EDGE} in the last "
        f"{LIVE_EDGE_MONTHS} months). Historical series still uses ≥{MIN_PILLARS_HISTORICAL} "
        f"pillars (see docs/methods.md)."
    )

st.markdown("---")

# ---------- Composite chart ----------
st.subheader("AI Bubble Pressure Score over time")

df_plot = comp_df.reset_index().rename(columns={"index": "date"})

x_min = df_plot["date"].min()
x_max = df_plot["date"].max()

bands_df = pd.DataFrame(
    [
        {"date_start": x_min, "date_end": x_max, "ymin": 0, "ymax": 25, "label": "Cold"},
        {"date_start": x_min, "date_end": x_max, "ymin": 25, "ymax": 50, "label": "Stable"},
        {"date_start": x_min, "date_end": x_max, "ymin": 50, "ymax": 75, "label": "Elevated"},
        {"date_start": x_min, "date_end": x_max, "ymin": 75, "ymax": 90, "label": "Stretched"},
        {"date_start": x_min, "date_end": x_max, "ymin": 90, "ymax": 100, "label": "Bubble"},
    ]
)

band_colors = {
    "Cold": "#d9f0d3",
    "Stable": "#e8f5e9",
    "Elevated": "#ffffbf",
    "Stretched": "#fee090",
    "Bubble": "#fc8d59",
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

thresholds_df = pd.DataFrame({"y": [25, 50, 75, 90]})

regime_rules = (
    alt.Chart(thresholds_df)
    .mark_rule(strokeDash=[3, 3], color="black", opacity=0.5)
    .encode(y="y:Q")
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
# Keep event markers inside the composite span so they do not pad empty years
event_data = event_data[
    (event_data["date"] >= x_min) & (event_data["date"] <= x_max)
]

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
    bands + regime_rules + aibps_line + event_rules + event_labels
).properties(height=420).interactive()

st.altair_chart(composite_chart, use_container_width=True)

# ---------- Pillar trajectories ----------
st.subheader("Pillar trajectories")

available_cols = list(df.columns)

pillar_map = {
    "Market": "Market",
    "Capex_Supply": "Capex / Supply",
    "Infra": "Infrastructure",
    "Adoption": "Adoption",
    "Sentiment": "Sentiment",
    "Credit": "Credit",
}

plot_cols = [col for col in pillar_map.keys() if col in available_cols]

if not plot_cols:
    st.info("No pillar columns found to plot trajectories.")
else:
    traj_df = (
        df[plot_cols]
        .reset_index(names="date")
        .melt(id_vars="date", var_name="Pillar", value_name="Value")
    )

    traj_df["Pillar"] = traj_df["Pillar"].map(pillar_map)

    traj_chart = (
        alt.Chart(traj_df)
        .mark_line()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y(
                "Value:Q",
                title="Pillar score (0–100, normalized)",
                scale=alt.Scale(domain=[0, 100]),
            ),
            color=alt.Color("Pillar:N", title="Pillar"),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("Pillar:N", title="Pillar"),
                alt.Tooltip("Value:Q", title="Score", format=".1f"),
            ],
        )
        .properties(height=280)
    )

    st.altair_chart(traj_chart, use_container_width=True)

# ---------- Pillar debug ----------
st.markdown("### Pillar debug")

# ---------- Market pillar debug ----------
with st.expander("Market pillar debug"):
    mkt_path = os.path.join("data", "processed", "market_processed.csv")

    if not os.path.exists(mkt_path):
        st.info("market_processed.csv not found. Run the update-data workflow first.")
    else:
        mkt = pd.read_csv(mkt_path, index_col=0, parse_dates=True).sort_index()
        mkt.index.name = "date"

        numeric_cols = mkt.select_dtypes(include="number").columns.tolist()

        preferred_candidates = [
            "SP500",
            "NASDAQ",
            "QQQ",
            "VIX",
            "NVDA",
            "BTC",
            "market_component_composite_z",
        ]

        show_cols = [c for c in preferred_candidates if c in numeric_cols]

        if not show_cols:
            st.info("No Market component series found to debug.")
            with st.expander("Available market_processed.csv columns"):
                st.write(list(mkt.columns))
        else:
            label_map = {
                "SP500": "S&P 500",
                "NASDAQ": "NASDAQ",
                "QQQ": "QQQ",
                "VIX": "VIX",
                "NVDA": "NVIDIA",
                "BTC": "Bitcoin",
                "market_component_composite_z": "Composite Market Pressure",
            }

            summary_labels = [label_map.get(c, c) for c in show_cols]
            st.caption("Market components detected: " + ", ".join(summary_labels))

            plot_df = mkt[show_cols].copy()

            # Visual-only normalization:
            # each series gets its own 0–100 scale so NVDA does not swamp the others.
            vis_df = plot_df.copy()

            for col in vis_df.columns:
                col_min = vis_df[col].min(skipna=True)
                col_max = vis_df[col].max(skipna=True)

                if pd.isna(col_min) or pd.isna(col_max) or col_min == col_max:
                    vis_df[col] = np.nan
                else:
                    vis_df[col] = 100.0 * (vis_df[col] - col_min) / (col_max - col_min)

            vis_long = (
                vis_df
                .reset_index()
                .melt(id_vars="date", var_name="Series", value_name="Value")
                .dropna(subset=["Value"])
            )

            vis_long["Series"] = vis_long["Series"].map(lambda x: label_map.get(x, x))

            st.write("Market components, visually normalized to 0–100 per series:")

            mkt_chart = (
                alt.Chart(vis_long)
                .mark_line()
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y(
                        "Value:Q",
                        title="Visual index (0–100 per series)",
                        scale=alt.Scale(domain=[0, 100]),
                    ),
                    color=alt.Color("Series:N", title="Market Component"),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("Series:N", title="Series"),
                        alt.Tooltip("Value:Q", title="Visual index", format=".1f"),
                    ],
                )
                .properties(height=300)
                .interactive()
            )

            st.altair_chart(mkt_chart, use_container_width=True)

            st.caption(
                "Visual-only: each market component is independently rescaled to 0–100 "
                "over its available history. This prevents high-growth series such as NVIDIA "
                "from visually flattening broader indexes like NASDAQ, QQQ, or S&P 500."
            )

            with st.expander("Raw market_processed.csv tail"):
                st.dataframe(mkt.tail(10))

# ---------- Credit pillar debug ----------
with st.expander("Credit pillar debug"):
    credit_path = os.path.join("data", "processed", "credit_fred_processed.csv")

    if not os.path.exists(credit_path):
        st.info("credit_fred_processed.csv not found. Run the update-data workflow first.")
    else:
        credit = pd.read_csv(credit_path, index_col=0, parse_dates=True).sort_index()
        credit.index.name = "date"

        st.write("Underlying credit series (FRED):")
        st.dataframe(credit.tail(10))

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

# ---------- Capex pillar debug ----------
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
            capex_cols = [c for c in capex_df.columns if c.startswith("Capex_")]

            if not capex_cols:
                st.info("No Capex_* columns found in macro_capex_processed.csv.")
            else:
                default_selection = [c for c in capex_cols if c != "Capex_Supply"] or capex_cols

                selected_cols = st.multiselect(
                    "Select Capex components to display",
                    options=capex_cols,
                    default=default_selection,
                )

                if not selected_cols:
                    st.warning("Select at least one Capex component to view.")
                else:
                    st.markdown("**Latest 12 months — raw capex indices**")
                    st.dataframe(capex_df[selected_cols].tail(12))

                    vis_df = capex_df[selected_cols].copy()

                    for col in vis_df.columns:
                        col_min = vis_df[col].min()
                        col_max = vis_df[col].max()

                        if pd.isna(col_min) or pd.isna(col_max) or col_min == col_max:
                            vis_df[col] = 50.0
                        else:
                            vis_df[col] = 100.0 * (vis_df[col] - col_min) / (col_max - col_min)

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
                                alt.Tooltip("Value:Q", title="Visual index", format=".1f"),
                            ],
                        )
                        .properties(height=260)
                    )

                    st.altair_chart(capex_ts, use_container_width=True)

# ---------- Infrastructure pillar debug ----------
with st.expander("Infra pillar debug", expanded=False):
    st.markdown("### Infrastructure subcomponents (diagnostic view)")

    infra_path = "data/processed/infra_processed.csv"

    if not os.path.exists(infra_path):
        st.warning(f"`{infra_path}` not found. Run the update-data workflow first.")
    else:
        try:
            infra_df = (
                pd.read_csv(infra_path, parse_dates=["Date"])
                .set_index("Date")
                .sort_index()
            )
        except Exception as e:
            st.error(f"Failed to read `{infra_path}`: {e}")
            infra_df = None

        if infra_df is None or infra_df.empty:
            st.info("infra_processed.csv is empty.")
        else:
            infra_cols = [
                c for c in infra_df.columns
                if c.startswith("Infra_") and c not in ["Infra", "Infra_Supply"]
            ]

            if not infra_cols:
                st.info("No Infra_* subcomponent columns found in infra_processed.csv.")
            else:
                selected_cols = st.multiselect(
                    "Select Infra components to display",
                    options=infra_cols,
                    default=infra_cols,
                )

                if not selected_cols:
                    st.warning("Select at least one Infra component to view.")
                else:
                    st.markdown("**Latest 12 months — raw Infra indices**")
                    st.dataframe(infra_df[selected_cols].tail(12))

                    vis_df = infra_df[selected_cols].copy()

                    for col in vis_df.columns:
                        col_min = vis_df[col].min()
                        col_max = vis_df[col].max()

                        if pd.isna(col_min) or pd.isna(col_max) or col_min == col_max:
                            vis_df[col] = 50.0
                        else:
                            vis_df[col] = 100.0 * (vis_df[col] - col_min) / (col_max - col_min)

                    vis_long = (
                        vis_df
                        .reset_index(names="date")
                        .melt(id_vars="date", var_name="Component", value_name="Value")
                    )

                    infra_ts = (
                        alt.Chart(vis_long)
                        .mark_line()
                        .encode(
                            x=alt.X("date:T", title="Date"),
                            y=alt.Y(
                                "Value:Q",
                                title="Visual index (0–100 per component)",
                                scale=alt.Scale(domain=[0, 100]),
                            ),
                            color=alt.Color("Component:N", title="Infra Component"),
                            tooltip=[
                                alt.Tooltip("date:T", title="Date"),
                                alt.Tooltip("Component:N", title="Component"),
                                alt.Tooltip("Value:Q", title="Visual index", format=".1f"),
                            ],
                        )
                        .properties(height=260)
                    )

                    st.altair_chart(infra_ts, use_container_width=True)

# ---------- Adoption pillar debug ----------
with st.expander("Adoption pillar debug", expanded=False):
    st.markdown("### Adoption subcomponents (diagnostic view)")

    adopt_path = "data/processed/adoption_processed.csv"

    if not os.path.exists(adopt_path):
        st.warning(f"`{adopt_path}` not found. Run the update-data workflow first.")
    else:
        try:
            adopt_df = (
                pd.read_csv(adopt_path, parse_dates=["Date"])
                .set_index("Date")
                .sort_index()
            )
        except Exception as e:
            st.error(f"Failed to read `{adopt_path}`: {e}")
            adopt_df = None

        if adopt_df is None or adopt_df.empty:
            st.info("adoption_processed.csv is empty.")
        else:
            sub_cols = [
                c for c in adopt_df.columns
                if c.startswith("Adoption_")
                and c not in ["Adoption", "Adoption_Supply"]
            ]

            if not sub_cols:
                st.info("No Adoption_* subcomponent columns found.")
            else:
                selected_cols = st.multiselect(
                    "Select Adoption components to display",
                    options=sub_cols,
                    default=sub_cols,
                )

                if not selected_cols:
                    st.warning("Select at least one Adoption component to view.")
                else:
                    st.markdown("**Latest 12 months — raw Adoption indices**")
                    st.dataframe(adopt_df[selected_cols].tail(12))

                    vis_df = adopt_df[selected_cols].copy()

                    for col in vis_df.columns:
                        col_min = vis_df[col].min()
                        col_max = vis_df[col].max()

                        if pd.isna(col_min) or pd.isna(col_max) or col_min == col_max:
                            vis_df[col] = 50.0
                        else:
                            vis_df[col] = 100.0 * (vis_df[col] - col_min) / (col_max - col_min)

                    vis_long = (
                        vis_df.reset_index(names="date")
                        .melt(id_vars="date", var_name="Component", value_name="Value")
                    )

                    ad_ts = (
                        alt.Chart(vis_long)
                        .mark_line()
                        .encode(
                            x=alt.X("date:T", title="Date"),
                            y=alt.Y(
                                "Value:Q",
                                title="Visual index (0–100 per component)",
                                scale=alt.Scale(domain=[0, 100]),
                            ),
                            color=alt.Color("Component:N", title="Adoption Component"),
                            tooltip=[
                                alt.Tooltip("date:T", title="Date"),
                                alt.Tooltip("Component:N", title="Component"),
                                alt.Tooltip("Value:Q", title="Visual index", format=".1f"),
                            ],
                        )
                        .properties(height=260)
                    )

                    st.altair_chart(ad_ts, use_container_width=True)

# ---------- Sentiment pillar debug ----------
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
                    y=alt.Y("Value:Q", title="Value"),
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
st.caption(
    f"Data through {updated_str}. AIBPS is an experimental composite indicator and may be revised."
)
