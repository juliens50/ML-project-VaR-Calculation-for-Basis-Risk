"""
06_load_manual_crude.py
Extract ICE WTI L1..L6 and Platts/ICE Dubai L1..L3 from Data_crude.xlsx.

Input:  Data_crude.xlsx at the project root (or path overridden via --input).
        Combined Brent + WTI + Dubai file, 3 header rows:

          row 0  |  <blank> | BRUT
          row 1  |  <blank> | Dated  | ICE Brent  ...  | ICE WTI ...     | DUBAI PLATTS ...
          row 2  |  <blank> | cr.BRED.DTD@SP@P.M | fu.BI.E1.C..fu.BI.E6.C | fu.OI.E1.C..fu.OI.E6.C | fu.DB.E1.C..fu.DB.E3.C
          row 3+ |  date    | <values>

        OI = ICE WTI Light Sweet Crude (Refinitiv code).
        DB = Dubai (Platts assessment / ICE-cleared swap, depending on feed).

        Brent columns are intentionally SKIPPED here -- they are already produced
        by 04_load_manual_brent.py from Data_brent.xlsx. If Data_brent.xlsx ever
        goes away, set --include-brent to also extract them from Data_crude.

Output: data/raw/manual/<series>.csv with schema [date, value], USD/bbl
          wti_l1.csv ... wti_l6.csv      (6 files)
          dubai_l1.csv ... dubai_l3.csv  (3 files)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "Data_crude.xlsx"
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "manual"

# Column index in the sheet -> (output filename, expected source ticker, description)
COLUMN_SPEC: dict[int, tuple[str, str, str]] = {
    # WTI ICE (columns 8..13)
     8: ("wti_l1.csv",   "fu.OI.E1.C", "ICE WTI L1 continuous"),
     9: ("wti_l2.csv",   "fu.OI.E2.C", "ICE WTI L2 continuous"),
    10: ("wti_l3.csv",   "fu.OI.E3.C", "ICE WTI L3 continuous"),
    11: ("wti_l4.csv",   "fu.OI.E4.C", "ICE WTI L4 continuous"),
    12: ("wti_l5.csv",   "fu.OI.E5.C", "ICE WTI L5 continuous"),
    13: ("wti_l6.csv",   "fu.OI.E6.C", "ICE WTI L6 continuous"),
    # Dubai Platts (columns 14..16)
    14: ("dubai_l1.csv", "fu.DB.E1.C", "Dubai L1 (Platts swap)"),
    15: ("dubai_l2.csv", "fu.DB.E2.C", "Dubai L2 (Platts swap)"),
    16: ("dubai_l3.csv", "fu.DB.E3.C", "Dubai L3 (Platts swap)"),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                   help=f"Path to the crude Excel file (default: {DEFAULT_INPUT.name})")
    p.add_argument("--sheet", default="Feuil1",
                   help="Sheet name within the Excel file (default: Feuil1)")
    return p.parse_args()


def verify_tickers(path: Path, sheet: str) -> None:
    """Read row 2 (the ticker row) and confirm columns we care about match expectation."""
    ticker_row = pd.read_excel(path, sheet_name=sheet, header=None, skiprows=2, nrows=1).iloc[0]
    mismatches: list[str] = []
    for col_idx, (_, expected, _) in COLUMN_SPEC.items():
        if col_idx >= len(ticker_row):
            mismatches.append(f"  col {col_idx}: missing (file has only {len(ticker_row)} cols)")
            continue
        found = str(ticker_row.iloc[col_idx]).strip()
        if found != expected:
            mismatches.append(f"  col {col_idx}: expected {expected!r}, found {found!r}")
    if mismatches:
        sys.exit("Ticker layout mismatch:\n" + "\n".join(mismatches) +
                 "\nIf the Excel layout changed, update COLUMN_SPEC in this script.")


def load_excel(path: Path, sheet: str) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"Input file not found: {path}")
    verify_tickers(path, sheet)

    cols_needed = [0] + sorted(COLUMN_SPEC.keys())  # date column + value columns
    out_names   = ["date"] + [COLUMN_SPEC[c][0] for c in sorted(COLUMN_SPEC.keys())]

    df = pd.read_excel(
        path, sheet_name=sheet, header=None, skiprows=3,
        usecols=cols_needed, names=out_names,
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

    for col_idx in sorted(COLUMN_SPEC.keys()):
        csv_name, ticker, description = COLUMN_SPEC[col_idx]
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
