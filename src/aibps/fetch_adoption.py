# src/aibps/fetch_adoption.py
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("data")
PROC_OUT = DATA_DIR / "processed" / "adoption_processed.csv"
START = "1980-01-01"

# FRED series:
# - ITNETUSERP2USA: Internet users per 100 people (annual)
# - CEU6054150001: All employees, computer systems design and related services (monthly, NSA)
ADOPTION_SERIES = {
    "Adopt_InternetUsers": "ITNETUSERP2USA",
    "Adopt_CompSys_Empl": "CEU6054150001",
}


def _to_monthly(s: pd.Series) -> pd.Series:
    """
    Convert annual or monthly FRED series to end-of-month monthly frequency via forward fill.
    """
    s = pd.Series(s).sort_index()
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"
    s = s.resample("M").ffill()
    s = s[s.index >= pd.to_datetime(START)]
    return s


def _rebase_100(s: pd.Series) -> pd.Series:
    if not s.notna().any():
        return s * np.nan
    first = s.dropna().iloc[0]
    if not np.isfinite(first) or first == 0:
        return s * np.nan
    return (s / first) * 100.0


def main():
    key = os.getenv("FRED_API_KEY")
    if not key:
        print("⚠️ No FRED_API_KEY — cannot fetch Adoption data.")
        return

    from fredapi import Fred
    fred = Fred(api_key=key)

    frames = {}
    for label, sid in ADOPTION_SERIES.items():
        try:
            raw = fred.get_series(sid, observation_start=START)
            monthly = _to_monthly(raw)
            frames[label] = monthly
        except Exception as e:
            print(f"⚠️ Failed to fetch {sid} ({label}): {e}")

    if not frames:
        print("❌ No Adoption series fetched; not writing file.")
        return

    df = pd.concat(frames.values(), axis=1)
    df.columns = list(frames.keys())
    df.index.name = "date"

    # Rebase each component to 100 at its first valid point
    rebased = df.apply(_rebase_100)
    rebased_cols = [f"{c}_idx" for c in rebased.columns]
    rebased.columns = rebased_cols

    # Composite: equal-weight of rebased components
    composite = rebased.mean(axis=1, skipna=True).rename("Adoption")

    out = pd.concat([composite, rebased, df.add_suffix("_raw")], axis=1)
    out = out.dropna(how="all")

    PROC_OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROC_OUT)

    print("---- Adoption composite tail ----")
    print(out[["Adoption"]].tail(6))
    print(f"💾 Wrote {PROC_OUT} with columns: {list(out.columns)}")
    print(f"Range: {out.index.min().date()} → {out.index.max().date()}")


if __name__ == "__main__":
    main()
