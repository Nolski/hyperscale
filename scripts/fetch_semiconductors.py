#!/usr/bin/env python3
"""
fetch_semiconductors.py -- Acquisition step.

Pulls annual revenue for the major US-listed AI-chip suppliers from the SEC EDGAR
XBRL `companyconcept` API and writes:
  - raw JSON per company -> data/raw/sec_semirev_<ticker>_<retrieval-date>.json
  - tidy annual panel    -> data/processed/semiconductor_revenue_annual.csv

This is the "supply mirror" layer of the AI-investment accounts (see
notes/methodology): chip revenue is the supply-side reflection of the hardware
portion of hyperscaler capex. It is a CROSS-CHECK, never added to the
real-investment layer -- those GPUs already sit inside hyperscaler capex.

Covered (USD filers): NVIDIA, AMD, Broadcom, Micron, Intel.
NOT covered here: TSMC files IFRS 20-Fs in New Taiwan dollars -- excluded from
this USD panel; handle via a manual entry (TSMC publishes monthly revenue on its
investor-relations site). SIA total-market figures are likewise manual (Tier 3).

Source : SEC EDGAR, https://data.sec.gov/api/xbrl/companyconcept/
No API key required; SEC asks for a descriptive User-Agent (SEC_EDGAR_USER_AGENT).

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

# Company -> (display name, SEC CIK). CIKs verified via SEC EDGAR, 2026-05-15.
COMPANIES = {
    "NVDA": ("NVIDIA",   1045810),
    "AMD":  ("AMD",      2488),
    "AVGO": ("Broadcom", 1730168),
    "MU":   ("Micron",   723125),
    "INTC": ("Intel",    50863),
}

# Candidate us-gaap revenue concepts, tried in order; the script keeps whichever
# extends to the latest period (NVIDIA uses `Revenues`; others retagged to
# `RevenueFromContractWithCustomerExcludingAssessedTax`).
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
]

URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
MIN_DAYS, MAX_DAYS = 340, 380  # 1-year-ish periods only


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
    """Deduplicated annual facts keyed by period-end; keep latest-filed vintage."""
    best: dict[str, dict] = {}
    for fact in doc.get("units", {}).get("USD", []):
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


def main() -> None:
    headers = {"User-Agent": get_user_agent()}
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    for ticker, (name, cik) in COMPANIES.items():
        candidates = []  # (concept, doc, facts)
        for concept in REVENUE_CONCEPTS:
            doc = fetch_concept(cik, concept, headers)
            time.sleep(0.2)  # under SEC's 10 req/s limit
            if doc is None:
                continue
            facts = annual_facts(doc)
            if facts:
                candidates.append((concept, doc, facts))

        if not candidates:
            print(f"  {ticker:6s} no revenue concept found -- skipped", file=sys.stderr)
            continue

        concept, doc, facts = max(candidates, key=lambda c: max(c[2]))
        (RAW / f"sec_semirev_{ticker}_{RETRIEVED}.json").write_text(json.dumps(doc, indent=2))

        rows = []
        for end_str, fact in sorted(facts.items()):
            end = dt.date.fromisoformat(end_str)
            rows.append({
                "ticker": ticker,
                "company": name,
                "fiscal_year": end.year,
                "period_start": fact["start"],
                "period_end": end_str,
                "revenue_usd": fact["val"],
                "revenue_concept": concept,
                "form": fact["form"],
                "accession": fact["accn"],
                "filed": fact["filed"],
                "retrieved": RETRIEVED,
            })
        all_rows.extend(rows)
        latest = rows[-1]
        print(f"  {ticker:6s} {concept:48s} {len(rows):2d} yrs  "
              f"latest FY{latest['fiscal_year']}: ${latest['revenue_usd'] / 1e9:.1f}B")

    if not all_rows:
        sys.exit("ERROR: no revenue data retrieved.")

    df = pd.DataFrame(all_rows).sort_values(["ticker", "period_end"])
    out = PROCESSED / "semiconductor_revenue_annual.csv"
    df.to_csv(out, index=False)

    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")

    latest = df.sort_values("period_end").groupby("ticker").tail(1)
    total = latest["revenue_usd"].sum()
    print("\nLatest annual revenue (USD bn):")
    for _, r in latest.sort_values("revenue_usd", ascending=False).iterrows():
        print(f"  {r['company']:10s} FY{r['fiscal_year']}  ${r['revenue_usd'] / 1e9:8,.1f} B")
    print(f"  {'5-firm total':10s}        ${total / 1e9:8,.1f} B")


if __name__ == "__main__":
    main()
