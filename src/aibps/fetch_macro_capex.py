"""
fetch_capex_macro.py

Builds a fabrication + cloud-compute-oriented Capex index for the AIBPS:

- Macro compute/fab component from FRED:
  * A679RL1Q225SBEA – Real private fixed investment in information processing equipment and software
  * B935RX1A020NBEA – Real private fixed investment: nonresidential equipment: computers and peripherals
  * PCU333242333242 – PPI: Semiconductor Machinery Manufacturing

- Hyperscaler capex component from:
  data/raw/hyperscaler_capex.csv

Outputs:
  data/processed/macro_capex_processed.csv with columns:
    - Capex_Supply          (composite of macro + hyperscaler where available)
    - Capex_Macro_Comp      (macro compute/fab sub-index)
    - Capex_Hyperscaler     (hyperscaler capex sub-index)
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROC_DIR = Path("data") / "processed"
RAW_DIR = Path("data") / "raw"
OUT_PATH = PROC_DIR / "macro_capex_processed.csv"

# FRED series IDs (compute & semiconductor-related)
SERIES_INFO = {
    "A679RL1Q225SBEA": "InfoProc_EquipSoft_Real",  # Real private fixed investment in info processing equipment & software
    "B935RX1A020NBEA": "Comp_Periph_Real",         # Real private fixed investment: computers & peripherals
    "PCU333242333242": "PPI_Semi_Machinery",       # PPI: Semiconductor Machinery Manufacturing
}

BASELINE_DATE = pd.Timestamp("2015-12-31")  # baseline for index=100 scaling


def get_fred():
    """Instantiate Fred client if API key exists, else return None."""
    key = os.getenv("FRED_API_KEY")
    if not key:
        print("⚠️ No FRED_API_KEY set; cannot fetch real macro capex. Will fall back to placeholder if needed.")
        return None

    try:
        from fredapi import Fred  # type: ignore
    except ImportError:
        print("⚠️ fredapi not installed; falling back to placeholder synthetic capex.")
        return None

    try:
        fred = Fred(api_key=key)
        return fred
    except Exception as e:
        print(f"⚠️ Failed to initialize Fred with provided API key: {e}")
        return None


def fetch_macro_series(fred):
    """
    Fetch and assemble macro/fab-related series from FRED.

    Returns:
        pd.DataFrame monthly with columns for each macro sub-series,
        or None if everything fails.
    """
    if fred is None:
        return None

    frames = []
    for sid, col_name in SERIES_INFO.items():
        try:
            ser = fred.get_series(sid)
            if ser is None or len(ser) == 0:
                print(f"⚠️ FRED returned empty for {sid}; skipping.")
                continue
            df = ser.to_frame(name=col_name)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            # Resample to monthly end with forward fill
            df_m = df.resample("M").ffill()
            frames.append(df_m)
            print(f"✅ FRED series {sid} → {col_name}: {df_m.index.min().date()} to {df_m.index.max().date()}")
        except Exception as e:
            print(f"⚠️ Failed to fetch {sid}: {e}")

    if not frames:
        print("⚠️ No macro capex series fetched from FRED.")
        return None

    combined = pd.concat(frames, axis=1).sort_index()
    combined = combined.dropna(how="all")
    return combined


def scale_to_index(series: pd.Series, baseline_date: pd.Timestamp, name: str) -> pd.Series:
    """
    Scale a series to an index=100 at baseline_date (or first non-NaN as fallback).
    """
    s = series.copy()

    baseline_val = np.nan
    if baseline_date in s.index and not pd.isna(s.loc[baseline_date]):
        baseline_val = s.loc[baseline_date]
        print(f"🔧 {name}: using baseline {baseline_date.date()} value={baseline_val:.3f} for index=100")
    else:
        first_idx = s.first_valid_index()
        if first_idx is not None:
            baseline_val = s.loc[first_idx]
            print(f"🔧 {name}: baseline {baseline_date.date()} missing; using first valid {first_idx.date()} value={baseline_val:.3f} for index=100")
        else:
            print(f"⚠️ {name}: series has no valid values; returning as-is.")
            return s

    if baseline_val == 0 or np.isnan(baseline_val):
        print(f"⚠️ {name}: baseline value invalid; returning unscaled.")
        return s

    s = (s / baseline_val) * 100.0
    return s


def build_macro_capex_index(macro_df: pd.DataFrame) -> pd.Series:
    """
    Given a DataFrame of macro series, create a composite macro capex index.

    Returns:
        pd.Series named 'Capex_Macro_Comp'
    """
    df = macro_df.copy()
    for col in df.columns:
        df[col] = scale_to_index(df[col], BASELINE_DATE, col)

    macro_index = df.mean(axis=1)
    macro_index.name = "Capex_Macro_Comp"
    print("✅ Built Capex_Macro_Comp composite.")
    return macro_index


def load_hyperscaler_capex() -> pd.Series | None:
    """
    Load hyperscaler capex data from:
      data/raw/hyperscaler_capex.csv

    Expected schema (what we just created):
      Year,AWS,Microsoft,Google,Meta,Total,IsEstimate,Source

    Returns:
        Monthly pd.Series named 'Capex_Hyperscaler' or None if file missing/invalid.
    """
    csv_path = RAW_DIR / "hyperscaler_capex.csv"
    if not csv_path.exists():
        print(f"ℹ️ No hyperscaler capex file at {csv_path}; skipping hyperscaler component.")
        return None

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"⚠️ Failed to read {csv_path}: {e}")
        return None

    # Handle date / Year
    if "date" in df.columns:
        # Already have a date column
        try:
            df["date"] = pd.to_datetime(df["date"])
        except Exception as e:
            print(f"⚠️ Failed to parse 'date' column in hyperscaler_capex.csv: {e}")
            return None
    elif "Year" in df.columns:
        # Convert Year to end-of-year date
        try:
            df["date"] = pd.to_datetime(df["Year"].astype(str) + "-12-31")
        except Exception as e:
            print(f"⚠️ Failed to convert 'Year' to dates in hyperscaler_capex.csv: {e}")
            return None
    else:
        print("⚠️ hyperscaler_capex.csv must contain either 'date' or 'Year' column.")
        return None

    df = df.set_index("date").sort_index()

    # Known provider columns we care about
    candidate_cols = ["AWS", "Microsoft", "Google", "Meta"]
    value_cols = [c for c in candidate_cols if c in df.columns]

    if not value_cols:
        # Fallback: any numeric columns that are not clearly metadata
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        value_cols = [
            c for c in numeric_cols
            if c.lower() not in ["total", "isestimate", "year"]
        ]

    if not value_cols:
        print("⚠️ hyperscaler_capex.csv has no usable numeric provider columns; skipping.")
        return None

    total = df[value_cols].sum(axis=1)
    total.name = "Capex_Hyperscaler"

    # Make it monthly by forward-filling annual points
    monthly_idx = pd.date_range(total.index.min(), total.index.max(), freq="M")
    total_m = total.reindex(monthly_idx).ffill()
    total_m.index.name = "Date"

    total_m = scale_to_index(total_m, BASELINE_DATE, "Capex_Hyperscaler")
    total_m.name = "Capex_Hyperscaler"

    print(f"✅ Loaded Capex_Hyperscaler from {csv_path}: {total_m.index.min().date()} to {total_m.index.max().date()}")
    return total_m


def main():
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    fred = get_fred()
    macro_df = fetch_macro_series(fred)

    if macro_df is None:
        print("⚠️ Falling back to synthetic macro capex index (constant 100).")
        idx = pd.date_range("1980-01-31", periods=12 * 10, freq="M")
        macro_index = pd.Series(100.0, index=idx, name="Capex_Macro_Comp")
    else:
        macro_index = build_macro_capex_index(macro_df)

    hyper_series = load_hyperscaler_capex()

    df = pd.DataFrame(index=macro_index.index)
    df["Capex_Macro_Comp"] = macro_index

    if hyper_series is not None:
        df = df.join(hyper_series, how="outer")
        df["Capex_Macro_Comp"] = df["Capex_Macro_Comp"].ffill()
        df["Capex_Hyperscaler"] = df["Capex_Hyperscaler"].ffill()
        df["Capex_Supply"] = df[["Capex_Macro_Comp", "Capex_Hyperscaler"]].mean(axis=1)
        print("✅ Built Capex_Supply from macro + hyperscaler components.")
    else:
        df["Capex_Supply"] = df["Capex_Macro_Comp"]
        print("ℹ️ Capex_Supply uses Capex_Macro_Comp only (no hyperscaler component).")

    df = df.sort_index()
    df = df.dropna(subset=["Capex_Supply"])

    print("---- Tail of macro_capex_processed.csv ----")
    print(df.tail(10))

    df.to_csv(OUT_PATH, index_label="Date")
    print(f"💾 Wrote {OUT_PATH} with columns: {list(df.columns)} (rows={len(df)})")


if __name__ == "__main__":
    sys.exit(main())
