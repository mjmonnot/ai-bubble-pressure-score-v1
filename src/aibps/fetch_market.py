# MARKER: fetch_market.py SAFE v2 (no .rename anywhere)
import os, sys, time
import pandas as pd, numpy as np

RAW_DIR = os.path.join("data","raw"); PRO_DIR = os.path.join("data","processed")
os.makedirs(RAW_DIR, exist_ok=True); os.makedirs(PRO_DIR, exist_ok=True)

START = "2015-01-01"; TICKERS = ["SOXX","QQQ"]

def download_live():
    try:
        import yfinance as yf
        frames = []
        for t in TICKERS:
            df = yf.download(t, start=START, auto_adjust=True, progress=False)
            if df is None or df.empty or "Close" not in df:
                print(f"⚠️ empty for {t}; skipping"); continue
            s = df["Close"]; s.index = pd.to_datetime(s.index); s.index.name = "Date"
            frames.append(s.to_frame(name=t))  # ← SAFE naming (no .rename)
        if not frames: return None
        out = pd.concat(frames, axis=1); out.index.name = "Date"; return out
    except Exception as e:
        print(f"⚠️ yfinance failed: {e}"); return None

def load_sample_or_generate():
    sample = "data/sample/market_prices_sample.csv"
    if os.path.exists(sample): return pd.read_csv(sample, index_col=0, parse_dates=True)
    idx = pd.date_range("2015-01-31","2025-12-31",freq="M")
    soxx = np.linspace(100,400,len(idx))+np.random.normal(0,10,len(idx))
    qqq  = np.linspace( 90,380,len(idx))+np.random.normal(0,10,len(idx))
    df = pd.DataFrame({"SOXX":soxx,"QQQ":qqq}, index=idx); df.index.name="Date"; return df

def pct_rank(s, invert=False):
    r = s.rank(pct=True)*100; return 100-r if invert else r

def main():
    print("RUNNING:", __file__)
    print("MARKER present? SAFE v2")
    mkt = download_live() or load_sample_or_generate()
    raw_path = os.path.join(RAW_DIR,"market_prices.csv"); mkt.to_csv(raw_path)
    print(f"💾 raw → {raw_path}")
    one_year = mkt.pct_change(252)*100
    ret_m = one_year.resample("M").last()
    out = pd.DataFrame({
        "MKT_SOXX_1y_pct": pct_rank(ret_m["SOXX"]),
        "MKT_QQQ_1y_pct":  pct_rank(ret_m["QQQ"]),
    }).dropna()
    pro_path = os.path.join(PRO_DIR,"market_processed.csv"); out.to_csv(pro_path)
    print(f"💾 processed → {pro_path}")

if __name__=="__main__":
    try: main()
    except Exception as e: print(f"❌ {e}"); sys.exit(1)
