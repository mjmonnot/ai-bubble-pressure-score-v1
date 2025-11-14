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

