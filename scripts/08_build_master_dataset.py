"""
08_build_master_dataset.py
Build the single master dataset that the modelling phase will consume.

Inputs (all already produced by scripts 01..06):
  - data/raw/manual/   brent_dated, brent_l1..l6, wti_l1..l6, dubai_l1..l3, gasoil_l1..l2
  - data/raw/fred/     DCOILBRENTEU (cross-check only -- not in master), VIXCLS, DTWEXBGS
                       DCOILWTICO (cross-check only -- not in master)
  - data/raw/yfinance/ CL_F (NYMEX WTI L1, cross-check kept in master per user choice)
  - data/raw/eia/      WCESTUS1 (US crude stocks), WDISTUS1 (US distillate stocks)

Calendar:
  ICE Brent business calendar is the master. Brent dates drive everything.

Forward-fill policy:
  None. NaN gaps are preserved as NaN (single-market holidays, Asian non-trading
  days for Dubai, weekly EIA stocks released only on Wednesdays). The modelling
  step downstream is responsible for handling NaN explicitly.

Derived features (computed AFTER alignment):
  Target           : DFL = brent_dated - brent_l1
  Brent curve      : brent_l1_l2, brent_l1_l3, brent_l1_l6
  WTI curve        : wti_l1_l2, wti_l1_l3, wti_l1_l6
  Dubai curve      : dubai_l1_l2, dubai_l1_l3
  Cross-products   : brent_wti_arb, brent_dubai_efs, gasoil_brent_crack
  Returns          : brent_l1_log_ret_1d, dfl_chg_1d
  Realised vol 20d : brent_l1_vol_20d, dfl_vol_20d
  Macro changes    : vix_chg_5d, dxy_chg_5d
  Stock anomalies  : crude_stock_anomaly, dist_stock_anomaly
                     (= value - 5y rolling seasonal mean for same iso-week)

Output: data/master_dataset.csv  (single file, all features, one row per business day)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data" / "raw"
OUT_PATH = PROJECT_ROOT / "data" / "master_dataset.csv"

GASOIL_BBL_PER_TONNE = 7.45  # conversion factor for gasoil USD/tonne -> USD/bbl

# -----------------------------------------------------------------------------
# Loaders for the different raw layouts
# -----------------------------------------------------------------------------

def _read_simple(path: Path, value_col_name: str) -> pd.Series:
    """Read a 2-col CSV {date|period, value} and return a Series indexed by date."""
    df = pd.read_csv(path)
    date_col = "date" if "date" in df.columns else "period"
    df[date_col] = pd.to_datetime(df[date_col])
    return df.set_index(date_col)["value"].rename(value_col_name).sort_index()


def load_daily_series() -> pd.DataFrame:
    """Merge all daily series on a union index, then we will reindex to Brent calendar."""
    series: list[pd.Series] = []

    # Manual: Brent
    series.append(_read_simple(RAW / "manual" / "brent_dated.csv", "brent_dated"))
    for k in range(1, 7):
        series.append(_read_simple(RAW / "manual" / f"brent_l{k}.csv", f"brent_l{k}"))

    # Manual: WTI ICE
    for k in range(1, 7):
        series.append(_read_simple(RAW / "manual" / f"wti_l{k}.csv", f"wti_l{k}"))

    # Manual: Dubai Platts
    for k in range(1, 4):
        series.append(_read_simple(RAW / "manual" / f"dubai_l{k}.csv", f"dubai_l{k}"))

    # Manual: Gasoil
    series.append(_read_simple(RAW / "manual" / "gasoil_l1.csv", "gasoil_l1_usd_tonne"))
    series.append(_read_simple(RAW / "manual" / "gasoil_l2.csv", "gasoil_l2_usd_tonne"))

    # FRED: macro
    series.append(_read_simple(RAW / "fred" / "VIXCLS.csv",   "vix"))
    series.append(_read_simple(RAW / "fred" / "DTWEXBGS.csv", "dxy"))

    # yfinance: WTI NYMEX cross-check (close only)
    cl = pd.read_csv(RAW / "yfinance" / "CL_F.csv")
    cl["date"] = pd.to_datetime(cl["date"])
    series.append(cl.set_index("date")["close"].rename("cl_f_close").sort_index())

    df = pd.concat(series, axis=1)
    df.index.name = "date"
    return df.sort_index()


def load_weekly_stocks() -> pd.DataFrame:
    """
    Load EIA weekly stocks indexed by *publication_date* (= when the data becomes
    publicly available). Forward-filling from this index into the daily master
    is automatically look-ahead-safe.
    """
    frames: list[pd.Series] = []
    spec = {
        "WCESTUS1": "crude_stocks_us",
        "WDISTUS1": "dist_stocks_us",
    }
    for series_id, col_name in spec.items():
        df = pd.read_csv(RAW / "eia" / f"{series_id}.csv", parse_dates=["period", "publication_date"])
        s = df.set_index("publication_date")["value"].rename(col_name).sort_index()
        # If two releases share the same publication_date (unlikely), keep the last.
        s = s[~s.index.duplicated(keep="last")]
        frames.append(s)
    return pd.concat(frames, axis=1).sort_index()


# -----------------------------------------------------------------------------
# Feature engineering
# -----------------------------------------------------------------------------

def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    # Target
    df["DFL"] = df["brent_dated"] - df["brent_l1"]

    # Brent calendar spreads
    df["brent_l1_l2"] = df["brent_l1"] - df["brent_l2"]
    df["brent_l1_l3"] = df["brent_l1"] - df["brent_l3"]
    df["brent_l1_l6"] = df["brent_l1"] - df["brent_l6"]

    # WTI calendar spreads (ICE WTI)
    df["wti_l1_l2"] = df["wti_l1"] - df["wti_l2"]
    df["wti_l1_l3"] = df["wti_l1"] - df["wti_l3"]
    df["wti_l1_l6"] = df["wti_l1"] - df["wti_l6"]

    # Dubai calendar spreads
    df["dubai_l1_l2"] = df["dubai_l1"] - df["dubai_l2"]
    df["dubai_l1_l3"] = df["dubai_l1"] - df["dubai_l3"]

    # Cross-product features
    df["brent_wti_arb"]   = df["brent_l1"]  - df["wti_l1"]
    df["brent_dubai_efs"] = df["brent_l1"]  - df["dubai_l1"]
    df["gasoil_brent_crack"] = df["gasoil_l1_usd_tonne"] / GASOIL_BBL_PER_TONNE - df["brent_l1"]

    # Returns / changes
    df["brent_l1_log_ret_1d"] = np.log(df["brent_l1"] / df["brent_l1"].shift(1))
    df["dfl_chg_1d"]          = df["DFL"].diff()

    # 20-business-day realised volatility (slow, stable)
    df["brent_l1_vol_20d"] = df["brent_l1_log_ret_1d"].rolling(20).std()
    df["dfl_vol_20d"]      = df["dfl_chg_1d"].rolling(20).std()

    # EWMA realised volatility of the DFL (fast-reacting, smooth — RiskMetrics-style).
    # alpha=0.10 → ~9-day effective memory: reacts faster than the 20d window and
    # avoids the "ghost effect" of a fixed window. Look-ahead-safe (uses changes up to t).
    df["dfl_vol_ewma"] = np.sqrt((df["dfl_chg_1d"] ** 2).ewm(alpha=0.10).mean())

    # Macro short-horizon changes
    df["vix_chg_5d"] = df["vix"].diff(5)
    df["dxy_chg_5d"] = df["dxy"].diff(5)

    # Stock anomalies (5y rolling seasonal mean for same iso-week)
    df["crude_stock_anomaly"] = _seasonal_anomaly(df.index, df["crude_stocks_us"])
    df["dist_stock_anomaly"]  = _seasonal_anomaly(df.index, df["dist_stocks_us"])

    return df


def _seasonal_anomaly(idx: pd.DatetimeIndex, series: pd.Series, lookback_years: int = 5) -> pd.Series:
    """
    For each date, compute (value - mean of same iso-week over the previous N years).
    NOT used on the year itself: only strictly past years contribute, so this is
    look-ahead-safe.
    """
    iso_year = idx.isocalendar().year.astype(int)
    iso_week = idx.isocalendar().week.astype(int)
    tmp = pd.DataFrame({"yr": iso_year, "wk": iso_week, "v": series.values}, index=idx)
    # Mean per (year, week)
    weekly = tmp.groupby(["yr", "wk"])["v"].mean().unstack("wk")
    # Rolling mean of the previous `lookback_years` years (shift(1) excludes current year)
    seasonal_mean = weekly.rolling(window=lookback_years, min_periods=3).mean().shift(1)
    # Map back to the daily index
    out = pd.Series(np.nan, index=idx, dtype=float)
    for (yr, wk), val in seasonal_mean.stack().items():
        mask = (tmp["yr"] == yr) & (tmp["wk"] == wk)
        out.loc[mask] = val
    return series - out


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> int:
    print("== Loading daily series ==")
    daily = load_daily_series()
    print(f"  Union index: {len(daily)} dates ({daily.index.min().date()} → {daily.index.max().date()})")

    # Use Brent ICE calendar as the master (Brent dates are the universe for DFL)
    brent_mask = daily["brent_l1"].notna()
    master_index = daily.loc[brent_mask].index
    print(f"  Master calendar (Brent business days): {len(master_index)} dates")

    df = daily.loc[master_index].copy()

    # NO forward-fill. Single-market holidays (UK / US / Asia) leave NaN as-is.

    print("\n== Loading weekly EIA stocks and merging (publication-date aligned, no ffill) ==")
    stocks = load_weekly_stocks()
    # Align stocks on their publication_date only; non-publication days stay NaN.
    stocks_daily = stocks.reindex(master_index)
    df = df.join(stocks_daily)

    print("\n== Computing derived features ==")
    df = add_derived_features(df)

    # Order columns: date as index, raw groups first, derived at the end.
    raw_order = [
        # Crude prices
        "brent_dated", "brent_l1", "brent_l2", "brent_l3", "brent_l4", "brent_l5", "brent_l6",
        "wti_l1", "wti_l2", "wti_l3", "wti_l4", "wti_l5", "wti_l6",
        "cl_f_close",
        "dubai_l1", "dubai_l2", "dubai_l3",
        "gasoil_l1_usd_tonne", "gasoil_l2_usd_tonne",
        # Macro
        "vix", "dxy",
        # Fundamentals
        "crude_stocks_us", "dist_stocks_us",
    ]
    derived_order = [
        "DFL",
        "brent_l1_l2", "brent_l1_l3", "brent_l1_l6",
        "wti_l1_l2", "wti_l1_l3", "wti_l1_l6",
        "dubai_l1_l2", "dubai_l1_l3",
        "brent_wti_arb", "brent_dubai_efs", "gasoil_brent_crack",
        "brent_l1_log_ret_1d", "dfl_chg_1d",
        "brent_l1_vol_20d", "dfl_vol_20d", "dfl_vol_ewma",
        "vix_chg_5d", "dxy_chg_5d",
        "crude_stock_anomaly", "dist_stock_anomaly",
    ]
    df = df[raw_order + derived_order]

    # Save
    df.index.name = "date"
    df.to_csv(OUT_PATH, index=True, date_format="%Y-%m-%d")
    print(f"\n== Master dataset written ==")
    print(f"  Path : {OUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"  Shape: {df.shape}  ({len(df)} rows, {df.shape[1]} columns + date)")

    # Quick coverage summary
    print("\nColumn coverage (non-NaN %):")
    cov = (df.notna().sum() / len(df) * 100).round(1)
    for c in df.columns:
        print(f"  {c:30s} {cov[c]:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
