# src/aibps/fetch_credit.py
"""
Fetch credit conditions for AIBPS.

Writes data/processed/credit_fred_processed.csv with:
- AAA_yield, BAA_yield, BAA_AAA_spread_pct (diagnostics / long-history backbone)
- HY_OAS_bp, IG_OAS_bp (ICE BofA OAS; FRED may truncate to ~3y)
- Credit  ← canonical pillar column for compute.py

Credit construction:
- Prefer equal-weight HY + IG OAS when coverage is deep enough for rolling norms
- Otherwise fall back to BAA–AAA spread (long history from 1980)
- Wider spreads → higher funding stress → higher Credit pressure

Note: FRED currently limits some ICE BofA OAS series to recent observations only,
so the BAA–AAA fallback is required for multi-decade AIBPS history.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


DATA_DIR = Path("data")
PROC_OUT = DATA_DIR / "processed" / "credit_fred_processed.csv"

# FRED series IDs
AAA = "AAA"              # Moody's Seasoned Aaa Corporate Bond Yield (%)
BAA = "BAA"              # Moody's Seasoned Baa Corporate Bond Yield (%)
HY_OAS = "BAMLH0A0HYM2"  # ICE BofA US High Yield OAS
IG_OAS = "BAMLC0A0CM"    # ICE BofA US Corporate (IG) OAS

# Minimum non-null months before OAS is trusted as the Credit backbone
MIN_OAS_HISTORY = 120

START = "1980-01-01"


def _to_monthly(s: pd.Series) -> pd.Series:
    s = s.sort_index()
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"
    return s.resample("ME").last()


def build_credit_pillar(df: pd.DataFrame, min_oas_history: int = MIN_OAS_HISTORY) -> pd.Series:
    """
    Build Credit from OAS when history is deep enough; else BAA–AAA spread.

    OAS values from FRED are percent (not bp); BAA–AAA is also in percentage
    points. Rolling-z normalization makes absolute units secondary, but we keep
    each series on its native scale and pick one backbone for continuity.
    """
    oas_cols = [c for c in ["HY_OAS_bp", "IG_OAS_bp"] if c in df.columns]
    oas = df[oas_cols].mean(axis=1, skipna=True) if oas_cols else None
    oas_n = int(oas.notna().sum()) if oas is not None else 0

    baa_aaa = None
    if "BAA_AAA_spread_pct" in df.columns:
        # Scale to similar magnitude as OAS percent levels for readability
        baa_aaa = (df["BAA_AAA_spread_pct"] * 100.0).rename("Credit")
    baa_n = int(baa_aaa.notna().sum()) if baa_aaa is not None else 0

    if oas is not None and oas_n >= min_oas_history:
        credit = oas.rename("Credit")
        print(f"✅ Credit backbone: OAS mean of {oas_cols} (n={oas_n})")
        return credit

    if baa_aaa is not None and baa_n > 0:
        credit = baa_aaa.copy()
        # Overlay recent OAS onto the long backbone after mean-aligning on overlap
        if oas is not None and oas_n > 0:
            overlap = oas.notna() & credit.notna()
            if int(overlap.sum()) >= 12:
                oas_mu = float(oas.loc[overlap].mean())
                baa_mu = float(credit.loc[overlap].mean())
                if oas_mu != 0:
                    aligned = oas * (baa_mu / oas_mu)
                    credit = credit.where(oas.isna(), aligned)
                    print(
                        f"ℹ️ Credit backbone: BAA–AAA with OAS overlay "
                        f"(baa_n={baa_n}, oas_n={oas_n}, overlap={int(overlap.sum())})"
                    )
                else:
                    print(f"ℹ️ Credit backbone: BAA–AAA only (n={baa_n}); OAS mean was 0")
            else:
                print(
                    f"ℹ️ Credit backbone: BAA–AAA only (n={baa_n}); "
                    f"OAS too short to overlay (n={oas_n})"
                )
        else:
            print(f"ℹ️ Credit backbone: BAA–AAA only (n={baa_n})")
        return credit

    if oas is not None and oas_n > 0:
        print(f"⚠️ Credit backbone: short OAS only (n={oas_n} < {min_oas_history})")
        return oas.rename("Credit")

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
            series = _to_monthly(get_series(sid)).rename(rename)
            frames[rename] = series
            print(
                f"✅ Fetched {sid} → {rename} "
                f"(n={int(series.notna().sum())}, "
                f"{series.first_valid_index().date()} → {series.last_valid_index().date()})"
            )
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
        f"💾 Wrote {PROC_OUT} (rows={len(df)}, Credit n={int(df['Credit'].notna().sum())}) "
        f"span: {df.index.min().date()} → {df.index.max().date()}"
    )


if __name__ == "__main__":
    main()
