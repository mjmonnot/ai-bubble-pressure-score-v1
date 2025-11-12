# src/aibps/fetch_market.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import yfinance as yf


DATA_DIR = Path("data")
RAW_OUT = DATA_DIR / "raw" / "market_prices.csv"
PROC_OUT = DATA_DIR / "processed" / "market_processed.csv"

# Pull deep history — set as far back as you want (e.g., your 1980 birth-year!)
START = "1980-01-01"

# Broad, long-history proxies (all exist on Yahoo and go back decades):
# - ^GSPC = S&P 500 (long, stable history)
# - ^IXIC = Nasdaq Composite
# - ^NDX  = Nasdaq 100 (starts in the 1980s/1990s depending on vendor)
# You can add/remove tickers; the code will equal-weight whatever succeeds.
TICKERS: List[str] = ["^GSPC", "^IXIC", "^NDX"]


def _fetch_one(ticker: str, start: str) -> pd.Series | None:
    """Fetch one ticker's adjusted close as a monthly series."""
    try:
        df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    except Exception as e:
        print(f"⚠️ yfinance exception for {ticker}: {e}")
        return None

    if df is None or df.empty or "Close" not in df.columns:
        print(f"⚠️ Empty/invalid data for {ticker}; skipping.")
        return None

    s = df["Close"].copy()
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"

    # Convert to month-end frequency: last available close in each month
    s = s.resample("M").last().dropna()

    # Guard against all-NaN
    if s.empty:
        print(f"⚠️ No monthly data for {ticker} after resample; skipping.")
        return None

    # Return as a named Series (no .rename(...) to avoid previous pitfalls)
    s.name = ticker
    return s


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    PROC_OUT.parent.mkdir(parents=True, exist_ok=True)

    frames: List[pd.Series] = []
    for t in TICKERS:
        s = _fetch_one(t, START)
        if s is not None:
            frames.append(s)

    if not frames:
        print("❌ No market series fetched; aborting.")
        return

    # Wide panel of monthly levels
    wide = pd.concat(frames, axis=1).sort_index()
    wide.index.name = "date"

    # Persist raw multi-ticker panel for reference/debug
    wide.to_csv(RAW_OUT)
    print(f"💾 Wrote {RAW_OUT} with columns: {list(wide.columns)}")
    print(f"   Date span: {wide.index.min().date()} → {wide.index.max().date()}")

    # Build an equal-weighted, rebased composite so scales are comparable
    # 1) Rebase each ticker to 100 at its first valid point
    rebased = wide.copy()
    for col in rebased.columns:
        first_valid = rebased[col].dropna().iloc[0] if rebased[col].notna().any() else np.nan
        if np.isfinite(first_valid) and first_valid != 0:
            rebased[col] = (rebased[col] / first_valid) * 100.0
        else:
            rebased[col] = np.nan

    # 2) Equal-weight across available tickers each month
    market_eqw = rebased.mean(axis=1, skipna=True)

    # 3) Clean output frame for compute.py
    out = pd.DataFrame({"Market": market_eqw}).dropna(how="all")
    out.index.name = "date"

    # Sanity prints
    print("---- Market composite tail (rebased, EW) ----")
    print(out.tail(6))
    print(f"✅ Market composite span: {out.index.min().date()} → {out.index.max().date()}")

    out.to_csv(PROC_OUT)
    print(f"💾 Wrote {PROC_OUT} (rows={len(out)})")


if __name__ == "__main__":
    main()
