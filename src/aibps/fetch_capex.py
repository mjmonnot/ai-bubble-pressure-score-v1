# src/aibps/fetch_capex.py
# Manual/corporate Capex: flexible percentile + monthly grid + ffill(limit=3) + clip(1,99)

import os, sys, time
import pandas as pd
import numpy as np

RAW = os.path.join("data","raw","capex_manual.csv")
OUT = os.path.join("data","processed","capex_processed.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

def _expanding_pct(series: pd.Series) -> pd.Series:
    out = []
    vals = series.values
    for i in range(len(vals)):
        s = pd.Series(vals[:i+1])
        out.append(float(s.rank(pct=True).iloc[-1] * 100.0))
    return pd.Series(out, index=series.index)

def rolling_pct_rank_flexible(series: pd.Series, window: int = 120) -> pd.Series:
    series = series.dropna()
    n = len(series)
    if n == 0:
        return series
    if n < 24:
        return _expanding_pct(series)
    def _rank_last(x):
        s = pd.Series(x)
        return float(s.rank(pct=True).iloc[-1] * 100.0)
    minp = max(24, window // 4)
    return series.rolling(window, min_periods=minp).apply(_rank_last, raw=False)

def main():
    t0 = time.time()
    if not os.path.exists(RAW):
        print(f"ℹ️ {RAW} not found. Header only.")
        pd.DataFrame(columns=["Capex_Supply"]).to_csv(OUT); return

    df = pd.read_csv(RAW)
    if "date" not in df.columns or "value" not in df.columns:
        raise ValueError("capex_manual.csv must include 'date' and 'value'.")

    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df          = df[~df["date"].isna()].copy()
    df["date"]  = df["date"].dt.to_period("M").dt.to_timestamp("M")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df          = df[~df["value"].isna()].copy()

    monthly_sum = df.groupby("date")["value"].sum().sort_index()

    capex_pct = rolling_pct_rank_flexible(monthly_sum, window=120)

       # Reindex to full month grid through today; forward-fill only up to 12 months
    if not capex_pct.empty:
        start = capex_pct.index.min().to_period("M").to_timestamp("M")
        end   = pd.Timestamp.today().to_period("M").to_timestamp("M")
        full_idx = pd.period_range(start, end, freq="M").to_timestamp("M")
        capex_pct = capex_pct.reindex(full_idx).ffill(limit=12)  # was limit=3 before
        capex_pct = capex_pct.clip(1, 99)
        capex_pct.index.name = "date"


    out = pd.DataFrame({"Capex_Supply": capex_pct}).dropna(how="all")
    out.to_csv(OUT)

    print(f"💾 Wrote {OUT} ({len(out)} rows)")
    print("Tail:"); print(out.tail(6))
    print(f"⏱  Done in {time.time()-t0:.2f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ fetch_capex.py: {e}")
        sys.exit(1)
