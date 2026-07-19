#!/usr/bin/env python3
"""
fetch_hyperscaler_equity_funding.py -- Acquisition step (one script = one step).

Pulls the EQUITY / CASH-ALLOCATION lines for the 7 AI hyperscalers from SEC EDGAR
XBRL `companyconcept`, to answer: how much of the buildout's "self-funding" runs on
the equity currency (stock-based pay) versus cash, and how much cash is diverted to
buybacks rather than capex.

Concepts (us-gaap; candidate tags tried in order):
  * ShareBasedCompensation (DURATION) -- comp paid in stock; a non-cash add-back that
    inflates operating cash flow. The measurable "paid with stock" channel.
  * PaymentsForRepurchaseOfCommonStock (DURATION) -- buybacks; cash spent supporting the
    share price / mopping up SBC dilution, i.e. cash NOT available for capex.
  * ProceedsFromIssuanceOfCommonStock (DURATION) -- new equity raised (small for giants,
    material for the edge).
  * NetCashProvidedByUsedInOperatingActivities (DURATION) -- OCF, the self-funding numerator.
  * PaymentsToAcquirePropertyPlantAndEquipment (DURATION) -- cash capex, the denominator.

Writes:
  - raw JSON per company/concept -> data/raw/sec_equity_<ticker>_<concept>_<date>.json
  - tidy annual panel            -> data/processed/hyperscaler_equity_funding.csv

Source : SEC EDGAR https://data.sec.gov/api/xbrl/companyconcept/ (no key; SEC_EDGAR_USER_AGENT).
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
    ("share_based_comp_usd", "duration", [
        "ShareBasedCompensation",
        "ShareBasedCompensationExpense",
        "AllocatedShareBasedCompensationExpense",
    ]),
    ("buybacks_usd", "duration", [
        "PaymentsForRepurchaseOfCommonStock",
        "PaymentsForRepurchaseOfEquity",
    ]),
    ("equity_issuance_usd", "duration", [
        "ProceedsFromIssuanceOfCommonStock",
        "ProceedsFromIssuanceOrSaleOfEquity",
        "ProceedsFromIssuanceOfCommonStockNetOfIssuanceCosts",
    ]),
    ("operating_cash_flow_usd", "duration", [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ]),
    ("capex_usd", "duration", [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
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


def best_concept(cik: int, candidates: list[str], headers: dict) -> tuple[str, dict, dict] | None:
    found = []
    for concept in candidates:
        doc = fetch_concept(cik, concept, headers)
        time.sleep(0.2)
        if doc is None:
            continue
        facts = annual_duration_facts(doc)
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
        for col, _kind, candidates in METRICS:
            picked = best_concept(cik, candidates, headers)
            if picked is None:
                used[col] = "n/a"
                continue
            concept, doc, facts = picked
            used[col] = concept
            (RAW / f"sec_equity_{ticker}_{concept}_{RETRIEVED}.json").write_text(
                json.dumps(doc, indent=2))
            for end_str, fact in facts.items():
                by_period.setdefault(end_str, {})[col] = fact["val"]

        for end_str, vals in sorted(by_period.items()):
            end = dt.date.fromisoformat(end_str)
            all_rows.append({
                "ticker": ticker, "company": name, "fiscal_year": end.year,
                "period_end": end_str,
                "share_based_comp_usd": vals.get("share_based_comp_usd"),
                "buybacks_usd": vals.get("buybacks_usd"),
                "equity_issuance_usd": vals.get("equity_issuance_usd"),
                "operating_cash_flow_usd": vals.get("operating_cash_flow_usd"),
                "capex_usd": vals.get("capex_usd"),
                "retrieved": RETRIEVED,
            })
        latest = max((dt.date.fromisoformat(e).year for e in by_period), default=None)
        print(f"  {ticker:6s} {name:16s} sbc-tag={used.get('share_based_comp_usd','n/a'):26s} "
              f"years={len(by_period):2d} latest FY={latest}")

    if not all_rows:
        sys.exit("ERROR: no equity-funding data retrieved.")
    df = pd.DataFrame(all_rows).sort_values(["ticker", "period_end"])
    out = PROCESSED / "hyperscaler_equity_funding.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
