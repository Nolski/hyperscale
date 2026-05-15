#!/usr/bin/env python3
"""
analyze_energy_linkage.py -- Analysis step (Question 3a, energy/grid linkage).

Connects the AI/data-center buildout to the US energy sector: data-center
electricity demand, its share of US load, and what is happening to prices.

Reads   : data/processed/{us_electricity,datacenter_energy}.csv
Writes  : output/energy_linkage.csv
          output/fig_us_electricity_demand.png
          output/fig_datacenter_electricity_share.png
          output/fig_electricity_prices.png

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
SRC = f"Sources: EIA API v2 (retail sales/price); LBNL & EPRI (data-center demand). Compiled {RETRIEVED}."


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    elec = pd.read_csv(PROCESSED / "us_electricity.csv")
    dce = pd.read_csv(PROCESSED / "datacenter_energy.csv")

    allsec = elec[elec.sector == "all sectors"].set_index("year").sort_index()
    res = elec[elec.sector == "residential"].set_index("year").sort_index()
    y0, y1 = int(allsec.index.min()), int(allsec.index.max())

    # --- Data-center share cross-check against EIA retail sales -------------
    dc_2023 = dce[(dce.year == 2023) & (dce.metric == "datacenter_electricity")
                  ].iloc[0]["value"]
    us_2023 = allsec.loc[2023, "sales_twh"]
    dc_share_check = dc_2023 / us_2023 * 100
    lbnl_share = dce[(dce.year == 2023) & (dce.metric == "datacenter_share_of_us")
                     ].iloc[0]["value"]

    # --- Demand growth: the flat era vs the recent surge -------------------
    cagr = lambda a, b, n: ((b / a) ** (1 / n) - 1) * 100
    growth_0720 = cagr(allsec.loc[2007, "sales_twh"], allsec.loc[2020, "sales_twh"], 13)
    growth_2025 = cagr(allsec.loc[2020, "sales_twh"], allsec.loc[y1, "sales_twh"], y1 - 2020)

    # --- Summary table -----------------------------------------------------
    share = dce[dce.metric == "datacenter_share_of_us"]
    rows = [
        ("US electricity demand, all sectors", y0, allsec.loc[y0, "sales_twh"], "TWh"),
        ("US electricity demand, all sectors", y1, allsec.loc[y1, "sales_twh"], "TWh"),
        ("Data-center electricity (LBNL)", 2023, dc_2023, "TWh"),
        ("Data-center share of US load (LBNL)", 2023, lbnl_share, "%"),
        ("Residential retail price", y0, res.loc[y0, "price_cents_per_kwh"], "c/kWh"),
        ("Residential retail price", y1, res.loc[y1, "price_cents_per_kwh"], "c/kWh"),
    ]
    table = pd.DataFrame(rows, columns=["indicator", "year", "value", "unit"])
    table["retrieved"] = RETRIEVED
    table.to_csv(OUTPUT / "energy_linkage.csv", index=False)

    # --- Console report ----------------------------------------------------
    print("=" * 72)
    print("QUESTION 3a — ENERGY / GRID LINKAGE")
    print("=" * 72)
    print(f"US electricity demand: {allsec.loc[y0, 'sales_twh']:,.0f} TWh ({y0}) "
          f"-> {allsec.loc[y1, 'sales_twh']:,.0f} TWh ({y1})")
    print(f"  growth 2007-2020: {growth_0720:+.2f}%/yr (the 'flat' era)")
    print(f"  growth 2020-{y1}: {growth_2025:+.2f}%/yr (the surge)")
    print(f"Data centers, 2023: {dc_2023:.0f} TWh = {lbnl_share:.1f}% of US load (LBNL)")
    print(f"  cross-check vs EIA retail sales: {dc_2023:.0f}/{us_2023:,.0f} "
          f"= {dc_share_check:.1f}% (retail-sales basis; LBNL uses total generation)")
    print("  projected data-center share of US electricity:")
    for yr in (2028, 2030):
        lo = share[(share.year == yr) & (share.scenario == "low")].iloc[0]["value"]
        hi = share[(share.year == yr) & (share.scenario == "high")].iloc[0]["value"]
        print(f"    {yr}: {lo:.1f}% - {hi:.1f}%")
    print(f"Residential electricity price: {res.loc[y0, 'price_cents_per_kwh']:.2f} "
          f"-> {res.loc[y1, 'price_cents_per_kwh']:.2f} c/kWh "
          f"(x{res.loc[y1, 'price_cents_per_kwh'] / res.loc[y0, 'price_cents_per_kwh']:.2f})")
    print("=" * 72)

    # --- Figure 1: US electricity demand -----------------------------------
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(allsec.index, allsec["sales_twh"], marker="o", ms=3, color="#2a6f97", lw=2)
    ax.axvspan(2007, 2020, color="grey", alpha=0.12)
    ax.text(2013.5, allsec["sales_twh"].min() + 30, "~flat, 2007-2020",
            ha="center", fontsize=8, color="grey")
    ax.set_title("US electricity demand, all sectors (EIA retail sales)")
    ax.set_xlabel("Year")
    ax.set_ylabel("TWh")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_us_electricity_demand.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: data-center share of US electricity, actual + projected --
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot([2023], [lbnl_share], marker="o", ms=10, color="#013a63", label="Actual (LBNL)")
    for yr in (2028, 2030):
        lo = share[(share.year == yr) & (share.scenario == "low")].iloc[0]["value"]
        hi = share[(share.year == yr) & (share.scenario == "high")].iloc[0]["value"]
        ax.plot([yr, yr], [lo, hi], color="#e09f3e", lw=8, solid_capstyle="round",
                label="Projected range" if yr == 2028 else None)
        ax.text(yr + 0.15, (lo + hi) / 2, f"{lo:g}-{hi:g}%", fontsize=9, va="center")
    ax.set_title("Data-center electricity as a share of US load")
    ax.set_xlabel("Year")
    ax.set_ylabel("% of US electricity")
    ax.set_xticks([2023, 2028, 2030])
    ax.set_ylim(0, 19)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_datacenter_electricity_share.png", dpi=150)
    plt.close(fig)

    # --- Figure 3: retail electricity prices -------------------------------
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(res.index, res["price_cents_per_kwh"], marker="o", ms=3,
            color="#9d0208", lw=2, label="Residential")
    ax.plot(allsec.index, allsec["price_cents_per_kwh"], marker="o", ms=3,
            color="#2a6f97", lw=2, label="All sectors")
    ax.set_title("US average retail electricity price")
    ax.set_xlabel("Year")
    ax.set_ylabel("cents per kWh (nominal)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_electricity_prices.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/energy_linkage.csv + 3 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
