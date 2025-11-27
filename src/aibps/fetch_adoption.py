#!/usr/bin/env python3
"""
fetch_adoption.py

Builds a multi-component Adoption pillar for AIBPS from real FRED macro series.

Sub-pillars (block composites):

    - Adoption_Enterprise_Software
        * B985RC1A027NBEA – Private fixed investment: IP products: Software

    - Adoption_Cloud_Services
        * IPB541   – Industrial Production: Data Processing, Hosting, and Related Services
        * AIPDC    – Private fixed investment: Data processing equipment
        * TLHICS   – Private fixed investment: Computers & peripheral equipment
      (currently failing: FRED reports these IDs as non-existent; block will be empty.)

    - Adoption_Digital_Labor
        * PRS85006092 – Nonfinancial corporate sector output per hour
        * ULCBS       – Unit labor costs: Business sector
        * IPN11110    – Industrial Production: Computing & Electronics
      (IPN11110 currently failing; the first two work.)

    - Adoption_Connectivity
        * IPN323        – Industrial Production: Communications equipment
        * IPN2211       – Electric power equipment & distribution
        * CES1020000001 – Employment: Telecommunications
      (currently failing: FRED reports these IDs as non-existent; block will be empty.)

Output:
    data/processed/adoption_processed.csv with columns:
        - Adoption_Enterprise_Software
        - Adoption_Cloud_Services
        - Adoption_Digital_Labor
        - Adoption_Connectivity
        - Adoption_Supply
        - Adoption
"""

import os
import sys
from datetime import datetime

import pandas as pd

# fredapi is required for this script
try:
    from fredapi import Fred
except ImportError:
    Fred = None

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

START_DATE = "1980-01-31"
OUT_PATH = "data/processed/adoption_processed.csv"

# 1) Enterprise software / IP investment
ENTERPRISE_SERIES = [
    ("B985RC1A027NBEA", "Enterprise_Software"),
]

# 2) Cloud / data-processing / hosting
CLOUD_SERIES = [
    ("IPB541",  "Cloud_Hosting_Production"),   # (currently failing)
    ("AIPDC",   "Cloud_DataProcessing_Equip"), # (currently failing)
    ("TLHICS",  "Cloud_IT_Comp_Equip"),        # (currently failing)
]

# 3) Digital labor / automation-related
DIGITAL_LABOR_SERIES = [
    ("PRS85006092", "Labor_Productivity"),
    ("ULCBS",       "Unit_Labor_Costs"),
    ("IPN11110",    "Comp_Electronics_Prod"),  # (currently failing)
]

# 4) Connectivity / telecom / power backbone
CONNECTIVITY_SERIES = [
    ("IPN323",        "Comm_Equipment_Prod"),   # (currently failing)
    ("IPN2211",       "Electric_Power_Equip"),  # (currently failing)
    ("CES1020000001", "Telecom_Employment"),    # (currently failing)
]


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def get_fred_client() -> Fred | None:
    """Instantiate a Fred client from FRED_API_KEY, or return None if unavailable."""
    if Fred is None:
        print("❌ fredapi is not installed. Install it in your environment.")
        return None

    key = os.getenv("FRED_API_KEY")
    if not key:
        print("⚠️ FRED_API_KEY not set; cannot fetch Adoption data from FRED.")
        return None

    try:
        fred = Fred(api_key=key)
        return fred
    except Exception as e:
        print(f"❌ Failed to initialize Fred client: {e}")
        return None


def fetch_series_block(fred: Fred, pairs: list[tuple[str, str]], label: str) -> pd.DataFrame:
    """
    Fetch a block of FRED series and return a DataFrame with datetime index.

    Each pair in `pairs` is (fred_id, column_name).

    Returns:
        DataFrame with columns named per column_name; may be empty if everything fails.
    """
    frames: list[pd.Series] = []

    for sid, colname in pairs:
        try:
            ser = fred.get_series(sid)
            if ser is None or len(ser) == 0:
                print(f"⚠️ Block={label}: empty or missing series {sid} ({colname}); skipping.")
                continue
            s = pd.Series(ser, name=colname)
            s.index = pd.to_datetime(s.index)
            s = s.sort_index()
            frames.append(s)
            print(
                f"✅ Block={label}: fetched {sid} → {colname} "
                f"({s.index.min().date()} → {s.index.max().date()}, n={len(s)})"
            )
        except Exception as e:
            print(f"⚠️ Block={label}: failed fetching {sid} ({colname}): {e}")

    if not frames:
        print(f"⚠️ Block={label}: no usable series; returning empty DataFrame.")
        return pd.DataFrame()

    df = pd.concat(frames, axis=1).sort_index()
    return df


def block_to_composite(df_block: pd.DataFrame, out_name: str) -> pd.Series:
    """
    Convert a multi-column block into a single composite Series by row-wise mean.

    Returns empty Series if df_block is empty.
    """
    if df_block is None or df_block.empty:
        print(f"ℹ️ Composite {out_name}: input block empty; returning empty Series.")
        return pd.Series(dtype=float, name=out_name)

    ser = df_block.mean(axis=1)
    ser.name = out_name
    print(f"✅ Composite {out_name}: built from columns {list(df_block.columns)}")
    return ser


def reindex_monthly(df: pd.DataFrame, start_date: str) -> pd.DataFrame:
    """
    Resample an irregular-frequency DataFrame to month-end, forward-fill, and
    then trim to dates >= start_date.

    This avoids the bug where we reindexed to a brand-new monthly index that
    never included the original observation dates (e.g., Jan 1 vs Jan 31),
    which caused all-NaN series.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.sort_index()
    # Resample to month-end and forward-fill
    monthly = df.resample("M").last().ffill()

    # Restrict to dates >= start_date
    start_ts = pd.to_datetime(start_date)
    monthly = monthly[monthly.index >= start_ts]
    monthly.index.name = "Date"
    return monthly


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> int:
    fred = get_fred_client()
    if fred is None:
        # Write an empty shell file so downstream steps don't blow up.
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        empty_cols = [
            "Adoption_Enterprise_Software",
            "Adoption_Cloud_Services",
            "Adoption_Digital_Labor",
            "Adoption_Connectivity",
            "Adoption_Supply",
            "Adoption",
        ]
        pd.DataFrame(columns=empty_cols).to_csv(OUT_PATH, index_label="Date")
        print(f"💾 Wrote empty {OUT_PATH} (no FRED client).")
        return 0

    # ---- Fetch blocks ----
    ent_block   = fetch_series_block(fred, ENTERPRISE_SERIES,    "Enterprise_Software")
    cloud_block = fetch_series_block(fred, CLOUD_SERIES,         "Cloud_Services")
    labor_block = fetch_series_block(fred, DIGITAL_LABOR_SERIES, "Digital_Labor")
    conn_block  = fetch_series_block(fred, CONNECTIVITY_SERIES,  "Connectivity")

    # ---- Build composites ----
    ent_idx   = block_to_composite(ent_block,   "Adoption_Enterprise_Software")
    cloud_idx = block_to_composite(cloud_block, "Adoption_Cloud_Services")
    labor_idx = block_to_composite(labor_block, "Adoption_Digital_Labor")
    conn_idx  = block_to_composite(conn_block,  "Adoption_Connectivity")

    # ---- Combine into one frame ----
    combined = pd.concat(
        [ent_idx, cloud_idx, labor_idx, conn_idx],
        axis=1,
    ).sort_index()

    if combined.empty:
        print("⚠️ All Adoption sub-blocks empty; writing empty adoption_processed.csv.")
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        empty_cols = [
            "Adoption_Enterprise_Software",
            "Adoption_Cloud_Services",
            "Adoption_Digital_Labor",
            "Adoption_Connectivity",
            "Adoption_Supply",
            "Adoption",
        ]
        pd.DataFrame(columns=empty_cols).to_csv(OUT_PATH, index_label="Date")
        print(f"💾 Wrote empty {OUT_PATH}")
        return 0

    # Monthly, forward-filled from START_DATE
    combined_m = reindex_monthly(combined, START_DATE)

    # ---- Build Adoption_Supply and Adoption ----
    component_cols = [
        c
        for c in [
            "Adoption_Enterprise_Software",
            "Adoption_Cloud_Services",
            "Adoption_Digital_Labor",
            "Adoption_Connectivity",
        ]
        if c in combined_m.columns
    ]

    if component_cols:
        combined_m["Adoption_Supply"] = combined_m[component_cols].mean(axis=1)
        combined_m["Adoption"] = combined_m["Adoption_Supply"]
        print(f"✅ Adoption_Supply constructed from: {component_cols}")
    else:
        combined_m["Adoption_Supply"] = float("nan")
        combined_m["Adoption"] = float("nan")
        print("⚠️ No Adoption component columns found; Adoption_Supply/Adoption are NaN.")

    # ---- Tail debug ----
    print("---- Tail of adoption_processed.csv ----")
    print(combined_m.tail(12))

    # ---- Write output ----
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    combined_m.to_csv(OUT_PATH, index_label="Date")
    print(
        f"💾 Wrote {OUT_PATH} with {len(combined_m)} rows and columns: "
        f"{list(combined_m.columns)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
