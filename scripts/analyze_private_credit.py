#!/usr/bin/env python3
"""
analyze_private_credit.py -- Analysis step (the systemic-financing / private-credit layer).

The report's thinnest strand was "who lends to the AI builders that cannot self-fund, and where
does that risk sit?" This sizes the AI debt wave and maps the holder chain the FSB flagged.

DISCIPLINE: the HARD anchor is primary SEC-EDGAR debt (output/ai_financing.csv) -- long-term debt,
new issuance, and the debt-funded share of capex per firm. The macro/systemic context
(data/raw/manual/private_credit.csv) is Tier-2 (regulator/bank/press), validated 2026-07-19 against
live sources but read as framing, not measurement. Primary and Tier-2 are kept in separate `tier`
rows and never blended into one total.

Reads : output/ai_financing.csv (SEC primary), data/raw/manual/private_credit.csv (Tier-2 macro)
Writes: output/private_credit_summary.csv  (tidy indicators, tier-labelled)

Re-runnable: reads existing files, overwrites output. No network.
"""

import datetime as dt
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "raw" / "manual"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fin = pd.read_csv(OUTPUT / "ai_financing.csv")
    firms = fin[fin.section == "latest_fy_by_firm"].copy()
    agg = fin[fin.section == "aggregate_latest_fy"].iloc[0]

    # --- Primary (SEC EDGAR): the debt already on the balance sheets ---
    firms["debt_funded_share"] = pd.to_numeric(firms["debt_funded_share"], errors="coerce")
    edge = firms[firms["debt_funded_share"] >= 0.5]["company"].tolist()
    rows = [
        ("ltd_7firm", float(agg["long_term_debt_usd_bn"]), "usd_billion", "primary",
         "SEC EDGAR", "combined long-term debt, 7 hyperscalers/edge builders, latest FY"),
        ("debt_issuance_7firm", float(agg["debt_issuance_usd_bn"]), "usd_billion", "primary",
         "SEC EDGAR", "new long-term-debt issuance in the latest FY across the 7"),
        ("edge_debt_funded_max", float(firms["debt_funded_share"].max() * 100), "percent",
         "primary", "SEC EDGAR",
         f"most debt-funded builder's new capex covered by new debt ({', '.join(edge)} are the edge)"),
    ]

    # --- Tier-2 (regulator/bank/press): the systemic context, validated 2026-07-19 ---
    pc = pd.read_csv(MANUAL / "private_credit.csv", comment="#")
    for r in pc.itertuples():
        rows.append((r.metric, float(r.value), r.unit, "tier-2", r.source, r.note))

    out = pd.DataFrame(rows, columns=["metric", "value", "unit", "tier", "source", "note"])
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "private_credit_summary.csv", index=False)

    print("=" * 78)
    print("SYSTEMIC FINANCING / PRIVATE CREDIT  (primary SEC anchor + validated Tier-2 context)")
    print("=" * 78)
    print(f"  PRIMARY (SEC EDGAR): 7 firms carry ${agg['long_term_debt_usd_bn']:.0f}B long-term debt; "
          f"${agg['debt_issuance_usd_bn']:.0f}B new issuance last FY.")
    print(f"    edge builders (>=50% of capex debt-funded): {', '.join(edge)}")
    for r in firms.sort_values('debt_funded_share', ascending=False).itertuples():
        if pd.notna(r.debt_funded_share):
            print(f"      {r.company:18s} {r.debt_funded_share*100:5.0f}% of capex debt-funded, "
                  f"coverage {r.coverage_ocf_over_capex:.2f}x")
    print("\n  TIER-2 (validated 2026-07-19): AI debt issuance ~$570B in 2026 (~4x prior pace); "
          ">$200B private-credit\n    loans outstanding; FSB sizes private credit $1.5-2T; "
          "BofA Jul-2026: 48% call AI capex the\n    likeliest systemic credit event. "
          "Holders: insurers, pensions, Blackstone/Apollo/Ares.")
    print(f"\n  Wrote {(OUTPUT / 'private_credit_summary.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
