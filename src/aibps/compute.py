# src/aibps/compute.py
# Robust compute for AIBPS:
# - Reads processed pillar inputs from data/processed/
# - Builds Market, Credit, Capex_Supply (manual + macro blend)
# - Forward-fills Capex up to 6 months so it doesn't disappear at the tail
# - Keeps Capex_Supply_Manual / Capex_Supply_Macro for debugging
# - Writes data/processed/aibps_monthly.csv

import os, sys, time
import numpy as np
import pandas as pd

PRO_DIR = os.path.join("data", "processed")
OUT = os.path.join(PRO_DIR, "aibps_monthly.csv")
os.makedirs(PRO_DIR, exist_ok=True)

def read_proc(filename: str) -> pd.DataFrame | None:
    path = os.path.join(PRO_DIR, filename)
    if not os.path.exists(path):
        print(f"ℹ️ {path} missing")
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.empty or df.dropna(how="all").empty:
            print(f"ℹ️ {filename} is empty or all-NaN; ignoring.")
            return None
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors="coerce")
        df = df[~df.index.isna()].sort_index()
        # Coerce numeric
        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        # Normalize to month-end
        df.index = df.index.to_period("M").to_timestamp("M")
        return df
    except Exception as e:
        print(f"⚠️ read_proc({filename}) failed: {e}")
        return None

def build_market(mkt: pd.DataFrame | None) -> pd.DataFrame | None:
    if mkt is None or mkt.empty:
        return None
    mcols = [c for c in mkt.columns if c.startswith("MKT_")]
    if not mcols:
        mcols = [c for c in mkt.columns if pd.api.types.is_numeric_dtype(mkt[c])]
    if not mcols:
        return None
    ser = mkt[mcols].mean(axis=1, skipna=True)
    return ser.to_frame("Market")

def build_credit(crd: pd.DataFrame | None) -> pd.DataFrame | None:
    if crd is None or crd.empty:
        return None
    ccols = [c for c in crd.columns if c.endswith("_pct")]
    if not ccols:
        ccols = [c for c in crd.columns if pd.api.types.is_numeric_dtype(crd[c])]
    if not ccols:
        return None
    ser = crd[ccols].mean(axis=1, skipna=True)
    return ser.to_frame("Credit")

def main():
    t0 = time.time()

    # ---- Load processed sources (optional ones may be missing) ----
    mkt   = read_proc("market_processed.csv")
    crd   = read_proc("credit_fred_processed.csv")
    cap   = read_proc("capex_processed.csv")          # manual / corporate
    capM  = read_proc("macro_capex_processed.csv")    # macro FRED
    infra = read_proc("infra_processed.csv")
    adop  = read_proc("adoption_processed.csv")
    sent  = read_proc("sentiment_processed.csv")

    pieces = []

    # ---- Market pillar ----
    mk = build_market(mkt)
    if mk is not None:
        pieces.append(mk)

    # ---- Credit pillar ----
    cr = build_credit(crd)
    if cr is not None:
        pieces.append(cr)

    # ---- Capex components & blended pillar ----
    cap_sources = []
    cap_manual = None
    cap_macro  = None

    if cap is not None:
        if "Capex_Supply" in cap.columns:
            cap_manual = cap["Capex_Supply"].rename("Capex_Supply_Manual")
            cap_sources.append(cap_manual.rename("Capex_Supply"))
        else:
            print(f"ℹ️ capex_processed.csv columns: {list(cap.columns)}")

    if capM is not None:
        if "Capex_Supply_Macro" in capM.columns:
            cap_macro = capM["Capex_Supply_Macro"].rename("Capex_Supply_Macro")
            cap_sources.append(cap_macro.rename("Capex_Supply"))
        else:
            print(f"ℹ️ macro_capex_processed.csv columns: {list(capM.columns)}")

    if cap_sources:
        cap_blend = (
            pd.concat(cap_sources, axis=1)
            .mean(axis=1, skipna=True)
            .to_frame("Capex_Supply")
        )
        cap_cols = [cap_blend]
        if cap_manual is not None:
            cap_cols.append(cap_manual.to_frame())
        if cap_macro is not None:
            cap_cols.append(cap_macro.to_frame())
        cap_full = pd.concat(cap_cols, axis=1)
        pieces.append(cap_full)

# ---- Infra pillar ----
    infraM = read_proc("infra_macro_processed.csv")
   
# ---- Infra components & blended pillar ----
    infra_sources = []
    infra_manual = None
    infra_macro  = None

    if infra is not None and "Infra" in infra.columns:
        infra_manual = infra["Infra"].rename("Infra_Manual")
        infra_sources.append(infra_manual.rename("Infra"))

    if infraM is not None and "Infra_Macro" in infraM.columns:
        infra_macro = infraM["Infra_Macro"].rename("Infra_Macro")
        infra_sources.append(infra_macro.rename("Infra"))

    if infra_sources:
        infra_blend = (
            pd.concat(infra_sources, axis=1)
            .mean(axis=1, skipna=True)
            .to_frame("Infra")
        )
        infra_cols = [infra_blend]
        if infra_manual is not None:
            infra_cols.append(infra_manual.to_frame())
        if infra_macro is not None:
            infra_cols.append(infra_macro.to_frame())
        infra_full = pd.concat(infra_cols, axis=1)
        pieces.append(infra_full)

        
    if adop is not None and "Adoption" in adop.columns:
        pieces.append(adop[["Adoption"]])

    if not pieces:
        raise RuntimeError("No pillar inputs found. Check processed CSVs in data/processed/.")

    # ---- Join all pieces on month-end index ----
    df = pd.concat(pieces, axis=1, join="outer").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # ---- Forward-fill Capex up to 6 months so it doesn't vanish at the tail ----
    if "Capex_Supply" in df.columns:
        df["Capex_Supply"] = df["Capex_Supply"].ffill(limit=6)
    if "Capex_Supply_Manual" in df.columns:
        df["Capex_Supply_Manual"] = df["Capex_Supply_Manual"].ffill(limit=6)
    if "Capex_Supply_Macro" in df.columns:
        df["Capex_Supply_Macro"] = df["Capex_Supply_Macro"].ffill(limit=6)

    # ---- Drop rows where all main pillars are NaN ----
    main_pillars = [c for c in ["Market", "Capex_Supply", "Credit", "Infra", "Adoption"] if c in df.columns]
    if main_pillars:
        df = df.loc[~df[main_pillars].isna().all(axis=1)]

    # Also drop rows where BOTH Market and Credit are missing
    core = [c for c in ["Market", "Credit"] if c in df.columns]
    if core:
        df = df.loc[~df[core].isna().all(axis=1)]

    # ---- Static baseline composite (app recomputes with sliders) ----
    desired  = ["Market", "Capex_Supply", "Infra", "Adoption", "Credit"]
    present  = [p for p in desired if p in df.columns]
    defaults = {"Market":0.25, "Capex_Supply":0.25, "Infra":0.20, "Adoption":0.15, "Credit":0.15}
    w = np.array([defaults[p] for p in present], dtype=float)
    w = w / w.sum() if w.sum() else np.ones(len(present)) / max(len(present), 1)

    df["AIBPS"] = (df[present] * w).sum(axis=1, skipna=True)
    df["AIBPS_RA"] = df["AIBPS"].rolling(3, min_periods=1).mean()

    # ---- Sanity prints ----
    print("---- Columns in composite ----")
    print(list(df.columns))
    print("---- Tail (Market / Capex_Supply / components / Credit / AIBPS_RA) ----")
    for col in [c for c in ["Market","Capex_Supply","Capex_Supply_Manual","Capex_Supply_Macro","Credit","AIBPS","AIBPS_RA"] if c in df.columns]:
        print(f"{col}:")
        print(df[col].tail(6))

    # ---- Write output ----
    df.to_csv(OUT)
    print(f"💾 Wrote {OUT} with pillars: {present} (rows={len(df)})")
    print(f"⏱ Done in {time.time()-t0:.2f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ compute.py: {e}")
        sys.exit(1)
