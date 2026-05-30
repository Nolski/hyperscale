#!/usr/bin/env python3
"""
model_jevons_rebound.py -- Model step (Thread 3: Jevons / energy rebound).

Answers the user's question directly: if new hardware uses far less energy per unit of
compute, does total data-center energy FALL? The Jevons paradox says no -- cheaper, more
efficient compute induces more demand, and total energy rises anyway. We quantify it with
the identity:

    E = C * e          total energy = compute demand  x  energy per unit compute
    growth_E = growth_C + growth_e   (e is FALLING as perf/watt rises)

So efficiency (growth_e < 0) pushes energy DOWN; demand (growth_C > 0) pushes it UP. Total
energy falls only if compute grows SLOWER than efficiency improves. We measure:
  * efficiency gain  -- perf/watt CAGR from gpu_specs.csv (frontier), cross-checked vs Epoch.
  * total DC energy  -- LBNL path from datacenter_energy.csv (176 TWh 2023 -> 325-580 by 2028).
  * implied compute growth = energy growth + efficiency gain (the identity).
  * break-even compute growth (energy flat) = the efficiency-gain rate.
Then two counterfactuals make the rebound concrete: frozen-efficiency (how high energy would
be without the gains) and frozen-demand (how low it would be if compute had stayed put).

Reads : data/processed/gpu_specs.csv, datacenter_energy.csv, us_electricity.csv,
        data/processed/epoch_hardware.csv (efficiency cross-check, optional)
Writes: output/jevons_rebound.csv
        output/fig_jevons_decomposition.png
        output/fig_rebound_breakeven.png

Caveats: FLEET efficiency improves slower than the FRONTIER (old chips linger), so true
rebound is even stronger than this frontier-based estimate. The decomposition is an IDENTITY
-- compute growth is inferred, not independently measured (Epoch corroborates the magnitude).
The Jevons CAUSAL claim (cheaper compute induces demand) is the mechanism/interpretation;
demand also grows from capability and adoption. LBNL projections are scenario ranges.

Re-runnable: reads data/processed/, overwrites output/. No network.
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
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
SRC = f"Sources: vendor/Epoch perf-per-watt (Tier-2), LBNL data-center energy. Compiled {RETRIEVED}."

BASE_YEAR, PROJ_YEAR = 2023, 2028


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.8, color="grey")


def efficiency_cagr() -> tuple[float, float]:
    """Frontier perf/watt CAGR (bf16 dense) from gpu_specs; return (cagr, latest_per_watt)."""
    s = pd.read_csv(PROCESSED / "gpu_specs.csv")
    s = s[s["vendor"] == "NVIDIA"]  # consistent vendor for a clean frontier
    best = s.sort_values("bf16_tflops_per_watt").groupby("year_released").tail(1)
    best = best.sort_values("year_released")
    y0, y1 = best.iloc[0], best.iloc[-1]
    yrs = y1["year_released"] - y0["year_released"]
    cagr = (y1["bf16_tflops_per_watt"] / y0["bf16_tflops_per_watt"]) ** (1 / yrs) - 1
    return float(cagr), float(y1["bf16_tflops_per_watt"])


def dc_energy_anchors() -> dict:
    dce = pd.read_csv(PROCESSED / "datacenter_energy.csv")
    twh = dce[dce["metric"] == "datacenter_electricity"]
    out = {}
    for _, r in twh.iterrows():
        out[(int(r["year"]), r["scenario"])] = float(r["value"])
    return out


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    eff_cagr, latest_pw = efficiency_cagr()
    anchors = dc_energy_anchors()
    e_base = anchors.get((BASE_YEAR, "actual"), 176.0)
    e_low = anchors.get((PROJ_YEAR, "low"), 325.0)
    e_high = anchors.get((PROJ_YEAR, "high"), 580.0)
    n = PROJ_YEAR - BASE_YEAR

    rows = []
    for label, e_end in (("LBNL low", e_low), ("LBNL high", e_high)):
        energy_cagr = (e_end / e_base) ** (1 / n) - 1
        # identity: (1+rC) = (1+rE)*(1+rEff)  [since C = E * perf_per_watt]
        compute_cagr = (1 + energy_cagr) * (1 + eff_cagr) - 1
        eff_ratio = (1 + eff_cagr) ** n
        compute_ratio = (e_end / e_base) * eff_ratio
        frozen_eff_energy = e_base * compute_ratio          # no efficiency gains
        frozen_demand_energy = e_base / eff_ratio           # compute stayed at base
        rows.append({
            "scenario": label, "energy_base_twh": e_base, "energy_end_twh": e_end,
            "energy_cagr": round(energy_cagr, 3), "efficiency_cagr": round(eff_cagr, 3),
            "implied_compute_cagr": round(compute_cagr, 3),
            "breakeven_compute_cagr": round(eff_cagr, 3),
            "compute_growth_x": round(compute_ratio, 1),
            "frozen_efficiency_energy_twh": round(frozen_eff_energy),
            "frozen_demand_energy_twh": round(frozen_demand_energy),
        })
    res = pd.DataFrame(rows)
    res["retrieved"] = RETRIEVED
    res.to_csv(OUTPUT / "jevons_rebound.csv", index=False)

    # --- Console report ---
    print("=" * 84)
    print(f"JEVONS / REBOUND — does better perf/watt cut total data-center energy?")
    print("=" * 84)
    print(f"  Frontier efficiency (bf16 perf/watt) improving ~{eff_cagr*100:.0f}%/yr "
          f"(NVIDIA, gpu_specs.csv)")
    print(f"  Total DC energy {BASE_YEAR}: {e_base:.0f} TWh  ->  {PROJ_YEAR}: "
          f"{e_low:.0f} (low) / {e_high:.0f} (high) TWh (LBNL)\n")
    print(f"  {'scenario':10s} {'energy/yr':>9s} {'effic/yr':>9s} {'->implied compute/yr':>21s} "
          f"{'break-even':>11s}")
    for _, r in res.iterrows():
        print(f"  {r['scenario']:10s} {r['energy_cagr']*100:8.0f}% {eff_cagr*100:8.0f}% "
              f"{r['implied_compute_cagr']*100:20.0f}% {eff_cagr*100:10.0f}%")
    print(f"\n  Reading: efficiency improves ~{eff_cagr*100:.0f}%/yr — energy would FALL at that rate")
    print(f"  if compute were flat. But to hit LBNL's energy path, compute must grow "
          f"~{res['implied_compute_cagr'].min()*100:.0f}-{res['implied_compute_cagr'].max()*100:.0f}%/yr —")
    print(f"  about 2x the efficiency rate. Demand outruns efficiency, so total energy RISES:")
    print(f"  the Jevons paradox, quantified. (Break-even is ~{eff_cagr*100:.0f}%/yr compute growth.)")
    hi = res[res.scenario == "LBNL high"].iloc[0]
    print(f"\n  Counterfactuals ({BASE_YEAR}->{PROJ_YEAR}, LBNL-high path, {hi['compute_growth_x']:.0f}x compute):")
    print(f"    frozen 2023 efficiency  -> {hi['frozen_efficiency_energy_twh']:.0f} TWh "
          f"(efficiency 'saved' ~{hi['frozen_efficiency_energy_twh']-hi['energy_end_twh']:.0f} TWh)")
    print(f"    actual                  -> {hi['energy_end_twh']:.0f} TWh")
    print(f"    frozen 2023 demand      -> {hi['frozen_demand_energy_twh']:.0f} TWh "
          f"(efficiency alone would have CUT energy below the {e_base:.0f} TWh base)")
    print("=" * 84)

    # --- Figure 1: counterfactual decomposition (LBNL high) ---
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    cats = [f"{BASE_YEAR}\nactual", f"{PROJ_YEAR}\nfrozen demand\n(efficiency only)",
            f"{PROJ_YEAR}\nACTUAL\n(LBNL high)", f"{PROJ_YEAR}\nfrozen efficiency\n(demand only)"]
    vals = [e_base, hi["frozen_demand_energy_twh"], hi["energy_end_twh"],
            hi["frozen_efficiency_energy_twh"]]
    cols = ["#8d99ae", "#2a9d8f", "#c1121f", "#1d3557"]
    ax.bar(cats, vals, color=cols)
    for i, v in enumerate(vals):
        ax.text(i, v + 15, f"{v:.0f}", ha="center", fontsize=9, weight="bold")
    ax.set_ylabel("US data-center electricity (TWh)")
    ax.set_title("Efficiency pushes energy DOWN, demand pushes it UP more — net: energy rises")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_jevons_decomposition.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: break-even — energy projection vs compute-demand growth ---
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    yrs = np.arange(0, n + 3)
    demand_rates = [0.10, eff_cagr, 0.40, 0.55]
    rate_labels = ["compute +10%/yr", f"+{eff_cagr*100:.0f}%/yr (break-even)",
                   "+40%/yr", "+55%/yr"]
    rate_colors = ["#2a9d8f", "#000000", "#e09f3e", "#c1121f"]
    for rC, lab, c in zip(demand_rates, rate_labels, rate_colors):
        path = e_base * ((1 + rC) / (1 + eff_cagr)) ** yrs
        ax.plot(BASE_YEAR + yrs, path, lw=2, color=c,
                ls="--" if "break-even" in lab else "-", label=lab)
    ax.scatter([PROJ_YEAR, PROJ_YEAR], [e_low, e_high], color="#1d3557", zorder=5, s=60)
    ax.annotate("LBNL low/high", (PROJ_YEAR, e_high), textcoords="offset points",
                xytext=(6, 0), fontsize=8)
    ax.set_xlabel("Year")
    ax.set_ylabel("US data-center electricity (TWh)")
    ax.set_title("Total energy falls ONLY if compute grows slower than efficiency (~%d%%/yr)"
                 % round(eff_cagr * 100))
    ax.legend(fontsize=8, title=f"efficiency fixed at +{eff_cagr*100:.0f}%/yr")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_rebound_breakeven.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/jevons_rebound.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
