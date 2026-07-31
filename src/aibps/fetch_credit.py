# src/aibps/fetch_credit.py
"""
Fetch credit conditions for AIBPS.

Writes data/processed/credit_fred_processed.csv with:
- AAA_yield, BAA_yield, BAA_AAA_spread_pct (diagnostics)
- HY_OAS_bp, IG_OAS_bp (spread inputs)
- Credit  ← canonical pillar column for compute.py

Credit construction (docs/data_sources.md):
- Mean of available ICE BofA OAS series (HY + IG)
- Wider spreads → higher funding stress → higher Credit pressure
"""
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
IG_OAS = "BAMLCC0A0CM"   # ICE BofA US Corporate OAS (bp)

START = "1980-01-01"


def _to_monthly(s: pd.Series) -> pd.Series:
    s = s.sort_index()
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"
    return s.resample("ME").last()


def build_credit_pillar(df: pd.DataFrame) -> pd.Series:
    """
    Build Credit from available OAS series.

    Prefers HY + IG OAS (equal-weight mean in bp). Falls back to BAA-AAA spread
    converted to approximate bp if OAS columns are missing.
    """
    oas_cols = [c for c in ["HY_OAS_bp", "IG_OAS_bp"] if c in df.columns]
    if oas_cols:
        credit = df[oas_cols].mean(axis=1, skipna=True)
        credit.name = "Credit"
        return credit

    if "BAA_AAA_spread_pct" in df.columns:
        # Convert percentage-point spread to bp-scale levels for continuity
        credit = df["BAA_AAA_spread_pct"] * 100.0
        credit.name = "Credit"
        return credit

    return pd.Series(dtype=float, name="Credit")


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

    frames = {}
    for sid, rename in [
        (AAA, "AAA_yield"),
        (BAA, "BAA_yield"),
        (HY_OAS, "HY_OAS_bp"),
        (IG_OAS, "IG_OAS_bp"),
    ]:
        try:
            frames[rename] = _to_monthly(get_series(sid)).rename(rename)
            print(f"✅ Fetched {sid} → {rename}")
        except Exception as e:
            print(f"⚠️ FRED fetch failed for {sid}: {e}")

    if not frames:
        print("⚠️ No credit series fetched.")
        return

    df = pd.concat(frames.values(), axis=1).dropna(how="all")

    if {"AAA_yield", "BAA_yield"}.issubset(df.columns):
        df["BAA_AAA_spread_pct"] = df["BAA_yield"] - df["AAA_yield"]

    df["Credit"] = build_credit_pillar(df)
    df.index.name = "date"

    # Prefer Credit as the leading column
    ordered = ["Credit"] + [c for c in df.columns if c != "Credit"]
    df = df[ordered]

    if df.empty or df["Credit"].isna().all():
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
