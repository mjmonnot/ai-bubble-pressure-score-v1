# src/aibps/fetch_credit.py
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("data")
PROC_OUT = DATA_DIR / "processed" / "credit_fred_processed.csv"

# FRED series IDs
AAA = "AAA"              # Moody's Seasoned Aaa Corporate Bond Yield (%)
BAA = "BAA"              # Moody's Seasoned Baa Corporate Bond Yield (%)
HY_OAS = "BAMLH0A0HYM2"  # ICE BofA US High Yield OAS (bp)

START = "1980-01-01"


def _to_monthly(s: pd.Series) -> pd.Series:
    s = s.sort_index()
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"
    return s.resample("ME").last()


def main():
    key = os.getenv("FRED_API_KEY")
    if not key:
        print("⚠️ No FRED_API_KEY — cannot fetch credit series.")
        return

    from fredapi import Fred
    fred = Fred(api_key=key)

    def get_series(sid: str) -> pd.Series:
        s = fred.get_series(sid, observation_start=START)
        s = pd.Series(s, name=sid).sort_index()
        s.index = pd.to_datetime(s.index)
        s.index.name = "date"
        return s

    # Fetch raw series
    try:
        aaa = get_series(AAA)
        baa = get_series(BAA)
        hy = get_series(HY_OAS)
    except Exception as e:
        print(f"⚠️ FRED fetch failed for credit series: {e}")
        return

    # Convert to monthly
    aaa_m = _to_monthly(aaa).rename("AAA_yield")
    baa_m = _to_monthly(baa).rename("BAA_yield")
    hy_m = _to_monthly(hy).rename("HY_OAS_bp")

    # Baa - Aaa spread in percentage points
    spread = (baa_m - aaa_m).rename("BAA_AAA_spread_pct")

    df = pd.concat([aaa_m, baa_m, spread, hy_m], axis=1).dropna(how="all")
    df.index.name = "date"

    if df.empty:
        print("⚠️ No combined credit data to write.")
        return

    PROC_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROC_OUT)

    print("---- credit_fred_processed tail ----")
    print(df.tail(6))
    print(
        f"💾 Wrote {PROC_OUT} (rows={len(df)}) "
        f"span: {df.index.min().date()} → {df.index.max().date()}"
    )


if __name__ == "__main__":
    main()
