#!/usr/bin/env python3
"""
fetch_forecasts.py -- Acquisition step (manual-source loader, Question 2).

Loads the inputs for the projected-investment analysis and writes:
  - data/processed/investment_forecasts.csv     (third-party forecasts, Method A)
  - data/processed/projection_assumptions.csv   (bottom-up assumptions, Method B)

Both are MANUAL (Tier 3). Third-party forecasts are not published as data; the
bottom-up assumptions are the researcher's own modelling choices. This script
validates and tidies the two hand-keyed files in data/raw/manual/; it hits no API.

To refresh: update the manual CSVs as new forecasts are published.
Re-runnable: reads data/raw/manual/, overwrites data/processed/. No network.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "raw" / "manual"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

INPUTS = {
    "investment_forecasts.csv": {"source", "report", "pub_date", "geography",
                                 "scope", "scenario", "metric", "horizon",
                                 "value_usd_billion", "assumptions"},
    "projection_assumptions.csv": {"parameter", "scenario", "year", "value", "note"},
}


def load(name: str, required: set) -> pd.DataFrame:
    path = MANUAL / name
    if not path.exists():
        sys.exit(f"ERROR: manual source file missing: {path.relative_to(ROOT)}")
    df = pd.read_csv(path, comment="#")
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"ERROR: {name} missing columns: {sorted(missing)}")
    return df


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)

    forecasts = load("investment_forecasts.csv", INPUTS["investment_forecasts.csv"])
    assumptions = load("projection_assumptions.csv", INPUTS["projection_assumptions.csv"])

    # Validation: the McKinsey base-case headline must be present and sane.
    mck = forecasts[(forecasts.source == "McKinsey") &
                    (forecasts.scenario.str.contains("base", case=False))]
    if mck.empty or not (5000 <= mck.iloc[0]["value_usd_billion"] <= 9000):
        sys.exit("ERROR: McKinsey base-case forecast missing/out of range "
                 "(check data/raw/manual/investment_forecasts.csv).")
    # Validation: all three Method-B scenarios present.
    growth = assumptions[assumptions.parameter == "yoy_growth_pct"]
    for sc in ("low", "mid", "high"):
        if growth[growth.scenario == sc]["year"].nunique() != 5:
            sys.exit(f"ERROR: projection scenario '{sc}' must have 5 years (2026-2030).")

    for df in (forecasts, assumptions):
        df["retrieved"] = RETRIEVED
    forecasts.to_csv(PROCESSED / "investment_forecasts.csv", index=False)
    assumptions.to_csv(PROCESSED / "projection_assumptions.csv", index=False)

    print(f"Loaded {len(forecasts)} forecast rows -> data/processed/investment_forecasts.csv")
    print(f"Loaded {len(assumptions)} assumption rows -> data/processed/projection_assumptions.csv")
    print("\nThird-party forecasts (Method A):")
    for _, r in forecasts.iterrows():
        print(f"  {r['source']:14s} {r['scope'][:34]:34s} {r['metric']:10s} "
              f"{r['horizon']:10s} ${r['value_usd_billion'] / 1000:5.2f}T")


if __name__ == "__main__":
    main()
