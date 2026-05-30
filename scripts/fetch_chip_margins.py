#!/usr/bin/env python3
"""
fetch_chip_margins.py -- Acquisition step.

Pulls gross profit and revenue for the leading AI-chip vendors from SEC EDGAR XBRL and
writes:
  - raw JSON per company/concept -> data/raw/sec_margin_<ticker>_<concept>_<date>.json
  - tidy annual panel            -> data/processed/chip_margins.csv

The GROSS MARGIN is the vendor-markup slice of the cost-stack decomposition
(model_cost_stack.py): NVIDIA's ~70-75% data-center gross margin is why a GPU's MSRP sits
far above its manufacturing cost, which is in turn why operating energy looks like only a
small share of chip-level TCO. Quantifying the markup is the point.

Concepts (candidates tried in order):
  * GrossProfit
  * Revenue: RevenueFromContractWithCustomerExcludingAssessedTax, then Revenues.
  gross_margin = GrossProfit / Revenue.

Source : SEC EDGAR, https://data.sec.gov/api/xbrl/companyconcept/  (User-Agent only).

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
    "NVDA": ("NVIDIA", 1045810),
    "AMD":  ("AMD", 2488),
}
GROSS_PROFIT = ["GrossProfit"]
REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"]

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


def annual_facts(doc: dict) -> dict[str, dict]:
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


def best(cik, candidates, headers):
    found = []
    for c in candidates:
        doc = fetch_concept(cik, c, headers)
        time.sleep(0.2)
        if doc is None:
            continue
        f = annual_facts(doc)
        if f:
            found.append((c, doc, f))
    return max(found, key=lambda t: max(t[2])) if found else None


def main() -> None:
    headers = {"User-Agent": get_user_agent()}
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    rows = []
    for ticker, (name, cik) in COMPANIES.items():
        gp = best(cik, GROSS_PROFIT, headers)
        rev = best(cik, REVENUE, headers)
        if gp is None or rev is None:
            print(f"  {ticker}: missing gross profit or revenue concept -- skipped", file=sys.stderr)
            continue
        for tag, picked in (("grossprofit", gp), ("revenue", rev)):
            (RAW / f"sec_margin_{ticker}_{picked[0]}_{RETRIEVED}.json").write_text(
                json.dumps(picked[1], indent=2))
        gp_facts, rev_facts = gp[2], rev[2]
        for end_str in sorted(set(gp_facts) & set(rev_facts)):
            g, r = gp_facts[end_str]["val"], rev_facts[end_str]["val"]
            if r:
                rows.append({"ticker": ticker, "company": name,
                             "fiscal_year": dt.date.fromisoformat(end_str).year,
                             "period_end": end_str, "gross_profit_usd": g,
                             "revenue_usd": r, "gross_margin": round(g / r, 4),
                             "retrieved": RETRIEVED})

    if not rows:
        sys.exit("ERROR: no margin data retrieved.")
    df = pd.DataFrame(rows).sort_values(["ticker", "period_end"])
    out = PROCESSED / "chip_margins.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows -> {out.relative_to(ROOT)}")
    latest = df.sort_values("period_end").groupby("ticker").tail(1)
    print("\nLatest fiscal-year gross margin (the vendor markup):")
    for _, r in latest.iterrows():
        print(f"  {r['company']:8s} FY{r['fiscal_year']}: gross margin {r['gross_margin']*100:.1f}% "
              f"(revenue ${r['revenue_usd']/1e9:.0f}B)")


if __name__ == "__main__":
    main()
