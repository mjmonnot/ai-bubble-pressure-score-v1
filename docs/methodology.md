# 🧭 AI Bubble Pressure Score (AIBPS)  
### *Methodology, Data Sources, and Interpretation Guide*  
_Last updated: {{DATE}}_

---

## 📌 Overview

The **AI Bubble Pressure Score (AIBPS)** is a composite macro-indicator designed to quantify speculative pressure in the AI ecosystem. It integrates six independent pillars:

| Pillar | Icon | Domain |
|-------|------|---------|
| **Market** | 📈 | Prices, flows, risk appetite |
| **Credit** | 💳 | Liquidity, spreads, leverage |
| **Capex / Supply** | 🏗️ | Compute, chips, investment |
| **Infrastructure** | 🔌 | Power, grid, communication |
| **Adoption** | 🌐 | Real usage, workforce, diffusion |
| **Sentiment** | 🔥 | Hype intensity, narrative tone |

Each pillar is normalized, transformed, and aggregated into a **0–100 index** representing system-wide “bubble pressure.”

---

# 🎯 1. Conceptual Goal

Bubbles emerge when **expectations, investment, and sentiment** outpace **real-world fundamentals**.

The AIBPS tracks this imbalance by measuring *how extreme the current environment is compared to its own historical norms* dating back to **1980**.

It is not:

- a price target  
- a valuation model  
- a forecast  

It is a **stress indicator**.

---

# 🧱 2. Pillar Definitions

Below is the **current implementation (v0.2)**, scoped to what is *actually* running in your automated GitHub → Streamlit pipeline.

---

## 📈 2.1 Market Pillar  
**Icon:** 📈  
**Concept:** Investor exuberance, flows into AI-exposed assets, valuation momentum.

**Current Data Sources:**

- NVDA  
- SOXX, SMH  
- QQQ, XLK  
- AMD, TSM, ARM  
- Market-volume proxies  

**Processing:**

- Daily → monthly resampling  
- Rolling 10-year z-score  
- Sigmoid transformation → 0–100  

**Interpretation:**  
Higher = increasing investor overconfidence; speculative valuations.

---

## 💳 2.2 Credit Pillar  
**Icon:** 💳  
**Concept:** Bubbles thrive when credit markets underprice risk.

**Current Data Sources (FRED):**

- High-Yield OAS (BAMLH0A0HYM2)  
- Investment-Grade OAS (BAMLCC0A0CM)  

**Processing:**

- Invert spreads (low spreads = high pressure)  
- Rolling 10-year z-sigmoid  

**Interpretation:**  
Higher = cheaper risk-taking, low fear, liquidity abundance.

---

## 🏗️ 2.3 Capex / Supply Pillar  
**Icon:** 🏗️  
**Concept:** Overexpansion of compute, chips, and data center capacity.

**Current Data Sources (FRED):**

- PNFI (Private Nonresidential Fixed Investment)  
- UNXANO (Nonresidential structures)  
- Software investment series  
- ICT equipment investment  
- Semiconductor production index  
- Fab capacity utilization  

**Processing:**

- Annual/quarterly → monthly  
- Rebase first non-NA = 100  
- Composite = average of all rebased components  

**Interpretation:**  
Higher = increasing risk of overbuild.

---

## 🔌 2.4 Infrastructure Pillar  
**Icon:** 🔌  
**Concept:** Grid, power, and communication infrastructure stress.

**Current Data Sources (FRED):**

- Power + communication structures investment  
- Electric grid capacity utilization  

**Processing:**  
Same as Capex (rebased monthly composite).

**Interpretation:**  
Higher = more rapid expansion of physical infrastructure.

---

## 🌐 2.5 Adoption Pillar  
**Icon:** 🌐  
**Concept:** Sustainable demand: real-world adoption by businesses, consumers, and labor.

**Current Data Sources (placeholder):**

- Internet users per 100 people (annually)  
- Computer systems workforce employment  

**Current Behavior:**  
Flat—requires upgrade to more granular datasets.

**Planned Improvements:**

- ITU broadband data  
- AI publications (OpenAlex)  
- Cloud adoption metrics  
- AI workforce share (LinkedIn/BLS)  
- HuggingFace model usage  

---

## 🔥 2.6 Sentiment Pillar  
**Icon:** 🔥  
**Concept:** Narrative hype intensity, media attention, public obsession.

**Current Data Sources:**

- Google Trends for:
  - “AI”
  - “Artificial Intelligence”
  - “ChatGPT”
  - “OpenAI”
  - “Machine Learning”

**Current Behavior:**  
Inflated post-2023 (values near 99).

**Planned Upgrades:**

- GDELT news volume  
- Earnings call NLP  
- Reddit / HackerNews discussion volumes  
- X/Twitter (if available)  

---

# ⚙️ 3. Data Flow Architecture

     +------------------------+
     |   GitHub Actions CI     |
     +------------------------+
                 |
                 v
    +--------------------------+
    |  fetch_* scripts (FRED,  |
    |  yfinance, trends, etc.) |
    +--------------------------+
                 |
                 v
    +--------------------------+
    |   data/processed/*.csv   |
    +--------------------------+
                 |
                 v
    +--------------------------+
    |      compute.py          |
    | (normalize + composite)  |
    +--------------------------+
                 |
                 v
    +--------------------------+
    |   aibps_monthly.csv      |
    +--------------------------+
                 |
                 v
    +--------------------------+
    |   Streamlit dashboard    |
    +--------------------------+


---

# 📊 4. Normalization & Scaling

Because pillars use heterogeneous units, each is normalized using:

### **4.1 Rolling Z-Score**
Captures how unusual the present is relative to the last 24–120 months.

### **4.2 Clipping**
Prevents rare extremes from dominating.

### **4.3 Sigmoid Transform**
Maps z-scores → 0–100, compressing pathological outliers.

---

# 📚 5. Composite Score Construction

AIBPS(t):

\[
\text{AIBPS}(t) = \sum_{i=1}^{6} w_i\,P_i(t)
\]

A rolling average version is also computed:

\[
\text{AIBPS\_RA}(t) = \text{SMA}_{6\text{mo}}(\text{AIBPS}(t))
\]

Weights default to equal (1/6), but are user-adjustable.

---

# 🎓 6. How to Interpret the AIBPS

### ✔ **0–20: Depressed / Deflated**
- Weak private investment  
- Fearful credit markets  
- No speculative excess  
- Often seen after recessions  

### ✔ **20–40: Stable / Normal**
- Healthy growth  
- No overheating indicators  
- Reasonable credit conditions  

### ✔ **40–60: Accelerating**
- Investment rising  
- Valuations expanding  
- Media attention increasing  

### ✔ **60–80: Elevated Risk**
- Credit spreads tight  
- Capex rising faster than adoption  
- Sentiment markets heating up  

### ✔ **80–100: Bubble Pressure Zone**
Indicates that multiple pillars simultaneously show atypical exuberance.

Historically consistent with:

- Dot-Com (1998–2000)  
- Housing bubble peak (2006–2007)  
- Crypto bubble (late 2021)  

---

# 📘 7. APA References

**FRED Series**  
Federal Reserve Bank of St. Louis. (n.d.). *FRED Economic Data.* https://fred.stlouisfed.org/

- BAMLH0A0HYM2. (n.d.). ICE BofA high yield option-adjusted spread.  
- BAMLCC0A0CM. (n.d.). ICE BofA corporate index option-adjusted spread.  
- PNFI. (n.d.). Private nonresidential fixed investment.  
- UNXANO. (n.d.). Nonresidential structures.  
- IPB53800. (n.d.). Semiconductor industrial production index.  
- CAPUTLB50001SQ. (n.d.). Semiconductor capacity utilization.  
- CAPUTLG2211S. (n.d.). Electric power generation capacity utilization.  
- DTCTRC1A027NBEA. (n.d.). Software investment.  
- TLPCINS. (n.d.). ICT equipment investment.  
- ITNETUSERP2USA. (n.d.). Internet users per 100 people.  
- CEU6054150001. (n.d.). Computer systems employment.  

**Google Trends**  
Google. (n.d.). *Google Trends.* https://trends.google.com/

---

# 🚀 8. Roadmap

### Near-Term  
- Expand Infra (EIA grid + power data)  
- Expand Adoption (ITU + OpenAlex + cloud adoption)  
- Add GDELT sentiment components  
- Add “raw vs normalized vs indexed” toggle  

### Mid-Term  
- Bubble regime classification module  
- Subpillar weighting panel  
- Scenario simulation engine  

### Long-Term  
- Full academic preprint (AIBPS v1.0)  
- Real-time API  
- Research-grade backtesting suite  

---

# 📎 End of Document



