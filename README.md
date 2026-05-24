# DFL Brent — Conditional VaR Project

Coursework / portfolio project: regime-conditional Value-at-Risk on the **DFL Brent**
(Dated Brent − front-month ICE Brent), the residual basis risk borne by any physical
desk that buys Dated-priced cargoes and hedges with ICE Brent paper.

This repository covers **Phase 1: data collection and fusion only**. Modelling
(PCA → K-means regimes → XGBoost quantile regression for VaR_95 / VaR_99) is a later phase.

## Repository layout

```
.
├── config/
│   ├── api_keys.env.example   # template; copy to api_keys.env and fill in
│   └── api_keys.env           # (gitignored — your keys)
├── data/
│   ├── raw/
│   │   ├── fred/              # raw FRED downloads
│   │   ├── yfinance/          # raw Yahoo Finance downloads
│   │   └── manual/            # CSVs you supply yourself (Brent L1, Brent L2)
│   ├── processed/             # cleaned per-series (later)
│   └── master_dataset.parquet # final merged dataset (later)
├── scripts/
│   ├── 01_download_fred.py        # DCOILBRENTEU, DCOILWTICO, VIXCLS, DTWEXBGS
│   ├── 02_download_yfinance.py    # CL=F (NYMEX WTI front-month)
│   ├── 03_download_eia.py         # Stocks (WCESTUS1, WDISTUS1) + WTI futures historical (RCLC1, RCLC2)
│   ├── 04_load_manual_brent.py    # Splits Data_brent.xlsx into brent_dated.csv + brent_l1..l6.csv
│   └── 05_load_manual_gasoil.py   # Extracts gasoil L1/L2 from the multi-maturity Excel
├── requirements.txt
└── README.md
```

## Quick start

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Set up API keys
#    FRED — free: https://fred.stlouisfed.org/docs/api/api_key.html
#    EIA  — free: https://www.eia.gov/opendata/register.php
cp config/api_keys.env.example config/api_keys.env
# Edit config/api_keys.env and paste your keys after FRED_API_KEY= and EIA_API_KEY=

# 3. Run the downloads
python scripts/01_download_fred.py
python scripts/02_download_yfinance.py
python scripts/03_download_eia.py
python scripts/04_load_manual_brent.py    # requires Data_brent.xlsx at project root
python scripts/05_load_manual_gasoil.py   # requires 'Data_all_maturities - Copie.xlsx' at project root
```

Both scripts are **idempotent**: re-running overwrites the raw CSVs with a fresh pull.

## Data sources implemented so far

| Source | Script | Series |
|---|---|---|
| FRED | `01_download_fred.py` | `DCOILBRENTEU` (Brent spot, Argus-derived Dated proxy), `DCOILWTICO` (WTI Cushing spot), `VIXCLS` (VIX), `DTWEXBGS` (Trade-Weighted USD Broad) |
| Yahoo Finance | `02_download_yfinance.py` | `CL=F` (NYMEX WTI front-month continuous) |
| EIA | `03_download_eia.py` | Stocks (weekly, ongoing): `WCESTUS1` (US crude excl. SPR), `WDISTUS1` (US distillate fuel oil). Futures (daily, **historical only — EIA discontinued 2024-04-05**): `RCLC1`, `RCLC2` (NYMEX WTI L1/L2 continuous) |
| Manual | `04_load_manual_brent.py` | Splits user-supplied `Data_brent.xlsx` into per-series CSVs: Platts Dated Brent + ICE Brent L1..L6 continuous |
| Manual | `05_load_manual_gasoil.py` | Extracts ICE Low-Sulphur Gasoil L1 + L2 from `Data_all_maturities - Copie.xlsx` (USD/tonne) |

History window: **2014-01-01 → today**.

## Manual Brent file

Drop a single Excel file named `Data_brent.xlsx` at the project root with the
following layout (3 header rows, then daily data):

```
row 0   |  <blank>  |  BRUT
row 1   |  <blank>  |  Dated               |  ICE Brent  ...
row 2   |  <blank>  |  cr.BRED.DTD@SP@P.M  |  fu.BI.E1.C  fu.BI.E2.C ... fu.BI.E6.C
row 3+  |   date    |  price values across 7 columns (Platts Dated + L1..L6)
```

Running `python scripts/04_load_manual_brent.py` splits this into:

```
data/raw/manual/
├── brent_dated.csv     # Platts Dated Brent assessment
├── brent_l1.csv ... brent_l6.csv   # ICE Brent continuous L1..L6
```

Each file has schema `date,value` (USD/bbl).

## Notes on the data

- `DCOILBRENTEU` is EIA's "Europe Brent Spot Price FOB", sourced from Argus North Sea
  Dated since 2011. It is a reasonable Dated proxy (Argus, not Platts). Differences
  vs Platts Dated are typically a few cents/bbl.
- `CL=F` returned by yfinance is a continuous front-month series; treat it as a
  back-adjusted proxy. Use it as a cross-check against `DCOILWTICO`.

## Roadmap (not implemented yet)

- Manual loader: read Brent Dated + ICE L1..L6 from CSV / Excel into normalized per-series files
- Master dataset build (alignment, derived features, lag bookkeeping, quality report)
- Optional: ICE COT positioning data for ICE Brent (FCA-regulated; CFTC does not cover it)
- Optional Tier 2: yield curve (`DGS2`, `DGS10`), `HO=F` and `RB=F` (for 3-2-1 crack)
