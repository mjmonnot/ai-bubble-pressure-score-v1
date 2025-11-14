# 📘 AI Bubble Pressure Score (AIBPS)
### Overview, Methods, Pillars, Interpretation & Data Sources (v0.2)  
_Last updated: {{ auto-updated by GitHub Action }}_

---

# 🧠 1. What Is the AIBPS?

The **AI Bubble Pressure Score (AIBPS)** is a multi-pillar economic composite designed to estimate **systemic overheating** in the AI-driven economy. Its goal is to detect **bubble-like pressure** using signals from:

- Financial markets  
- Corporate investment & supply chains  
- Credit conditions  
- Infrastructure capacity  
- AI adoption trends  
- Public & institutional sentiment  

Unlike simple price indices, the AIBPS attempts to measure **structural stress**, not just valuation spikes.

---

# 🏗️ 2. Pillar Framework

AIBPS aggregates **six pillars**, each normalized onto a **0–100 pressure scale** using rolling z-sigmoid normalization.

| Pillar | Meaning | Why It Matters | Normalization |
|-------|---------|----------------|---------------|
| **Market** | AI-equity–linked pricing & volatility | Captures speculative excess | Rolling Z-Sigmoid |
| **Credit** | HY & IG spreads | Detects financial conditions & risk | Rolling Z-Sigmoid |
| **Capex / Supply** | AI-major capex + macro ICT investment | Detects overbuilding cycles | Rolling Z-Sigmoid |
| **Infrastructure** | DC power, cooling, rackspace constraints | Capacity strain amplifies bubbles | Rolling Z-Sigmoid |
| **Adoption** | Enterprise penetration & usage | Measures real economic absorption | Rolling Z-Sigmoid |
| **Sentiment** | Google Trends + narrative intensity | Social hype accelerates bubbles | Rolling Z-Sigmoid |

Each pillar contributes **equally** by default (weights editable in `config.yaml`).

---

# 🔧 3. Data Pipeline Overview


## Scripts (in `src/aibps/`)
- `fetch_market.py` – AI-linked asset series (NDX, SOXX, NVDA basket)
- `fetch_credit.py` – FRED HY/IG spreads  
- `fetch_capex.py` – Macro capex + AI corporate capex  
- `fetch_infra.py` – Data center capacity, power, cooling  
- `fetch_adoption.py` – Enterprise AI adoption  
- `fetch_sentiment.py` – Google Trends + narrative mentions  
- `normalize.py` – Rolling Z / Z-Sigmoid transforms  
- `compute.py` – Pillar combination → composite → AIBPS output  

## Automated Updates  
GitHub Actions (`.github/workflows/update-data.yml`) runs nightly:
- Fetches fresh data  
- Normalizes pillars  
- Recomputes composite  
- Commits updated processed files  
- Refreshes Streamlit app  

---

# 🧮 4. Normalization Model

AIBPS uses **Rolling Z-Sigmoid normalization**, which:

- Captures **local deviation** (short-term overheating)  
- Adapts to **long-run drift**  
- Produces intuitive **0–100 scaled pressure**  

### Formula (simplified)

z = (x − rolling_mean) / rolling_std
z_clipped = clip(z, -z_clip, +z_clip)
score = 100 * sigmoid(z_clipped)

This keeps the model robust over long time horizons (1980 → present).

---

# 📊 5. Composite Construction

The AIBPS composite is:

AIBPS = Σ ( weight_i × pillar_i_normalized )


Default weights:

Market: 1/6
Credit: 1/6
Capex/Supply: 1/6
Infrastructure: 1/6
Adoption: 1/6
Sentiment: 1/6


Weights are configurable via `config.yaml`.

---

# 📈 6. Interpretation Guide

### **0–30: Low Pressure (Green)**
- Normal structural conditions  
- Underbuilding or steady expansion  
- No speculation signal  

### **30–55: Neutral (Yellow)**
- Mixed indicators  
- Investment and adoption rising  
- No clear bubble dynamics  

### **55–75: Elevated (Orange)**
- Bubble formation zone  
- Sentiment rising faster than fundamentals  
- Credit spreads narrowing despite risk  
- Infrastructure strain emerging  

### **75–100: Extreme (Red)**
- Bubble acceleration  
- Speculative feedback loops  
- Rapid capex + euphoric sentiment  
- Historically associated with crash regimes  

---

# 🏦 7. Historical Anchors

AIBPS marks historically relevant peaks:

- **Dot-Com Peak (Mar 2000)**  
- **Housing Bubble Peak (2006)**  
- **Lehman Event (Sep 2008)**  
- **Generative AI Breakout (2022–2025)**  

As long-run data (1980s onward) is integrated, these periods help calibrate structural comparisons.

---

# 🌐 8. Data Sources (Primary)

## Market
- NASDAQ 100  
- SOXX Semiconductor Index  
- NVDA/AMD/MSFT/GOOGL/META weighted basket  
- Source: Yahoo Finance  

## Credit
- FRED HY OAS (`BAMLH0A0HYM2`)  
- FRED IG OAS (`BAMLC0A0CM`)  

## Capex / Supply
- PNFI (Nonresidential Fixed Investment)  
- UNXANO (Information Processing Equipment)  
- Major AI capex (NVDA, AMD, MSFT, GOOGL 10-K/10-Q)  

## Infrastructure
- Data center power capacity (EIA, CBRE, Statista)  
- Cooling demand trends  
- Rackspace inventory / pricing  

## Adoption
- Global enterprise AI penetration (McKinsey, Deloitte)  
- Cloud compute consumption  
- Model API usage  

## Sentiment
- Google Trends search intensity  
- Newswire frequency (GDELT — planned)  
- Social sentiment (planned)  

---

# 🔮 9. Planned Enhancements

- **AI Compute Cost Index** (GPU availability, cluster cost)  
- **Token-inflation–adjusted compute demand metrics**  
- **VC funding cycle integration**  
- **Labor displacement indicators**  
- **International AI adoption differentials**  
- **Regulatory acceleration / deceleration metrics**  

---

# 📚 10. Key References (APA)

McKinsey Global Institute. (2023). *The State of AI in 2023.*  
OpenAI. (2024). *GPT-4 Technical Report.*  
Federal Reserve Bank of St. Louis. (2025). *FRED Economic Database.*  
GDELT Project. (2024). *Global Database of Events, Language, and Tone.*  
CBRE Research. (2024). *North America Data Center Trends.*  
Statista. (2024). *Global AI Market & Adoption Indicators.*  

---

# 📎 11. How to Use This Document

This file should serve as the **primary methodological reference** for the AIBPS project.  
It is linked from:

- GitHub repository  
- Streamlit dashboard  
- Documentation portal (optional future GitHub Pages site)  

---
