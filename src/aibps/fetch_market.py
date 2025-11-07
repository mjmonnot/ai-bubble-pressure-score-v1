# src/aibps/fetch_market.py
"""
Fetches market proxies via yfinance, with safe fallbacks.
Writes:
  - data/raw/market_prices.csv
  - data/processed/market_processed.csv  (includes percentile columns)
"""
import os, sys, time
import pandas as pd
import numpy as np

RAW_DIR = os.path.join("data", "raw")
PRO_DIR = os.path.join("data", "processed")
SAMPLE_FILE = os.path.join("data", "sample", "market_prices_sample.csv")  # optional

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PRO_DIR, exist_ok=True)

def download_live(start="2015-01-01"):
    try:
        import yfinance as yf
        tickers = ["SOXX", "QQQ"]
        data = {}
        for t in tickers:
            s = yf.download(t, start=start, auto_adjust=True, progress=False)["Close"].rename(t).to_frame()
            data[t] = s
        df = pd.concat(data.values(), axis=1)
        df.index.name = "Date"
        return df
    except Exception as e:
        print(f"⚠️ yfinance fetch failed: {e}")
        return None

def load_sample_or_generate():
    if os.path.exists(SAMPLE_FILE):
        print(f"ℹ️ Using sample market file: {SAMPLE_FILE}")
        return pd.read_csv(SAMPLE_FILE, index_col=0, parse_dates=True)
    # generate simple synthetic sample to keep pipeline running
    print("ℹ️ No sample market file found. Generating synthetic series.")
    idx = pd.date_range("2015-01-31", "2025-12-31", freq="M")
    soxx = np.linspace(100, 400, len(idx)) + np.random.normal(0, 10, len(idx))
    qqq  = np.linspace(90,  380, len(idx)) + np.random.normal(0, 10, len(idx))
    df = pd.DataFrame({"SOXX": soxx, "QQQ": qqq}, index=idx)
    df.index.name = "Date"
    return df

def pct_rank(s, invert=False):
    r = s.rank(pct=True) * 100
    return 100 - r if invert else r

def main():
    start = time.time()
    df = download_live()
    if df is None or df.empty:
        df = load_sample_or_generate()

    raw_path = os.path.join(RAW_DIR, "market_prices.csv")
    df.to_csv(raw_path)
    print(f"💾 Saved raw market data → {raw_path}")

    # Simple proxies: 1y returns (annualized) → percentile
    m = df.copy()
    m["SOXX_ret_1y"] = m["SOXX"].pct_change(252) * 100
    m["QQQ_ret_1y"]  = m["QQQ"].pct_change(252)  * 100
    out = pd.DataFrame({
        "MKT_SOXX_1y_pct": pct_rank(m["SOXX_ret_1y"]),
        "MKT_QQQ_1y_pct":  pct_rank(m["QQQ_ret_1y"]),
    }).dropna()

    pro_path = os.path.join(PRO_DIR, "market_processed.csv")
    out.to_csv(pro_path)
    print(f"💾 Saved processed market data → {pro_path}")
    print(f"⏱ Done in {time.time()-start:.1f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ fetch_market.py failed: {e}")
        sys.exit(1)
