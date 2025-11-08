# src/aibps/fetch_infra.py
# Infra pillar (manual / curated):
# - Reads data/raw/infra_manual.csv
# - Aggregates to monthly total
# - Computes rolling/expanding percentile (0–100)
# - Reindexes to monthly grid and ffill(limit=6)
# - Writes data/processed/infra_processed.csv with column "Infra"

import os, sys, time
import pandas as pd
import numpy as np

RAW = os.path.join("data", "raw", "infra_manual.csv")
OUT = os.path.join("data", "processed", "infra_processed.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

def _expanding_pct(series: pd.Series) -> pd.Series:
    out = []
    vals = series.values
    for i in range(len(vals)):
        s = pd.Series(vals[: i+1])
        out.append(float(s.rank(pct=True).iloc[-1] * 100.0))
    return pd.Series(out, index=series.index)

def rolling_pct_rank_flexible(series: pd.Series, window: int = 120) -> pd.Series:
    """
    For short histories: expanding percentile.
    For longer histories: rolling window percentile with reasonable min_periods.
    """
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
        print(f"ℹ️ {RAW} not found. Writing header only.")
        pd.DataFrame(columns=["Infra"]).to_csv(OUT)
        return

    df = pd.read_csv(RAW)

    # Expect at least date + value; extra columns are fine.
    if "date" not in df.columns or "value" not in df.columns:
        raise ValueError("infra_manual.csv must include 'date' and 'value' columns.")

    # Parse and normalize date to month-end
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[~df["date"].isna()].copy()
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp("M")

    # Clean numeric values
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[~df["value"].isna()].copy()

    # Aggregate to monthly total across segments/companies
    monthly = df.groupby("date")["value"].sum().sort_index()

    # Percentile transform
    infra_pct = rolling_pct_rank_flexible(monthly, window=120)

    # Reindex to full month-end grid through today, ffill up to 6 months
    if not infra_pct.empty:
        start = infra_pct.index.min().to_period("M").to_timestamp("M")
        end   = pd.Timestamp.today().to_period("M").to_timestamp("M")
        full_idx = pd.period_range(start, end, freq="M").to_timestamp("M")
        infra_pct = infra_pct.reindex(full_idx).ffill(limit=6)
        infra_pct = infra_pct.clip(1, 99)
        infra_pct.index.name = "date"

    out = pd.DataFrame({"Infra": infra_pct}).dropna(how="all")
    out.to_csv(OUT)

    print(f"💾 Wrote {OUT} ({len(out)} rows)")
    print("Tail:")
    print(out.tail(6))
    print(f"⏱  Done in {time.time()-t0:.2f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ fetch_infra.py: {e}")
        sys.exit(1)
