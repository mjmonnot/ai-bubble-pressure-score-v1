# src/aibps/compute.py
"""
Compute AIBPS composite from processed pillar inputs.

Pillars:
- Market
- Credit
- Capex_Supply (from manual + macro)
- Infra (from manual + macro)
- Adoption
- Sentiment

Canonical normalization:
- All pillars use "rolling_z_sigmoid" -> 0–100 heat score.
- Windows differ by pillar:
    - Market, Credit: 120 months  (~10 years, long-cycle)
    - Capex_Supply, Infra: 36 months (~3 years, investment cycles)
    - Adoption, Sentiment: 24 months (~2 years, hype/adoption pulses)
"""

import os
import sys
import time

import numpy as np
import pandas as pd

# Make sure "src" is on sys.path so we can import aibps.normalize
HERE = os.path.dirname(__file__)              # .../src/aibps
SRC_ROOT = os.path.abspath(os.path.join(HERE, ".."))  # .../src
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from aibps.normalize import normalize_series


PROC_DIR = os.path.join("data", "processed")
OUT_PATH = os.path.join(PROC_DIR, "aibps_monthly.csv")


def _read_processed(filename: str) -> pd.DataFrame | None:
    path = os.path.join(PROC_DIR, filename)
    if not os.path.exists(path):
        print(f"ℹ️ {filename} missing.")
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
        if df.empty:
            print(f"ℹ️ {filename} exists but is empty.")
            return None
        df.index.name = "date"
        return df
    except Exception as e:
        print(f"❌ Error reading {filename}: {e}")
        return None


def main():
    t0 = time.time()

    # ---- Load pillar inputs ----
    market = _read_processed("market_processed.csv")
    credit = _read_processed("credit_fred_processed.csv")
    capex = _read_processed("capex_processed.csv")
    macro_capex = _read_processed("macro_capex_processed.csv")
    infra = _read_processed("infra_processed.csv")
    infra_macro = _read_processed("infra_macro_processed.csv")
    adoption = _read_processed("adoption_processed.csv")
    sentiment = _read_processed("sentiment_processed.csv")

    frames = [x for x in [market, credit, capex, macro_capex, infra, infra_macro, adoption, sentiment] if x is not None]
    if not frames:
        print("❌ No processed pillar data found. Aborting.")
        sys.exit(1)

    # Build a monthly date index covering all available data
    start = min(df.index.min() for df in frames)
    end = max(df.index.max() for df in frames)
    idx = pd.date_range(start=start.to_period("M").to_timestamp("M"),
                        end=end.to_period("M").to_timestamp("M"),
                        freq="M")
    base = pd.DataFrame(index=idx)
    base.index.name = "date"

    # ---- Attach "raw-ish" pillar series ----
    # We treat the main processed columns as raw signals suitable for normalization.
    # If your processed files are already normalized, this will re-normalize them in a consistent way.

    # Market
    if market is not None:
        col = "Market" if "Market" in market.columns else market.columns[0]
        base["Market_raw"] = market[col].reindex(base.index)

    # Credit
    if credit is not None:
        col = "Credit" if "Credit" in credit.columns else credit.columns[0]
        base["Credit_raw"] = credit[col].reindex(base.index)

    # Capex (manual)
    if capex is not None:
        # Accept either "Capex_Supply" or "Capex_Supply_Manual"
        if "Capex_Supply" in capex.columns:
            base["Capex_Supply_Manual_raw"] = capex["Capex_Supply"].reindex(base.index)
        elif "Capex_Supply_Manual" in capex.columns:
            base["Capex_Supply_Manual_raw"] = capex["Capex_Supply_Manual"].reindex(base.index)

    # Capex (macro)
    if macro_capex is not None:
        if "Capex_Supply_Macro" in macro_capex.columns:
            base["Capex_Supply_Macro_raw"] = macro_capex["Capex_Supply_Macro"].reindex(base.index)

    # Infra (manual)
    if infra is not None:
        if "Infra" in infra.columns:
            base["Infra_Manual_raw"] = infra["Infra"].reindex(base.index)
        elif "Infra_Manual" in infra.columns:
            base["Infra_Manual_raw"] = infra["Infra_Manual"].reindex(base.index)

    # Infra (macro)
    if infra_macro is not None:
        if "Infra_Macro" in infra_macro.columns:
            base["Infra_Macro_raw"] = infra_macro["Infra_Macro"].reindex(base.index)

    # Adoption
    if adoption is not None:
        if "Adoption" in adoption.columns:
            base["Adoption_raw"] = adoption["Adoption"].reindex(base.index)

    # Sentiment
    if sentiment is not None:
        if "Sentiment" in sentiment.columns:
            base["Sentiment_raw"] = sentiment["Sentiment"].reindex(base.index)

    # ---- Combine manual/macro where relevant ----
    # Capex_Supply = mean of manual + macro where both exist
    if ("Capex_Supply_Manual_raw" in base.columns) or ("Capex_Supply_Macro_raw" in base.columns):
        cols = [c for c in ["Capex_Supply_Manual_raw", "Capex_Supply_Macro_raw"] if c in base.columns]
        base["Capex_Supply_raw"] = base[cols].mean(axis=1, skipna=True)

    # Infra = mean of manual + macro where both exist
    if ("Infra_Manual_raw" in base.columns) or ("Infra_Macro_raw" in base.columns):
        cols = [c for c in ["Infra_Manual_raw", "Infra_Macro_raw"] if c in base.columns]
        base["Infra_raw"] = base[cols].mean(axis=1, skipna=True)

    # ---- Normalization config (rolling_z_sigmoid for all pillars) ----

    # Windows in months for each pillar
    norm_windows = {
        "Market": 120,        # ~10 years
        "Credit": 120,        # ~10 years
        "Capex_Supply": 36,   # ~3 years
        "Infra": 36,          # ~3 years
        "Adoption": 24,       # ~2 years
        "Sentiment": 24,      # ~2 years
    }

    normalized_pillars = []

    for name, window in norm_windows.items():
        raw_col = f"{name}_raw"
        if raw_col not in base.columns:
            print(f"ℹ️ No raw series for {name}; skipping normalization for this pillar.")
            continue

        print(f"🔧 Normalizing {name} using rolling_z_sigmoid (window={window})")
        norm_series = normalize_series(
            base[raw_col],
            method="rolling_z_sigmoid",
            window=window,
            z_clip=4.0,
        )
        base[name] = norm_series
        normalized_pillars.append(name)

    if not normalized_pillars:
        print("❌ No pillars normalized; cannot compute AIBPS.")
        sys.exit(1)

    # ---- Compute AIBPS composite ----

    # Equal weights across all available normalized pillars
    w = np.ones(len(normalized_pillars), dtype=float)
    w = w / w.sum()
    weights = pd.Series(w, index=normalized_pillars)

    print("---- Pillars used in composite ----")
    print(normalized_pillars)
    print("---- Weights ----")
    print(weights)

    # Composite (AIBPS) and 3-month rolling average (AIBPS_RA)
    base["AIBPS"] = base[normalized_pillars].mul(weights, axis=1).sum(axis=1, skipna=True)
    base["AIBPS_RA"] = base["AIBPS"].rolling(3, min_periods=1).mean()

    # Drop rows that are completely NaN for composite
    out = base.dropna(subset=["AIBPS"], how="all")

    # ---- Debug tail ----
    print("---- Columns in composite output ----")
    print(list(out.columns))
    print("---- Tail (pillars + AIBPS + AIBPS_RA) ----")
    cols_for_tail = normalized_pillars + ["AIBPS", "AIBPS_RA"]
    cols_for_tail = [c for c in cols_for_tail if c in out.columns]
    print(out[cols_for_tail].tail(6))

    # ---- Write to disk ----
    os.makedirs(PROC_DIR, exist_ok=True)
    out.to_csv(OUT_PATH)
    print(f"💾 Wrote {OUT_PATH} (rows={len(out)}) in {time.time() - t0:.2f}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ compute.py: {e}")
        sys.exit(1)
