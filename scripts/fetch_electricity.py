#!/usr/bin/env python3
"""
fetch_electricity.py -- Acquisition step (Question 3a, energy linkage).

Pulls US electricity demand and prices from the EIA API v2 and writes:
  - raw JSON          -> data/raw/eia_retail_sales_<retrieval-date>.json
  - tidy annual panel -> data/processed/us_electricity.csv

These are the macro electricity series the data-center energy-linkage analysis
needs: total US electricity sales (demand) and average retail price, for all
sectors and for residential customers (the household-cost angle).

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
SECTORS = {"ALL": "all sectors", "RES": "residential", "COM": "commercial",
           "IND": "industrial"}


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
        ("facets[stateid][]", "US"),
        ("start", "2001"), ("length", "5000"),
        ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
    ]
    for s in SECTORS:
        params.append(("facets[sectorid][]", s))

    resp = requests.get(API, params=params, timeout=60)
    resp.raise_for_status()
    doc = resp.json()
    # EIA echoes the request params -- including the API key -- back in the
    # response. Redact it before saving so the raw file carries no secret.
    if doc.get("request", {}).get("params", {}).get("api_key"):
        doc["request"]["params"]["api_key"] = "REDACTED"
    (RAW / f"eia_retail_sales_{RETRIEVED}.json").write_text(json.dumps(doc, indent=2))

    records = doc["response"]["data"]
    rows = []
    for r in records:
        if r.get("sales") is None:
            continue
        rows.append({
            "year": int(r["period"]),
            "sector": SECTORS.get(r["sectorid"], r["sectorid"]),
            # sales reported in million kWh -> convert to TWh.
            "sales_twh": float(r["sales"]) / 1000,
            "price_cents_per_kwh": float(r["price"]) if r.get("price") else None,
            "retrieved": RETRIEVED,
        })

    df = pd.DataFrame(rows).sort_values(["sector", "year"])
    out = PROCESSED / "us_electricity.csv"
    df.to_csv(out, index=False)

    print(f"Wrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")

    allsec = df[df.sector == "all sectors"].set_index("year")
    res = df[df.sector == "residential"].set_index("year")
    latest = int(allsec.index.max())
    first = int(allsec.index.min())
    print(f"\nUS electricity, all sectors:")
    print(f"  {first}: {allsec.loc[first, 'sales_twh']:,.0f} TWh @ "
          f"{allsec.loc[first, 'price_cents_per_kwh']:.2f} c/kWh")
    print(f"  {latest}: {allsec.loc[latest, 'sales_twh']:,.0f} TWh @ "
          f"{allsec.loc[latest, 'price_cents_per_kwh']:.2f} c/kWh")
    print(f"  residential price {first}->{latest}: "
          f"{res.loc[first, 'price_cents_per_kwh']:.2f} -> "
          f"{res.loc[latest, 'price_cents_per_kwh']:.2f} c/kWh")


if __name__ == "__main__":
    main()
