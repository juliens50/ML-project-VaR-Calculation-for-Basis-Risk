"""
02_download_yfinance.py
Download daily futures series from Yahoo Finance for the DFL Brent VaR project.

Series:
  CL=F  - NYMEX WTI front-month continuous (USD/bbl)

Brent L1 / L2 are supplied separately as CSV files in data/raw/manual/.

Output: data/raw/yfinance/<TICKER>.csv with columns [date, open, high, low, close, volume].
The file name replaces '=' with '_' (e.g. CL_F.csv) to stay shell-friendly.

Re-runnable: each invocation overwrites the per-ticker CSV with a fresh pull.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "yfinance"

START_DATE = "2014-01-01"

TICKERS: dict[str, str] = {
    "CL=F": "NYMEX WTI front-month continuous (USD/bbl)",
}


def fetch_ticker(ticker: str) -> pd.DataFrame:
    raw = yf.download(
        ticker,
        start=START_DATE,
        end=date.today().isoformat(),
        progress=False,
        auto_adjust=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance returned no data for {ticker}")

    # yfinance can return a MultiIndex column even for a single ticker; flatten it.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = [c.lower() for c in df.columns]
    df = df.rename_axis("date").reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for ticker, description in TICKERS.items():
        print(f"[{ticker}] {description}")
        try:
            df = fetch_ticker(ticker)
        except Exception as exc:
            print(f"  ! failed: {exc}")
            continue

        safe_name = ticker.replace("=", "_")
        out_path = RAW_DIR / f"{safe_name}.csv"
        df.to_csv(out_path, index=False)

        n_total = len(df)
        n_nan = int(df["close"].isna().sum())
        first, last = df["date"].iloc[0], df["date"].iloc[-1]
        rel = out_path.relative_to(PROJECT_ROOT)
        print(f"  -> {rel}  ({n_total} rows, {n_nan} NaN close, {first} -> {last})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
