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
- All pillars use "rolling_z_sigmoid" -> 0–100 heat score by default.
- Windows differ by pillar, but are configurable via config.yaml.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd
import yaml

# Ensure we can import aibps.normalize when running as a script
HERE = os.path.dirname(__file__)                       # .../src/aibps
SRC_ROOT = os.path.abspath(os.path.join(HERE, ".."))   # .../src
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from aibps.normalize import normalize_series  # noqa: E402

PROC_DIR = os.path.join("data", "processed")
OUT_PATH = os.path.join(PROC_DIR, "aibps_monthly.csv")
CONFIG_PATH = os.path.join(HERE, "config.yaml")

CANONICAL_PILLARS = ["Market", "Credit", "Capex_Supply", "Infra", "Adoption", "Sentiment"]

# Historical months: keep long-run chart continuity (≥2 pillars, as before).
# Live edge only: require ≥5 pillars so FRED reporting lag cannot cliff the latest print.
MIN_PILLARS_HISTORICAL = 2
MIN_PILLARS_LIVE_EDGE = 5
LIVE_EDGE_MONTHS = 4


def _min_pillars_by_date(index: pd.DatetimeIndex) -> pd.Series:
    """Stricter coverage only for the most recent LIVE_EDGE_MONTHS."""
    if len(index) == 0:
        return pd.Series(dtype=float)
    end = pd.Timestamp(index.max()).to_period("M").to_timestamp("M")
    live_start = (end.to_period("M") - (LIVE_EDGE_MONTHS - 1)).to_timestamp("M")
    required = pd.Series(MIN_PILLARS_HISTORICAL, index=index, dtype=int)
    required.loc[index >= live_start] = MIN_PILLARS_LIVE_EDGE
    return required


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


def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        print(f"ℹ️ No config.yaml at {CONFIG_PATH}; using built-in defaults.")
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
        print("🔧 Loaded config.yaml")
        return cfg
    except Exception as e:
        print(f"❌ Failed to load config.yaml: {e}")
        return {}


def _load_norm_config(cfg: dict):
    """
    Returns
    -------
    defaults : dict
    pillar_cfg : dict
    """
    norm_cfg = cfg.get("normalization", {}) or {}
    defaults = norm_cfg.get("defaults", {}) or {}
    pillar_cfg = norm_cfg.get("pillars", {}) or {}
    return defaults, pillar_cfg


def _load_weights(cfg: dict, pillars: list[str]) -> pd.Series:
    """
    Load pillar weights from config and renormalize over available pillars.
    Falls back to equal weights.
    """
    raw = cfg.get("weights") or {}
    if not raw:
        w = np.ones(len(pillars), dtype=float)
        return pd.Series(w / w.sum(), index=pillars)

    series = pd.Series({p: float(raw.get(p, 0.0)) for p in pillars}, dtype=float)
    if (series <= 0).all() or series.sum() == 0:
        w = np.ones(len(pillars), dtype=float)
        return pd.Series(w / w.sum(), index=pillars)

    # Drop non-positive weights among available pillars, then renormalize
    series = series.clip(lower=0)
    if series.sum() == 0:
        w = np.ones(len(pillars), dtype=float)
        return pd.Series(w / w.sum(), index=pillars)
    return series / series.sum()


def _rebased_equal_weight(df: pd.DataFrame, cols: list[str]) -> pd.Series | None:
    """Equal-weight basket of rebased levels for offline Market repair."""
    present = [c for c in cols if c in df.columns]
    if not present:
        return None
    rebased = pd.DataFrame(index=df.index)
    for col in present:
        s = df[col].astype(float)
        first = s.first_valid_index()
        if first is None or s.loc[first] == 0 or pd.isna(s.loc[first]):
            continue
        rebased[col] = 100.0 * s / s.loc[first]
    if rebased.empty:
        return None
    return rebased.mean(axis=1, skipna=True)


def _resolve_market_raw(market: pd.DataFrame) -> pd.Series:
    """Prefer explicit Market column; else build QQQ/SOXX/NVDA basket offline."""
    if "Market" in market.columns:
        print("✅ Market: using explicit Market column")
        return market["Market"]

    basket = _rebased_equal_weight(market, ["QQQ", "SOXX", "NVDA"])
    if basket is not None:
        print("ℹ️ Market: built offline equal-weight QQQ/SOXX/NVDA basket")
        return basket

    if "market_component_composite_z" in market.columns:
        print("ℹ️ Market: falling back to market_component_composite_z")
        return market["market_component_composite_z"]

    print(f"⚠️ Market: no basket columns; using first column ({market.columns[0]})")
    return market.iloc[:, 0]


def _resolve_credit_raw(credit: pd.DataFrame) -> pd.Series:
    """
    Resolve Credit pillar input with history-aware fallback.

    Prefer an explicit Credit column when it has deep coverage. If Credit (or OAS)
    is truncated — FRED currently limits some ICE BofA OAS series to ~3y — fall
    back to the longer BAA–AAA spread so rolling windows have enough history.
    """
    min_history = 120
    candidates: list[tuple[str, pd.Series]] = []

    if "Credit" in credit.columns and credit["Credit"].notna().any():
        candidates.append(("Credit column", credit["Credit"]))

    oas_cols = [c for c in ["HY_OAS_bp", "IG_OAS_bp"] if c in credit.columns]
    if oas_cols:
        oas = credit[oas_cols].mean(axis=1, skipna=True)
        candidates.append((f"OAS mean of {oas_cols}", oas))

    if "BAA_AAA_spread_pct" in credit.columns:
        candidates.append(
            ("BAA_AAA_spread_pct (bp-scaled)", credit["BAA_AAA_spread_pct"] * 100.0)
        )

    if not candidates:
        print(f"⚠️ Credit: no spread columns; using first column ({credit.columns[0]})")
        return credit.iloc[:, 0]

    # Prefer OAS/Credit only when coverage is deep enough; else deepest series
    deep = [(label, s) for label, s in candidates if int(s.notna().sum()) >= min_history]
    pool = deep if deep else candidates
    label, series = max(pool, key=lambda item: int(item[1].notna().sum()))
    print(f"ℹ️ Credit: using {label} (n={int(series.notna().sum())})")
    return series



def _first_matching_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def main():
    t0 = time.time()
    cfg = _load_config()

    # ---- Load pillar inputs ----
    market = _read_processed("market_processed.csv")
    credit = _read_processed("credit_fred_processed.csv")
    capex = _read_processed("capex_processed.csv")
    macro_capex = _read_processed("macro_capex_processed.csv")
    infra = _read_processed("infra_processed.csv")
    infra_macro = _read_processed("infra_macro_processed.csv")
    adoption = _read_processed("adoption_processed.csv")
    sentiment = _read_processed("sentiment_processed.csv")

    frames = [
        x for x in [
            market, credit, capex, macro_capex, infra, infra_macro, adoption, sentiment
        ]
        if x is not None
    ]
    if not frames:
        print("❌ No processed pillar data found. Aborting.")
        sys.exit(1)

    # Build a monthly date index covering all available data
    start = min(df.index.min() for df in frames)
    end = max(df.index.max() for df in frames)
    idx = pd.date_range(
        start=start.to_period("M").to_timestamp("M"),
        end=end.to_period("M").to_timestamp("M"),
        freq="ME",
    )
    base = pd.DataFrame(index=idx)
    base.index.name = "date"

    # ---- Attach "raw-ish" pillar series ----

    # Market
    if market is not None:
        base["Market_raw"] = _resolve_market_raw(market).reindex(base.index)

    # Credit
    if credit is not None:
        base["Credit_raw"] = _resolve_credit_raw(credit).reindex(base.index)

    # Capex (manual)
    if capex is not None:
        col = _first_matching_col(capex, ["Capex_Supply", "Capex_Supply_Manual"])
        if col:
            base["Capex_Supply_Manual_raw"] = capex[col].reindex(base.index)
            print(f"✅ Capex manual: using {col}")

    # Capex (macro) — accept Capex_Supply (current fetcher) or Capex_Supply_Macro
    if macro_capex is not None:
        col = _first_matching_col(macro_capex, ["Capex_Supply_Macro", "Capex_Supply"])
        if col:
            base["Capex_Supply_Macro_raw"] = macro_capex[col].reindex(base.index)
            print(f"✅ Capex macro: using {col}")
        else:
            print("⚠️ Capex macro file present but no Capex_Supply / Capex_Supply_Macro column")

    # Infra (manual)
    if infra is not None:
        col = _first_matching_col(infra, ["Infra", "Infra_Manual"])
        if col:
            base["Infra_Manual_raw"] = infra[col].reindex(base.index)
            print(f"✅ Infra manual: using {col}")

    # Infra (macro) — accept Infra (current fetcher) or Infra_Macro
    if infra_macro is not None:
        col = _first_matching_col(infra_macro, ["Infra_Macro", "Infra"])
        if col:
            base["Infra_Macro_raw"] = infra_macro[col].reindex(base.index)
            print(f"✅ Infra macro: using {col}")
        else:
            print("⚠️ Infra macro file present but no Infra / Infra_Macro column")

    # Adoption
    if adoption is not None:
        if "Adoption" in adoption.columns:
            base["Adoption_raw"] = adoption["Adoption"].reindex(base.index)

    # Sentiment
    if sentiment is not None:
        if "Sentiment" in sentiment.columns:
            base["Sentiment_raw"] = sentiment["Sentiment"].reindex(base.index)

    # ---- Combine manual/macro where relevant ----

    if ("Capex_Supply_Manual_raw" in base.columns) or ("Capex_Supply_Macro_raw" in base.columns):
        cols = [c for c in ["Capex_Supply_Manual_raw", "Capex_Supply_Macro_raw"] if c in base.columns]
        base["Capex_Supply_raw"] = base[cols].mean(axis=1, skipna=True)
        print(f"✅ Capex_Supply_raw from: {cols}")

    if ("Infra_Manual_raw" in base.columns) or ("Infra_Macro_raw" in base.columns):
        cols = [c for c in ["Infra_Manual_raw", "Infra_Macro_raw"] if c in base.columns]
        base["Infra_raw"] = base[cols].mean(axis=1, skipna=True)
        print(f"✅ Infra_raw from: {cols}")

    # ---- Normalization config ----
    defaults, pillar_cfg = _load_norm_config(cfg)

    def get_norm_params(pillar_name: str):
        pcfg = pillar_cfg.get(pillar_name, {}) or {}
        method = pcfg.get("method", defaults.get("method", "rolling_z_sigmoid"))
        kwargs = {k: v for k, v in {**defaults, **pcfg}.items() if k != "method"}
        if "window" not in kwargs:
            kwargs["window"] = 24
        if "z_clip" not in kwargs:
            kwargs["z_clip"] = 4.0
        return method, kwargs

    normalized_pillars = []

    for name in CANONICAL_PILLARS:
        raw_col = f"{name}_raw"
        if raw_col not in base.columns:
            print(f"ℹ️ No raw series for {name}; skipping.")
            continue

        method, kwargs = get_norm_params(name)
        print(f"🔧 Normalizing {name} with method={method}, params={kwargs}")

        try:
            norm_series = normalize_series(base[raw_col], method=method, **kwargs)
        except Exception as e:
            print(f"❌ Normalization failed for {name}: {e}")
            continue

        base[name] = norm_series
        normalized_pillars.append(name)

    if not normalized_pillars:
        print("❌ No pillars normalized; cannot compute AIBPS.")
        sys.exit(1)

    print("---- Pillars used in composite ----")
    print(normalized_pillars)

    # ---- Weights from config, renormalized over available pillars ----
    weights = _load_weights(cfg, normalized_pillars)
    print("---- Weights ----")
    print(weights)

    vals = base[normalized_pillars]
    weight_matrix = pd.DataFrame(
        np.broadcast_to(weights.values, (len(vals), len(weights))),
        index=vals.index,
        columns=normalized_pillars,
    )

    effective_weights = weight_matrix.where(vals.notna())
    weighted_vals = vals * effective_weights

    weighted_sum = weighted_vals.sum(axis=1, skipna=True)
    total_w = effective_weights.sum(axis=1)

    composite = weighted_sum / total_w
    composite[total_w == 0] = np.nan

    # Coverage rule: ≥2 historically; ≥5 only on the live edge (see docs/methods.md)
    num_pillars_available = vals.notna().sum(axis=1)
    min_required = _min_pillars_by_date(base.index)
    publish_mask = num_pillars_available >= min_required
    composite = composite.where(publish_mask)

    base["Pillars_reporting"] = num_pillars_available
    base["AIBPS"] = composite
    # Docs specify ~6-month smoothing; keep min_periods=1 for early history.
    # RA follows the same live-edge freeze so the latest point cannot drift alone.
    base["AIBPS_RA"] = base["AIBPS"].rolling(6, min_periods=1).mean()
    base.loc[~publish_mask, "AIBPS_RA"] = np.nan

    # Keep diagnostic pillar rows even when AIBPS is frozen/blank at the live edge
    keep_cols = [c for c in CANONICAL_PILLARS if c in base.columns] + ["AIBPS"]
    out = base.dropna(subset=keep_cols, how="all")

    live_frozen = int((~publish_mask & (min_required >= MIN_PILLARS_LIVE_EDGE)).sum())
    print(
        f"ℹ️ Publication rule: ≥{MIN_PILLARS_HISTORICAL} pillars historically; "
        f"≥{MIN_PILLARS_LIVE_EDGE} in last {LIVE_EDGE_MONTHS} months "
        f"(live-edge frozen months={live_frozen})"
    )
    published = out.dropna(subset=["AIBPS"])
    if len(published):
        print(
            f"ℹ️ AIBPS span: {published.index.min().date()} → {published.index.max().date()} "
            f"(latest pillars={int(published['Pillars_reporting'].iloc[-1])})"
        )

    print("---- Columns in composite ----")
    print(list(out.columns))

    def _safe_tail(name):
        if name in out.columns:
            print(f"{name}:")
            print(out[name].tail(6))
        else:
            print(f"{name}: (missing)")

    print("---- Tail (Market / Capex_Supply / Infra / Credit / AIBPS_RA) ----")
    for col in ["Market", "Capex_Supply", "Infra", "Credit", "Adoption", "Sentiment", "AIBPS_RA"]:
        _safe_tail(col)

    non_null = {p: int(out[p].notna().sum()) for p in normalized_pillars if p in out.columns}
    print("---- Non-null pillar months ----")
    print(non_null)

    os.makedirs(PROC_DIR, exist_ok=True)
    out.to_csv(OUT_PATH)
    elapsed = time.time() - t0
    print(
        f"💾 Wrote {OUT_PATH} with pillars: {normalized_pillars} "
        f"(rows={len(out)}, {elapsed:.1f}s)"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ compute.py: {e}")
        sys.exit(1)
