#!/usr/bin/env python3
"""
fetch_credit_spreads.py -- Acquisition step (one script = one step).

Pulls corporate-credit spreads and bank lending standards from FRED, and writes:
  - raw JSON per series -> data/raw/fred_<series_id>_<retrieval-date>.json
  - tidy long panel     -> data/processed/credit_spreads.csv

Why these series: credit spreads are the market's price of corporate-default risk.
If the bond market were really pricing a "collapse," high-yield and investment-grade
spreads would be blowing out and banks would be slamming the lending window shut.
Tight, calm spreads alongside a heavy long end is the tell that the long-end move
is a TERM-PREMIUM / SUPPLY story, not a CREDIT-DISTRESS story. These feed
analyze_credit_equity_coherence.py.

  * BAMLH0A0HYM2 -- ICE BofA US High-Yield OAS (option-adjusted spread, %)
  * BAMLC0A0CM   -- ICE BofA US Corporate (investment-grade) OAS (%)
  * BAMLH0A3HYC  -- ICE BofA US CCC & lower OAS -- the riskiest tier; first to move (%)
  * BAA10Y       -- Moody's Baa corporate yield minus 10y Treasury (%)
  * AAA10Y       -- Moody's Aaa corporate yield minus 10y Treasury (%)
  * DRTSCILM     -- SLOOS: net % of banks tightening C&I standards, large/mid firms
                    (quarterly; survey-based, leads credit conditions)

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

SERIES = {
    "BAMLH0A0HYM2": ("hy_oas",            "spread_oas"),    # high-yield OAS
    "BAMLC0A0CM":   ("ig_oas",            "spread_oas"),    # investment-grade OAS
    "BAMLH0A3HYC":  ("ccc_oas",           "spread_oas"),    # CCC & lower OAS
    "BAA10Y":       ("baa_minus_10y",     "spread_moody"),  # Moody's Baa - 10y
    "AAA10Y":       ("aaa_minus_10y",     "spread_moody"),  # Moody's Aaa - 10y
    "DRTSCILM":     ("sloos_tighten_ci",  "lending"),       # bank tightening, C&I
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
    for series_id, (label, group) in SERIES.items():
        meta = fred_get("series", key, series_id=series_id)["seriess"][0]
        obs_doc = fred_get("series/observations", key, series_id=series_id)
        (RAW / f"fred_{series_id}_{RETRIEVED}.json").write_text(json.dumps(obs_doc, indent=2))

        observations = [o for o in obs_doc["observations"] if o["value"] != "."]
        for o in observations:
            rows.append({
                "series_id": series_id,
                "label": label,
                "group": group,
                "title": meta["title"],
                "units": meta["units_short"],
                "frequency": meta["frequency_short"],
                "date": o["date"],
                "value": float(o["value"]),
                "retrieved": RETRIEVED,
            })
        last = observations[-1]
        print(f"  {series_id:14s} {label:18s} {len(observations):6d} obs  "
              f"latest {last['date']}: {float(last['value']):7.2f} {meta['units_short']}")

    df = pd.DataFrame(rows).sort_values(["group", "series_id", "date"])
    out = PROCESSED / "credit_spreads.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
