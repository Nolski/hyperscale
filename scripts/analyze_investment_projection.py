#!/usr/bin/env python3
"""
analyze_investment_projection.py -- Analysis step (Question 2).

Answers "what is the projected coming investment?" two ways:

  METHOD A -- catalogue & compare third-party forecasts (McKinsey, Goldman,
              Morgan Stanley, Bain), harmonised for scope/metric/horizon.
  METHOD B -- an INDEPENDENT bottom-up projection: the 2025 actual seven-
              hyperscaler capital investment grown forward 2026-2030 under
              documented low/mid/high scenarios, with a capacity cross-check.

Method B's scope (7 US hyperscalers, capex + finance leases) is NARROWER than
the third-party global all-operator forecasts -- the comparison is annotated,
not conflated.

Reads   : data/processed/{hyperscaler_capex_annual,investment_forecasts,
          projection_assumptions}.csv
Writes  : output/investment_projection.csv
          output/fig_investment_projection.png   (Method B scenario band)
          output/fig_forecast_comparison.png     (Method A third-party forecasts)

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
SRC = f"Sources: SEC EDGAR (actuals); McKinsey/Goldman/Morgan Stanley/Bain (forecasts). Compiled {RETRIEVED}."
SCENARIOS = ["low", "mid", "high"]
COLORS = {"low": "#5fa8d3", "mid": "#2a6f97", "high": "#013a63"}


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    capex = pd.read_csv(PROCESSED / "hyperscaler_capex_annual.csv")
    forecasts = pd.read_csv(PROCESSED / "investment_forecasts.csv")
    assum = pd.read_csv(PROCESSED / "projection_assumptions.csv")

    # --- Historical actuals, calendar-aligned (NVDA Jan FY-end -> prior year) ---
    end_month = pd.to_datetime(capex["period_end"]).dt.month
    capex["chart_year"] = capex["fiscal_year"].where(end_month != 1, capex["fiscal_year"] - 1)
    actuals = (capex[capex.chart_year <= 2025]
               .groupby("chart_year")["total_capacity_investment_usd"].sum() / BN)
    base_2025 = actuals.loc[2025]

    # --- METHOD B: grow the 2025 base under each scenario ---------------------
    growth = assum[assum.parameter == "yoy_growth_pct"].copy()
    growth["year"] = growth["year"].astype(int)
    proj_rows, cumulative = [], {}
    for sc in SCENARIOS:
        g = growth[growth.scenario == sc].set_index("year")["value"].astype(float)
        value = base_2025
        for year in range(2026, 2031):
            value *= 1 + g.loc[year] / 100
            proj_rows.append({"scenario": sc, "year": year,
                              "annual_capex_usd_bn": round(value, 1)})
        cumulative[sc] = sum(r["annual_capex_usd_bn"] for r in proj_rows
                             if r["scenario"] == sc)

    proj = pd.DataFrame(proj_rows)
    proj["retrieved"] = RETRIEVED
    proj.to_csv(OUTPUT / "investment_projection.csv", index=False)

    # Capacity cross-check: McKinsey base 156 GW global at Goldman's $15M/MW.
    intensity = float(assum.loc[assum.parameter == "capex_intensity_usd_per_mw",
                                "value"].iloc[0])
    capacity_check = 156_000 * intensity / 1000  # 156 GW -> MW -> $bn

    # --- Console report -------------------------------------------------------
    print("=" * 74)
    print("QUESTION 2 — PROJECTED AI INVESTMENT")
    print("=" * 74)
    print("\nMETHOD A — third-party forecasts (global unless noted):")
    for _, r in forecasts.iterrows():
        print(f"  {r['source']:14s} {r['scenario'][:24]:24s} {r['metric']:10s} "
              f"{r['horizon']:10s} ${r['value_usd_billion'] / 1000:5.2f}T")
    print("\nMETHOD B — independent bottom-up, 7 US hyperscalers (capex + leases):")
    print(f"  2025 actual base: ${base_2025:,.0f}B")
    print(f"  {'scenario':9s} {'2026':>8s}{'2027':>8s}{'2028':>8s}{'2029':>8s}"
          f"{'2030':>8s}{'cum 26-30':>12s}")
    for sc in SCENARIOS:
        path = proj[proj.scenario == sc].set_index("year")["annual_capex_usd_bn"]
        cells = "".join(f"{path[y]:8,.0f}" for y in range(2026, 2031))
        print(f"  {sc:9s}{cells}{cumulative[sc]:11,.0f}B")
    print(f"\n  Independent estimate, cumulative 2026-2030 (7 US hyperscalers):")
    print(f"    ${cumulative['low'] / 1000:.1f}T (low) .. "
          f"${cumulative['mid'] / 1000:.1f}T (mid) .. "
          f"${cumulative['high'] / 1000:.1f}T (high)")
    print(f"  Capacity cross-check: McKinsey's 156 GW (base) x ${intensity:.0f}M/MW "
          f"= ${capacity_check / 1000:.1f}T of data-center build cost.")
    print("  NOTE: Method B = 7 US hyperscalers; McKinsey/Goldman = global, all")
    print("  operators, and include chips/power. Method B is a US-hyperscaler")
    print("  SUBSET of those totals — compare with that scope difference in mind.")
    print("=" * 74)

    # --- Figure 1: Method B scenario band -------------------------------------
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    hist = actuals[actuals.index >= 2015]
    ax.plot(hist.index, hist.values, marker="o", color="black", lw=2, label="Actual")
    for sc in SCENARIOS:
        path = proj[proj.scenario == sc].set_index("year")["annual_capex_usd_bn"]
        years = [2025] + list(path.index)
        vals = [base_2025] + list(path.values)
        ax.plot(years, vals, marker="o", ls="--", color=COLORS[sc],
                label=f"{sc.capitalize()} scenario")
    lo = [base_2025] + list(proj[proj.scenario == "low"]["annual_capex_usd_bn"])
    hi = [base_2025] + list(proj[proj.scenario == "high"]["annual_capex_usd_bn"])
    ax.fill_between(range(2025, 2031), lo, hi, color="#2a6f97", alpha=0.12)
    ax.set_title("Independent projection: 7 US hyperscalers' annual capital investment")
    ax.set_xlabel("Year (calendar-aligned)")
    ax.set_ylabel("USD billion")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_investment_projection.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: Method A cumulative third-party forecasts ------------------
    cum = forecasts[forecasts.metric == "cumulative"].copy()
    cum["label"] = cum["source"] + "\n" + cum["scenario"] + "\n(" + cum["horizon"] + ")"
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    bars = ax.bar(cum["label"], cum["value_usd_billion"] / 1000,
                  color=["#2a6f97", "#5fa8d3", "#013a63", "#89c2d9", "#e09f3e"][:len(cum)])
    for b, v in zip(bars, cum["value_usd_billion"] / 1000):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.1, f"${v:.1f}T",
                ha="center", fontsize=9, weight="bold")
    ax.set_ylabel("USD trillion (cumulative)")
    ax.set_title("Method A — third-party cumulative forecasts (global, all operators)")
    ax.tick_params(axis="x", labelsize=7.5)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_forecast_comparison.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/investment_projection.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
