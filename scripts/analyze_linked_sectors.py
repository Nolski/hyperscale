#!/usr/bin/env python3
"""
analyze_linked_sectors.py -- Analysis step (Questions 3b & 3d).

Two linked sectors of the AI buildout:
  SEMICONDUCTORS -- AI-chip suppliers' revenue (the supply side of the hardware
                    that fills the data centers).
  CONSTRUCTION   -- data-center construction set against all US construction.

Reads   : data/processed/{semiconductor_revenue_annual,datacenter_construction_annual,
          construction_sector}.csv
Writes  : output/linked_sectors_summary.csv
          output/fig_semiconductor_revenue.png
          output/fig_datacenter_share_of_construction.png

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
SRC = f"Sources: SEC EDGAR (chip revenue); US Census/OWID & FRED (construction). Compiled {RETRIEVED}."


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    semi = pd.read_csv(PROCESSED / "semiconductor_revenue_annual.csv")
    dc_constr = pd.read_csv(PROCESSED / "datacenter_construction_annual.csv")
    constr = pd.read_csv(PROCESSED / "construction_sector.csv")

    # --- SEMICONDUCTORS: calendar-align (NVDA Jan FY-end -> prior year) -----
    end_month = pd.to_datetime(semi["period_end"]).dt.month
    semi["chart_year"] = semi["fiscal_year"].where(end_month != 1,
                                                   semi["fiscal_year"] - 1)
    semi["revenue_bn"] = semi["revenue_usd"] / BN
    latest = semi.sort_values("period_end").groupby("ticker").tail(1)
    five_firm = latest["revenue_usd"].sum() / BN
    nvda = latest.loc[latest.ticker == "NVDA", "revenue_usd"].iloc[0] / BN
    nvda_share = nvda / five_firm * 100

    # --- CONSTRUCTION: data-center spending vs all US construction ---------
    tc = constr[constr.label == "total_construction_spending"].copy()
    tc["year"] = pd.to_datetime(tc["date"]).dt.year
    # TTLCONS is monthly SAAR; the mean of a year's months ~= that year's annual $.
    tc_annual = tc.groupby("year").agg(total_msaar=("value", "mean"),
                                       n=("value", "count")).reset_index()
    tc_annual = tc_annual[tc_annual["n"] == 12]              # complete years only
    tc_annual["total_construction_bn"] = tc_annual["total_msaar"] / 1000

    dc = dc_constr[~dc_constr["partial_year"]].copy()
    dc["datacenter_bn"] = dc["spending_usd"] / BN
    constr_link = dc.merge(tc_annual[["year", "total_construction_bn"]], on="year")
    constr_link["dc_share_pct"] = (constr_link["datacenter_bn"]
                                   / constr_link["total_construction_bn"] * 100)

    emp = constr[constr.label == "construction_employment"].sort_values("date")
    emp_latest = emp.iloc[-1]["value"] / 1000  # thousands -> millions

    # --- Summary table -----------------------------------------------------
    last = constr_link.iloc[-1]
    rows = [
        ("AI-chip suppliers' revenue (5 US firms, latest FY)", five_firm, "USD bn"),
        ("  of which NVIDIA", nvda, "USD bn"),
        ("NVIDIA share of the five", nvda_share, "%"),
        (f"Data-center construction ({int(last['year'])})", last["datacenter_bn"], "USD bn"),
        (f"Total US construction ({int(last['year'])})",
         last["total_construction_bn"], "USD bn"),
        (f"Data-center share of all US construction ({int(last['year'])})",
         last["dc_share_pct"], "%"),
        ("US construction employment (latest)", emp_latest, "million"),
    ]
    summary = pd.DataFrame(rows, columns=["indicator", "value", "unit"])
    summary["value"] = summary["value"].round(2)
    summary["retrieved"] = RETRIEVED
    summary.to_csv(OUTPUT / "linked_sectors_summary.csv", index=False)

    # --- Console report ----------------------------------------------------
    print("=" * 72)
    print("QUESTIONS 3b & 3d — SEMICONDUCTORS & CONSTRUCTION")
    print("=" * 72)
    print(f"AI-chip suppliers (5 US firms), latest fiscal year: ${five_firm:,.0f}B")
    print(f"  NVIDIA ${nvda:,.0f}B = {nvda_share:.0f}% of the five.")
    print(f"Data-center construction vs. all US construction:")
    for _, r in constr_link.iterrows():
        if int(r["year"]) % 2 == 1 or r["year"] == constr_link["year"].max():
            print(f"  {int(r['year'])}: ${r['datacenter_bn']:6.1f}B of "
                  f"${r['total_construction_bn']:8,.0f}B  = {r['dc_share_pct']:.2f}%")
    print(f"US construction employment (latest): {emp_latest:.1f} million")
    print("=" * 72)

    # --- Figure 1: semiconductor revenue, stacked by firm ------------------
    pivot = (semi[semi.chart_year >= 2016]
             .pivot_table(index="chart_year", columns="company",
                          values="revenue_bn", aggfunc="sum").fillna(0))
    fig, ax = plt.subplots(figsize=(9, 5.2))
    pivot.plot(kind="bar", stacked=True, ax=ax, width=0.82, colormap="cividis")
    ax.set_title("AI-chip suppliers' revenue (5 US-listed firms)")
    ax.set_xlabel("Year (calendar-aligned)")
    ax.set_ylabel("USD billion")
    ax.legend(fontsize=8)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_semiconductor_revenue.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: data-center share of all US construction ----------------
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(constr_link["year"], constr_link["dc_share_pct"], color="#2a6f97", width=0.7)
    ax.set_title("Data-center construction as a share of all US construction spending")
    ax.set_xlabel("Year")
    ax.set_ylabel("% of total US construction")
    ax.grid(alpha=0.3, axis="y")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_datacenter_share_of_construction.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/linked_sectors_summary.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
