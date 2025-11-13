# src/aibps/fetch_capex.py
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("data")
PROC_OUT = DATA_DIR / "processed" / "capex_processed.csv"

# Macro capex (broad supply-side investment)
PNFI = "PNFI"         # Private Nonresidential Fixed Investment
UNXANO = "UNXANO"     # Nonresidential structures

# Digital/AI capex proxies (software/ICT)
SOFTWARE = "DTCTRC1A027NBEA"   # Real private fixed investment: software
ICT_EQUIP = "TLPCINS"          # ICT equipment
COMP_ELEC = "ITNETPC"          # Computer/electronic investment

# Semiconductor/fab capex proxies
SEMICON_IP = "IPB53800"            # Industrial production: semiconductors
SEMICON_CAPUTIL = "CAPUTLB50001SQ" # Capacity Utilization: Semiconductor Fab

START = "1980-01-01"


def _to_monthly(s: pd.Series) -> pd.Series:
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"
    return s.resample("M").last()


def fetch_fred_series(fred, sid: str) -> pd.Series:
    s = fred.get_series(sid, observation_start=START)
    s = pd.Series(s, name=sid).sort_index()
    return _to_monthly(s)


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
        print("⚠️ No FRED_API_KEY — cannot fetch Capex data.")
        return

    from fredapi import Fred
    fred = Fred(api_key=key)

    series_ids = [
        PNFI,
        UNXANO,
        SOFTWARE,
        ICT_EQUIP,
        COMP_ELEC,
        SEMICON_IP,
        SEMICON_CAPUTIL,
    ]

    data = {}
    for sid in series_ids:
        try:
            s = fetch_fred_series(fred, sid)
            data[sid] = s
        except Exception as e:
            print(f"⚠️ Failed to fetch {sid}: {e}")

    if not data:
        print("❌ No Capex series fetched.")
        return

    df = pd.concat(data.values(), axis=1)
    df.index.name = "date"

    # Rebase each to 100
    rebased = df.apply(_rebase_100)
    rebased.columns = [
        f"Capex_{c.replace('-', '_')}_idx" for c in rebased.columns
    ]

    # Composite: equal-weight of all rebased components
    composite = rebased.mean(axis=1, skipna=True).rename("Capex_Supply")

    out = pd.concat([composite, rebased], axis=1)
    out = out.dropna(how="all")

    PROC_OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROC_OUT)

    print("---- Capex composite tail ----")
    print(out[["Capex_Supply"]].tail(6))
    print(f"💾 Wrote {PROC_OUT} with columns: {list(out.columns)}")
    print(f"Range: {out.index.min().date()} → {out.index.max().date()}")


if __name__ == "__main__":
    main()
