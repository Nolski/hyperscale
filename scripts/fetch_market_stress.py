#!/usr/bin/env python3
"""
fetch_market_stress.py -- Acquisition step (one script = one step).

Pulls market-stress / financial-conditions indices, model-based recession
signals, and a real-economy reality check from FRED, and writes:
  - raw JSON per series -> data/raw/fred_<series_id>_<retrieval-date>.json
  - tidy long panel     -> data/processed/market_stress.csv

Why these series: to answer "is a collapse actually being priced / happening?"
we need (a) cross-asset stress gauges, (b) the model-based probability of
recession, and (c) the hard real-economy data. If volatility is low, financial
conditions are loose, recession probability is tiny, and the labour market is
intact, then the "bonds signal collapse" read is mostly a misread of a long-end
term-premium move (see analyze_curve_decomposition.py / analyze_recession_signals.py).

  * VIXCLS         -- CBOE equity implied volatility (the "fear gauge")
  * NFCI           -- Chicago Fed National Financial Conditions Index (0 = avg;
                      negative = looser than average)
  * STLFSI4        -- St. Louis Fed Financial Stress Index (0 = normal)
  * RECPROUSM156N  -- smoothed US recession probability, 12-month (%)
  * SAHMREALTIME   -- real-time Sahm-rule recession indicator (>=0.50 triggers)
  * USREC          -- NBER recession indicator (1/0) -- dates for event studies
  * UNRATE, PAYEMS, ICSA, GDPC1 -- unemployment, payrolls, jobless claims, real GDP

NOTE -- bond-market volatility: the ICE BofA MOVE index is the natural analogue
of the VIX for Treasuries but is paywalled and not on FRED. analyze_* scripts
substitute REALIZED 10y vol computed from DGS10 daily changes (a proxy, not MOVE).

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
    "VIXCLS":        ("vix",                "stress"),
    "NFCI":          ("nfci",               "conditions"),
    "STLFSI4":       ("stlfsi",             "stress"),
    "RECPROUSM156N": ("recession_prob_12m", "recession_signal"),
    "SAHMREALTIME":  ("sahm_realtime",      "recession_signal"),
    "USREC":         ("nber_recession",     "recession_signal"),
    "UNRATE":        ("unemployment_rate",  "real_economy"),
    "PAYEMS":        ("nonfarm_payrolls",   "real_economy"),
    "ICSA":          ("initial_claims",     "real_economy"),
    "GDPC1":         ("real_gdp",           "real_economy"),
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
        print(f"  {series_id:14s} {label:20s} {len(observations):6d} obs  "
              f"latest {last['date']}: {float(last['value']):10.2f} {meta['units_short']}")

    df = pd.DataFrame(rows).sort_values(["group", "series_id", "date"])
    out = PROCESSED / "market_stress.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
