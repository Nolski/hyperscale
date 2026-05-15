#!/usr/bin/env python3
"""
fetch_electricity_states.py -- Acquisition step (Question 3a, state-level energy).

Pulls US electricity demand and prices BY STATE from the EIA API v2 and writes:
  - raw JSON          -> data/raw/eia_retail_sales_states_<retrieval-date>.json
  - tidy annual panel -> data/processed/us_electricity_by_state.csv

This is the same EIA `retail-sales` source as fetch_electricity.py, pulled at
state granularity (the `stateid` dimension) so the energy analysis can ask where
data-center load concentrates and how prices move with it. Census-region
aggregates are dropped; the 50 states + DC + the US total are kept.

Source : EIA API v2, https://api.eia.gov/v2/electricity/retail-sales/
Key    : EIA_API_KEY (set in .claude/settings.local.json).

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

API = "https://api.eia.gov/v2/electricity/retail-sales/data/"
SECTORS = {"ALL": "all sectors", "RES": "residential"}
# 2-letter state/DC codes (the API also returns 3-letter census regions, dropped).
STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}


def get_key() -> str:
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key or key == "REPLACE_ME":
        sys.exit("ERROR: EIA_API_KEY is not set (see .claude/settings.local.json).")
    return key


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    params = [
        ("api_key", get_key()), ("frequency", "annual"),
        ("data[]", "sales"), ("data[]", "price"),
        ("start", "2001"), ("length", "8000"),
        ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
    ]
    for s in SECTORS:
        params.append(("facets[sectorid][]", s))

    resp = requests.get(API, params=params, timeout=90)
    resp.raise_for_status()
    doc = resp.json()
    # EIA echoes request params (incl. the API key); redact before saving.
    if doc.get("request", {}).get("params", {}).get("api_key"):
        doc["request"]["params"]["api_key"] = "REDACTED"
    (RAW / f"eia_retail_sales_states_{RETRIEVED}.json").write_text(json.dumps(doc, indent=2))

    rows = []
    for r in doc["response"]["data"]:
        sid = r.get("stateid")
        if r.get("sales") is None or (sid not in STATES and sid != "US"):
            continue
        rows.append({
            "year": int(r["period"]),
            "stateid": sid,
            "state_name": r.get("stateDescription", sid),
            "sector": SECTORS.get(r["sectorid"], r["sectorid"]),
            "sales_twh": float(r["sales"]) / 1000,           # million kWh -> TWh
            "price_cents_per_kwh": float(r["price"]) if r.get("price") else None,
            "retrieved": RETRIEVED,
        })

    df = pd.DataFrame(rows).sort_values(["stateid", "sector", "year"])
    out = PROCESSED / "us_electricity_by_state.csv"
    df.to_csv(out, index=False)

    n_states = df.loc[df.stateid != "US", "stateid"].nunique()
    latest = int(df.year.max())
    print(f"Wrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")
    print(f"  states + DC covered: {n_states};  years through {latest}")
    # Sanity: state all-sector sales should sum near the US total.
    a = df[(df.sector == "all sectors") & (df.year == latest)]
    st = a.loc[a.stateid != "US", "sales_twh"].sum()
    us = a.loc[a.stateid == "US", "sales_twh"]
    if len(us):
        print(f"  {latest}: sum of states {st:,.0f} TWh vs US total "
              f"{us.iloc[0]:,.0f} TWh ({st / us.iloc[0] * 100:.1f}%)")


if __name__ == "__main__":
    main()
