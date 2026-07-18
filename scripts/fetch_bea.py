#!/usr/bin/env python3
"""
fetch_bea.py -- Acquisition step (one script = one step).

Pulls the national-accounts series needed to measure AI/IT investment's contribution to US
economic growth, from the Bureau of Economic Analysis API, and writes:
  - raw JSON per table -> data/raw/bea_<table>_<retrieval-date>.json
  - tidy long panels   -> data/processed/bea_fixed_investment.csv  (Table 5.3.6, real)
                          data/processed/bea_real_gdp.csv           (Table 1.1.6, real GDP level)
                          data/processed/bea_contributions.csv      (Table 1.1.2, sanity x-check)

Why: this is the macro layer of the broadened analysis. It lets analyze_macro_attribution.py
replicate, with PRIMARY data, the finding that information-processing equipment + software has
driven the bulk of recent US GDP growth (Furman). BEA tables:
  * T50306 -- Real Private Fixed Investment by Type (chained $). Carries the line
    "Private fixed investment in information processing equipment and software" (Furman's
    category) plus its parts. The numerator.
  * T10106 -- Real GDP, chained-$ levels (line 1). The denominator for contribution-to-growth.
  * T10102 -- Contributions to % change in real GDP (aggregate Equipment + IP-products) -- a
    cross-check on the level-based computation.

Source : BEA API, https://apps.bea.gov/api/data/  (UserID = BEA_API_KEY).
Key    : BEA_API_KEY (in .env.sh / session env). Values are REAL (chained), SAAR, quarterly,
         and subject to revision -- note the retrieval/vintage date.

Re-runnable: hits the API, overwrites data/raw/ + data/processed/. No manual steps.
"""

import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()
API = "https://apps.bea.gov/api/data"
YEARS = ",".join(str(y) for y in range(2010, 2027))

# table -> (output csv, what it is)
TABLES = {
    "T50306": ("bea_fixed_investment.csv", "Real Private Fixed Investment by Type (chained $)"),
    "T10106": ("bea_real_gdp.csv", "Real GDP, chained-$ levels"),
    "T10102": ("bea_contributions.csv", "Contributions to % change in real GDP"),
}


def get_key() -> str:
    key = os.environ.get("BEA_API_KEY", "").strip()
    if not key:
        sys.exit("ERROR: BEA_API_KEY is not set (see .env.sh / settings.local.json).")
    return key


def bea_get(key: str, table: str) -> dict:
    params = dict(UserID=key, method="GetData", datasetname="NIPA", TableName=table,
                  Frequency="Q", Year=YEARS, ResultFormat="JSON")
    resp = requests.get(API, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    key = get_key()
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    for table, (out_name, what) in TABLES.items():
        doc = bea_get(key, table)
        results = doc.get("BEAAPI", {}).get("Results", {})
        # GetData returns a dict (single result) with "Data"; guard for error payloads.
        if isinstance(results, list):
            results = results[0]
        if not isinstance(results, dict) or "Data" not in results:
            sys.exit(f"ERROR: BEA {table} returned no Data: {json.dumps(results)[:300]}")
        (RAW / f"bea_{table}_{RETRIEVED}.json").write_text(json.dumps(doc, indent=2))

        rows = []
        for d in results["Data"]:
            val = d.get("DataValue", "")
            try:
                value = float(str(val).replace(",", ""))
            except (ValueError, TypeError):
                continue
            rows.append({
                "table": table,
                "line": int(d.get("LineNumber", 0) or 0),
                "description": d.get("LineDescription", "").strip(),
                "time_period": d.get("TimePeriod", ""),     # e.g. 2025Q1
                "value": value,
                "units": results.get("UTCProductionTime") and d.get("CL_UNIT", "") or d.get("CL_UNIT", ""),
                "retrieved": RETRIEVED,
            })
        df = pd.DataFrame(rows).sort_values(["line", "time_period"])
        out = PROCESSED / out_name
        df.to_csv(out, index=False)
        print(f"  {table}  {what:48s} {len(df):5d} rows -> {out.relative_to(ROOT)}")

    # Console: confirm the Furman category is present and show its latest value.
    inv = pd.read_csv(PROCESSED / "bea_fixed_investment.csv")
    ipe = inv[inv["description"].str.contains("information processing equipment and software",
                                              case=False, na=False)]
    if not ipe.empty:
        latest = ipe.sort_values("time_period").iloc[-1]
        print(f"\n  IT investment (info-processing equip + software), real chained $bn SAAR:")
        print(f"    latest {latest['time_period']}: {latest['value']:,.0f}")
    print(f"\nRaw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED}; BEA data is revised)")


if __name__ == "__main__":
    main()
