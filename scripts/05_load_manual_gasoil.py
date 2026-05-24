"""
05_load_manual_gasoil.py
Extract ICE Low-Sulphur Gasoil L1 and L2 from the multi-maturity manual Excel.

Input:  Data_all_maturities - Copie.xlsx at the project root (or path overridden via --input).
        Expected layout (3 header rows then daily data):

          row 0  |  <blank>  |  ICE GO 1st line  |  ICE GO 2nd line  |  ...
          row 1  |  <blank>  |  M+1              |  M+2              |  ...
          row 2  |   Date    |  fu.ULS.E1.C      |  fu.ULS.E2.C      |  ...
          row 3+ |   date    |  prices in USD/tonne                  |  ...

Output: data/raw/manual/gasoil_l1.csv, gasoil_l2.csv with schema [date, value]
        Values stay in USD/tonne (the master dataset will convert to $/bbl
        using factor 7.45 when computing the gasoil-Brent crack).

Re-runnable: each invocation overwrites the per-series CSVs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "Data_all_maturities - Copie (1).xlsx"
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "manual"

# (output filename, expected source ticker on row 2, description) in column order after the date.
SERIES_SPEC = [
    ("gasoil_l1.csv", "fu.ULS.E1.C", "ICE Low-Sulphur Gasoil L1 continuous (USD/tonne)"),
    ("gasoil_l2.csv", "fu.ULS.E2.C", "ICE Low-Sulphur Gasoil L2 continuous (USD/tonne)"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Path to the gasoil Excel file (default: {DEFAULT_INPUT.name})",
    )
    p.add_argument(
        "--sheet", default="Feuil1",
        help="Sheet name within the Excel file (default: Feuil1)",
    )
    return p.parse_args()


def verify_tickers(header_row: pd.Series, expected: list[str]) -> None:
    found = [str(v).strip() for v in header_row.tolist()[1:1 + len(expected)]]
    if found != expected:
        raise RuntimeError(
            "Source tickers do not match expected schema.\n"
            f"  Expected (cols 1..{len(expected)}): {expected}\n"
            f"  Found    (cols 1..{len(expected)}): {found}\n"
            "If the Excel layout changed, update SERIES_SPEC in this script."
        )


def load_excel(path: Path, sheet: str) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"Input file not found: {path}")

    ticker_row = pd.read_excel(path, sheet_name=sheet, header=None, skiprows=2, nrows=1).iloc[0]
    verify_tickers(ticker_row, [t for _, t, _ in SERIES_SPEC])

    # Read only the columns we need: date + L1 + L2.
    df = pd.read_excel(
        path, sheet_name=sheet, header=None, skiprows=3,
        usecols=[0, 1, 2],
        names=["date"] + [name for name, _, _ in SERIES_SPEC],
    )
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    n_before = len(df)
    df = df.drop_duplicates(subset=["date"], keep="first").reset_index(drop=True)
    n_dup = n_before - len(df)
    if n_dup:
        print(f"  (dropped {n_dup} duplicate date row{'s' if n_dup > 1 else ''})")

    df["date"] = df["date"].dt.date
    return df


def main() -> int:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_excel(args.input, args.sheet)
    print(f"Loaded {len(df)} rows from {args.input.name}  "
          f"({df['date'].iloc[0]} -> {df['date'].iloc[-1]})\n")

    for csv_name, ticker, description in SERIES_SPEC:
        s = df[["date", csv_name]].rename(columns={csv_name: "value"}).copy()
        s["value"] = pd.to_numeric(s["value"], errors="coerce")

        out_path = OUT_DIR / csv_name
        s.to_csv(out_path, index=False)

        n_total = len(s)
        n_obs   = int(s["value"].notna().sum())
        n_nan   = n_total - n_obs
        rel = out_path.relative_to(PROJECT_ROOT)
        print(f"[{ticker}] {description}")
        print(f"  -> {rel}  ({n_total} rows, {n_nan} NaN, "
              f"min={s['value'].min():.2f}, max={s['value'].max():.2f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
