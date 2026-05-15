#!/usr/bin/env python3
"""
analyze_ai_investment_accounts.py -- Analysis step (Question 1).

Reconciles the AI-investment data into a three-layer accounts table and figures,
answering "what is the current total AI investment, by category?".

The THREE LAYERS are reported separately and never summed across (see
notes/provenance.md and the research plan):
  - REAL INVESTMENT  -- the buildout itself (hyperscaler capex + finance leases;
                        data-center construction is the building-shell SUBSET).
  - FINANCING        -- equity into AI-native firms (VC).
  - SUPPLY MIRROR    -- chip revenue; hardware already inside the capex layer.

Reads   : data/processed/{hyperscaler_capex_annual,datacenter_construction_annual,
          semiconductor_revenue_annual,vc_ai,macro_investment}.csv
Writes  : output/ai_investment_accounts.csv  (reconciled table)
          output/fig_hyperscaler_capex_ramp.png
          output/fig_ai_investment_layers.png
          output/fig_capex_share_of_gdp.png

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
SRC = f"Sources: SEC EDGAR, US Census/OWID, OECD, FRED. Compiled {RETRIEVED}."


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    capex = pd.read_csv(PROCESSED / "hyperscaler_capex_annual.csv")
    # Calendar-aligned year for time-series charts: a fiscal year ending in
    # January (NVIDIA) overwhelmingly covers the *prior* calendar year, so
    # NVDA FY2026 (ends Jan 2026) charts as 2025 alongside the others' FY2025.
    _end_month = pd.to_datetime(capex["period_end"]).dt.month
    capex["chart_year"] = capex["fiscal_year"].where(_end_month != 1,
                                                     capex["fiscal_year"] - 1)
    constr = pd.read_csv(PROCESSED / "datacenter_construction_annual.csv")
    semi = pd.read_csv(PROCESSED / "semiconductor_revenue_annual.csv")
    vc = pd.read_csv(PROCESSED / "vc_ai.csv")
    macro = pd.read_csv(PROCESSED / "macro_investment.csv")

    # --- Latest fiscal year per hyperscaler (NVDA's latest is FY2026) ---
    latest_capex = capex.sort_values("period_end").groupby("ticker").tail(1)
    hyper_capex = latest_capex["capex_usd"].sum() / BN
    hyper_lease = latest_capex["finance_lease_additions_usd"].sum() / BN  # NaN-safe sum
    hyper_total = latest_capex["total_capacity_investment_usd"].sum() / BN

    # --- Other layers, reference year 2025 ---
    constr_2025 = constr.loc[constr.year == 2025, "spending_usd"].iloc[0] / BN
    semi_latest = semi.sort_values("period_end").groupby("ticker").tail(1)
    semi_total = semi_latest["revenue_usd"].sum() / BN
    vc_world = vc[(vc.year == 2025) & (vc.geography == "World") & (vc.series == "ai_vc")
                  ].iloc[0]["value_usd_billion"]
    vc_us = vc[(vc.year == 2025) & (vc.geography == "United States") & (vc.series == "ai_vc")
               ].iloc[0]["value_usd_billion"]

    # --- Macro denominators: annualise quarterly SAAR series (mean of 2025 quarters) ---
    macro["year"] = pd.to_datetime(macro["date"]).dt.year
    def annual(label, year=2025):
        s = macro[(macro.label == label) & (macro.year == year)]
        return s["value"].mean()  # SAAR quarterly mean ~= annual level ($bn)
    gdp = annual("gdp_nominal")
    pnfi = annual("private_nonresidential_fixed_invest")
    it_inv = annual("fixed_invest_it_equip_and_software")

    # --- Reconciled accounts table ---
    rows = [
        ("Real investment", "Hyperscaler cash capex (7 firms, latest FY)", hyper_capex,
         "Spine of the real-investment layer."),
        ("Real investment", "Hyperscaler finance-lease additions (7 firms)", hyper_lease,
         "Non-cash; lease-funded capacity."),
        ("Real investment", "= Hyperscaler total capital investment", hyper_total,
         "Cash capex + finance leases."),
        ("Real investment", "US data-center construction (all builders, 2025)", constr_2025,
         "Building shells only; SUBSET of capex above + non-hyperscaler/colo builders. Not additive."),
        ("Financing", "Global VC into AI firms (2025)", vc_world,
         "Equity into AI-native firms; separate flow, not additive to capex."),
        ("Financing", "  of which United States (2025)", vc_us, "US share of global AI VC."),
        ("Supply mirror", "AI-chip supplier revenue (5 US firms, latest FY)", semi_total,
         "Hardware sold into the buildout; already INSIDE hyperscaler capex. Cross-check only."),
    ]
    table = pd.DataFrame(rows, columns=["layer", "item", "value_usd_billion", "note"])
    table["value_usd_billion"] = table["value_usd_billion"].round(1)
    table["reference"] = "latest fiscal year (2025; NVDA FY2026)"
    table["retrieved"] = RETRIEVED
    table.to_csv(OUTPUT / "ai_investment_accounts.csv", index=False)

    # --- Console report ---
    print("=" * 72)
    print("AI INVESTMENT ACCOUNTS — latest year (2025; NVDA FY2026), USD billion")
    print("=" * 72)
    cur = None
    for _, r in table.iterrows():
        if r["layer"] != cur:
            cur = r["layer"]
            print(f"\n[{cur.upper()}]")
        print(f"  {r['item']:48s} {r['value_usd_billion']:9,.1f}")
    print("\n[CONTEXT] hyperscaler total capital investment vs. US macro (2025):")
    print(f"  as % of GDP                                  {hyper_total / gdp * 100:6.2f}%")
    print(f"  as % of private nonresidential fixed invest. {hyper_total / pnfi * 100:6.2f}%")
    print(f"  as % of IT-equipment + software investment   {hyper_total / it_inv * 100:6.2f}%")
    print("  (company fiscal-year actuals vs. SAAR macro — indicative, not exact.)")
    print("=" * 72)

    # --- Figure 1: hyperscaler capacity-investment ramp, stacked by company ---
    capex["invest"] = capex["total_capacity_investment_usd"] / BN
    pivot = (capex[(capex.chart_year >= 2015) & (capex.chart_year <= 2025)]
             .pivot_table(index="chart_year", columns="company", values="invest", aggfunc="sum")
             .fillna(0))
    fig, ax = plt.subplots(figsize=(9, 5.2))
    pivot.plot(kind="bar", stacked=True, ax=ax, width=0.82, colormap="viridis")
    ax.set_title("Hyperscaler capital investment (cash capex + finance leases)")
    ax.set_xlabel("Year (calendar-aligned)")
    ax.set_ylabel("USD billion")
    ax.legend(fontsize=8, ncol=2)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_hyperscaler_capex_ramp.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: the three layers, side by side (explicitly not summed) ---
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = ["Real investment\n(hyperscaler total)", "Financing\n(global VC into AI)",
              "Supply mirror\n(AI-chip revenue)"]
    values = [hyper_total, vc_world, semi_total]
    colors = ["#2a6f97", "#e09f3e", "#9d4edd"]
    ax.bar(labels, values, color=colors, width=0.6)
    for i, v in enumerate(values):
        ax.text(i, v + 8, f"${v:,.0f}B", ha="center", fontsize=10, weight="bold")
    ax.set_ylabel("USD billion")
    ax.set_title("AI investment by accounting layer, 2025 — layers are NOT additive")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_ai_investment_layers.png", dpi=150)
    plt.close(fig)

    # --- Figure 3: hyperscaler capital investment as % of US GDP, over time ---
    gdp_by_year = (macro[macro.label == "gdp_nominal"].groupby("year")["value"].mean())
    by_year = (capex[capex.chart_year <= 2025]
               .groupby("chart_year")["total_capacity_investment_usd"].sum() / BN)
    share = (by_year / gdp_by_year * 100).dropna()
    share = share[share.index >= 2015]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(share.index, share.values, marker="o", color="#2a6f97", lw=2)
    ax.set_title("Seven-hyperscaler capital investment as % of US GDP")
    ax.set_xlabel("Year (calendar-aligned)")
    ax.set_ylabel("% of US GDP")
    ax.grid(alpha=0.3)
    ax.annotate("company fiscal-year actuals\nvs. annual-average GDP — indicative",
                xy=(0.02, 0.92), xycoords="axes fraction", fontsize=7, color="grey")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_capex_share_of_gdp.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/ai_investment_accounts.csv + 3 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
