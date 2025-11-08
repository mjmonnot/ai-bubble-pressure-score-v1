# src/aibps/fetch_infra_macro.py
# Macro Infra pillar via FRED:
# - Pulls 1–2 construction-related series from FRED
# - Converts to monthly
# - Uses YoY % change of a smoothed series
# - Outputs 0–100 percentile as "Infra_Macro" in data/processed/infra_macro_processed.csv

import os, sys, time
import pandas as pd
import numpy as np

OUT = os.path.join("data", "processed", "infra_macro_processed.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

def _expanding_pct(series: pd.Series) -> pd.Series:
    out = []
    vals = series.values
    for i in range(len(vals)):
        s = pd.Series(vals[:i+1])
        out.append(float(s.rank(pct=True).iloc[-1] * 100.0))
    return pd.Series(out, index=series.index)

def rolling_pct_rank(series: pd.Series, window: int = 120) -> pd.Series:
    series = series.dropna()
    n = len(series)
    if n == 0:
        return series
    if n < 36:
        return _expanding_pct(series)
    def _rank_last(x):
        s = pd.Series(x)
        return float(s.rank(pct=True).iloc[-1] * 100.0)
    return series.rolling(window, min_periods=24).apply(_rank_last, raw=False)

def get_series_safely(fred, series_id: str, label: str) -> pd.Series | None:
    try:
        s = fred.get_series(series_id, observation_start="2010-01-01")
        if s is None or len(s) == 0:
            print(f"⚠️ FRED series {series_id} ({label}) returned empty.")
            return None
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s[~s.index.isna()].sort_index()
        return s
    except Exception as e:
        print(f"⚠️ Error fetching {series_id} ({label}): {e}")
        return None

def main():
    t0 = time.time()
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("❌ FRED_API_KEY not found. Set GitHub Secret FRED_API_KEY.")
        pd.DataFrame(columns=["Infra_Macro"]).to_csv(OUT)
        sys.exit(1)

    try:
        from fredapi import Fred
    except Exception as e:
        print(f"❌ fredapi not installed: {e}")
        pd.DataFrame(columns=["Infra_Macro"]).to_csv(OUT)
        sys.exit(1)

    fred = Fred(api_key=api_key)

    # Example macro infra proxies (you can refine IDs later):
    # We'll fetch 1–2 broad construction series and blend them.
    candidates = [
        # (series_id, label)
        ("TTLCONS", "Total Construction Spending"),  # example ID; adjust as needed
        # You can add a power/communication-specific series here later
    ]

    series_list = []
    for sid, label in candidates:
        s = get_series_safely(fred, sid, label)
        if s is not None:
            series_list.append(s.rename(sid))

    if not series_list:
        print("⚠️ No macro infra series fetched; writing header only.")
        pd.DataFrame(columns=["Infra_Macro"]).to_csv(OUT)
        sys.exit(0)

    # Merge all macro infra series and build a composite level
    macro_df = pd.concat(series_list, axis=1).sort_index()
    level = macro_df.mean(axis=1, skipna=True)

    # Convert to monthly via interpolation on a month-end grid
    start = level.index.min().to_period("M").to_timestamp("M")
    end   = pd.Timestamp.today().to_period("M").to_timestamp("M")
    idx_m = pd.period_range(start, end, freq="M").to_timestamp("M")
    level_m = level.reindex(idx_m).interpolate(method="linear")
    level_m.index.name = "date"

    # Use YoY % change of a smoothed level as the signal
    roll_12 = level_m.rolling(12, min_periods=9).mean()
    yoy = (roll_12.pct_change(12) * 100.0).rolling(3, min_periods=1).mean()

    infra_pct = rolling_pct_rank(yoy, window=120)
    infra_pct = infra_pct.clip(1, 99)

    out = pd.DataFrame({"Infra_Macro": infra_pct}).dropna(how="all")
    out.index.name = "date"
    out.to_csv(OUT)

    print(f"💾 Wrote {OUT} ({len(out)} rows)")
    print("Tail:")
    print(out.tail(6))
    print(f"⏱  Done in {time.time()-t0:.2f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ fetch_infra_macro.py: {e}")
        sys.exit(1)
