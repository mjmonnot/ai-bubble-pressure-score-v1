# src/aibps/fetch_sentiment.py
# Sentiment pillar = AI hype INTENSITY (unipolar)
# - Uses Google Trends search interest for AI-related terms
# - Aggregates to monthly, then converts to 0–100 percentile vs history
# - Output: data/processed/sentiment_processed.csv with column "Sentiment"
#
# Interpretation:
#   0   = AI barely discussed
#   100 = AI dominates public attention (search interest peak)

import os
import sys
import time
import pandas as pd
import numpy as np
from pytrends.request import TrendReq

OUT = os.path.join("data", "processed", "sentiment_processed.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# Core AI search terms (you can tweak these later)
TERMS = [
    "artificial intelligence",
    "ai",
    "chatgpt",
    "openai",
    "generative ai",
    "machine learning",
]


def expanding_pct(series: pd.Series) -> pd.Series:
    """Expanding percentile: for each t, percentile of current value vs all past."""
    series = series.dropna()
    vals = []
    idx = []
    for i in range(len(series)):
        window = series.iloc[: i + 1]
        pct = window.rank(pct=True).iloc[-1] * 100.0
        vals.append(float(pct))
        idx.append(series.index[i])
    return pd.Series(vals, index=idx)


def main():
    t0 = time.time()

    try:
        pytrends = TrendReq(hl="en-US", tz=360)
    except Exception as e:
        print(f"❌ pytrends init failed: {e}")
        # Write empty file so downstream code doesn't crash
        pd.DataFrame(columns=["Sentiment"]).to_csv(OUT)
        sys.exit(1)

    # Use dynamic end date so we don't query far into the future
    end_str = pd.Timestamp.today().strftime("%Y-%m-%d")
    timeframe = f"2015-01-01 {end_str}"
    print(f"Using Google Trends timeframe: {timeframe}")

    series_list = []

    for term in TERMS:
        try:
            pytrends.build_payload([term], timeframe=timeframe, geo="")
            df_t = pytrends.interest_over_time()
            if df_t is None or df_t.empty or term not in df_t.columns:
                print(f"⚠️ No trends data for term: {term}")
                continue

            s = df_t[term].copy()
            s.name = term
            series_list.append(s)
            print(f"  ✓ fetched {len(s)} points for '{term}'")
        except Exception as e:
            print(f"⚠️ pytrends failed for '{term}': {e}")

    # ---- Combine ----
    if not series_list:
        print("⚠️ No Google Trends series fetched.")
        if os.path.exists(OUT):
            print("⚠️ Keeping existing sentiment_processed.csv (no overwrite).")
            return
        else:
            print("⚠️ No existing sentiment file; writing empty Sentiment file.")
            pd.DataFrame(columns=["Sentiment"]).to_csv(OUT)
            return

    df = pd.concat(series_list, axis=1).sort_index()
    df["Sentiment"] = df.mean(axis=1, skipna=True)
    df = df[["Sentiment"]].dropna()

    print(df.tail(10))
    df.to_csv(OUT)
    print(f"💾 Wrote {OUT} (rows={len(df)})")



    # Combine all terms into one dataframe
    df_all = pd.concat(series_list, axis=1)
    df_all.index = pd.to_datetime(df_all.index)
    df_all = df_all.sort_index()

    # Resample to monthly mean to smooth weekly noise
    monthly = df_all.resample("M").mean()
    monthly.index.name = "date"

    # Aggregate across terms to a single "hype intensity" series
    monthly["hype_mean"] = monthly.mean(axis=1, skipna=True)

    # Convert to expanding percentile (0–100)
    hype = expanding_pct(monthly["hype_mean"]).clip(1, 99)
    hype.index.name = "date"
    hype.name = "Sentiment"

    out = pd.DataFrame({"Sentiment": hype}).dropna()
    out.to_csv(OUT)

    print(f"💾 Wrote {OUT} ({len(out)} rows) using Google Trends terms: {TERMS}")
    print("Tail:")
    print(out.tail(6))
    print(f"⏱ Done in {time.time() - t0:.2f}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ fetch_sentiment.py: {e}")
        sys.exit(1)
