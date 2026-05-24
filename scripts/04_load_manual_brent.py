"""
04_load_manual_brent.py
Split the user-supplied Brent Excel into per-series CSVs.

Input:  Data_brent.xlsx at the project root (or path overridden via --input).
        Expected schema (3 header rows, then data):

          row 0  | <NaT>  | BRUT                |             |  ICE Brent  | ...
          row 1  | <NaT>  | Dated               | ICE Brent   |  ...
          row 2  | <NaT>  | cr.BRED.DTD@SP@P.M  | fu.BI.E1.C  | fu.BI.E2.C  | ... | fu.BI.E6.C
          row 3+ |  date  |  values             | values      | values      | ... | values

        Series read (in column order):
          cr.BRED.DTD@SP@P.M  - Platts Dated Brent assessment (USD/bbl)
          fu.BI.E1.C          - ICE Brent L1 continuous
          fu.BI.E2.C          - ICE Brent L2 continuous
          fu.BI.E3.C          - ICE Brent L3 continuous
          fu.BI.E4.C          - ICE Brent L4 continuous
          fu.BI.E5.C          - ICE Brent L5 continuous
          fu.BI.E6.C          - ICE Brent L6 continuous

Output: one CSV per series in data/raw/manual/, schema [date, value]:
          brent_dated.csv
          brent_l1.csv  ...  brent_l6.csv

Re-runnable: each invocation overwrites the per-series CSVs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "Data_brent.xlsx"
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "manual"

# (output filename, source ticker on row 2, description) in column order after the date.
SERIES_SPEC = [
    ("brent_dated.csv", "cr.BRED.DTD@SP@P.M", "Platts Dated Brent assessment"),
    ("brent_l1.csv",    "fu.BI.E1.C",         "ICE Brent L1 continuous"),
    ("brent_l2.csv",    "fu.BI.E2.C",         "ICE Brent L2 continuous"),
    ("brent_l3.csv",    "fu.BI.E3.C",         "ICE Brent L3 continuous"),
    ("brent_l4.csv",    "fu.BI.E4.C",         "ICE Brent L4 continuous"),
    ("brent_l5.csv",    "fu.BI.E5.C",         "ICE Brent L5 continuous"),
    ("brent_l6.csv",    "fu.BI.E6.C",         "ICE Brent L6 continuous"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Path to the Brent Excel file (default: {DEFAULT_INPUT.relative_to(PROJECT_ROOT)})",
    )
    p.add_argument(
        "--sheet", default="Feuil1",
        help="Sheet name within the Excel file (default: Feuil1)",
    )
    return p.parse_args()


def verify_tickers(header_row: pd.Series, expected: list[str]) -> None:
    """Confirm the source tickers in the input match what this loader expects."""
    found = [str(v).strip() for v in header_row.tolist()[1:]]  # skip date column
    if found[:len(expected)] != expected:
        raise RuntimeError(
            "Source tickers do not match expected schema.\n"
            f"  Expected (cols 1..): {expected}\n"
            f"  Found    (cols 1..): {found[:len(expected)]}\n"
            "If the Excel layout changed, update SERIES_SPEC in this script."
        )


def load_excel(path: Path, sheet: str) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"Input file not found: {path}")

    # Pull the ticker row (row index 2) separately for verification.
    ticker_row = pd.read_excel(path, sheet_name=sheet, header=None, skiprows=2, nrows=1).iloc[0]
    verify_tickers(ticker_row, [t for _, t, _ in SERIES_SPEC])

    df = pd.read_excel(
        path, sheet_name=sheet, header=None, skiprows=3,
        names=["date"] + [name for name, _, _ in SERIES_SPEC],
    )
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    # Source Excel occasionally repeats a row verbatim (e.g. Easter week 2024-03-28);
    # values are identical so it's safe to deduplicate.
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
        col = csv_name  # we named the column = csv filename above
        s = df[["date", col]].rename(columns={col: "value"}).copy()
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
