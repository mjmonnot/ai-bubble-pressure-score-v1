"""
fetch_market.py

Fetches market data for AIBPS and creates:

1. data/raw/market_prices.csv
   - Monthly month-end raw price/index levels

2. data/processed/market_processed.csv
   - Raw levels plus market-derived component/debug columns

Fix:
- pandas newer versions no longer support resample("M")
- use resample("ME") for month-end
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


START = "2000-01-01"

TICKERS = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "VIX": "^VIX",
    "NVDA": "NVDA",
    "BTC": "BTC-USD",
}

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _fetch_one(ticker: str, start: str) -> pd.Series:
    """Fetch one ticker and return month-end close series."""

    df = yf.download(
        ticker,
        start=start,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for {ticker}")

    if "Close" in df.columns:
        s = df["Close"]
    else:
        s = df.select_dtypes(include="number").iloc[:, 0]

    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]

    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    # pandas >=2.2: "M" replaced by "ME"
    s = s.resample("ME").last().dropna()

    return s


def _zscore(s: pd.Series, window: int = 60) -> pd.Series:
    """Rolling z-score."""
    mean = s.rolling(window, min_periods=24).mean()
    std = s.rolling(window, min_periods=24).std()
    return (s - mean) / std.replace(0, np.nan)


def _make_processed(market: pd.DataFrame) -> pd.DataFrame:
    """Create processed market features and debug component columns."""

    processed = market.copy()

    # Generic features for every market series
    for col in market.columns:
        processed[f"{col}_ret_1m"] = market[col].pct_change()
        processed[f"{col}_mom_12m"] = market[col].pct_change(12)
        processed[f"{col}_vol_12m"] = market[col].pct_change().rolling(12, min_periods=6).std()
        processed[f"{col}_drawdown"] = market[col] / market[col].cummax() - 1

    # Explicit market component columns for Streamlit debug panel
    if "NASDAQ" in market.columns:
        processed["market_nasdaq_momentum_12m"] = market["NASDAQ"].pct_change(12)
        processed["market_nasdaq_momentum_12m_z"] = _zscore(
            processed["market_nasdaq_momentum_12m"]
        )

    if "SP500" in market.columns:
        processed["market_sp500_momentum_12m"] = market["SP500"].pct_change(12)
        processed["market_sp500_momentum_12m_z"] = _zscore(
            processed["market_sp500_momentum_12m"]
        )

    if "NVDA" in market.columns:
        processed["market_nvda_momentum_12m"] = market["NVDA"].pct_change(12)
        processed["market_nvda_momentum_12m_z"] = _zscore(
            processed["market_nvda_momentum_12m"]
        )

    if "BTC" in market.columns:
        processed["market_btc_momentum_12m"] = market["BTC"].pct_change(12)
        processed["market_btc_momentum_12m_z"] = _zscore(
            processed["market_btc_momentum_12m"]
        )

    if "VIX" in market.columns:
        processed["market_vix_level"] = market["VIX"]
        processed["market_vix_level_z"] = _zscore(processed["market_vix_level"])

    # Composite market pressure debug score
    component_cols = [
        c
        for c in processed.columns
        if c.startswith("market_") and c.endswith("_z")
    ]

    if component_cols:
        processed["market_component_composite_z"] = processed[component_cols].mean(axis=1)

    processed.index.name = "Date"
    processed = processed.sort_index()

    return processed


def main() -> None:
    series_list = []

    for name, ticker in TICKERS.items():
        print(f"Fetching {name} ({ticker})...")

        try:
            s = _fetch_one(ticker, START)

            one = pd.DataFrame({name: s})
            one.index.name = "Date"
            series_list.append(one)

            print(f"  OK: {len(one)} rows")

        except Exception as e:
            print(f"  FAILED: {ticker}: {e}")

    if not series_list:
        raise RuntimeError("No market series downloaded successfully.")

    market = pd.concat(series_list, axis=1)
    market.index = pd.to_datetime(market.index)
    market.index.name = "Date"
    market = market.sort_index()

    raw_path = RAW_DIR / "market_prices.csv"
    market.to_csv(raw_path)

    processed = _make_processed(market)

    processed_path = PROCESSED_DIR / "market_processed.csv"
    processed.to_csv(processed_path)

    print("\nSaved:")
    print(f"  Raw market prices: {raw_path}")
    print(f"  Processed market:  {processed_path}")

    print("\nProcessed columns:")
    for col in processed.columns:
        print(f"  - {col}")

    print("\nTail:")
    print(processed.tail())


if __name__ == "__main__":
    main()
