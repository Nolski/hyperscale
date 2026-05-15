#!/usr/bin/env python3
"""
fetch_hyperscaler_capex.py -- Acquisition step (one script = one step).

Pulls annual capital investment for the major AI hyperscalers from the SEC EDGAR
XBRL `companyconcept` API and writes:
  - raw JSON per company  -> data/raw/sec_capex_<ticker>_<retrieval-date>.json
  - raw JSON per company  -> data/raw/sec_finlease_<ticker>_<retrieval-date>.json
  - tidy annual panel     -> data/processed/hyperscaler_capex_annual.csv

Two components are pulled, because cash capex alone understates the buildout:
  1. CASH CAPEX -- the cash-flow-statement line for purchases of property &
     equipment. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment for most;
     Amazon and NVIDIA report it as us-gaap:PaymentsToAcquireProductiveAssets.
     The script tries each and uses whichever extends to the latest period.
  2. FINANCE-LEASE ADDITIONS -- us-gaap:RightOfUseAssetObtainedInExchangeFor
     FinanceLeaseLiability. A *non-cash* item: data-center capacity funded by
     finance leases rather than cash. Material for hyperscalers (Microsoft FY2025:
     ~$20B of finance leases on top of ~$65B cash capex).

`total_capacity_investment_usd` = cash capex + finance-lease additions. The two
components differ in nature (cash flow vs. non-cash) -- they are reported
separately AND summed, and analysis should keep the distinction in view.

Source : SEC EDGAR, https://data.sec.gov/api/xbrl/companyconcept/
No API key required; SEC asks for a descriptive User-Agent (SEC_EDGAR_USER_AGENT).
Still excluded: operating-lease-funded capacity. See notes/provenance.md.

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
    "MSFT":  ("Microsoft",      789019),
    "GOOGL": ("Alphabet",       1652044),
    "AMZN":  ("Amazon",         1018724),
    "META":  ("Meta Platforms", 1326801),
    "NVDA":  ("NVIDIA",         1045810),
    "ORCL":  ("Oracle",         1341439),
    "CRWV":  ("CoreWeave",      1769628),
}

# Candidate us-gaap concepts for cash capex, tried in order until one returns data.
CAPEX_CONCEPTS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
]
# Non-cash finance-lease asset additions (single concept across all filers).
LEASE_CONCEPT = "RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability"

URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
# 1-year-ish periods only; isolates the annual line from quarterly facts.
MIN_DAYS, MAX_DAYS = 340, 380


def get_user_agent() -> str:
    ua = os.environ.get("SEC_EDGAR_USER_AGENT", "").strip()
    if not ua:
        sys.exit("ERROR: SEC_EDGAR_USER_AGENT is not set (see .claude/settings.local.json).")
    return ua


def fetch_concept(cik: int, concept: str, headers: dict) -> dict | None:
    """Fetch one company/concept; return parsed JSON, or None if not reported (404)."""
    resp = requests.get(URL.format(cik=cik, concept=concept), headers=headers, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def annual_facts(doc: dict) -> dict[str, dict]:
    """Deduplicated annual facts from a companyconcept doc, keyed by period-end.

    A 10-K's cash-flow statement reports ~3 years of data, and later filings
    restate prior years -- so the same period recurs across filings. We keep,
    per period-end, the most recently *filed* value (latest vintage).
    """
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
        # --- Cash capex: try candidate concepts, keep the most current series ---
        candidates = []  # (concept, doc, facts)
        for concept in CAPEX_CONCEPTS:
            doc = fetch_concept(cik, concept, headers)
            time.sleep(0.2)  # stay well under SEC's 10 req/s limit
            if doc is None:
                continue
            facts = annual_facts(doc)
            if facts:
                candidates.append((concept, doc, facts))

        if not candidates:
            print(f"  {ticker:6s} no capex concept found -- skipped", file=sys.stderr)
            continue

        # Companies retag capex over time (Amazon, NVIDIA moved to
        # PaymentsToAcquireProductiveAssets); pick whichever reaches the latest period.
        capex_concept, capex_doc, capex_facts = max(
            candidates, key=lambda c: max(c[2]))
        (RAW / f"sec_capex_{ticker}_{RETRIEVED}.json").write_text(json.dumps(capex_doc, indent=2))

        # --- Finance-lease additions (non-cash); optional, not all filers report ---
        lease_doc = fetch_concept(cik, LEASE_CONCEPT, headers)
        time.sleep(0.2)
        lease_facts = annual_facts(lease_doc) if lease_doc else {}
        if lease_doc:
            (RAW / f"sec_finlease_{ticker}_{RETRIEVED}.json").write_text(
                json.dumps(lease_doc, indent=2))

        # --- Merge into one row per company-year, keyed on capex period-end ---
        rows = []
        for end_str, fact in sorted(capex_facts.items()):
            end = dt.date.fromisoformat(end_str)
            capex = fact["val"]
            lease = lease_facts[end_str]["val"] if end_str in lease_facts else None
            rows.append({
                "ticker": ticker,
                "company": name,
                # Fiscal year labelled by period-end calendar year; fiscal-year-end
                # months differ (MSFT Jun, NVDA Jan, ORCL May, others Dec).
                "fiscal_year": end.year,
                "period_start": fact["start"],
                "period_end": end_str,
                "capex_usd": capex,
                "finance_lease_additions_usd": lease,
                "total_capacity_investment_usd": capex + lease if lease is not None else capex,
                "capex_concept": capex_concept,
                "form": fact["form"],
                "accession": fact["accn"],
                "filed": fact["filed"],
                "retrieved": RETRIEVED,
            })
        all_rows.extend(rows)

        latest = rows[-1]
        lease_str = (f" + lease ${latest['finance_lease_additions_usd'] / 1e9:.1f}B"
                     if latest["finance_lease_additions_usd"] is not None else "")
        print(f"  {ticker:6s} {capex_concept:42s} {len(rows):2d} yrs  "
              f"latest FY{latest['fiscal_year']}: capex ${latest['capex_usd'] / 1e9:.1f}B{lease_str}")

    if not all_rows:
        sys.exit("ERROR: no capex data retrieved.")

    df = pd.DataFrame(all_rows).sort_values(["ticker", "period_end"])
    out = PROCESSED / "hyperscaler_capex_annual.csv"
    df.to_csv(out, index=False)

    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")

    # Console summary: latest fiscal year per company, largest total first.
    latest = df.sort_values("period_end").groupby("ticker").tail(1)
    print("\nLatest annual capital investment (USD bn):")
    print(f"  {'Company':16s} {'FY':>6s} {'cash capex':>11s} {'fin. leases':>12s} {'total':>9s}")
    for _, r in latest.sort_values("total_capacity_investment_usd", ascending=False).iterrows():
        lease = r["finance_lease_additions_usd"]
        lease_str = f"{lease / 1e9:11.1f}" if pd.notna(lease) else f"{'n/a':>11s}"
        print(f"  {r['company']:16s} {r['fiscal_year']:6d} "
              f"{r['capex_usd'] / 1e9:10.1f} {lease_str} "
              f"{r['total_capacity_investment_usd'] / 1e9:8.1f}")


if __name__ == "__main__":
    main()
