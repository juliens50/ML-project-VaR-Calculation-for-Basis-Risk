# DFL Brent — Regime-Conditional VaR

Coursework / portfolio project building a regime-conditional Value-at-Risk model for the
DFL Brent (Platts Dated Brent − front-month ICE Brent) — the residual basis risk borne by any
physical desk that buys Dated-priced cargoes and hedges with ICE Brent paper.

The DFL is a structural premium that cannot be fully arbitraged away, and it is strongly
non-Gaussian (skewness +5.5, kurtosis +62), so a flat parametric VaR fails. The project
conditions the VaR on the market regime instead, then validates it against the baselines a
bank or trading house would actually run.

## The pipeline

Data collection and fusion (scripts 01–09) feed five modelling notebooks:

| Notebook | What it does |
|---|---|
| `01_eda` | Shows the DFL is strongly non-Gaussian and behaves as a mixture of regimes — no single distribution (Gaussian, Student-t, skew-normal) fits both the fat tails and the asymmetry. |
| `02_features_pca` | Compresses 17 correlated market-state features into 5 interpretable PCA factors: global curve tightness, risk-off, East-West arbitrage, macro momentum, trans-Atlantic spread. |
| `03_regimes_kmeans` | K-means (k=3) on the PCA factors → three directional regimes: Contango (downside risk), Calm, Physical tightness (upside risk). Found without ever using the DFL, yet they separate its distribution sharply and asymmetrically. |
| `04_var_quantile` | XGBoost quantile regression on regime + continuous features, temporal split (train 2014–2023, test 2024–2026), with split-conformal recalibration of the quantiles. |
| `05_backtest` | Kupiec / Christoffersen backtests, comparison against six baselines, and a winning XGBoost + FHS ensemble. |

## Key results

- Conditioning on the market state matters far more than the choice of distribution: moving
  from an unconditional Student-t to a regime-conditional model cuts pinball loss by about 26%,
  versus only 3% for adding fat tails.
- No single model dominates (FHS 0.376, per-regime 0.381, XGBoost 0.395), but the ensemble of
  XGBoost and FHS (0.354) beats them all and is the only model to pass every regulatory backtest
  on all four quantiles (Kupiec + Christoffersen).
- The target is the next-day change of the DFL (the 1-day P&L of the basis), modelled as
  conditional quantiles q01 / q05 / q95 / q99 — the downside and upside VaR.

## Data

12 years of daily data (2014-01 → 2026-05, ~3,000 ICE Brent business days):

- Three crude benchmarks (Brent, WTI, Dubai) across their forward curves L1–L6, plus gasoil.
- Macro variables (VIX, trade-weighted USD) and US inventory anomalies (EIA).
- Sources: Platts (Dated), ICE (futures), FRED, EIA — all look-ahead-safe (publication dates
  respected, no future leakage).

The merged master dataset is committed at `data/master_dataset.csv` (and `.pkl`), documented in
`data/master_dataset.md`. Raw per-source files and processed intermediates (`data/raw/`,
`data/processed/`) are gitignored.

## Repository layout

```
.
├── config/                       # API keys (gitignored)
├── data/
│   ├── master_dataset.csv/.pkl   # final merged dataset (committed)
│   ├── master_dataset.md         # feature documentation
│   ├── raw/                      # raw per-source downloads (gitignored)
│   └── processed/                # PCA scores, regime labels, VaR predictions (gitignored)
├── scripts/                      # 01–09: data collection, fusion, export
├── notebooks/                    # 01–05: EDA → PCA → regimes → VaR → backtest
├── requirements.txt
└── README.md
```

## Data collection scripts

| Script | Series |
|---|---|
| `01_download_fred.py` | `VIXCLS` (VIX), `DTWEXBGS` (trade-weighted USD), `DCOILBRENTEU` / `DCOILWTICO` (cross-check) |
| `02_download_yfinance.py` | `CL=F` (NYMEX WTI front-month, cross-check) |
| `03_download_eia.py` | US stocks `WCESTUS1` (crude), `WDISTUS1` (distillate) |
| `04_load_manual_brent.py` | Platts Dated Brent + ICE Brent L1–L6 from `Data_brent.xlsx` |
| `05_load_manual_gasoil.py` | ICE Low-Sulphur Gasoil L1/L2 |
| `06_load_manual_crude.py` | ICE WTI L1–L6 + Dubai L1–L3 from `Data_crude.xlsx` |
| `08_build_master_dataset.py` | Aligns all series on the ICE Brent calendar and computes derived features |
| `09_export_pkl.py` | Exports the master dataset to `.pkl` for the notebooks |

## Quick start

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Set up API keys (free: FRED + EIA)
cp config/api_keys.env.example config/api_keys.env
# Edit config/api_keys.env and paste your keys

# 3. Rebuild the data (manual Excel files required at project root), or skip —
#    the committed data/master_dataset.pkl is enough to run the notebooks directly.
python scripts/01_download_fred.py
python scripts/02_download_yfinance.py
python scripts/03_download_eia.py
python scripts/04_load_manual_brent.py
python scripts/05_load_manual_gasoil.py
python scripts/06_load_manual_crude.py
python scripts/08_build_master_dataset.py
python scripts/09_export_pkl.py

# 4. Run the notebooks in order (01 → 05)
```

The notebooks read the committed `data/master_dataset.pkl`, so they run without re-downloading.
Each notebook writes its intermediate output (PCA scores, regime labels, VaR predictions) into
`data/processed/` for the next one.

## Limitations (stated honestly)

- The 2026 spike (a +$18 one-day move) exceeds anything in the training history — VaR must be
  complemented by stress testing.
- K-means is fit on the full sample; a production system would refit on a rolling window.
- Part of the measured daily DFL move is snap-time noise (Platts assessed ~16:30 London, ICE
  settles 19:30), not true economic risk.

## Possible extensions

- An applied "trader's view" notebook: dollar VaR for a position, P&L simulation, Expected
  Shortfall, and position sizing.
- Walk-forward / expanding-window refitting; Expected Shortfall (Basel/FRTB); ICE COT positioning
  and ARA inventory data as additional fat-tail signals.
