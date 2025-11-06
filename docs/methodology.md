# 📐 AIBPS Methodology — Quantitative Framework

The **AI Bubble Pressure Score (AIBPS)** is a composite indicator derived from 20+ sub-indicators organized into five structural pillars.  
Each component is normalized, weighted, and combined to produce a continuous 0–100 composite score representing systemic “bubble pressure.”

---

## 🧮 1. Core Equation

The composite index at time *t* is defined as:

\[
AIBPS_t = \sum_{i=1}^{5} w_i \cdot P_{i,t}
\]

where:  
- \( P_{i,t} \) = Pillar *i* normalized percentile score at time *t*  
- \( w_i \) = Weight of pillar *i* (default weights sum to 1.0)  

Default weight vector:

| Pillar | Symbol | Default Weight |
|---------|---------|----------------|
| Market Valuations | \( w_1 \) | 0.25 |
| Capex & Supply Chain | \( w_2 \) | 0.25 |
| Infrastructure (Power/DC) | \( w_3 \) | 0.20 |
| Adoption & Productivity | \( w_4 \) | 0.15 |
| Credit & Liquidity | \( w_5 \) | 0.15 |

---

## ⚙️ 2. Normalization

Each indicator is standardized using its **10-year historical distribution**:

### a. For risk-positive metrics (where higher = more speculative)
\[
P_{i,t} = 100 \times \text{PercentileRank}(X_{i,t})
\]

### b. For risk-negative metrics (where higher = less speculative)
\[
P_{i,t} = 100 \times \left(1 - \text{PercentileRank}(X_{i,t})\right)
\]

Where \( X_{i,t} \) represents the raw indicator value (e.g., P/E ratio, HY spread).

This transformation ensures comparability across diverse units and scales.

---

## 📊 3. Rolling Smoothing

To minimize noise and highlight cycle trends, a **three-quarter rolling average** is applied:

\[
AIBPS_{t,smoothed} = \frac{AIBPS_t + AIBPS_{t-1} + AIBPS_{t-2}}{3}
\]

This version is used in the dashboard’s primary time-series visualization.

---

## 🚨 4. Threshold Logic

AIBPS defines four interpretive zones:

| Range | Label | Typical Interpretation |
|--------|--------|------------------------|
| 0–50 | **Watch** | Normal activity |
| 50–70 | **Rising Pressure** | Overinvestment building |
| 70–85 | **Elevated Risk** | Reflexivity & concentration increasing |
| 85–100 | **Critical Zone** | Systemic overheating; high fragility |

**Trigger Conditions:**
1. AIBPS > 80 for 3+ consecutive months → *Systemic Overheating Alert*  
2. Any two pillars exceed 85th percentile simultaneously → *Sectoral Bubble Alert*  
3. Market pillar declines >15 points within 2 quarters while composite >70 → *Early Collapse Signal*

---

## 🧠 5. Pillar Sub-Indicators (Examples)

| Pillar | Example Indicators | Frequency | Source |
|---------|-------------------|------------|---------|
| Market | SOXX, QQQ, NVDA returns, volatility skew | Daily | Yahoo Finance |
| Capex & Supply | Hyperscaler capex %, SEMI book-to-bill | Quarterly | SEC filings, SEMI.org |
| Infra | Power queue MW, DC vacancy, rent growth | Semiannual | ISO, CBRE |
| Adoption | Cloud AI revenue, token usage, productivity deltas | Quarterly | Company reports |
| Credit | HY/IG OAS, margin debt, VC funding volumes | Monthly | FRED, Crunchbase |

---

## 🧩 6. Data Integration Pipeline

data/raw/ # Source CSVs, APIs
data/processed/ # Normalized & z-scored data
app/streamlit_app.py
src/aibps/compute.py -> normalization, weighting, smoothing
src/aibps/visualize.py -> radar, timeseries, export


---

## 📈 7. Example Pseudocode

```python
import pandas as pd
import numpy as np

# Load and standardize indicator data
df = pd.read_csv("data/processed/indicators.csv")
for col in df.columns:
    ascending = col not in ["credit_spread", "liquidity_index"]
    df[col + "_pct"] = df[col].rank(pct=True, ascending=ascending) * 100

# Compute pillar and composite
weights = {"Market":0.25,"Capex_Supply":0.25,"Infra":0.2,"Adoption":0.15,"Credit":0.15}
df["AIBPS"] = sum(df[p]*w for p,w in weights.items())

# Rolling average for dashboard
df["AIBPS_RA"] = df["AIBPS"].rolling(3, min_periods=1).mean()

🔮 8. Future Extensions

- Add sub-pillar decomposition (e.g., “AI hardware vs software exposure”)
- Integrate sentiment and policy uncertainty indices
- Model lag effects with VAR or Bayesian updating

🪪 License

MIT License © 2025  
See the LICENSE file for details.
