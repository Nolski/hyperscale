#!/usr/bin/env python3
"""
fetch_datacenter_construction.py -- Acquisition step.

Pulls US data-center construction spending and writes:
  - raw CSV            -> data/raw/owid_datacenter_construction_<retrieval-date>.csv
  - tidy monthly panel -> data/processed/datacenter_construction_monthly.csv
  - annual rollup      -> data/processed/datacenter_construction_annual.csv

In the AI-investment accounts this is the building-shell component -- a SUBSET of
hyperscaler capex (which already includes data-center construction), used as a
cross-check and to capture non-hyperscaler / colocation builders. Not additive to
the hyperscaler capex spine.

Source: US Census Bureau, Value of Construction Put in Place (C30) survey,
data-center category. Accessed via Our World in Data's machine-readable mirror,
which republishes the Census series verbatim:
  https://ourworldindata.org/grapher/monthly-spending-data-center-us
Direct Census EITS API access was attempted but the EITS `vip` category code for
data centers could not be resolved without the Census category codebook; the OWID
mirror is the same Census numbers in accessible form. See notes/provenance.md.

Values are NOT seasonally adjusted -- actual monthly construction put in place.

Re-runnable: downloads the CSV, overwrites data/raw/ + data/processed/.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

SOURCE_URL = "https://ourworldindata.org/grapher/monthly-spending-data-center-us.csv?csvType=full"
SOURCE_LABEL = "US Census Bureau (C30 Value of Construction Put in Place) via Our World in Data"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    resp = requests.get(SOURCE_URL, timeout=60)
    resp.raise_for_status()
    raw_path = RAW / f"owid_datacenter_construction_{RETRIEVED}.csv"
    raw_path.write_bytes(resp.content)

    df = pd.read_csv(raw_path)
    # OWID columns: Entity, Code, Day, <long value column>.
    value_col = [c for c in df.columns if c not in ("Entity", "Code", "Day")][0]
    monthly = pd.DataFrame({
        "date": df["Day"],
        "spending_usd": df[value_col].astype("int64"),
        "seasonally_adjusted": "no",
        "source": SOURCE_LABEL,
        "retrieved": RETRIEVED,
    }).sort_values("date")
    out_m = PROCESSED / "datacenter_construction_monthly.csv"
    monthly.to_csv(out_m, index=False)

    # Annual rollup; flag partial years (n_months < 12).
    monthly["year"] = pd.to_datetime(monthly["date"]).dt.year
    annual = (monthly.groupby("year")
              .agg(spending_usd=("spending_usd", "sum"), n_months=("date", "count"))
              .reset_index())
    annual["partial_year"] = annual["n_months"] < 12
    annual["source"] = SOURCE_LABEL
    annual["retrieved"] = RETRIEVED
    out_a = PROCESSED / "datacenter_construction_annual.csv"
    annual.to_csv(out_a, index=False)

    print(f"Raw CSV  -> {raw_path.relative_to(ROOT)}  (retrieved {RETRIEVED})")
    print(f"Monthly  -> {out_m.relative_to(ROOT)}  ({len(monthly)} months, "
          f"{monthly['date'].iloc[0]} .. {monthly['date'].iloc[-1]})")
    print(f"Annual   -> {out_a.relative_to(ROOT)}")
    print("\nAnnual data-center construction spending (USD bn, NSA):")
    for _, r in annual.iterrows():
        flag = "  (partial year)" if r["partial_year"] else ""
        print(f"  {int(r['year'])}  ${r['spending_usd'] / 1e9:7,.1f} B{flag}")


if __name__ == "__main__":
    main()
