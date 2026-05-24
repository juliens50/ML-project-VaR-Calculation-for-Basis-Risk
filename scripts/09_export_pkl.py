"""
09_export_pkl.py
Convert data/master_dataset.csv into data/master_dataset.pkl for fast
Python loading.

Why both formats?
  - CSV is the source of truth: human-readable, inspectable in Excel/text editor,
    safe for version control diffs (not committed because gitignored, but auditable).
  - PKL preserves dtypes (datetime64, float64, NaN) and loads ~10x faster — useful
    inside the modelling notebook where you load the dataset on every kernel restart.

Re-runnable: regenerate the pkl any time master_dataset.csv has been refreshed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "master_dataset.csv"
PKL_PATH = PROJECT_ROOT / "data" / "master_dataset.pkl"


def main() -> int:
    if not CSV_PATH.exists():
        sys.exit(
            f"Source CSV not found: {CSV_PATH}\n"
            "Run scripts/08_build_master_dataset.py first."
        )

    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    df = df.set_index("date").sort_index()

    df.to_pickle(PKL_PATH)

    csv_size_mb = CSV_PATH.stat().st_size / (1024 ** 2)
    pkl_size_mb = PKL_PATH.stat().st_size / (1024 ** 2)

    print(f"Read  : {CSV_PATH.relative_to(PROJECT_ROOT)}  ({csv_size_mb:.2f} MB)")
    print(f"Wrote : {PKL_PATH.relative_to(PROJECT_ROOT)}  ({pkl_size_mb:.2f} MB)")
    print(f"Shape : {df.shape}  ({df.index.min().date()} → {df.index.max().date()})")
    print(f"Dtypes: date as DatetimeIndex, {df.shape[1]} value columns "
          f"({(df.dtypes == 'float64').sum()} float, {(df.dtypes != 'float64').sum()} other)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
