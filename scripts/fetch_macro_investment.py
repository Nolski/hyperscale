#!/usr/bin/env python3
"""
fetch_macro_investment.py -- Acquisition step.

Pulls the macro denominator series the AI-investment analysis needs to put the
buildout in context -- total fixed investment, GDP, and the market index -- from
the FRED API, and writes:
  - raw JSON per series -> data/raw/fred_<series_id>_<retrieval-date>.json
  - tidy long panel     -> data/processed/macro_investment.csv

These series let later analysis express hyperscaler/data-center capex as a share
of total private investment and of GDP, and track market concentration context.

Source : FRED (Federal Reserve Bank of St. Louis), https://api.stlouisfed.org/fred/
Key    : FRED_API_KEY (set in .claude/settings.local.json).

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

API = "https://api.stlouisfed.org/fred"

# series_id -> short label. Series chosen as denominators / context for AI capex.
SERIES = {
    "A679RC1Q027SBEA": "fixed_invest_it_equip_and_software",   # nominal, SAAR, quarterly
    "B985RC1Q027SBEA": "fixed_invest_software",                # nominal, SAAR, quarterly
    "PNFI":            "private_nonresidential_fixed_invest",  # nominal, SAAR, quarterly
    "GDP":             "gdp_nominal",                          # nominal, SAAR, quarterly
    "GDPC1":           "gdp_real",                             # real (chained), SAAR, quarterly
    "SP500":           "sp500_index",                          # daily index level
}


def get_key() -> str:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        sys.exit("ERROR: FRED_API_KEY is not set (see .claude/settings.local.json).")
    return key


def fred_get(endpoint: str, key: str, **params) -> dict:
    params.update(api_key=key, file_type="json")
    resp = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    key = get_key()
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for series_id, label in SERIES.items():
        meta = fred_get("series", key, series_id=series_id)["seriess"][0]
        obs_doc = fred_get("series/observations", key, series_id=series_id)
        (RAW / f"fred_{series_id}_{RETRIEVED}.json").write_text(json.dumps(obs_doc, indent=2))

        observations = [o for o in obs_doc["observations"] if o["value"] != "."]
        for o in observations:
            rows.append({
                "series_id": series_id,
                "label": label,
                "title": meta["title"],
                "units": meta["units_short"],
                "frequency": meta["frequency_short"],
                "date": o["date"],
                "value": float(o["value"]),
                "retrieved": RETRIEVED,
            })
        last = observations[-1]
        print(f"  {series_id:18s} {label:38s} {len(observations):5d} obs  "
              f"latest {last['date']}: {float(last['value']):,.1f} {meta['units_short']}")

    df = pd.DataFrame(rows).sort_values(["series_id", "date"])
    out = PROCESSED / "macro_investment.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
