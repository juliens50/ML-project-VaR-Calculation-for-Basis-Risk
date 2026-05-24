"""
01_download_fred.py
Download daily macro / oil-price series from FRED for the DFL Brent VaR project.

Series:
  DCOILBRENTEU - Europe Brent Spot (USD/bbl)         -> Dated Brent proxy
  DCOILWTICO   - WTI Cushing Spot (USD/bbl)
  VIXCLS       - CBOE Volatility Index
  DTWEXBGS     - Trade-Weighted USD Index (Broad)

Output: data/raw/fred/<TICKER>.csv with two columns [date, value].

Re-runnable: each invocation overwrites the per-ticker CSV with a fresh pull.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "fred"
ENV_PATH = PROJECT_ROOT / "config" / "api_keys.env"

START_DATE = "2014-01-01"

TICKERS: dict[str, str] = {
    "DCOILBRENTEU": "Europe Brent Spot (Dated proxy, USD/bbl)",
    "DCOILWTICO":   "WTI Cushing Spot (USD/bbl)",
    "VIXCLS":       "CBOE Volatility Index",
    "DTWEXBGS":     "Trade-Weighted USD Index (Broad)",
}


def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    key = os.getenv("FRED_API_KEY")
    if not key:
        sys.exit(
            f"FRED_API_KEY not set.\n"
            f"  1. Copy   config/api_keys.env.example  ->  config/api_keys.env\n"
            f"  2. Paste your key (free): "
            f"https://fred.stlouisfed.org/docs/api/api_key.html"
        )
    return key


def fetch_series(fred: Fred, ticker: str) -> pd.DataFrame:
    series = fred.get_series(ticker, observation_start=START_DATE)
    df = (
        series.rename("value")
        .rename_axis("date")
        .reset_index()
    )
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fred = Fred(api_key=load_api_key())

    for ticker, description in TICKERS.items():
        print(f"[{ticker}] {description}")
        try:
            df = fetch_series(fred, ticker)
        except Exception as exc:
            print(f"  ! failed: {exc}")
            continue

        out_path = RAW_DIR / f"{ticker}.csv"
        df.to_csv(out_path, index=False)

        n_total = len(df)
        n_nan = int(df["value"].isna().sum())
        first, last = df["date"].iloc[0], df["date"].iloc[-1]
        rel = out_path.relative_to(PROJECT_ROOT)
        print(f"  -> {rel}  ({n_total} rows, {n_nan} NaN, {first} -> {last})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
