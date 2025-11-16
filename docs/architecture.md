# 🏗️ AIBPS System Architecture  
### Data Pipeline • Normalization Engine • Composite Computation • Visualization Layer  
_Last updated: {{ auto-updated }}_

---

# 🎯 Purpose of This Document
This document explains the **end-to-end architecture** of the AI Bubble Pressure Score (AIBPS), including:

- System flow  
- Data ingestion  
- Processing & normalization  
- Pillar computation  
- Composite scoring  
- Streamlit UI architecture  
- GitHub Actions automation  
- File structure & extensibility  

It is intended for contributors and analysts who want to understand how AIBPS is built and how to extend it.

---

# 🧭 High-Level Overview

AIBPS operates as a **fully automated data pipeline**, with:

1. **Fetchers**  
   - Pull raw data (FRED, Yahoo Finance, Google Trends, manual CSVs)
   - Write into the `data/raw/` directory

2. **Processors**  
   - Clean, resample, validate, normalize  
   - Output standardized pillar time series into `data/processed/`

3. **Composite Engine**  
   - Loads all pillar time series  
   - Normalizes them using rolling Z-score → sigmoid  
   - Applies weights  
   - Computes the composite AIBPS  
   - Writes monthly output to `data/processed/aibps_monthly.csv`

4. **Streamlit Visualization**  
   - Loads the composite output  
   - Produces interactive charts and diagnostics  
   - Highlights historical bubble regimes (Dot Com, Housing, AI 2023–2025)  

5. **GitHub Actions Automation**  
   - Runs nightly or manually  
   - Fetches new data  
   - Rebuilds processed pillar files  
   - Recomputes the composite  
   - Commits changes automatically  
   - Refreshes the Streamlit Cloud dashboard  

---

# 🔁 Architecture Diagram

             ┌─────────────────────────┐
             │   GitHub Actions (CRON) │
             └──────────────┬──────────┘
                            ▼
               ┌──────────────────────────┐
               │      Fetchers Layer      │
               │  (market, credit, etc.)  │
               └──────────────┬───────────┘
                            Raw CSVs
                            ▼
               ┌──────────────────────────┐
               │   Processing Layer        │
               │  clean → resample → QA    │
               │ Writes to processed CSVs  │
               └──────────────┬───────────┘
                          Pillar Time Series
                            ▼
               ┌──────────────────────────┐
               │   Composite Engine        │
               │ normalize → weight → sum  │
               │ produces AI BPS monthly   │
               └──────────────┬───────────┘
                          aibps_monthly.csv
                            ▼
               ┌──────────────────────────┐
               │   Streamlit Frontend      │
               │ interactive charts & UI   │
               └───────────────────────────┘
