# src/aibps/compute.py
import os, sys, time
import pandas as pd
import numpy as np

PRO_DIR = os.path.join("data", "processed")
SAMPLE = os.path.join("data", "sample", "aibps_monthly_sample.csv")
os.makedirs(PRO_DIR, exist_ok=True)

def safe_read(path, **kwargs):
    if os.path.exists(path):
        try:
            return pd.read_csv(path, **kwargs)
        except Exception as e:
            print(f"⚠️ Failed to read {path}: {e}")
    return None

def main():
    start = time.time()
    market = safe_read(os.path.join(PRO_DIR, "market_processed.csv"), index_col=0, parse_dates=True)
    credit = safe_read(os.path.join(PRO_DIR, "credit_fred_processed.csv"), index_col=0, parse_dates=True)

    if market is None and credit is None:
        if os.path.exists(SAMPLE):
            print("ℹ️ Inputs missing → using sample composite.")
            df = pd.read_csv(SAMPLE, index_col=0, parse_dates=True)
            df.to_csv(os.path.join(PRO_DIR, "aibps_monthly.csv"))
            print("💾 Wrote sample composite → data/processed/aibps_monthly.csv")
            return
        raise RuntimeError("No inputs and no sample composite found.")

    # Merge monthly processed inputs
    frames = []
    if market is not None: frames.append(market)
    if credit is not None: frames.append(credit)
    df = pd.concat(frames, axis=1).sort_index()

    # Map processed columns to pillars (v0.1)
    out = pd.DataFrame(index=df.index)

    mkt_cols = [c for c in df.columns if c.startswith("MKT_")]
    if mkt_cols:
        out["Market"] = df[mkt_cols].mean(axis=1)

    cred_cols = [c for c in df.columns if c.endswith("_pct") and ("OAS" in c or "CREDIT" in c)]
    if cred_cols:
        out["Credit"] = df[cred_cols].mean(axis=1)

    # Only use pillars that actually exist; do NOT inject 55s
    pillars = [c for c in ["Market","Credit","Capex_Supply","Infra","Adoption"] if c in out.columns]
    if not pillars:
        raise RuntimeError("No pillar columns available after mapping.")

    # Default weights (renormalize to present pillars only)
    default_w = {"Market":0.25,"Capex_Supply":0.25,"Infra":0.20,"Adoption":0.15,"Credit":0.15}
    w_vec = np.array([default_w[p] for p in pillars], dtype=float)
    w_vec = w_vec / w_vec.sum()

    out = out[pillars].dropna(how="all")
    out["AIBPS"] = (out[pillars] * w_vec).sum(axis=1)
    out["AIBPS_RA"] = out["AIBPS"].rolling(3, min_periods=1).mean()

    out.to_csv(os.path.join(PRO_DIR, "aibps_monthly.csv"))
    print("💾 Wrote composite → data/processed/aibps_monthly.csv")
    print(f"⏱ Done in {time.time()-start:.1f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ compute.py failed: {e}")
        sys.exit(1)
