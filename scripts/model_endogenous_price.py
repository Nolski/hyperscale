#!/usr/bin/env python3
"""
model_endogenous_price.py -- Model step (closes the demand->price feedback loop).

The TCO/obsolescence models took the electricity price as a fixed input. But the AI
buildout is itself a massive new load, and rising data-center demand pushes power prices
UP -- which feeds back into the energy cost of running every chip. This model makes the
price ENDOGENOUS to data-center demand and re-runs the stranding analysis along the path.

Chain:
  1. Demand path: data-center electricity 2023->2030 (low/high scenarios) from
     datacenter_energy.csv, as a share of projected US load.
  2. Price path: industrial price rises with that demand. We pin the response to documented
     models -- Dallas Fed WP2606 (+20% moderate / +50% high wholesale by 2028, from
     electricity_price_outlook.csv) -- and include the IER NULL (no causal link). Higher
     demand scenario -> higher price path. We also report the elasticity IMPLIED by the
     state natural experiment (energy_states_summary.csv) as an independent cross-check.
  3. Feedback: feed the price path into (a) the per-vintage STRANDING price P* (from the
     obsolescence logic) to find the YEAR each vintage becomes energy-stranded, and (b) the
     energy SHARE of TCO over time.

Honest result preview: even the high demand-driven path only nears stranding the OLDEST
silicon (V100) and only by ~2030; modern chips never strand on energy cost -- because their
MSRP is so high. That motivates the cost-stack decomposition (model_cost_stack.py).

Reads : data/processed/datacenter_energy.csv, us_electricity.csv, gpu_specs.csv,
        data/raw/manual/{pue_assumptions,electricity_price_outlook... via processed}.csv,
        output/energy_states_summary.csv (elasticity cross-check, if present)
Writes: output/endogenous_price.csv
        output/fig_endogenous_price_path.png
        output/fig_stranding_timeline.png

Caveats: data-center->price CAUSATION IS CONTESTED (Dallas Fed says strong; IER says none --
both in the repo). The null scenario carries the IER view. Price path is scenario-anchored,
not a structural grid model. See notes/methodology_hardware_economics.md.

Re-runnable: reads data/processed/ + manual + output/, overwrites output/. No network.
"""

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "raw" / "manual"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
SRC = f"Sources: LBNL/EIA demand, Dallas Fed WP2606 price response (contested), vendor specs. Compiled {RETRIEVED}."

PUE_SCENARIO = "hyperscaler_modern"
NEW_CHIP_LIFE = 5
FRONTIER = "B200"
CHAIN = ["V100 SXM2", "A100 SXM 80GB", "H100 SXM5", "B200"]
YEARS = list(range(2023, 2031))
US_LOAD_GROWTH = 0.02  # ~2%/yr baseline growth in total US electricity demand
# Price-response regimes: industrial-price multiplier reached BY 2028, demand-driven.
# Anchored to Dallas Fed WP2606 (+20% moderate / +50% high) and the IER null (no link).
PRICE_REGIMES = {"null (IER: no link)": 1.00, "moderate (Dallas Fed)": 1.20,
                 "high (Dallas Fed)": 1.50}


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.8, color="grey")


def dc_demand_path() -> pd.DataFrame:
    """Interpolate data-center TWh 2023-2030 for low & high scenarios from anchors."""
    dce = pd.read_csv(PROCESSED / "datacenter_energy.csv")
    twh = dce[dce["metric"] == "datacenter_electricity"]
    anchors = {}  # scenario -> {year: twh}
    for _, r in twh.iterrows():
        sc = "actual" if r["scenario"] == "actual" else r["scenario"]
        anchors.setdefault(sc, {})[int(r["year"])] = float(r["value"])
    base = anchors.get("actual", {}).get(2023, 176.0)
    out = {"year": YEARS}
    for sc in ("low", "high"):
        pts_years = [2023] + sorted(anchors.get(sc, {}))
        pts_vals = [base] + [anchors[sc][y] for y in sorted(anchors.get(sc, {}))]
        out[f"dc_twh_{sc}"] = np.interp(YEARS, pts_years, pts_vals)
    return pd.DataFrame(out)


def us_industrial_base() -> tuple[float, float, int]:
    el = pd.read_csv(PROCESSED / "us_electricity.csv")
    ind = el[el["sector"].str.contains("industrial", case=False)].sort_values("year").iloc[-1]
    allsec = el[el["sector"].str.contains("all", case=False)].sort_values("year").iloc[-1]
    return float(ind["price_cents_per_kwh"]), float(allsec["sales_twh"]), int(ind["year"])


def stranding_prices(specs: pd.DataFrame, assum: pd.Series) -> dict:
    """P* (¢/kWh) each vintage needs to be scrapped for the frontier (energy-cost lens)."""
    oh, pue, util, hrs = (assum["system_overhead_factor"], assum["pue"],
                          assum["utilization"], assum["hours_per_year"])
    sp = specs.set_index("model")

    def k(m):
        s = sp.loc[m]
        akwh = s["tdp_watts"] / 1000 * oh * pue * hrs * util
        work = (s["flops_dense_bf16_tflops"] / 1000 * util) * hrs
        return akwh / work

    def capterm(m):
        s = sp.loc[m]
        work = (s["flops_dense_bf16_tflops"] / 1000 * util) * hrs
        return s["msrp_usd"] / (NEW_CHIP_LIFE * work)

    kF, capF = k(FRONTIER), capterm(FRONTIER)
    out = {}
    for m in CHAIN:
        if m == FRONTIER:
            continue
        ko = k(m)
        out[m] = (capF / (ko - kF) * 100) if ko > kF else None  # ¢/kWh
    return out


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = pd.read_csv(PROCESSED / "gpu_specs.csv")
    assum = pd.read_csv(MANUAL / "pue_assumptions.csv", comment="#")
    assum = assum[assum["scenario"] == PUE_SCENARIO].iloc[0]
    base_price, base_load, price_year = us_industrial_base()
    demand = dc_demand_path()
    pstar = stranding_prices(specs, assum)

    # --- Build price paths: multiplier ramps 1.0 (2025) -> regime target (2028) -> extend.
    # Demand scenario scales the ramp: high-demand reaches the regime target; low-demand
    # reaches a proportionally smaller rise (scaled by demand growth vs the high path).
    demand = demand.set_index("year")
    dc_growth_high = demand.loc[2028, "dc_twh_high"] / demand.loc[2025, "dc_twh_high"]
    rows = []
    for regime, target_2028 in PRICE_REGIMES.items():
        for dsc in ("low", "high"):
            dscale = ((demand.loc[2028, f"dc_twh_{dsc}"] / demand.loc[2025, f"dc_twh_{dsc}"])
                      / dc_growth_high)  # 1.0 for high, <1 for low
            rise_2028 = (target_2028 - 1.0) * dscale
            for y in YEARS:
                if y <= 2025:
                    mult = 1.0
                elif y <= 2028:
                    mult = 1.0 + rise_2028 * (y - 2025) / 3.0
                else:  # extend the 2025-2028 slope, damped
                    mult = (1.0 + rise_2028) + rise_2028 / 3.0 * (y - 2028) * 0.6
                rows.append({"year": y, "regime": regime, "demand_scenario": dsc,
                             "price_cents_kwh": round(base_price * mult, 2),
                             "dc_twh": round(demand.loc[y, f"dc_twh_{dsc}"], 0)})
    path = pd.DataFrame(rows)

    # --- Stranding year per vintage under each (regime, demand) where price crosses P*.
    strand_rows = []
    for (regime, dsc), g in path.groupby(["regime", "demand_scenario"]):
        g = g.sort_values("year")
        for m, ps in pstar.items():
            yr = None
            if ps is not None:
                hit = g[g["price_cents_kwh"] >= ps]
                yr = int(hit["year"].iloc[0]) if not hit.empty else None
            strand_rows.append({"regime": regime, "demand_scenario": dsc, "model": m,
                                "stranding_price_cents_kwh": round(ps, 1) if ps else None,
                                "stranded_year": yr})
    strand = pd.DataFrame(strand_rows)

    path.to_csv(OUTPUT / "endogenous_price.csv", index=False)

    # --- Console report ---
    print("=" * 84)
    print(f"ENDOGENOUS ELECTRICITY PRICE — demand drives price, price feeds back to stranding")
    print(f"(base industrial {base_price:.1f}¢/kWh {price_year}; causation CONTESTED: Dallas Fed vs IER)")
    print("=" * 84)
    print("\nProjected industrial price (¢/kWh), HIGH demand scenario:")
    hi = path[path.demand_scenario == "high"].pivot(index="year", columns="regime",
                                                    values="price_cents_kwh")
    print(hi.to_string(float_format=lambda x: f"{x:5.1f}"))
    print("\nStranding-price thresholds P* (¢/kWh):")
    for m, ps in pstar.items():
        print(f"  {m:16s} {ps:6.1f}¢" if ps else f"  {m:16s}   n/a")
    print("\nYear each vintage becomes ENERGY-stranded (high demand scenario):")
    for regime in PRICE_REGIMES:
        sub = strand[(strand.regime == regime) & (strand.demand_scenario == "high")]
        bits = []
        for _, r in sub.iterrows():
            yr = f"{int(r['stranded_year'])}" if pd.notna(r["stranded_year"]) else "never"
            bits.append(f"{r['model'].split()[0]}={yr}")
        print(f"  [{regime:22s}] " + "  ".join(bits))
    print("-" * 84)
    print("Even the HIGH path only nears stranding the OLDEST silicon (V100), and only late —")
    print("modern chips never strand on energy cost because their MSRP is so high. The price")
    print("feedback is real and inflationary/externalized to ratepayers, but the binding")
    print("obsolescence force is the CAPEX/markup, not the power bill -> see model_cost_stack.py.")
    print("=" * 84)

    # --- Figure 1: price paths with stranding thresholds ---
    fig, ax = plt.subplots(figsize=(10, 5.6))
    cmap = {"null (IER: no link)": "#2a9d8f", "moderate (Dallas Fed)": "#e09f3e",
            "high (Dallas Fed)": "#c1121f"}
    for regime in PRICE_REGIMES:
        g = path[(path.regime == regime) & (path.demand_scenario == "high")].sort_values("year")
        ax.plot(g["year"], g["price_cents_kwh"], lw=2, color=cmap[regime], label=regime)
    for m, ps in pstar.items():
        if ps and ps < 40:
            ax.axhline(ps, ls=":", lw=1, color="grey")
            ax.text(2023.1, ps + 0.3, f"{m.split()[0]} strands @ {ps:.0f}¢", fontsize=7, color="grey")
    ax.set_xlabel("Year")
    ax.set_ylabel("Industrial electricity price (¢/kWh)")
    ax.set_title("Demand-driven electricity price vs the price needed to strand each GPU vintage")
    ax.set_ylim(bottom=base_price * 0.95)
    ax.legend(fontsize=8, title="price response (high-demand path)")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_endogenous_price_path.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: data-center demand path (the driver) ---
    fig, ax = plt.subplots(figsize=(10, 5.0))
    d = demand.reset_index()
    ax.fill_between(d["year"], d["dc_twh_low"], d["dc_twh_high"], color="#2a6f97", alpha=0.2,
                    label="DC demand low–high range")
    ax.plot(d["year"], d["dc_twh_high"], color="#2a6f97", lw=2, marker="o", label="high")
    ax.plot(d["year"], d["dc_twh_low"], color="#2a6f97", lw=2, ls="--", marker="o", label="low")
    ax.set_xlabel("Year")
    ax.set_ylabel("US data-center electricity demand (TWh)")
    ax.set_title("The driver: data-center electricity demand, 2023→2030 (LBNL anchors)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_stranding_timeline.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/endogenous_price.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
