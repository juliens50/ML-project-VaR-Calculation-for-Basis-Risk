"""
03_download_eia.py
Download data from the EIA API v2 for the DFL Brent VaR project.

Two routes are pulled, sharing the same EIA API key:

  STOCKS (weekly, ongoing)
    WCESTUS1  - U.S. Ending Stocks Excluding SPR of Crude Oil   (kbbl)
    WDISTUS1  - U.S. Ending Stocks of Distillate Fuel Oil       (kbbl)
    Schema  : period, value, publication_date
    Notes   : publication_date = period + 5 days
              (EIA Weekly Petroleum Status Report, Wed 10:30 ET)

  FUTURES (daily, HISTORICAL ONLY -- EIA discontinued on 2024-04-05)
    RCLC1     - NYMEX WTI Cushing Future Contract 1  (USD/bbl)
    RCLC2     - NYMEX WTI Cushing Future Contract 2  (USD/bbl)
    Schema  : date, value
    Notes   : data ends on 2024-04-05. Kept for historical backtest only.

Output: data/raw/eia/<SERIES>.csv
Re-runnable: each invocation overwrites the per-series CSV with a fresh pull.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "eia"
ENV_PATH = PROJECT_ROOT / "config" / "api_keys.env"

START_DATE = "2014-01-01"
PAGE_SIZE = 5000
REQUEST_TIMEOUT = 60

STOCKS_URL  = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"
FUTURES_URL = "https://api.eia.gov/v2/petroleum/pri/fut/data/"

STOCK_SERIES: dict[str, str] = {
    "WCESTUS1": "U.S. Ending Stocks Excluding SPR of Crude Oil (kbbl)",
    "WDISTUS1": "U.S. Ending Stocks of Distillate Fuel Oil (kbbl)",
}

FUTURES_SERIES: dict[str, str] = {
    "RCLC1": "NYMEX WTI Cushing Future Contract 1 [historical only, ends 2024-04-05]",
    "RCLC2": "NYMEX WTI Cushing Future Contract 2 [historical only, ends 2024-04-05]",
}


def load_api_key() -> str:
    load_dotenv(ENV_PATH)
    key = os.getenv("EIA_API_KEY")
    if not key:
        sys.exit(
            f"EIA_API_KEY not set.\n"
            f"  1. Copy   config/api_keys.env.example  ->  config/api_keys.env\n"
            f"  2. Paste your key (free): https://www.eia.gov/opendata/register.php"
        )
    return key


def fetch_series(
    api_key: str, url: str, frequency: str, series_id: str
) -> pd.DataFrame:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "api_key": api_key,
            "frequency": frequency,
            "data[0]": "value",
            "facets[series][]": series_id,
            "start": START_DATE,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": PAGE_SIZE,
        }
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()

        if "error" in payload:
            raise RuntimeError(f"EIA API error: {payload['error']}")

        page = payload.get("response", {}).get("data", [])
        if not page:
            break
        rows.extend(page)

        total = int(payload["response"].get("total", 0))
        if len(rows) >= total or len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.2)  # be polite to the API

    return pd.DataFrame(rows)


def normalize_stocks(df: pd.DataFrame) -> pd.DataFrame:
    df["period"] = pd.to_datetime(df["period"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["publication_date"] = (
        pd.to_datetime(df["period"]) + pd.Timedelta(days=5)
    ).dt.date
    return (
        df[["period", "value", "publication_date"]]
        .sort_values("period")
        .reset_index(drop=True)
    )


def normalize_futures(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"period": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df[["date", "value"]].sort_values("date").reset_index(drop=True)


def download_route(
    api_key: str,
    url: str,
    frequency: str,
    series_dict: dict[str, str],
    normalize_fn: Callable[[pd.DataFrame], pd.DataFrame],
    date_col: str,
) -> None:
    for series_id, description in series_dict.items():
        print(f"[{series_id}] {description}")
        try:
            raw = fetch_series(api_key, url, frequency, series_id)
        except Exception as exc:
            print(f"  ! failed: {exc}")
            continue
        if raw.empty:
            print("  ! no data returned")
            continue

        df = normalize_fn(raw)
        out_path = RAW_DIR / f"{series_id}.csv"
        df.to_csv(out_path, index=False)

        n_total = len(df)
        n_nan = int(df["value"].isna().sum())
        first, last = df[date_col].iloc[0], df[date_col].iloc[-1]
        rel = out_path.relative_to(PROJECT_ROOT)
        print(f"  -> {rel}  ({n_total} rows, {n_nan} NaN, {first} -> {last})")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()

    print("== Weekly petroleum stocks ==")
    download_route(
        api_key, STOCKS_URL, "weekly",
        STOCK_SERIES, normalize_stocks, date_col="period",
    )

    print("\n== Daily NYMEX WTI futures (historical only, EIA stopped 2024-04-05) ==")
    download_route(
        api_key, FUTURES_URL, "daily",
        FUTURES_SERIES, normalize_futures, date_col="date",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
