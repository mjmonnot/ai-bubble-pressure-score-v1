"""
fetch_macro_capex.py

Builds a fabrication + cloud-compute-oriented Capex index for the AIBPS.

Components included:

(1) Core macro capex proxies (FRED):
    - A679RL1Q225SBEA – Real private fixed investment in info processing equipment & software
    - B935RX1A020NBEA – Real private fixed investment: nonresidential equipment: computers & peripherals
    - PCU333242333242 – PPI: Semiconductor Machinery Manufacturing

(2) Additional FRED-based capex / supply-chain signals:
    A. Semiconductor production / capacity:
       - IPG336413     – Industrial Production: Semiconductors and Related Devices
       - IPN336413     – Capacity Utilization: Semiconductors and Related Devices

    B. IT equipment & processing investment:
       - Y033RC1Q027SBEA – Private fixed investment in information processing equipment

    C. Construction / structures proxies:
       - PNFI        – Private nonresidential fixed investment
       - PRFI        – Private residential fixed investment
       - TLRESCONS   – Total construction spending (if available; skipped otherwise)

(3) Hyperscaler capex (optional):
    - data/raw/hyperscaler_capex.csv

(4) Fabrication capex (optional):
    - data/raw/fab_capex.csv

(5) Datacenter construction cost index (optional):
    - data/raw/dc_cost_index.csv

Output:
    data/processed/macro_capex_processed.csv with columns such as:
      - Capex_Macro_Comp
      - Capex_Semi_Activity
      - Capex_IT_Equip
      - Capex_Constr
      - Capex_Hyperscaler
      - Capex_Fab_Index
      - Capex_DC_Cost_Index
      - Capex_Supply
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROC_DIR = Path("data") / "processed"
RAW_DIR = Path("data") / "raw"
OUT_PATH = PROC_DIR / "macro_capex_processed.csv"

# ----------------------------
# FRED series configuration
# ----------------------------

# Core macro proxies
CORE_FRED_SERIES = {
    "A679RL1Q225SBEA": "InfoProc_EquipSoft_Real",
    "B935RX1A020NBEA": "Comp_Periph_Real",
    "PCU333242333242": "PPI_Semi_Machinery",
}

# Extra signals
EXTRA_FRED_SERIES = {
    # A: Semiconductor production / capacity
    "IPG336413": "IP_Semi_Prod",
    "IPN336413": "CU_Semi_Cap",

    # B: IT equipment / processing investment
    "Y033RC1Q027SBEA": "Inv_InfoProc_Equip",

    # C: Construction proxies
    "PNFI": "Priv_Nonres_FixedInv",
    "PRFI": "Priv_Res_FixedInv",
    "TLRESCONS": "Total_Constr_Spending",  # if absent, will be skipped
}

BASELINE_DATE = pd.Timestamp("2015-12-31")


def get_fred():
    """Instantiate Fred client if API key exists, else return None."""
    key = os.getenv("FRED_API_KEY")
    if not key:
        print("⚠️ No FRED_API_KEY set; cannot fetch real macro capex.")
        return None

    try:
        from fredapi import Fred  # type: ignore
    except ImportError:
        print("⚠️ fredapi not installed; cannot fetch from FRED.")
        return None

    try:
        fred = Fred(api_key=key)
        return fred
    except Exception as e:
        print(f"⚠️ Failed to initialize Fred: {e}")
        return None


def fetch_fred_block(fred, series_map, label: str) -> pd.DataFrame | None:
    """
    Fetch a group of FRED series and resample to monthly.
    """
    if fred is None:
        print(f"ℹ️ No FRED client; skipping {label} block.")
        return None

    frames = []
    for sid, col_name in series_map.items():
        try:
            ser = fred.get_series(sid)
            if ser is None or len(ser) == 0:
                print(f"⚠️ FRED returned empty for {sid} ({col_name}); skipping.")
                continue
            df = ser.to_frame(name=col_name)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            df_m = df.resample("M").ffill()
            frames.append(df_m)
            print(f"✅ FRED {sid} → {col_name} [{label}]: {df_m.index.min().date()} to {df_m.index.max().date()}")
        except Exception as e:
            print(f"⚠️ Failed to fetch {sid} ({col_name}) [{label}]: {e}")

    if not frames:
        print(f"⚠️ No series fetched for {label} block.")
        return None

    combined = pd.concat(frames, axis=1).sort_index()
    combined = combined.dropna(how="all")
    return combined


def scale_to_index(series: pd.Series, baseline_date: pd.Timestamp, name: str) -> pd.Series:
    """Scale a series so that baseline_date (or first valid) ≈ 100."""
    s = series.copy()

    baseline_val = np.nan
    if baseline_date in s.index and not pd.isna(s.loc[baseline_date]):
        baseline_val = s.loc[baseline_date]
        print(f"🔧 {name}: baseline {baseline_date.date()} value={baseline_val:.3f}")
    else:
        first_idx = s.first_valid_index()
        if first_idx is not None:
            baseline_val = s.loc[first_idx]
            print(f"🔧 {name}: using first valid {first_idx.date()} value={baseline_val:.3f} as baseline")
        else:
            print(f"⚠️ {name}: no valid values; returning unscaled.")
            return s

    if baseline_val == 0 or np.isnan(baseline_val):
        print(f"⚠️ {name}: invalid baseline; returning unscaled.")
        return s

    return (s / baseline_val) * 100.0


def build_macro_block_index(df: pd.DataFrame, name: str) -> pd.Series:
    """Scale each column to an index and average into a composite."""
    if df is None or df.empty:
        return pd.Series(dtype=float, name=name)

    tmp = df.copy()
    for col in tmp.columns:
        tmp[col] = scale_to_index(tmp[col], BASELINE_DATE, col)

    idx = tmp.mean(axis=1)
    idx.name = name
    print(f"✅ Built composite index {name} from columns: {list(tmp.columns)}")
    return idx


def load_hyperscaler_capex() -> pd.Series | None:
    """Load hyperscaler capex from data/raw/hyperscaler_capex.csv."""
    csv_path = RAW_DIR / "hyperscaler_capex.csv"
    if not csv_path.exists():
        print(f"ℹ️ No hyperscaler capex file at {csv_path}.")
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"⚠️ Failed to read {csv_path}: {e}")
        return None

    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["date"])
        except Exception as e:
            print(f"⚠️ Failed to parse 'date' in hyperscaler_capex.csv: {e}")
            return None
    elif "Year" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["Year"].astype(str) + "-12-31")
        except Exception as e:
            print(f"⚠️ Failed to convert 'Year' to dates in hyperscaler_capex.csv: {e}")
            return None
    else:
        print("⚠️ hyperscaler_capex.csv must contain 'date' or 'Year'.")
        return None

    df = df.set_index("date").sort_index()

    candidate_cols = ["AWS", "Microsoft", "Google", "Meta"]
    value_cols = [c for c in candidate_cols if c in df.columns]
    if not value_cols:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        value_cols = [c for c in numeric_cols if c.lower() not in ["total", "isestimate", "year"]]

    if not value_cols:
        print("⚠️ No usable provider columns in hyperscaler_capex.csv.")
        return None

    total = df[value_cols].sum(axis=1)
    total.name = "Capex_Hyperscaler"

    monthly_idx = pd.date_range(total.index.min(), total.index.max(), freq="M")
    total_m = total.reindex(monthly_idx).ffill()
    total_m.index.name = "Date"
    total_m = scale_to_index(total_m, BASELINE_DATE, "Capex_Hyperscaler")
    total_m.name = "Capex_Hyperscaler"

    print(f"✅ Loaded Capex_Hyperscaler from {csv_path}: {total_m.index.min().date()} to {total_m.index.max().date()}")
    return total_m


def load_fab_capex() -> pd.Series | None:
    """Load fabrication capex from data/raw/fab_capex.csv."""
    csv_path = RAW_DIR / "fab_capex.csv"
    if not csv_path.exists():
        print(f"ℹ️ No fab capex file at {csv_path}.")
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"⚠️ Failed to read {csv_path}: {e}")
        return None

    if "Year" not in df.columns:
        print("⚠️ fab_capex.csv must contain 'Year'.")
        return None

    try:
        df["date"] = pd.to_datetime(df["Year"].astype(str) + "-12-31")
    except Exception as e:
        print(f"⚠️ Failed to convert 'Year' to dates in fab_capex.csv: {e}")
        return None

    df = df.set_index("date").sort_index()

    candidate_cols = ["TSMC", "Samsung", "Intel"]
    value_cols = [c for c in candidate_cols if c in df.columns]
    if not value_cols:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        value_cols = [c for c in numeric_cols if c.lower() not in ["total", "isestimate", "year"]]

    if not value_cols:
        print("⚠️ No usable fab columns in fab_capex.csv.")
        return None

    total = df[value_cols].sum(axis=1)
    total.name = "Capex_Fab_Raw"

    monthly_idx = pd.date_range(total.index.min(), total.index.max(), freq="M")
    total_m = total.reindex(monthly_idx).ffill()
    total_m.index.name = "Date"

    total_m = scale_to_index(total_m, BASELINE_DATE, "Capex_Fab_Index")
    total_m.name = "Capex_Fab_Index"

    print(f"✅ Loaded Capex_Fab_Index from {csv_path}: {total_m.index.min().date()} to {total_m.index.max().date()}")
    return total_m


def load_dc_cost_index() -> pd.Series | None:
    """Load datacenter construction cost index from data/raw/dc_cost_index.csv."""
    csv_path = RAW_DIR / "dc_cost_index.csv"
    if not csv_path.exists():
        print(f"ℹ️ No DC cost index file at {csv_path}.")
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"⚠️ Failed to read {csv_path}: {e}")
        return None

    if "Date" not in df.columns:
        print("⚠️ dc_cost_index.csv must contain 'Date'.")
        return None

    try:
        df["Date"] = pd.to_datetime(df["Date"])
    except Exception as e:
        print(f"⚠️ Failed to parse 'Date' in dc_cost_index.csv: {e}")
        return None

    df = df.set_index("Date").sort_index()

    if "Cost_Index" in df.columns:
        value_col = "Cost_Index"
    else:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            print("⚠️ dc_cost_index.csv has no numeric columns.")
            return None
        value_col = numeric_cols[0]

    s = df[value_col].copy()
    s.name = "Capex_DC_Cost_Raw"

    monthly_idx = pd.date_range(s.index.min(), s.index.max(), freq="M")
    s_m = s.reindex(monthly_idx).ffill()
    s_m.index.name = "Date"

    s_m = scale_to_index(s_m, BASELINE_DATE, "Capex_DC_Cost_Index")
    s_m.name = "Capex_DC_Cost_Index"

    print(f"✅ Loaded Capex_DC_Cost_Index from {csv_path}: {s_m.index.min().date()} to {s_m.index.max().date()}")
    return s_m


def main():
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    fred = get_fred()

    # 1) Core macro capex index
    core_df = fetch_fred_block(fred, CORE_FRED_SERIES, label="core_macro")
    if core_df is None:
        print("⚠️ Falling back to synthetic macro capex index (constant 100).")
        idx = pd.date_range("1980-01-31", periods=12 * 10, freq="M")
        macro_index = pd.Series(100.0, index=idx, name="Capex_Macro_Comp")
    else:
        macro_index = build_macro_block_index(core_df, "Capex_Macro_Comp")

    # 2) Extra FRED blocks (A–C)
    extra_df = fetch_fred_block(fred, EXTRA_FRED_SERIES, label="extra_capex")
    semi_idx = it_idx = constr_idx = None
    if extra_df is not None and not extra_df.empty:
        semi_cols = [c for c in extra_df.columns if c.startswith("IP_") or c.startswith("CU_")]
        it_cols = [c for c in extra_df.columns if "Inv_InfoProc" in c or "Inv_IT" in c]
        constr_cols = [c for c in extra_df.columns if "Priv_" in c or "Total_Constr" in c]

        if semi_cols:
            semi_idx = build_macro_block_index(extra_df[semi_cols], "Capex_Semi_Activity")
        if it_cols:
            it_idx = build_macro_block_index(extra_df[it_cols], "Capex_IT_Equip")
        if constr_cols:
            constr_idx = build_macro_block_index(extra_df[constr_cols], "Capex_Constr")

    # 3) Other components
    hyper_series = load_hyperscaler_capex()
    fab_series = load_fab_capex()
    dc_cost_series = load_dc_cost_index()

    # Build unified DataFrame on macro_index index
    df = pd.DataFrame(index=macro_index.index)
    df["Capex_Macro_Comp"] = macro_index

    for ser in [semi_idx, it_idx, constr_idx, hyper_series, fab_series, dc_cost_series]:
        if ser is None or ser.empty:
            continue
        name = ser.name
        df = df.join(ser, how="outer")
        df[name] = df[name].ffill()

    # Build Capex_Supply from all available components
    component_cols = [
        col for col in [
            "Capex_Macro_Comp",
            "Capex_Semi_Activity",
            "Capex_IT_Equip",
            "Capex_Constr",
            "Capex_Hyperscaler",
            "Capex_Fab_Index",
            "Capex_DC_Cost_Index",
        ]
        if col in df.columns
    ]

    if not component_cols:
        print("⚠️ No capex components found; Capex_Supply will be NaN.")
        df["Capex_Supply"] = np.nan
    else:
        df["Capex_Supply"] = df[component_cols].mean(axis=1)
        print(f"✅ Capex_Supply built from components: {component_cols}")

    df = df.sort_index()
    df = df.dropna(subset=["Capex_Supply"])

    print("---- Tail of macro_capex_processed.csv ----")
    print(df.tail(10))

    df.to_csv(OUT_PATH, index_label="Date")
    print(f"💾 Wrote {OUT_PATH} with columns: {list(df.columns)} (rows={len(df)})")


if __name__ == "__main__":
    sys.exit(main())
