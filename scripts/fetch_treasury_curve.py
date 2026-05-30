#!/usr/bin/env python3
"""
fetch_treasury_curve.py -- Acquisition step (one script = one step).

Pulls the US Treasury yield curve and the series needed to DECOMPOSE the 10-year
yield, from the FRED API, and writes:
  - raw JSON per series -> data/raw/fred_<series_id>_<retrieval-date>.json
  - tidy long panel     -> data/processed/treasury_curve.csv

Why these series: the research question ("bonds look like collapse, stocks look
fine") hinges on separating two different signals that both move yields ->
  * CURVE SHAPE (T10Y2Y, T10Y3M) -- the classic recession signal (expectations
    of Fed cuts when growth fails).
  * The LONG-END LEVEL split into REAL (DFII10) + BREAKEVEN INFLATION (T10YIE),
    and separately into an EXPECTATIONS component + a TERM PREMIUM (THREEFYTP10).
A rising long-end yield driven by term premium is a fiscal/supply story, NOT a
recession story -- the decomposition is the whole point.

THREEFYTP10 is the Adrian-Crump-Moench (ACM) 10-year term premium. It is a
MODEL ESTIMATE, not an observed price -- flagged in notes/provenance.md.

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

# series_id -> (short label, analytic group). Groups document each series' role.
SERIES = {
    # Nominal constant-maturity curve (daily, percent)
    "DGS3MO":      ("nominal_3mo",       "curve_nominal"),
    "DGS2":        ("nominal_2y",        "curve_nominal"),
    "DGS5":        ("nominal_5y",        "curve_nominal"),
    "DGS10":       ("nominal_10y",       "curve_nominal"),
    "DGS30":       ("nominal_30y",       "curve_nominal"),
    # Curve-shape spreads -- the classic recession signals (percentage points)
    "T10Y2Y":      ("spread_10y_2y",     "curve_spread"),
    "T10Y3M":      ("spread_10y_3mo",    "curve_spread"),
    # Real (TIPS) yields (daily, percent)
    "DFII5":       ("real_5y",           "real"),
    "DFII10":      ("real_10y",          "real"),
    # Inflation compensation / breakevens (daily, percent)
    "T5YIE":       ("breakeven_5y",      "inflation"),
    "T10YIE":      ("breakeven_10y",     "inflation"),
    "T5YIFR":      ("breakeven_5y5y_fwd","inflation"),
    # Term premium -- ACM model estimate, NOT observed (percent)
    "THREEFYTP10": ("term_premium_10y",  "term_premium"),
    # Policy anchor (percent)
    "DFEDTARU":    ("fed_funds_target_upper", "policy"),
    "EFFR":        ("effective_fed_funds",    "policy"),
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
        print(f"  {series_id:12s} {label:24s} {len(observations):6d} obs  "
              f"latest {last['date']}: {float(last['value']):7.2f} {meta['units_short']}")

    df = pd.DataFrame(rows).sort_values(["group", "series_id", "date"])
    out = PROCESSED / "treasury_curve.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
