# ============================================
# README.md
# ============================================

# 🤖 AI Bubble Pressure Score (AIBPS)

The **AI Bubble Pressure Score (AIBPS)** is a research-grade, transparent index that tracks how overheated or subdued the AI economy is relative to its own history and to past macro bubble regimes (dot-com, housing/GFC, COVID).

AIBPS integrates **six major economic pillars**:
- 📈 **Market**
- 💳 **Credit**
- 🏭 **Capex / Supply**
- 🖥️ **Infrastructure**
- 🧩 **Adoption**
- 🧠 **Sentiment**

Each is normalized to **0–100** and combined into a single composite updated monthly.

---

## 📊 Live Dashboard

**👉 Streamlit App:**  
https://aibps-v0-1.streamlit.app

Features:
- Full AIBPS history (~1980–present)
- Dynamic bubble-regime shading (green → yellow → orange → red)
- Major macro event callouts (Dot-Com, Lehman, COVID, etc.)
- Pillar trajectories
- Sub-pillar debug charts
- Live adjustable pillar weights
- Pillar contribution breakdown

---

## 🧱 Project Structure

aibps-v0-1/
├── app/
│ └── streamlit_app.py
├── src/
│ └── aibps/
│ ├── compute.py
│ ├── normalize.py
│ ├── fetch_market.py
│ ├── fetch_credit.py
│ ├── fetch_macro_capex.py
│ ├── fetch_infra.py
│ ├── fetch_adoption.py
│ ├── fetch_sentiment.py
│ └── config.yaml
├── data/
│ ├── raw/
│ └── processed/
├── docs/
│ ├── METHODOLOGY.md
│ ├── ARCHITECTURE.md
│ └── INTERPRET_AIBPS.md
└── .github/workflows/update-data.yml


---

## ⚙️ How the System Works

### **1. Fetch raw data**
Automated scripts in `src/aibps/` pull:
- Market data (yfinance)
- Credit spreads (FRED)
- Capex (macro capex, hyperscaler AI capex CSV)
- Infrastructure proxies (FRED + curated CSVs)
- Adoption indicators (enterprise software, digital labor, etc.)
- Sentiment measures (consumer sentiment, uncertainty, VIX)

Raw → processed → monthly-aligned outputs written to  
`data/processed/*.csv`

---

### **2. Normalize & unify**
`compute.py`:
- Aligns all pillars on a **common monthly index** (≈1980+)
- Applies normalization (rolling-z-sigmoid, percentiles, z-score)
- Produces:
  - Normalized pillar scores (0–100)
  - Sub-pillar columns
  - Composite AIBPS
  - Smoothed AIBPS_RA (rolling average)

Outputs to:  
`data/processed/aibps_monthly.csv`

---

### **3. Visualize**
The Streamlit dashboard shows:
- 📈 AIBPS main line (0–100)
- 🟥/🟧/🟨/🟩 bubble regime shading
- 🏛️ historical macro events
- 🔧 pillar debug panels
- 🎛️ adjustable weights
- 🌡️ normalized pillar contributions

---

## ▶️ Run Locally



git clone https://github.com/mjmonnot/aibps-v0-1.git

cd aibps-v0-1
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FRED_API_KEY="YOUR_KEY"

python src/aibps/fetch_market.py
python src/aibps/fetch_credit.py
python src/aibps/fetch_macro_capex.py
python src/aibps/fetch_infra.py
python src/aibps/fetch_adoption.py
python src/aibps/fetch_sentiment.py
python src/aibps/compute.py

streamlit run app/streamlit_app.py

---

## 🤖 GitHub Actions (Auto Update)

`.github/workflows/update-data.yml` refreshes:
- raw data  
- processed pillars  
- composite AIBPS  
- dashboard-ready CSV  

Runs on schedule using your secret `FRED_API_KEY`.

---

## 📚 Documentation

See the `docs/` folder for:
- `METHODOLOGY.md` – scientific underpinnings  
- `ARCHITECTURE.md` – compute + dataflow diagrams  
- `INTERPRET_AIBPS.md` – how to read the index  

---


