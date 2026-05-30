#!/usr/bin/env python3
"""
analyze_ai_financing_linkage.py -- Analysis step (the AI-thesis bridge).

Answers: "Is the AI buildout shifting from cash-funded to DEBT-funded, and does
that connect the equity story to the bond/credit story?"

Three measures, per hyperscaler and in aggregate:
  1. INTERNAL-FUNDING COVERAGE = operating cash flow / capex. Above 1 -> the
     buildout is self-funded from earnings; below 1 -> external financing required.
  2. DEBT-FUNDED SHARE (proxy) = long-term-debt issuance / capex. How much of the
     year's investment is matched by new borrowing.
  3. DEBT-ISSUANCE TREND = aggregate new long-term debt raised per year -- the flow
     that adds to corporate-bond (and indirectly Treasury) supply.

The linkage to the wider question: as hyperscalers and AI-clouds (Oracle, CoreWeave,
Meta) lever up, their issuance adds to the supply of duration the market must absorb
-- the same supply pressure that shows up as a positive TERM PREMIUM in
analyze_curve_decomposition.py. That is the hinge between buoyant AI equities and a
heavy long end. The causal magnitude is a THESIS, not a measurement (flagged).

Reads   : data/processed/hyperscaler_debt.csv, hyperscaler_capex_annual.csv
Writes  : output/ai_financing.csv
          output/fig_capex_funding_coverage.png
          output/fig_hyperscaler_debt_issuance.png

Caveats : Debt-issuance is GROSS proceeds (not net of repayment); some firms
          (MSFT, GOOGL, NVDA) don't report an issuance tag in recent years (shown
          as missing, not zero). Financing -> term-premium causation is a thesis.

Re-runnable: reads data/processed/, overwrites output/. No network.
"""

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
BN = 1e9
SRC = f"Source: SEC EDGAR XBRL (10-K filings). Compiled {RETRIEVED}."


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def add_chart_year(df: pd.DataFrame) -> pd.DataFrame:
    """Calendar-align fiscal years (Jan FY-ends -> prior calendar year), matching
    analyze_ai_investment_accounts.py so debt and capex line up by chart_year."""
    m = pd.to_datetime(df["period_end"]).dt.month
    df = df.copy()
    df["chart_year"] = df["fiscal_year"].where(m != 1, df["fiscal_year"] - 1)
    return df


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    debt = add_chart_year(pd.read_csv(PROCESSED / "hyperscaler_debt.csv"))
    capex = add_chart_year(pd.read_csv(PROCESSED / "hyperscaler_capex_annual.csv"))

    # Merge debt + capex on ticker + period_end (same fiscal year-end).
    m = debt.merge(
        capex[["ticker", "period_end", "capex_usd", "total_capacity_investment_usd"]],
        on=["ticker", "period_end"], how="left")
    m["coverage"] = m["operating_cash_flow_usd"] / m["capex_usd"]
    m["debt_funded_share"] = m["debt_issuance_usd"] / m["capex_usd"]

    # --- Latest fiscal year per firm ---
    latest = m.sort_values("period_end").groupby("ticker").tail(1).copy()
    latest = latest.sort_values("capex_usd", ascending=False, na_position="last")

    # --- Summary table (latest FY per firm) ---
    out_rows = []
    for _, r in latest.iterrows():
        out_rows.append({
            "section": "latest_fy_by_firm",
            "ticker": r["ticker"],
            "company": r["company"],
            "fiscal_year": r["fiscal_year"],
            "capex_usd_bn": round(r["capex_usd"] / BN, 1) if pd.notna(r["capex_usd"]) else None,
            "long_term_debt_usd_bn": round(r["long_term_debt_usd"] / BN, 1) if pd.notna(r["long_term_debt_usd"]) else None,
            "debt_issuance_usd_bn": round(r["debt_issuance_usd"] / BN, 1) if pd.notna(r["debt_issuance_usd"]) else None,
            "operating_cash_flow_usd_bn": round(r["operating_cash_flow_usd"] / BN, 1) if pd.notna(r["operating_cash_flow_usd"]) else None,
            "coverage_ocf_over_capex": round(r["coverage"], 2) if pd.notna(r["coverage"]) else None,
            "debt_funded_share": round(r["debt_funded_share"], 2) if pd.notna(r["debt_funded_share"]) else None,
        })

    # --- Aggregate latest-year totals (firms with data) ---
    agg_capex = latest["capex_usd"].sum() / BN
    agg_ocf = latest["operating_cash_flow_usd"].sum() / BN
    agg_issuance = latest["debt_issuance_usd"].sum() / BN
    agg_debt = latest["long_term_debt_usd"].sum() / BN
    out_rows.append({"section": "aggregate_latest_fy", "company": "7-firm total",
                     "capex_usd_bn": round(agg_capex, 1),
                     "long_term_debt_usd_bn": round(agg_debt, 1),
                     "debt_issuance_usd_bn": round(agg_issuance, 1),
                     "operating_cash_flow_usd_bn": round(agg_ocf, 1),
                     "coverage_ocf_over_capex": round(agg_ocf / agg_capex, 2)})

    table = pd.DataFrame(out_rows)
    table["retrieved"] = RETRIEVED
    table.to_csv(OUTPUT / "ai_financing.csv", index=False)

    # --- Console report ---
    print("=" * 78)
    print("AI BUILDOUT FINANCING — latest fiscal year, USD billion")
    print("=" * 78)
    print(f"  {'Company':16s} {'capex':>7s} {'LT debt':>8s} {'issuance':>9s} "
          f"{'op cash':>8s} {'OCF/capex':>10s}")
    for _, r in latest.iterrows():
        def bn(x): return f"{x/BN:7.1f}" if pd.notna(x) else f"{'—':>7s}"
        cov = f"{r['coverage']:10.2f}" if pd.notna(r["coverage"]) else f"{'—':>10s}"
        print(f"  {r['company']:16s} {bn(r['capex_usd'])} {bn(r['long_term_debt_usd'])[-8:]:>8s} "
              f"{bn(r['debt_issuance_usd'])[-9:]:>9s} {bn(r['operating_cash_flow_usd'])[-8:]:>8s} {cov}")
    print("-" * 78)
    print(f"  7-firm aggregate: capex ${agg_capex:.0f}B, operating cash flow ${agg_ocf:.0f}B "
          f"(coverage {agg_ocf/agg_capex:.2f}x),")
    print(f"  reported new debt issuance ${agg_issuance:.0f}B, debt stock ${agg_debt:.0f}B.")
    print("  Read: the megacaps still out-earn their capex in aggregate, but the")
    print("  marginal builders (Oracle, CoreWeave, Meta) increasingly fund with DEBT —")
    print("  adding duration to the market that helps keep the term premium positive.")
    print("=" * 78)

    # --- Figure 1: coverage (OCF / capex) by firm, latest FY ---
    cov = latest.dropna(subset=["coverage"]).sort_values("coverage")
    fig, ax = plt.subplots(figsize=(9, 5.2))
    colors = ["#c1121f" if c < 1 else "#2a9d8f" for c in cov["coverage"]]
    ax.barh(cov["company"], cov["coverage"], color=colors)
    ax.axvline(1.0, color="black", ls="--", lw=1.2)
    for i, (_, r) in enumerate(cov.iterrows()):
        ax.text(r["coverage"], i, f"  {r['coverage']:.2f}x", va="center", fontsize=9)
    ax.set_title("Can they fund the buildout from earnings? (operating cash flow ÷ capex)")
    ax.set_xlabel("OCF / capex  (dashed = 1.0; red < 1 = needs external funding)")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_capex_funding_coverage.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: aggregate debt issuance by year, stacked by company ---
    iss = m[(m.chart_year >= 2015) & (m.chart_year <= 2025)].dropna(subset=["debt_issuance_usd"])
    pivot = (iss.assign(issuance_bn=iss["debt_issuance_usd"] / BN)
             .pivot_table(index="chart_year", columns="company",
                          values="issuance_bn", aggfunc="sum").fillna(0))
    fig, ax = plt.subplots(figsize=(9, 5.2))
    pivot.plot(kind="bar", stacked=True, ax=ax, width=0.82, colormap="plasma")
    ax.set_title("Hyperscaler long-term-debt issuance (gross proceeds, by year)")
    ax.set_xlabel("Year (calendar-aligned)")
    ax.set_ylabel("USD billion")
    ax.legend(fontsize=8, ncol=2)
    ax.annotate("MSFT/GOOGL/NVDA report no issuance tag in recent FYs (missing ≠ 0)",
                xy=(0.02, 0.93), xycoords="axes fraction", fontsize=7, color="grey")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_hyperscaler_debt_issuance.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/ai_financing.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
