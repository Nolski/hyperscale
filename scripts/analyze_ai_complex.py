#!/usr/bin/env python3
"""
analyze_ai_complex.py -- Analysis step (the supply-chain footprint of the broadened analysis).

Sizes the "AI-industrial complex" beyond the 7 hyperscalers -- the memory, equipment,
networking, data-center-REIT, electrical/cooling, power and neo-cloud firms the buildout runs
through -- by layer, in revenue and capex, against the hyperscaler core.

CRITICAL DISCIPLINE (notes/methodology_broadening.md): for most of these firms revenue is
AI-EXPOSURE, not AI-attribution. An Eaton or NextEra is only partly tied to data centers, so
their full revenue is an UPPER BOUND on the AI tie, not an "AI total." This script reports
layer totals as exposure, never sums them into a single "AI GDP" number, and notes where
disclosed segments would tighten the estimate.

Reads : data/processed/ai_complex.csv, ai_financing.csv (hyperscaler core capex),
        semiconductor_revenue_annual.csv (chip core, context)
Writes: output/ai_complex_summary.csv
        output/fig_ai_complex_footprint.png

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
SRC = f"Source: SEC EDGAR filings (latest FY). Revenue = AI-EXPOSURE, not AI-only. Compiled {RETRIEVED}."
PALETTE = ["#1a3a5c", "#4a6e8f", "#9fb6c8", "#a4262c", "#c08a2e", "#6a4c93", "#2a9d8f"]


def caption(ax):
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.8, color="#8a8a8a")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cx = pd.read_csv(PROCESSED / "ai_complex.csv")
    cx = cx.dropna(subset=["revenue_usd"])
    cx["revenue_bn"] = cx["revenue_usd"] / BN
    cx["capex_bn"] = cx["capex_usd"] / BN

    by_layer = (cx.groupby("layer")
                .agg(firms=("ticker", "count"), revenue_bn=("revenue_bn", "sum"),
                     capex_bn=("capex_bn", "sum"))
                .sort_values("revenue_bn", ascending=False))

    # hyperscaler core capex (context) from the financing aggregate
    try:
        fin = pd.read_csv(OUTPUT / "ai_financing.csv")
        core_capex = float(fin[fin.section == "aggregate_latest_fy"]["capex_usd_bn"].iloc[0])
    except Exception:
        core_capex = float("nan")

    total_rev = cx["revenue_bn"].sum()
    total_capex = cx["capex_bn"].sum()

    out = by_layer.reset_index()
    out["note"] = "AI-EXPOSURE (upper bound), not AI-only revenue"
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "ai_complex_summary.csv", index=False)

    print("=" * 78)
    print("THE AI-INDUSTRIAL COMPLEX BEYOND THE 7  (latest FY, SEC primary)")
    print("=" * 78)
    print(f"  {len(cx)} firms across {by_layer.shape[0]} layers. Revenue is AI-EXPOSURE, not AI-only.\n")
    print(f"  {'layer':20s} {'firms':>5s} {'revenue':>10s} {'capex':>9s}")
    for layer, r in by_layer.iterrows():
        print(f"  {layer:20s} {int(r['firms']):5d} ${r['revenue_bn']:8.0f}B ${r['capex_bn']:7.0f}B")
    print("-" * 78)
    print(f"  {'TOTAL (exposure)':20s} {len(cx):5d} ${total_rev:8.0f}B ${total_capex:7.0f}B")
    print(f"\n  For scale: the 7-hyperscaler core spent ~${core_capex:.0f}B of capex last year.")
    print(f"  The complex around it adds ${total_rev:.0f}B of (AI-exposed) revenue and "
          f"${total_capex:.0f}B of capex")
    print(f"  across memory, equipment, networking, real estate, power and the neoclouds. The")
    print(f"  buildout is not 7 companies; it is an industrial base. But most of this revenue is")
    print(f"  NOT all-AI -- it is the upper bound of these firms' exposure, not an AI total.")
    print("=" * 78)

    # --- Figure: revenue (and capex) by layer ---
    d = by_layer.reset_index()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = range(len(d))
    ax.barh(y, d["revenue_bn"], color=[PALETTE[i % len(PALETTE)] for i in range(len(d))],
            height=0.6)
    for i, r in enumerate(d.itertuples()):
        ax.text(r.revenue_bn + 5, i, f"${r.revenue_bn:.0f}B  ({int(r.firms)} firms)",
                va="center", fontsize=8.5, weight="bold")
    ax.set_yticks(list(y)); ax.set_yticklabels(d["layer"])
    ax.invert_yaxis()
    ax.set_xlabel("Latest-FY revenue, USD billion  (AI-EXPOSURE, upper bound — not AI-only)")
    ax.set_xlim(0, d["revenue_bn"].max() * 1.25)
    ax.set_title("The AI-industrial complex beyond the seven hyperscalers, by layer")
    ax.grid(axis="y", visible=False)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_ai_complex_footprint.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/ai_complex_summary.csv + 1 figure (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
