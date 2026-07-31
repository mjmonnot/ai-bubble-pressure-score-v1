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
Macro psychological temperature.

Inputs:
- UM Consumer Sentiment (UMCSENT)  
- Economic Policy Uncertainty (EPU)  
- VIX (monthly)

Composite: **Sentiment**

---

## 🧮 3. Normalization (0–100)

Applied via `normalize.py`:

### **Default method: Rolling-Z-Sigmoid**
- Computes rolling z-score (e.g., 36–60 months)
- Clips extreme outliers
- Passes through logistic sigmoid → stable 0–100 scale

### Pre-transforms (important for interpretability)

Before rolling-z-sigmoid, some pillars are converted so secular drift does not pin them in the “high” band for decades:

| Pillar | Input to normalization |
|--------|------------------------|
| **Market** | Equal-weight **12-month return** of QQQ / SOXX / NVDA (momentum), not rebased price levels |
| **Credit** | Spread level (OAS / BAA–AAA backbone) |
| **Capex / Infra / Adoption** | **12-month percent change** of the underlying level series |
| **Sentiment** | AI-attention composite (Trends + Wiki, optional FRED overlay) |

Without the YoY / momentum step, trending level series (software spending, fixed investment, NVDA prices) stay above their recent mean for long stretches and the composite looks permanently “elevated,” offering little regime contrast.

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
Weights are renormalized over the pillars that are non-missing in month _t_.

The system also computes:

- **AIBPS_RA** → rolling 6-month smoothing  
- **z-intensity metrics** (internal)
- **Pillars_reporting** → count of non-missing pillars in month _t_

### Publication rules

1. **Market required** — AIBPS is only published when the Market pillar is present. Capex/Infra decades before the equity basket are not labeled as AI bubble pressure.
2. **Live-edge freeze** — In the **most recent 4 months**, publish only when ≥ **5 of 6** pillars have reported (avoids false cliffs from FRED lag).
3. **Historical months** — before that live window, publish when ≥ **2** pillars are available (and Market is present).

Incomplete live-edge months still retain pillar-level values in `aibps_monthly.csv` for diagnostics; once Capex/Infra/Adoption catch up, the frozen month fills in automatically.

---

## 📉 5. Interpretation Guide

| AIBPS Range | Interpretation |
|-------------|----------------|
| **0–25**    | Cold / early-cycle |
| **25–50**   | Stable / neutral |
| **50–75**   | Elevated / late-cycle |
| **75–90**   | Stretched / fragile |
| **90–100**  | Bubble-like conditions |

**Important:**  
AIBPS ≠ prediction.  
It shows **relative pressure**, not future performance.

---

## 🧱 6. Limitations

- AI-capex data is partly manual until APIs exist  
- Cloud/connectivity adoption proxies still incomplete  
- The latest few months may be unpublished until Capex/Infra/Adoption catch up (live-edge ≥5-pillar rule)  
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

