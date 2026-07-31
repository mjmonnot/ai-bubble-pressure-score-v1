# 📘 AIBPS Methodology

This document details the conceptual scaffolding, data selection, normalization logic, and composite construction behind the **AI Bubble Pressure Score (AIBPS)**.

---

## 🎯 1. Purpose & Philosophy

AIBPS answers:

> **“Relative to its own historical behavior, how stretched are AI-related economic conditions today?”**

The index is:
- **Comparative** (vs. history)
- **Cross-disciplinary** (markets, macro, adoption, psychology)
- **Non-predictive** (not a trading signal)
- **Transparent** (open methodology)

---

## 🧊 2. Pillars & Sub-Pillars

AIBPS uses **six pillars**, each scaled to **0–100**:

### **📈 Market**
Tracks AI-exposed asset valuations & momentum.  
Inputs:
- Nasdaq-100  
- SOXX / SMH  
- NVDA, AMD, AVGO, MSFT (optionally)  
Processing:
- Monthly close
- Composite index

---

### **💳 Credit**
Measures financial conditions & macro stress.  
Inputs (FRED):
- High-Yield OAS  
- IG OAS  
Processing:
- Inversion & standardization (high spreads → stress → lower score)

---

### **🏭 Capex / Supply**
Tracks capital formation into AI compute.

Sub-pillars:
- **Capex_Macro_Comp** (macro capex series)
- **Capex_Hyperscaler** (Meta, AWS, GCP, MSFT AI capex)
- **Capex_Supply** (composite)

---

### **🖥️ Infrastructure**
Physical capacity & constraints affecting AI scale-up.

Sub-pillars:
- **Infra_DC_Construction** (data center buildout)
- **Infra_Power_Capacity** (electrical generation)
- **Infra_Grid_Stress** (optional)
- Composite: **Infra**

---

### **🧩 Adoption**
Tracks real-world AI, digital, and cloud utilization.

Sub-pillars (active):
- **Adoption_Enterprise_Software**  
- **Adoption_Digital_Labor** (productivity + unit labor costs)

Scaffolded (requires future data):
- **Adoption_Cloud_Services**  
- **Adoption_Connectivity**

---

### **🧠 Sentiment**
AI attention / hype intensity, with optional macro overlay.

Primary inputs (auto-refreshed):
- Google Trends basket (AI / generative AI / ChatGPT / machine learning)
- Wikipedia pageviews for AI-related articles

Secondary overlay (FRED, when available):
- UM Consumer Sentiment (UMCSENT)
- Economic Policy Uncertainty (EPU)
- VIX (monthly)

Composite: **Sentiment** = z-mean of available Trends/Wiki components (plus light FRED overlay when present).

---

## 🧮 3. Normalization (0–100)

Applied via `normalize.py`:

### **Default method: Rolling-Z-Sigmoid**
- Computes rolling z-score (e.g., 36–60 months)
- Clips extreme outliers
- Passes through logistic sigmoid → stable 0–100 scale

### Alternatives
- Percentile rank  
- Standard z-score (for debugging)

---

## 🧠 Why Rolling-Z-Sigmoid?

- Adjusts for **regime drift** (AI economy structurally changing over decades)  
- Ensures **bounded scale** (0–100)  
- Offers **interpretable tail conditions**  
- Used in macro risk systems, climate metrics, and credit analytics  

---

## 🎛️ 4. Composite Score Formula

Let each pillar _p_ be normalized to 0–100.

**AIBPS(t) = Σ [ weight_p * pillar_p(t) ]**

Defaults: **equal weights (1/6 each)**  
Changeable in `config.yaml` or Streamlit UI.

The system also computes:

- **AIBPS_RA** → rolling 6-month smoothing  
- **z-intensity metrics** (internal)

---

## 📉 5. Interpretation Guide

| AIBPS Range | Interpretation |
|-------------|----------------|
| **0–20**    | Deep stress, washout, capitulation |
| **20–40**   | Below-trend conditions |
| **40–60**   | Normal / typical | 
| **60–80**   | Elevated, overheating |
| **80–100**  | Bubble-like conditions |

**Important:**  
AIBPS ≠ prediction.  
It shows **relative pressure**, not future performance.

---

## ✅ Historical boom sanity check

Before accepting methodology, wiring, or normalization changes, verify that **AIBPS_RA** still shows elevated peaks in the known boom / stress windows:

| Episode | Approximate window | Expectation |
|---------|--------------------|-------------|
| Dot-com | 1999–2001 | Clear peak near early 2000 |
| Housing / pre-GFC | 2005–2008 | Elevated peak(s) into 2006–2007 |
| Lehman / GFC | 2008–2009 | Elevated reading around the crisis |
| AI boom (current) | 2023–present | Elevated late-sample peak |

**Rule of thumb:** if a change washes out these peaks, flattens the series into a permanently “high” band, or moves boom maxima far from those windows, **stop, double-check the work, and prefer reverting** rather than “fixing forward” with more transforms.

`compute.py` prints these window maxima after each recompute as a quick regression check.

---

## 🧱 6. Limitations

- AI-capex data is partly manual until APIs exist  
- Cloud/connectivity adoption proxies still incomplete  
- Sentiment is macro, not AI-specific  
- Normalization window selection affects sensitivity  
- Equal weighting may not reflect actual economic influence  

---

## 🔧 7. How to Extend

To add new sub-pillars:
1. Create new `fetch_*.py` script  
2. Add new processed CSV  
3. Update normalization mapping in `config.yaml`  
4. Include in `compute.py`  
5. Add visuals in Streamlit dashboard  

To adjust weights:
- Modify `config.yaml`  
- Or adjust sliders in Streamlit  

---

