#!/usr/bin/env python3
"""
analyze_equity_funding.py -- Analysis step.

Answers: how much of the giants' "self-funding" of the AI buildout leans on the equity
currency rather than cash? The data centers themselves are paid in cash/debt, not stock --
but the CASH-GENERATING MACHINE is subsidised by (a) paying labour in stock (SBC, a non-cash
add-back that inflates operating cash flow) and (b) is run alongside buybacks that divert cash
from capex to supporting the share price. This strips those out to get a stricter coverage.

Reads : data/processed/hyperscaler_equity_funding.csv (SEC EDGAR: SBC, buybacks, equity
        issuance, OCF, capex), data/raw/manual/circular_financing.csv (vendor equity stakes)
Writes: output/equity_funding_summary.csv

Discipline: SBC/buybacks/OCF/capex are PRIMARY (SEC). The vendor equity stakes are Tier-2
(announced). We can size the equity-currency dependence; we CANNOT prove how much of the
valuation is "artificial" -- that counterfactual is left unproven, like the backstop thesis.

Re-runnable: reads existing files, overwrites output. No network.
"""

import datetime as dt
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "raw" / "manual"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
BN = 1e9


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(PROCESSED / "hyperscaler_equity_funding.csv")
    d = d.sort_values("period_end").groupby("ticker").tail(1).copy()
    for c in ["share_based_comp_usd", "buybacks_usd", "equity_issuance_usd"]:
        d[c] = d[c].fillna(0)
    d["sbc_pct_ocf"] = d["share_based_comp_usd"] / d["operating_cash_flow_usd"] * 100
    d["coverage"] = d["operating_cash_flow_usd"] / d["capex_usd"]
    d["coverage_adj"] = ((d["operating_cash_flow_usd"] - d["share_based_comp_usd"])
                         / d["capex_usd"])

    keep = ["ticker", "company", "fiscal_year", "operating_cash_flow_usd",
            "share_based_comp_usd", "sbc_pct_ocf", "capex_usd", "buybacks_usd",
            "equity_issuance_usd", "coverage", "coverage_adj"]
    out = d[keep].copy()
    for c in ["operating_cash_flow_usd", "share_based_comp_usd", "capex_usd",
              "buybacks_usd", "equity_issuance_usd"]:
        out[c] = (out[c] / BN).round(2)
    out["retrieved"] = RETRIEVED
    order = {t: i for i, t in enumerate(["MSFT", "GOOGL", "AMZN", "META", "NVDA", "ORCL", "CRWV"])}
    out = out.sort_values("ticker", key=lambda s: s.map(order))
    out.to_csv(OUTPUT / "equity_funding_summary.csv", index=False)

    ocf, sbc = d.operating_cash_flow_usd.sum() / BN, d.share_based_comp_usd.sum() / BN
    cap, bb = d.capex_usd.sum() / BN, d.buybacks_usd.sum() / BN
    print("=" * 78)
    print("CASH vs THE EQUITY CURRENCY -- how the giants 'self-fund' (latest FY, SEC primary)")
    print("=" * 78)
    print(f"  operating cash flow  ${ocf:6.0f}B")
    print(f"  stock-based comp     ${sbc:6.0f}B   ({sbc/ocf*100:.0f}% of OCF -- paid in stock, not cash)")
    print(f"  cash capex           ${cap:6.0f}B")
    print(f"  buybacks             ${bb:6.0f}B   (cash to holders, NOT available for capex)")
    print(f"  coverage  OCF/capex          {ocf/cap:.2f}x")
    print(f"  coverage  (OCF-SBC)/capex    {(ocf-sbc)/cap:.2f}x   <- treating stock comp as the cash cost it is")
    print(f"  capex + buybacks ${cap+bb:.0f}B  = {(cap+bb)/ocf:.0%} of OCF")
    print("\n  per firm (coverage -> adjusted):")
    for _, r in out.iterrows():
        print(f"    {r.company:16s} FY{int(r.fiscal_year)}  cov {r.coverage:.2f} -> {r.coverage_adj:.2f}"
              f"   SBC {r.sbc_pct_ocf:.0f}% of OCF   buyback ${r.buybacks_usd:.0f}B")
    print(f"\n  Wrote {(OUTPUT / 'equity_funding_summary.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
