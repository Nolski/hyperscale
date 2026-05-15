#!/usr/bin/env python3
"""
analyze_energy_states.py -- Analysis step (Question 3a, state-level energy).

Takes the energy linkage below the national headline: where data-center load
concentrates, and whether electricity in data-center-heavy states behaves
differently from the rest.

The price comparison is deliberately honest. Whether data centers *cause* local
price rises is contested -- the Dallas Fed's dispatch model says yes; the
Institute for Energy Research finds no significant relationship. This script
just reports what the state series show; the report presents both sides.

Reads   : data/processed/us_electricity_by_state.csv
          data/raw/manual/datacenter_energy_states.csv
Writes  : output/energy_states_summary.csv
          output/fig_datacenter_load_by_state.png
          output/fig_state_price_trends.png

Re-runnable: reads data/, overwrites output/. No network.
"""

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "raw" / "manual"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
SRC = f"Sources: EIA API v2 (state retail sales/price); LBNL/EPRI (data-center load). Compiled {RETRIEVED}."

# States the manual data identifies as major data-center hubs.
DC_HEAVY = {"VA", "TX", "IL", "CA", "OR"}
BASE_YEAR, RECENT_FROM, RECENT_TO = 2010, 2020, 2025


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    elec = pd.read_csv(PROCESSED / "us_electricity_by_state.csv")
    dc = pd.read_csv(MANUAL / "datacenter_energy_states.csv", comment="#")

    states = elec[elec.stateid != "US"].copy()
    res = states[states.sector == "residential"]
    alls = states[states.sector == "all sectors"]

    # --- % change helper, per state, over a window ------------------------
    def pct_change(frame, col, y0, y1):
        a = frame[frame.year == y0].set_index("stateid")[col]
        b = frame[frame.year == y1].set_index("stateid")[col]
        return ((b - a) / a * 100).dropna()

    price_chg = pct_change(res, "price_cents_per_kwh", RECENT_FROM, RECENT_TO)
    cons_chg = pct_change(alls, "sales_twh", RECENT_FROM, RECENT_TO)

    def group_means(series):
        heavy = series[series.index.isin(DC_HEAVY)].mean()
        rest = series[~series.index.isin(DC_HEAVY)].mean()
        return heavy, rest

    p_heavy, p_rest = group_means(price_chg)
    c_heavy, c_rest = group_means(cons_chg)
    va_cons = cons_chg.get("VA", float("nan"))

    # --- Summary table -----------------------------------------------------
    rows = [
        ("Residential price change, data-center-heavy states", round(p_heavy, 1), "%"),
        ("Residential price change, other states", round(p_rest, 1), "%"),
        ("Electricity consumption change, data-center-heavy states", round(c_heavy, 1), "%"),
        ("Electricity consumption change, other states", round(c_rest, 1), "%"),
        ("Electricity consumption change, Virginia", round(va_cons, 1), "%"),
    ]
    summary = pd.DataFrame(rows, columns=["indicator", "value", "unit"])
    summary["window"] = f"{RECENT_FROM}-{RECENT_TO}"
    summary["retrieved"] = RETRIEVED
    summary.to_csv(OUTPUT / "energy_states_summary.csv", index=False)

    # --- Console report ----------------------------------------------------
    print("=" * 72)
    print("QUESTION 3a (state level) — WHERE THE LOAD LANDS")
    print("=" * 72)
    print("Data-center electricity by state (2023, approx., LBNL/EPRI):")
    for _, r in dc.sort_values("datacenter_twh", ascending=False).iterrows():
        sh = f"  ~{r['share_of_state_electricity_pct']:.0f}% of state load" \
            if pd.notna(r["share_of_state_electricity_pct"]) else ""
        print(f"  {r['state']:14s} {r['datacenter_twh']:5.0f} TWh{sh}")
    print(f"\nState trends, {RECENT_FROM}-{RECENT_TO} (mean across states):")
    print(f"  electricity consumption — DC-heavy {c_heavy:+.1f}% vs other {c_rest:+.1f}%")
    print(f"    Virginia alone: {va_cons:+.1f}%")
    print(f"  residential price    — DC-heavy {p_heavy:+.1f}% vs other {p_rest:+.1f}%")
    print("  NOTE: consumption clearly diverges; the price comparison is muddier —")
    print("  state price levels are driven by policy and fuel mix, not load alone.")
    print("  Whether data centers raise local prices stays genuinely contested.")
    print("=" * 72)

    # --- Figure 1: data-center load by state -------------------------------
    dcs = dc.sort_values("datacenter_twh", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.barh(dcs["state"], dcs["datacenter_twh"], color="#2a6f97", height=0.62)
    for i, v in enumerate(dcs["datacenter_twh"]):
        ax.text(v + 0.6, i, f"{v:.0f} TWh", va="center", fontsize=9, weight="bold")
    ax.set_xlabel("Data-center electricity, 2023 (TWh, approx.)")
    ax.set_title("Data-center electricity is geographically concentrated")
    caption(ax)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / "fig_datacenter_load_by_state.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: residential price trajectory, DC-heavy vs rest ----------
    res_idx = res.pivot_table(index="year", columns="stateid",
                              values="price_cents_per_kwh")
    res_idx = res_idx / res_idx.loc[BASE_YEAR] * 100        # index each state to 2010
    heavy_cols = [c for c in res_idx.columns if c in DC_HEAVY]
    rest_cols = [c for c in res_idx.columns if c not in DC_HEAVY]
    heavy_line = res_idx[heavy_cols].mean(axis=1)
    rest_line = res_idx[rest_cols].mean(axis=1)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(heavy_line.index, heavy_line, color="#a4262c", lw=2.4,
            label="Data-center-heavy states")
    ax.plot(rest_line.index, rest_line, color="#2a6f97", lw=2.4, label="Other states")
    ax.set_title(f"Residential electricity price, indexed to {BASE_YEAR} = 100")
    ax.set_ylabel(f"Index ({BASE_YEAR} = 100)")
    ax.set_xlabel("Year")
    ax.legend(fontsize=8.5, frameon=False)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / "fig_state_price_trends.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/energy_states_summary.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
