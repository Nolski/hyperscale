#!/usr/bin/env python3
"""
fetch_hyperscaler_debt.py -- Acquisition step (one script = one step).

Pulls the DEBT and CASH-FLOW lines for the major AI hyperscalers from the SEC
EDGAR XBRL `companyconcept` API and writes:
  - raw JSON per company/concept -> data/raw/sec_debt_<ticker>_<concept>_<date>.json
  - tidy annual panel            -> data/processed/hyperscaler_debt.csv

Why: the buildout is pivoting from CASH-funded to BOND-funded capex (Meta, Oracle,
Amazon mega-issuance, 2024-2026). That issuance is the bridge between the equity
story and the bond/credit story -- it adds to corporate-bond and (indirectly)
Treasury supply, which is the term-premium pressure documented in
analyze_curve_decomposition.py. analyze_ai_financing_linkage.py uses these to size
the debt-financed share of capex and capex-vs-cash-flow coverage.

Four concepts per company:
  * LongTermDebtNoncurrent (INSTANT / balance sheet) -- the debt stock at FY end.
  * ProceedsFromIssuanceOfLongTermDebt (DURATION / cash flow) -- new debt raised.
  * InterestExpense (DURATION / income statement) -- the carrying cost.
  * NetCashProvidedByUsedInOperatingActivities (DURATION) -- operating cash flow,
    the denominator for "can they fund capex internally?".
Several have company-specific tag variants; candidate tags are tried in order.

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

# Same 7 firms as fetch_hyperscaler_capex.py. CIKs verified via SEC EDGAR.
COMPANIES = {
    "MSFT":  ("Microsoft",      789019),
    "GOOGL": ("Alphabet",       1652044),
    "AMZN":  ("Amazon",         1018724),
    "META":  ("Meta Platforms", 1326801),
    "NVDA":  ("NVIDIA",         1045810),
    "ORCL":  ("Oracle",         1341439),
    "CRWV":  ("CoreWeave",      1769628),
}

# Each metric: (column name, kind, [candidate us-gaap concepts tried in order]).
# kind = "instant" (balance-sheet stock) or "duration" (flow over the year).
METRICS = [
    ("long_term_debt_usd", "instant", [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ]),
    ("debt_issuance_usd", "duration", [
        "ProceedsFromIssuanceOfLongTermDebt",
        "ProceedsFromIssuanceOfDebt",
        "ProceedsFromIssuanceOfSeniorLongTermDebt",
    ]),
    ("interest_expense_usd", "duration", [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestAndDebtExpense",
    ]),
    ("operating_cash_flow_usd", "duration", [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ]),
]

# Per-company override for the debt-stock concept where the defaults don't apply.
# Oracle does not file LongTermDebtNoncurrent; it reports the consolidated debt
# carrying amount under DebtInstrumentCarryingAmount (verified $92.9B at FY2025).
DEBT_STOCK_OVERRIDE = {
    "ORCL": ["DebtInstrumentCarryingAmount"],
}

URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
MIN_DAYS, MAX_DAYS = 340, 380  # ~1-year periods for duration concepts


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
    """~Annual (340-380 day) 10-K facts, keyed by period-end; latest vintage kept."""
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
    """Fiscal-year-end balance-sheet values from 10-Ks, keyed by period-end."""
    best: dict[str, dict] = {}
    for fact in doc.get("units", {}).get("USD", []):
        if fact.get("form") not in ("10-K", "10-K/A"):
            continue
        key = fact["end"]  # instant concepts carry only "end"
        if key not in best or fact["filed"] > best[key]["filed"]:
            best[key] = fact
    return best


def best_concept(cik: int, candidates: list[str], kind: str, headers: dict
                 ) -> tuple[str, dict, dict] | None:
    """Try candidate concepts; return (concept, raw_doc, facts) reaching latest period."""
    found = []
    for concept in candidates:
        if not isinstance(concept, str):  # guard against stray non-str entries
            continue
        doc = fetch_concept(cik, concept, headers)
        time.sleep(0.2)  # stay under SEC's 10 req/s
        if doc is None:
            continue
        facts = annual_instant_facts(doc) if kind == "instant" else annual_duration_facts(doc)
        if facts:
            found.append((concept, doc, facts))
    if not found:
        return None
    return max(found, key=lambda c: max(c[2]))  # whichever extends furthest


def main() -> None:
    headers = {"User-Agent": get_user_agent()}
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    for ticker, (name, cik) in COMPANIES.items():
        # period_end -> partial row accumulator
        by_period: dict[str, dict] = {}
        used_concepts: dict[str, str] = {}
        for col, kind, candidates in METRICS:
            if col == "long_term_debt_usd" and ticker in DEBT_STOCK_OVERRIDE:
                candidates = DEBT_STOCK_OVERRIDE[ticker]
            picked = best_concept(cik, candidates, kind, headers)
            if picked is None:
                used_concepts[col] = "n/a"
                continue
            concept, doc, facts = picked
            used_concepts[col] = concept
            (RAW / f"sec_debt_{ticker}_{concept}_{RETRIEVED}.json").write_text(
                json.dumps(doc, indent=2))
            for end_str, fact in facts.items():
                row = by_period.setdefault(end_str, {})
                row[col] = fact["val"]
                row.setdefault("_form", fact.get("form"))

        for end_str, vals in sorted(by_period.items()):
            end = dt.date.fromisoformat(end_str)
            all_rows.append({
                "ticker": ticker,
                "company": name,
                "fiscal_year": end.year,
                "period_end": end_str,
                "long_term_debt_usd": vals.get("long_term_debt_usd"),
                "debt_issuance_usd": vals.get("debt_issuance_usd"),
                "interest_expense_usd": vals.get("interest_expense_usd"),
                "operating_cash_flow_usd": vals.get("operating_cash_flow_usd"),
                "retrieved": RETRIEVED,
            })

        dbt = used_concepts.get("long_term_debt_usd", "n/a")
        latest_year = max((dt.date.fromisoformat(e).year for e in by_period), default=None)
        print(f"  {ticker:6s} {name:16s} debt-tag={dbt:24s} "
              f"years={len(by_period):2d} latest FY={latest_year}")

    if not all_rows:
        sys.exit("ERROR: no debt data retrieved.")

    df = pd.DataFrame(all_rows).sort_values(["ticker", "period_end"])
    out = PROCESSED / "hyperscaler_debt.csv"
    df.to_csv(out, index=False)
    print(f"\nWrote {len(df)} rows -> {out.relative_to(ROOT)}")
    print(f"Raw JSON -> {RAW.relative_to(ROOT)}/  (retrieved {RETRIEVED})")

    # Console: latest FY debt stock per company, largest first.
    latest = df.sort_values("period_end").groupby("ticker").tail(1)
    print("\nLatest fiscal-year debt & cash flow (USD bn):")
    print(f"  {'Company':16s} {'FY':>6s} {'LT debt':>9s} {'issuance':>9s} {'int exp':>8s} {'op cash':>9s}")
    for _, r in latest.sort_values("long_term_debt_usd", ascending=False, na_position="last").iterrows():
        def bn(x):
            return f"{x/1e9:9.1f}" if pd.notna(x) else f"{'n/a':>9s}"
        print(f"  {r['company']:16s} {r['fiscal_year']:6d} {bn(r['long_term_debt_usd'])} "
              f"{bn(r['debt_issuance_usd'])} {bn(r['interest_expense_usd'])[-8:]:>8s} "
              f"{bn(r['operating_cash_flow_usd'])}")


if __name__ == "__main__":
    main()
