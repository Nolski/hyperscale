#!/usr/bin/env python3
"""
fetch_datacenter_energy.py -- Acquisition step (manual-source loader, Q3a).

Loads US data-center electricity-demand figures and writes:
  - data/processed/datacenter_energy.csv

MANUAL source (Tier 3). The canonical reports -- LBNL's "US Data Center Energy
Usage Report" and EPRI's "Powering Intelligence" -- publish no machine-readable
data; figures are hand-keyed into data/raw/manual/datacenter_energy.csv. This
script validates and tidies that file; it hits no API.

Re-runnable: reads data/raw/manual/, overwrites data/processed/. No network.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "raw" / "manual" / "datacenter_energy.csv"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()
REQUIRED = {"year", "metric", "value", "unit", "scenario", "source", "note"}


def main() -> None:
    if not MANUAL.exists():
        sys.exit(f"ERROR: manual source file missing: {MANUAL.relative_to(ROOT)}")
    df = pd.read_csv(MANUAL, comment="#")
    missing = REQUIRED - set(df.columns)
    if missing:
        sys.exit(f"ERROR: {MANUAL.name} missing columns: {sorted(missing)}")

    # Validation: the 2023 anchor (176 TWh, 4.4%) must be present and sane.
    anchor = df[(df.year == 2023) & (df.metric == "datacenter_electricity")]
    if anchor.empty or not (150 <= anchor.iloc[0]["value"] <= 200):
        sys.exit("ERROR: 2023 data-center electricity anchor missing/out of range "
                 "(check data/raw/manual/datacenter_energy.csv).")

    df["retrieved"] = RETRIEVED
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "datacenter_energy.csv"
    df.to_csv(out, index=False)

    print(f"Loaded manual source -> {out.relative_to(ROOT)}  ({len(df)} rows)")
    for _, r in df.iterrows():
        sc = "" if r["scenario"] == "actual" else f" ({r['scenario']})"
        print(f"  {r['year']}  {r['metric']:24s} {r['value']:6.1f} {r['unit']}{sc}")


if __name__ == "__main__":
    main()
