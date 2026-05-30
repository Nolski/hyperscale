#!/usr/bin/env python3
"""
model_cost_stack.py -- Model step (opens the chip-price black box).

Decomposes the FULL deployed lifetime cost of an AI GPU into:
  manufacturing (logic die | HBM memory | packaging | other BOM)  +  vendor GROSS MARGIN
  +  facility/power/cooling capex (allocated per GPU)  +  lifetime electricity (energy).

Two findings this is built to show:
  1. The chip you buy is mostly MARGIN, not manufacturing -- NVIDIA's data-center markup
     (gross margin ~71% blended; higher on H100) means COGS is a small slice of MSRP. HBM
     memory, not the logic die, is the largest real BOM item and the supply bottleneck.
  2. That markup is WHY operating energy looked like only ~10% of chip-level TCO: the MSRP
     is inflated by scarcity/margin. At the full DEPLOYED level (adding facility + cooling +
     lifetime energy), power-related cost is a larger combined share -- but the vendor margin
     still dominates the stack.

Reads : data/raw/manual/cost_stack.csv, data/processed/gpu_specs.csv,
        data/raw/manual/pue_assumptions.csv, data/processed/us_electricity.csv,
        data/processed/chip_margins.csv (vendor margin context)
Writes: output/cost_stack.csv
        output/fig_cost_stack.png
        output/fig_cost_stack_shares.png

Caveats: BOM numbers are Tier-2 analyst ESTIMATES (verified=false); facility $/MW is an
assumption with wide range; product-level margin (msrp - COGS) exceeds the blended company
margin. Direction and proportions, not precision. See notes/methodology_hardware_economics.md.

Re-runnable: reads data/processed/ + manual, overwrites output/. No network.
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
SRC = f"Sources: BOM analyst estimates (Tier-2), SEC EDGAR margins, EIA power. Compiled {RETRIEVED}."

PUE_SCENARIO = "hyperscaler_modern"
LIFE_YEARS = 5
# Facility power+cooling+shell build cost, EXCLUDING the GPU servers themselves. Wide range
# in industry reporting (~$7-12M per MW of IT power); midpoint, flagged assumption.
FACILITY_USD_PER_MW = 9_000_000

STACK = ["die_cost_usd", "hbm_cost_usd", "packaging_cost_usd", "other_bom_usd",
         "vendor_margin_usd", "facility_cooling_usd", "lifetime_energy_usd"]
LABELS = {"die_cost_usd": "Logic die", "hbm_cost_usd": "HBM memory",
          "packaging_cost_usd": "Packaging (CoWoS)", "other_bom_usd": "Other BOM",
          "vendor_margin_usd": "Vendor gross margin", "facility_cooling_usd": "Facility+cooling capex",
          "lifetime_energy_usd": "Lifetime electricity"}
COLORS = {"die_cost_usd": "#1d3557", "hbm_cost_usd": "#457b9d",
          "packaging_cost_usd": "#a8dadc", "other_bom_usd": "#cbd5e1",
          "vendor_margin_usd": "#c1121f", "facility_cooling_usd": "#8d99ae",
          "lifetime_energy_usd": "#e09f3e"}


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.8, color="grey")


def industrial_price() -> float:
    el = pd.read_csv(PROCESSED / "us_electricity.csv")
    ind = el[el["sector"].str.contains("industrial", case=False)].sort_values("year").iloc[-1]
    return float(ind["price_cents_per_kwh"]) / 100.0


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cs = pd.read_csv(MANUAL / "cost_stack.csv", comment="#")
    specs = pd.read_csv(PROCESSED / "gpu_specs.csv").set_index("model")
    assum = pd.read_csv(MANUAL / "pue_assumptions.csv", comment="#")
    assum = assum[assum["scenario"] == PUE_SCENARIO].iloc[0]
    price = industrial_price()
    oh, pue, util, hrs = (assum["system_overhead_factor"], assum["pue"],
                          assum["utilization"], assum["hours_per_year"])

    cs["cogs_usd"] = cs[["die_cost_usd", "hbm_cost_usd", "packaging_cost_usd",
                         "other_bom_usd"]].sum(axis=1)
    cs["vendor_margin_usd"] = cs["msrp_usd"] - cs["cogs_usd"]
    # Per-GPU facility/cooling capex and lifetime energy from system power.
    cs["system_power_kw"] = cs["chip"].map(lambda m: specs.loc[m, "tdp_watts"]) / 1000 * oh * pue
    cs["facility_cooling_usd"] = cs["system_power_kw"] / 1000 * FACILITY_USD_PER_MW
    cs["lifetime_energy_usd"] = cs["system_power_kw"] * hrs * util * price * LIFE_YEARS
    cs["total_deployed_usd"] = cs[STACK].sum(axis=1)

    out = cs[["chip", "msrp_usd", "cogs_usd"] + STACK + ["total_deployed_usd"]].copy()
    out["facility_usd_per_mw"] = FACILITY_USD_PER_MW
    out["life_years"] = LIFE_YEARS
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "cost_stack.csv", index=False)

    # vendor margin context from SEC
    try:
        cm = pd.read_csv(PROCESSED / "chip_margins.csv")
        nv = cm[cm.ticker == "NVDA"].sort_values("period_end").iloc[-1]["gross_margin"]
        margin_ctx = f"(NVIDIA blended gross margin {nv*100:.0f}% per SEC EDGAR; product margin higher)"
    except Exception:
        margin_ctx = ""

    # --- Console report ---
    print("=" * 90)
    print(f"GPU COST STACK — full deployed {LIFE_YEARS}-yr cost {margin_ctx}")
    print("=" * 90)
    for _, r in cs.iterrows():
        print(f"\n  {r['chip']}  (MSRP ${r['msrp_usd']/1e3:.0f}k, est. COGS ${r['cogs_usd']/1e3:.1f}k "
              f"-> product margin {r['vendor_margin_usd']/r['msrp_usd']*100:.0f}% of price)")
        for k in STACK:
            share = r[k] / r["total_deployed_usd"] * 100
            print(f"      {LABELS[k]:24s} ${r[k]/1e3:6.1f}k  {share:5.1f}%")
        print(f"      {'TOTAL deployed':24s} ${r['total_deployed_usd']/1e3:6.1f}k")
    print("-" * 90)
    h = cs[cs.chip == "H100 SXM5"].iloc[0]
    en = h["lifetime_energy_usd"] / h["total_deployed_usd"] * 100
    mg = h["vendor_margin_usd"] / h["total_deployed_usd"] * 100
    hbm = h["hbm_cost_usd"] / h["cogs_usd"] * 100
    print(f"  Reading (H100): vendor MARGIN is ~{mg:.0f}% of the full deployed stack; lifetime")
    print(f"  electricity ~{en:.0f}%. HBM memory is ~{hbm:.0f}% of real manufacturing COGS — the")
    print(f"  logic die is not the costly part. Energy 'looks small' because the MSRP is mostly")
    print(f"  MARGIN (scarcity/pricing power); price it at COGS and energy's share would multiply.")
    print("=" * 90)

    chips = list(cs["chip"])
    short = [c.replace(" SXM5", "").replace(" SXM 80GB", "") for c in chips]

    # --- Figure 1: absolute stacked cost ($k) ---
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    bottom = [0.0] * len(cs)
    for k in STACK:
        vals = (cs[k] / 1e3).tolist()
        ax.bar(short, vals, bottom=bottom, label=LABELS[k], color=COLORS[k])
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_ylabel(f"Full deployed {LIFE_YEARS}-yr cost (USD thousands)")
    ax.set_title("What a deployed AI GPU actually costs — vendor margin dwarfs everything")
    ax.legend(fontsize=8, ncol=2)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_cost_stack.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: 100% shares ---
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    bottom = [0.0] * len(cs)
    for k in STACK:
        vals = (cs[k] / cs["total_deployed_usd"] * 100).tolist()
        ax.bar(short, vals, bottom=bottom, label=LABELS[k], color=COLORS[k])
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_ylabel("Share of full deployed cost (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Cost stack as shares — why operating energy 'looks small' next to margin")
    ax.legend(fontsize=8, ncol=2)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_cost_stack_shares.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/cost_stack.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
