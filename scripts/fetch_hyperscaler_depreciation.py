#!/usr/bin/env python3
"""
fetch_hyperscaler_depreciation.py -- Acquisition step (one script = one step).

Pulls the depreciation and property-asset lines for the AI hyperscalers from the
SEC EDGAR XBRL `companyconcept` API and writes:
  - raw JSON per company/concept -> data/raw/sec_deprec_<ticker>_<concept>_<date>.json
  - tidy annual panel            -> data/processed/hyperscaler_depreciation.csv

Why: this is the data behind the Burry/Chanos claim that hyperscalers FLATTER
EARNINGS by extending the assumed useful life of servers/GPUs (longer life -> less
annual depreciation -> higher reported profit). If true, the implied depreciation
RATE (annual depreciation / gross property, plant & equipment) should FALL even as
capex pours into short-lived servers. analyze_hyperscaler_depreciation.py computes
that rate and overlays the firms' DISCLOSED useful-life changes.

Concepts (candidate tags tried in order):
  * DepreciationDepletionAndAmortization (DURATION) -- annual D&A flow.
  * PropertyPlantAndEquipmentGross (INSTANT) -- gross PP&E, the denominator.
  * PropertyPlantAndEquipmentNet (INSTANT) -- net PP&E (context).

CAVEATS (carried into the analysis): D&A can include intangible amortization, and
gross PP&E includes long-life land/buildings, so the implied rate is a BLUNT proxy.
The TREND and cross-firm comparison are the signal; the disclosed useful-life
changes (manual reference) are the direct evidence.

Source : SEC EDGAR, https://data.sec.gov/api/xbrl/companyconcept/  (User-Agent only)

Re-runnable: hits the API, overwrites data/raw/ + data/processed/. No manual steps.
"""

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

COMPANIES = {
    "MSFT":  ("Microsoft",      789019),
    "GOOGL": ("Alphabet",       1652044),
    "AMZN":  ("Amazon",         1018724),
    "META":  ("Meta Platforms", 1326801),
    "NVDA":  ("NVIDIA",         1045810),
    "ORCL":  ("Oracle",         1341439),
    "CRWV":  ("CoreWeave",      1769628),
}

METRICS = [
    ("depreciation_amort_usd", "duration", [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        "Depreciation",
    ]),
    ("ppe_gross_usd", "instant", [
        "PropertyPlantAndEquipmentGross",
    ]),
    ("ppe_net_usd", "instant", [
        "PropertyPlantAndEquipmentNet",
    ]),
]

URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
MIN_DAYS, MAX_DAYS = 340, 380


def get_user_agent() -> str:
    ua = os.environ.get("SEC_EDGAR_USER_AGENT", "").strip()
    if not ua:
        sys.exit("ERROR: SEC_EDGAR_USER_AGENT is not set (see .claude/settings.local.json).")
    return ua


def fetch_concept(cik: int, concept: str, headers: dict) -> dict | None:
    resp = requests.get(URL.format(cik=cik, concept=concept), headers=headers, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def annual_duration_facts(doc: dict) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for fact in doc.get("units", {}).get("USD", []):
        if "start" not in fact or "end" not in fact:
            continue
        start = dt.date.fromisoformat(fact["start"])
        end = dt.date.fromisoformat(fact["end"])
        if not (MIN_DAYS <= (end - start).days <= MAX_DAYS):
            continue
        if fact.get("form") not in ("10-K", "10-K/A"):
            continue
        key = fact["end"]
        if key not in best or fact["filed"] > best[key]["filed"]:
            best[key] = fact
    return best


def annual_instant_facts(doc: dict) -> dict[str, dict]:
    best: dict[str, dict] = {}
    for fact in doc.get("units", {}).get("USD", []):
        if fact.get("form") not in ("10-K", "10-K/A"):
            continue
        key = fact["end"]
        if key not in best or fact["filed"] > best[key]["filed"]:
            best[key] = fact
    return best


def best_concept(cik: int, candidates: list[str], kind: str, headers: dict):
    found = []
    for concept in candidates:
        doc = fetch_concept(cik, concept, headers)
        time.sleep(0.2)
        if doc is None:
            continue
        facts = annual_instant_facts(doc) if kind == "instant" else annual_duration_facts(doc)
        if facts:
            found.append((concept, doc, facts))
    if not found:
        return None
    return max(found, key=lambda c: max(c[2]))


def main() -> None:
    headers = {"User-Agent": get_user_agent()}
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    for ticker, (name, cik) in COMPANIES.items():
        by_period: dict[str, dict] = {}
        used: dict[str, str] = {}
        for col, kind, candidates in METRICS:
            picked = best_concept(cik, candidates, kind, headers)
            if picked is None:
                used[col] = "n/a"
                continue
            concept, doc, facts = picked
            used[col] = concept
            (RAW / f"sec_deprec_{ticker}_{concept}_{RETRIEVED}.json").write_text(
                json.dumps(doc, indent=2))
            for end_str, fact in facts.items():
                by_period.setdefault(end_str, {})[col] = fact["val"]

        for end_str, vals in sorted(by_period.items()):
            end = dt.date.fromisoformat(end_str)
            all_rows.append({
                "ticker": ticker,
                "company": name,
                "fiscal_year": end.year,
                "period_end": end_str,
                "depreciation_amort_usd": vals.get("depreciation_amort_usd"),
                "ppe_gross_usd": vals.get("ppe_gross_usd"),
                "ppe_net_usd": vals.get("ppe_net_usd"),
                "retrieved": RETRIEVED,
            })
        latest_year = max((dt.date.fromisoformat(e).year for e in by_period), default=None)
        print(f"  {ticker:6s} {name:16s} D&A={used.get('depreciation_amort_usd','n/a'):36s} "
              f"gross_ppe={'yes' if used.get('ppe_gross_usd','n/a')!='n/a' else 'NO ':3s} "
              f"years={len(by_period):2d} latest FY={latest_year}")

    if not all_rows:
        sys.exit("ERROR: no depreciation data retrieved.")

    df = pd.DataFrame(all_rows).sort_values(["ticker", "period_end"])
    out = PROCESSED / "hyperscaler_depreciation.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
