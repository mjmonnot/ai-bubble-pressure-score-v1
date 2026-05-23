"""
fetch_market.py

Downloads market series used in the AI Bubble Pressure Score (AIBPS)
and converts them into monthly frequency data.

Fixes:
- pandas >=2.2 deprecates/removes "M" frequency alias
- uses "ME" (month end) instead
- safer handling of Series/DataFrame returns from yfinance
- explicit datetime index handling
"""

from pathlib import Path

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

START = "2000-01-01"

TICKERS = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "VIX": "^VIX",
    "NVDA": "NVDA",
    "BTC": "BTC-USD",
}

RAW_DIR = Path("data/raw")
PROC_DIR = Path("data/processed")

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# FETCH ONE SERIES
# ---------------------------------------------------------------------

def _fetch_one(ticker: str, start: str) -> pd.Series:
    """
    Download one ticker from Yahoo Finance and convert to
    month-end frequency.
    """

    df = yf.download(
        ticker,
        start=start,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for ticker: {ticker}")

    # yfinance sometimes returns DataFrame columns with multi-index
    # or a single-column DataFrame
    if "Close" in df.columns:
        s = df["Close"]
    else:
        # fallback to first numeric column
        s = df.select_dtypes(include="number").iloc[:, 0]

    # ensure Series
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]

    # clean index
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    # IMPORTANT:
    # pandas >=2.2 removed "M"
    # use "ME" (month-end) instead
    s = s.resample("ME").last().dropna()

    return s


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():

    series_list = []

    for name, ticker in TICKERS.items():

        print(f"Fetching {name} ({ticker})...")

        try:
            s = _fetch_one(ticker, START)

            df = pd.DataFrame({
                "Date": s.index,
                name: s.values,
            })

            df = df.set_index("Date")

            series_list.append(df)

            print(f"  OK: {len(df)} rows")

        except Exception as e:
            print(f"  FAILED: {e}")

    if not series_list:
        raise RuntimeError("No market series downloaded successfully.")

    # combine all series
    market = pd.concat(series_list, axis=1)

    # ensure datetime index
    market.index = pd.to_datetime(market.index)
    market.index.name = "Date"

    # sort
    market = market.sort_index()

    # save raw
    raw_path = RAW_DIR / "market_prices.csv"
    market.to_csv(raw_path)

    # simple processed version
    processed = market.copy()

    proc_path = PROC_DIR / "market_processed.csv"
    processed.to_csv(proc_path)

    print("\nSaved:")
    print(f"  Raw:       {raw_path}")
    print(f"  Processed: {proc_path}")

    print("\nTail:")
    print(processed.tail())


# ---------------------------------------------------------------------
# ENTRY
# ---------------------------------------------------------------------

if __name__ == "__main__":
    main()
