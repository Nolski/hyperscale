#!/usr/bin/env python3
"""
fetch_ai_complex.py -- Acquisition step (one script = one step).

Widens the firm-level lens past the 7 hyperscalers to the broader "AI-industrial complex" --
the memory, equipment, networking, real-estate, electrical, power and neo-cloud companies the
buildout runs through -- by reusing the SEC EDGAR `companyconcept` machinery on an expanded
ticker universe. Writes:
  - raw JSON per company/concept -> data/raw/sec_complex_<ticker>_<concept>_<date>.json
  - tidy annual panel            -> data/processed/ai_complex.csv

Each firm is tagged with a `layer`. Pulls annual REVENUE and CAPEX (latest fiscal year per
firm). CIKs are resolved from SEC's company_tickers.json. Foreign filers (ASML, Nebius) file
20-F and use the `ifrs-full` namespace, so we try us-gaap then ifrs-full and accept 20-F/40-F
forms; anything unresolved is flagged rather than guessed.

IMPORTANT (see notes/methodology_broadening.md): for most of these firms revenue is AI-EXPOSURE,
not AI-attribution -- an Eaton or NextEra is only partly tied to data centers. This file sizes
the complex; analyze_ai_complex.py keeps the exposure-vs-attribution distinction explicit and
uses disclosed segments where they exist.

Source : SEC EDGAR, https://data.sec.gov/  (User-Agent only).

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

# ticker -> (display name, layer). US-listed unless noted; foreign filers flagged in notes.
UNIVERSE = {
    "MU":   ("Micron",            "memory"),
    "ASML": ("ASML",              "equipment"),     # 20-F / ifrs-full
    "AMAT": ("Applied Materials", "equipment"),
    "LRCX": ("Lam Research",      "equipment"),
    "KLAC": ("KLA",               "equipment"),
    "ANET": ("Arista Networks",   "networking"),
    "MRVL": ("Marvell",           "networking"),
    "AVGO": ("Broadcom",          "networking"),
    "EQIX": ("Equinix",           "data-center REIT"),
    "DLR":  ("Digital Realty",    "data-center REIT"),
    "VRT":  ("Vertiv",            "electrical/cooling"),
    "ETN":  ("Eaton",             "electrical/cooling"),
    "GEV":  ("GE Vernova",        "electrical/cooling"),
    "PWR":  ("Quanta Services",   "electrical/cooling"),
    "CEG":  ("Constellation",     "power/IPP"),
    "VST":  ("Vistra",            "power/IPP"),
    "NRG":  ("NRG Energy",        "power/IPP"),
    "NEE":  ("NextEra Energy",    "power/IPP"),
    "CRWV": ("CoreWeave",         "neocloud"),
}

REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
           "RevenueFromContractWithCustomerIncludingAssessedTax", "Revenue"]
CAPEX = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
         "PurchaseOfPropertyPlantAndEquipment"]
NAMESPACES = ["us-gaap", "ifrs-full"]
FORMS = ("10-K", "10-K/A", "20-F", "40-F")
URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{ns}/{concept}.json"
MIN_DAYS, MAX_DAYS = 340, 380


def get_ua() -> str:
    ua = os.environ.get("SEC_EDGAR_USER_AGENT", "").strip()
    if not ua:
        sys.exit("ERROR: SEC_EDGAR_USER_AGENT is not set.")
    return ua


def resolve_ciks(headers: dict) -> dict:
    r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=30)
    r.raise_for_status()
    return {row["ticker"].upper(): int(row["cik_str"]) for row in r.json().values()}


def annual_facts(doc: dict) -> dict[str, dict]:
    best = {}
    for unit in ("USD",):
        for fact in doc.get("units", {}).get(unit, []):
            if "start" not in fact or "end" not in fact:
                continue
            d0 = dt.date.fromisoformat(fact["start"]); d1 = dt.date.fromisoformat(fact["end"])
            if not (MIN_DAYS <= (d1 - d0).days <= MAX_DAYS):
                continue
            if fact.get("form") not in FORMS:
                continue
            k = fact["end"]
            if k not in best or fact["filed"] > best[k]["filed"]:
                best[k] = fact
    return best


def best_concept(cik, candidates, headers):
    """Try (namespace, concept) combos; return (ns, concept, doc, facts) reaching latest period."""
    found = []
    for ns in NAMESPACES:
        for concept in candidates:
            r = requests.get(URL.format(cik=cik, ns=ns, concept=concept), headers=headers, timeout=30)
            time.sleep(0.15)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            facts = annual_facts(r.json())
            if facts:
                found.append((ns, concept, r.json(), facts))
        if found:  # prefer us-gaap if it already yielded data
            break
    return max(found, key=lambda c: max(c[3])) if found else None


def main() -> None:
    headers = {"User-Agent": get_ua()}
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ciks = resolve_ciks(headers)

    rows = []
    for tkr, (name, layer) in UNIVERSE.items():
        cik = ciks.get(tkr)
        if cik is None:
            print(f"  {tkr:5s} CIK not found -- skipped", file=sys.stderr)
            continue
        rev = best_concept(cik, REVENUE, headers)
        cap = best_concept(cik, CAPEX, headers)
        if rev is None:
            print(f"  {tkr:5s} {name:18s} no revenue concept (foreign/odd tagging) -- flagged",
                  file=sys.stderr)
        for tag, picked in (("rev", rev), ("cap", cap)):
            if picked:
                ns, concept, doc, _ = picked
                (RAW / f"sec_complex_{tkr}_{concept}_{RETRIEVED}.json").write_text(json.dumps(doc))
        rev_facts = rev[3] if rev else {}
        cap_facts = cap[3] if cap else {}
        # latest fiscal-year end present in revenue (fall back to capex)
        ends = sorted(rev_facts or cap_facts)
        if not ends:
            rows.append({"ticker": tkr, "company": name, "layer": layer, "fiscal_year": None,
                         "period_end": None, "revenue_usd": None, "capex_usd": None,
                         "namespace": None, "verified": False, "retrieved": RETRIEVED})
            continue
        end = ends[-1]
        rows.append({
            "ticker": tkr, "company": name, "layer": layer,
            "fiscal_year": dt.date.fromisoformat(end).year, "period_end": end,
            "revenue_usd": rev_facts[end]["val"] if end in rev_facts else None,
            "capex_usd": cap_facts.get(end, {}).get("val"),
            "namespace": rev[0] if rev else (cap[0] if cap else None),
            "verified": bool(rev), "retrieved": RETRIEVED,
        })
        rv = rows[-1]["revenue_usd"]; cp = rows[-1]["capex_usd"]
        print(f"  {tkr:5s} {name:18s} {layer:18s} FY{rows[-1]['fiscal_year']}  "
              f"rev ${rv/1e9:6.1f}B" if rv else f"  {tkr:5s} {name:18s} {layer:18s} rev n/a"
              f"  capex ${cp/1e9:.1f}B" if cp else "")

    df = pd.DataFrame(rows).sort_values(["layer", "ticker"])
    out = PROCESSED / "ai_complex.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} firms -> {out.relative_to(ROOT)}")
    ok = df["revenue_usd"].notna().sum()
    print(f"  revenue resolved for {ok}/{len(df)} firms (rest flagged for Tier-2 follow-up)")


if __name__ == "__main__":
    main()
