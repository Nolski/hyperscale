#!/usr/bin/env python3
"""
fetch_construction_sector.py -- Acquisition step (Question 3d, construction).

Pulls total US construction activity from the FRED API and writes:
  - raw JSON per series -> data/raw/fred_<series_id>_<retrieval-date>.json
  - tidy panel          -> data/processed/construction_sector.csv

These give the construction-sector denominators the linked-sector analysis needs
to size the data-center build against all US construction:
  - TTLCONS -- Total Construction Spending ($M, SAAR, monthly)
  - USCONS  -- All Employees: Construction (thousands, SA, monthly; BLS CES)

Source : FRED, https://api.stlouisfed.org/fred/  (USCONS mirrors BLS CES)
Key    : FRED_API_KEY (set in .claude/settings.local.json).

Re-runnable: hits the API, overwrites data/raw/ + data/processed/.
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

SERIES = {
    "TTLCONS": "total_construction_spending",   # $M, SAAR, monthly
    "USCONS":  "construction_employment",        # thousands, SA, monthly
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

        obs = [o for o in obs_doc["observations"] if o["value"] != "."]
        for o in obs:
            rows.append({
                "series_id": series_id, "label": label, "title": meta["title"],
                "units": meta["units_short"], "date": o["date"],
                "value": float(o["value"]), "retrieved": RETRIEVED,
            })
        last = obs[-1]
        print(f"  {series_id:9s} {label:30s} {len(obs):5d} obs  "
              f"latest {last['date']}: {float(last['value']):,.0f} {meta['units_short']}")

    df = pd.DataFrame(rows).sort_values(["series_id", "date"])
    out = PROCESSED / "construction_sector.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
