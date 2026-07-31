#!/usr/bin/env python3
"""
fetch_sentiment.py

Sentiment pillar v2 — AI attention + optional macro overlay.

Primary (AI-specific, auto-refreshable):
    - Sentiment_Trends : Google Trends basket (AI / ChatGPT / generative AI / ...)
    - Sentiment_Wiki   : Wikipedia pageviews for AI-related articles

Secondary (macro psychological temperature, FRED):
    - Sentiment_Consumer : UMCSENT
    - Sentiment_EPU      : USEPUINDXM
    - Sentiment_VIX      : VIXCLS

Composite:
    Sentiment = mean of z-scored available primary components.
    If Trends/Wiki unavailable, fall back to FRED macro z-mean.
    If a live fetch fails, reuse prior raw/processed values so CI stays green.

Outputs:
    data/raw/sentiment_trends_raw.csv
    data/raw/sentiment_wiki_raw.csv
    data/processed/sentiment_processed.csv
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests

try:
    from fredapi import Fred
except ImportError:
    Fred = None

RAW_DIR = Path("data/raw")
PROC_DIR = Path("data/processed")
OUT_PATH = PROC_DIR / "sentiment_processed.csv"
TRENDS_RAW_PATH = RAW_DIR / "sentiment_trends_raw.csv"
WIKI_RAW_PATH = RAW_DIR / "sentiment_wiki_raw.csv"

START_DATE = "1980-01-31"
TRENDS_START = "2004-01-01"
WIKI_START = "2015070100"

USER_AGENT = "AIBPS/0.1 (https://github.com/mjmonnot/aibps-v0-1; AI bubble pressure index)"

# Google Trends search terms (docs/pillars.md)
# Keep the basket small — Google rate-limits aggressive multi-term pulls in CI.
TREND_TERMS = [
    "artificial intelligence",
    "generative ai",
    "chatgpt",
    "machine learning",
]

# English Wikipedia articles
WIKI_ARTICLES = [
    "Artificial_intelligence",
    "ChatGPT",
    "Large_language_model",
    "OpenAI",
    "Machine_learning",
]

# FRED IDs (macro overlay)
CONSUMER_ID = "UMCSENT"
EPU_ID = "USEPUINDXM"
VIX_ID = "VIXCLS"


def _ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)


def _read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df[~df.index.isna()]
        return df
    except Exception as e:
        print(f"⚠️ Failed reading {path}: {e}")
        return pd.DataFrame()


def reindex_monthly(df: pd.DataFrame, start_date: str = START_DATE) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()].sort_index()
    if df.empty:
        return pd.DataFrame()
    monthly = df.resample("ME").mean()
    monthly = monthly[monthly.index >= pd.to_datetime(start_date)]
    monthly.index.name = "Date"
    return monthly


def z_standardize(series: pd.Series) -> pd.Series:
    if series is None or series.empty:
        return series
    s = series.astype(float)
    mu = s.mean(skipna=True)
    sd = s.std(skipna=True)
    if sd == 0 or pd.isna(sd):
        return pd.Series(np.nan, index=s.index, name=s.name)
    out = (s - mu) / sd
    out.name = s.name
    return out


def _merge_prefer_new(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Union on index/columns; new non-null values overwrite old."""
    if new is None or new.empty:
        return old.copy() if old is not None and not old.empty else pd.DataFrame()
    if old is None or old.empty:
        return new.copy()
    idx = old.index.union(new.index)
    cols = list(dict.fromkeys(list(old.columns) + list(new.columns)))
    combined = pd.DataFrame(index=idx, columns=cols, dtype=float)
    combined.update(old)
    combined.update(new)
    return combined.sort_index()


# ---------------------------------------------------------------------
# Google Trends
# ---------------------------------------------------------------------

def fetch_google_trends(terms: list[str] = TREND_TERMS) -> pd.DataFrame:
    """
    Fetch Google Trends interest for each term at weekly resolution.

    Uses `today 5-y` (not 2004→present): ultra-long windows collapse to yearly
    points and are useless for a monthly pillar. Wikipedia covers longer AI
    attention history; Trends captures the recent hype pulse. Prior raw cache
    is merged by the caller so brief 429s do not erase history.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("⚠️ pytrends not installed; skipping Google Trends.")
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    # retries=0 avoids urllib3 v2 incompatibility with pytrends' Retry kwargs
    # (method_whitelist). requirements.txt also pins urllib3<2 for CI.
    pytrends = TrendReq(hl="en-US", tz=360, retries=0)

    for i, term in enumerate(terms):
        interest = None
        used = None
        for window in ("today 5-y", "today 12-m"):
            try:
                print(f"🔎 Trends: fetching '{term}' ({window})...")
                pytrends.build_payload([term], timeframe=window, geo="")
                interest = pytrends.interest_over_time()
                if interest is not None and not interest.empty:
                    used = window
                    break
            except Exception as inner:
                print(f"⚠️ Trends window '{window}' failed for '{term}': {inner}")
                time.sleep(1.5)
                interest = None

        if interest is None or interest.empty:
            print(f"⚠️ Trends: empty for '{term}'")
        else:
            col = term.replace(" ", "_")
            s = (
                interest[term].rename(col)
                if term in interest.columns
                else interest.iloc[:, 0].rename(col)
            )
            frames.append(s.to_frame())
            print(
                f"✅ Trends '{term}' via {used}: "
                f"{s.index.min().date()} → {s.index.max().date()} (n={len(s)})"
            )

        if i < len(terms) - 1:
            time.sleep(4.0)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, axis=1).sort_index()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    df = df.drop(columns=[c for c in df.columns if c.lower() == "ispartial"], errors="ignore")
    return df


# ---------------------------------------------------------------------
# Wikipedia pageviews
# ---------------------------------------------------------------------

def fetch_wikipedia_pageviews(articles: list[str] = WIKI_ARTICLES) -> pd.DataFrame:
    """Fetch monthly Wikipedia pageviews via Wikimedia REST API."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    end = pd.Timestamp.today().strftime("%Y%m%d00")
    frames: list[pd.Series] = []

    for article in articles:
        encoded = quote(article, safe="")
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia/all-access/user/{encoded}/monthly/{WIKI_START}/{end}"
        )
        try:
            print(f"🔎 Wiki: fetching {article}...")
            resp = requests.get(url, headers=headers, timeout=45)
            if resp.status_code != 200:
                print(f"⚠️ Wiki {article}: HTTP {resp.status_code} — {resp.text[:160]}")
                continue
            items = resp.json().get("items", [])
            if not items:
                print(f"⚠️ Wiki {article}: no items")
                continue
            idx = pd.to_datetime([it["timestamp"][:8] for it in items], format="%Y%m%d")
            vals = [it["views"] for it in items]
            col = f"wiki_{article}"
            s = pd.Series(vals, index=idx, name=col).sort_index()
            # Stamp to month-end
            s.index = s.index.to_period("M").to_timestamp("M")
            frames.append(s)
            print(f"✅ Wiki {article}: {s.index.min().date()} → {s.index.max().date()} (n={len(s)})")
            time.sleep(0.2)
        except Exception as e:
            print(f"⚠️ Wiki failed for {article}: {e}")

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, axis=1).sort_index()
    df.index.name = "Date"
    return df


# ---------------------------------------------------------------------
# FRED macro overlay
# ---------------------------------------------------------------------

def get_fred_client():
    if Fred is None:
        print("⚠️ fredapi not installed; skipping FRED sentiment overlay.")
        return None
    key = os.getenv("FRED_API_KEY")
    if not key:
        print("ℹ️ FRED_API_KEY not set; skipping FRED sentiment overlay.")
        return None
    try:
        return Fred(api_key=key)
    except Exception as e:
        print(f"⚠️ Failed to init Fred: {e}")
        return None


def fetch_fred_overlay(fred) -> pd.DataFrame:
    if fred is None:
        return pd.DataFrame()

    frames = []
    for sid, col, label in [
        (CONSUMER_ID, "Sentiment_Consumer", "ConsumerSentiment"),
        (EPU_ID, "Sentiment_EPU", "EconomicPolicyUncertainty"),
        (VIX_ID, "Sentiment_VIX", "VIX"),
    ]:
        try:
            ser = fred.get_series(sid)
            if ser is None or len(ser) == 0:
                print(f"⚠️ {label}: empty {sid}")
                continue
            s = pd.Series(ser, name=col)
            s.index = pd.to_datetime(s.index)
            frames.append(s.to_frame())
            print(f"✅ {label}: {s.index.min().date()} → {s.index.max().date()} (n={len(s)})")
        except Exception as e:
            print(f"⚠️ {label}: failed {sid}: {e}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index()


# ---------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------

def build_sentiment_composite(monthly: pd.DataFrame) -> pd.DataFrame:
    """
    Build AI-attention composite + coverage metadata.

    Primary: Trends basket mean + Wiki basket mean (z-scored, then averaged).
    Fallback: FRED macro z-mean if no primary signal.
    """
    out = monthly.copy()

    # Normalize raw Trends term columns to trend_* prefix
    term_names = {t.replace(" ", "_") for t in TREND_TERMS}
    rename_trends = {
        c: f"trend_{c}"
        for c in out.columns
        if c in term_names and not c.startswith("trend_")
    }
    if rename_trends:
        out = out.rename(columns=rename_trends)

    trend_cols = [c for c in out.columns if c.startswith("trend_")]
    wiki_cols = [c for c in out.columns if c.startswith("wiki_")]
    macro_cols = [
        c for c in ["Sentiment_Consumer", "Sentiment_EPU", "Sentiment_VIX"] if c in out.columns
    ]

    if trend_cols:
        out["Sentiment_Trends"] = out[trend_cols].mean(axis=1, skipna=True)
    if wiki_cols:
        # log1p dampens ChatGPT launch spikes before z-scoring
        out["Sentiment_Wiki"] = np.log1p(out[wiki_cols].mean(axis=1, skipna=True))

    primary_z = []
    for col in ["Sentiment_Trends", "Sentiment_Wiki"]:
        if col in out.columns and out[col].notna().any():
            z = z_standardize(out[col])
            out[f"{col}_z"] = z
            primary_z.append(z)

    macro_z = []
    for col in macro_cols:
        z = z_standardize(out[col])
        out[f"{col}_z"] = z
        macro_z.append(z)

    if primary_z:
        primary = pd.concat(primary_z, axis=1).mean(axis=1, skipna=True)
        if macro_z:
            macro = pd.concat(macro_z, axis=1).mean(axis=1, skipna=True)
            # 80% AI attention / 20% macro overlay where both exist
            out["Sentiment"] = primary.where(macro.isna(), 0.8 * primary + 0.2 * macro)
            out["Sentiment"] = out["Sentiment"].fillna(primary)
            print("✅ Sentiment = 80% AI attention (Trends/Wiki) + 20% FRED macro overlay")
        else:
            out["Sentiment"] = primary
            print("✅ Sentiment = AI attention only (Trends/Wiki)")
        sources = []
        if "Sentiment_Trends" in out.columns:
            sources.append("Trends")
        if "Sentiment_Wiki" in out.columns:
            sources.append("Wiki")
        out["Sentiment_coverage"] = "+".join(sources) if sources else "none"
    elif macro_z:
        out["Sentiment"] = pd.concat(macro_z, axis=1).mean(axis=1, skipna=True)
        out["Sentiment_coverage"] = "macro_fallback"
        print("⚠️ Sentiment falling back to FRED macro only (no Trends/Wiki)")
    else:
        out["Sentiment"] = np.nan
        out["Sentiment_coverage"] = "none"
        print("⚠️ No Sentiment components available")

    # Put Sentiment first
    ordered = ["Sentiment", "Sentiment_coverage"]
    ordered += [c for c in ["Sentiment_Trends", "Sentiment_Wiki"] if c in out.columns]
    ordered += [c for c in out.columns if c not in ordered]
    out = out[ordered]
    return out


def main() -> int:
    _ensure_dirs()
    print("MARKER fetch_sentiment.py — Sentiment v2 (Trends + Wiki + FRED overlay)")

    # --- Live pulls ---
    trends_new = fetch_google_trends()
    wiki_new = fetch_wikipedia_pageviews()
    fred_df = fetch_fred_overlay(get_fred_client())

    # --- Merge with cached raw so rate-limits don't wipe history ---
    trends_old = _read_csv_optional(TRENDS_RAW_PATH)
    wiki_old = _read_csv_optional(WIKI_RAW_PATH)

    trends = _merge_prefer_new(trends_old, trends_new)
    wiki = _merge_prefer_new(wiki_old, wiki_new)

    if not trends.empty:
        trends.to_csv(TRENDS_RAW_PATH, index_label="Date")
        print(f"💾 Wrote {TRENDS_RAW_PATH} (cols={list(trends.columns)}, rows={len(trends)})")
    else:
        print("⚠️ No Trends data (live or cache)")

    if not wiki.empty:
        wiki.to_csv(WIKI_RAW_PATH, index_label="Date")
        print(f"💾 Wrote {WIKI_RAW_PATH} (cols={list(wiki.columns)}, rows={len(wiki)})")
    else:
        print("⚠️ No Wiki data (live or cache)")

    # --- Monthly align ---
    parts = []
    if not trends.empty:
        parts.append(reindex_monthly(trends, TRENDS_START))
    if not wiki.empty:
        parts.append(reindex_monthly(wiki, "2015-07-01"))
    if not fred_df.empty:
        parts.append(reindex_monthly(fred_df, START_DATE))

    # If everything failed, keep prior processed file intact
    if not parts:
        prior = _read_csv_optional(OUT_PATH)
        if not prior.empty:
            print(f"⚠️ All live sentiment sources failed; keeping prior {OUT_PATH}")
            return 0
        empty = pd.DataFrame(
            columns=["Sentiment", "Sentiment_coverage", "Sentiment_Trends", "Sentiment_Wiki"]
        )
        empty.to_csv(OUT_PATH, index_label="Date")
        print(f"💾 Wrote empty {OUT_PATH}")
        return 0

    monthly = parts[0]
    for p in parts[1:]:
        monthly = monthly.join(p, how="outer")

    monthly = monthly.sort_index()
    monthly = build_sentiment_composite(monthly)

    # Carry forward coverage label
    if "Sentiment_coverage" in monthly.columns:
        monthly["Sentiment_coverage"] = monthly["Sentiment_coverage"].astype(str)

    print("---- Tail of sentiment_processed.csv ----")
    show_cols = [
        c for c in [
            "Sentiment", "Sentiment_coverage", "Sentiment_Trends", "Sentiment_Wiki",
            "Sentiment_Consumer", "Sentiment_EPU", "Sentiment_VIX",
        ]
        if c in monthly.columns
    ]
    print(monthly[show_cols].tail(12))

    monthly.to_csv(OUT_PATH, index_label="Date")
    print(
        f"💾 Wrote {OUT_PATH} rows={len(monthly)} "
        f"Sentiment_n={int(monthly['Sentiment'].notna().sum())} "
        f"cols={list(monthly.columns)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
