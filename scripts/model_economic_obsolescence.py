#!/usr/bin/env python3
"""
model_economic_obsolescence.py -- Model step (the depreciation <-> energy headline).

Tests whether energy economics make a GPU's ECONOMIC life shorter than the 6-year
ACCOUNTING life. The honest answer is two-sided, and the model reports both lenses:

LENS A -- ENERGY COST. An old chip is worth scrapping for a newer one only when the old
chip's ENERGY-ONLY cost per unit compute exceeds the new chip's ALL-IN cost (capex sunk on
the old one). Solving that for the electricity price gives a STRANDING PRICE P* per vintage:

    energy_only(old) = k_old * P_elec ;  all_in(new) = capex_term(new) + k_new * P_elec
    P*  =  capex_term(new) / (k_old - k_new)      (k = system_power / annual_compute)

FINDING: at US industrial power (~9c/kWh), P* for modern chips is enormous (H100 ~ $1.00/kWh)
-- they are FAR too efficient relative to their capex to be stranded by energy cost. Only
OLD, inefficient silicon (V100 ~13c, A100 ~32c) strands at reachable prices. So energy COST
alone does NOT condemn the 6-year life for current hardware; cheap power keeps old chips
worth running. (China's even-cheaper power makes stranding still less likely there -- ties
to the China thread.)

LENS B -- POWER CAPACITY. Data-center power (MW) and space are the binding constraint, not
the energy bill. Each generation delivers far more compute PER WATT, so under a fixed MW
budget the OPPORTUNITY COST of running old silicon is large -- which drives ~generational
(2-3yr) refresh regardless of how cheap energy is. THIS, not energy cost, is the real
obsolescence pressure -- and it is an opportunity cost, not a cash expense, so it does not
translate cleanly into a depreciation number.

Reads : data/processed/gpu_specs.csv, data/raw/manual/pue_assumptions.csv,
        data/processed/us_electricity.csv, data/processed/hyperscaler_capex_annual.csv
Writes: output/economic_obsolescence.csv
        output/fig_stranding_price.png
        output/fig_compute_per_watt.png
        output/fig_scrap_frontier.png

Caveats: peak-FLOPS throughput proxy; economic (not failure) retirement; the Lens-B
earnings figure is conditional & illustrative. See notes/methodology_hardware_economics.md.

Re-runnable: reads data/processed/ + manual, overwrites output/. No network.
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
SRC = f"Sources: vendor specs (Tier-2), EIA industrial price, Dallas Fed scenarios. Compiled {RETRIEVED}."

PUE_SCENARIO = "hyperscaler_modern"
NEW_CHIP_LIFE = 5
ACCOUNTING_LIFE = 6
FRONTIER = "B200"
CHAIN = ["V100 SXM2", "A100 SXM 80GB", "H100 SXM5", "H200 SXM", "B200"]
# Price reference lines (multipliers on current industrial); +20/+50% = Dallas Fed WP2606
# 2028 range (data/raw/manual/electricity_price_outlook.csv).
PRICE_LINES = {"current": 1.0, "+20%": 1.2, "+50%": 1.5}


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def industrial_price_usd_per_kwh() -> tuple[float, int]:
    el = pd.read_csv(PROCESSED / "us_electricity.csv")
    ind = el[el["sector"].str.contains("industrial", case=False)].sort_values("year")
    return float(ind.iloc[-1]["price_cents_per_kwh"]) / 100.0, int(ind.iloc[-1]["year"])


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = pd.read_csv(PROCESSED / "gpu_specs.csv").set_index("model")
    assum = pd.read_csv(MANUAL / "pue_assumptions.csv", comment="#")
    assum = assum[assum["scenario"] == PUE_SCENARIO].iloc[0]
    price, price_year = industrial_price_usd_per_kwh()
    oh, pue, util, hrs = (assum["system_overhead_factor"], assum["pue"],
                          assum["utilization"], assum["hours_per_year"])

    def k_factor(m):  # kWh consumed per unit of annual compute (PFLOP/s-hour)
        s = specs.loc[m]
        power_kw = s["tdp_watts"] / 1000 * oh * pue
        annual_kwh = power_kw * hrs * util
        work = (s["flops_dense_bf16_tflops"] / 1000 * util) * hrs
        return annual_kwh / work

    def capex_term(m):  # $ per unit compute from amortized silicon
        s = specs.loc[m]
        work = (s["flops_dense_bf16_tflops"] / 1000 * util) * hrs
        return s["msrp_usd"] / (NEW_CHIP_LIFE * work)

    def compute_per_mw(m):  # PFLOP/s per MW of system power (the capacity lens)
        s = specs.loc[m]
        power_mw = s["tdp_watts"] / 1e6 * oh * pue
        return (s["flops_dense_bf16_tflops"] / 1000) / power_mw

    kF, capF = k_factor(FRONTIER), capex_term(FRONTIER)

    rows = []
    chain = specs.loc[CHAIN].sort_values("year_released")
    for m, s in chain.iterrows():
        ko = k_factor(m)
        pstar = (capF / (ko - kF)) if ko > kF else None     # $/kWh
        cmw = compute_per_mw(m)
        rows.append({
            "model": m, "year_released": int(s["year_released"]),
            "country": s["country"],
            "tflops_per_watt": round(s["bf16_tflops_per_watt"], 3),
            "compute_pflops_per_mw": round(cmw, 2),
            "energy_only_per_pflops_hour": round(ko * price, 3),
            "stranding_price_cents_kwh": round(pstar * 100, 1) if pstar else None,
            "stranded_at_current": bool(pstar and pstar <= price) if pstar else False,
            "stranded_at_plus50": bool(pstar and pstar <= price * 1.5) if pstar else False,
        })
    res = pd.DataFrame(rows)
    res["current_price_cents_kwh"] = round(price * 100, 1)
    res["frontier_chip"] = FRONTIER
    res["retrieved"] = RETRIEVED
    res.to_csv(OUTPUT / "economic_obsolescence.csv", index=False)

    # --- Console report ---
    print("=" * 86)
    print(f"ECONOMIC OBSOLESCENCE — two lenses ({PUE_SCENARIO}, power {price*100:.1f}¢/kWh {price_year}, "
          f"frontier = {FRONTIER})")
    print("=" * 86)
    print("\n[LENS A] ENERGY COST — electricity price needed to strand each vintage vs the frontier:")
    for _, r in res.iterrows():
        if r["model"] == FRONTIER:
            continue
        p = r["stranding_price_cents_kwh"]
        if p is None:
            print(f"  {r['model']:16s} ({r['year_released']}): never (already near frontier efficiency)")
            continue
        if r["stranded_at_current"]: tag = "STRANDED at today's US price"
        elif r["stranded_at_plus50"]: tag = "stranded under the +50% scenario"
        elif p <= 30: tag = "reached only in high-cost markets (CA/EU)"
        else: tag = "needs implausibly high power"
        print(f"  {r['model']:16s} ({r['year_released']}): P* = {p:6.1f}¢/kWh   ({tag})")
    print(f"  -> at US prices (~{price*100:.0f}¢) only ancient silicon is energy-stranded; modern chips")
    print(f"     are too efficient vs their capex. Cheap power keeps old chips worth running.")

    print("\n[LENS B] POWER CAPACITY — compute delivered per megawatt (the real refresh driver):")
    base = res[res.model == "V100 SXM2"]["compute_pflops_per_mw"].iloc[0]
    for _, r in res.iterrows():
        print(f"  {r['model']:16s} ({r['year_released']}): {r['compute_pflops_per_mw']:6.1f} PFLOP/s per MW "
              f"({r['compute_pflops_per_mw']/base:4.1f}x V100)")
    print("  -> under a fixed-MW build, each generation multiplies compute per scarce watt, so the")
    print("     OPPORTUNITY cost of old silicon forces ~2-3yr refresh even though its energy bill is cheap.")

    # --- Lens-B conditional earnings illustration ---
    capex = pd.read_csv(PROCESSED / "hyperscaler_capex_annual.csv")
    agg = capex.sort_values("period_end").groupby("ticker").tail(1)["capex_usd"].sum() / 1e9
    for life in (3, 6):
        print(f"     [illustrative] ${agg:.0f}B capex booked over {life}y -> ~${agg/life:.0f}B/yr depreciation")
    print(f"  -> IF capacity competition makes the true life ~3y not 6y, annual depreciation would")
    print(f"     roughly double (~${agg/3-agg/6:.0f}B/yr more) and reported operating income fall by that.")
    print(f"     But this is an OPPORTUNITY cost, not a cash cost — energy economics alone don't prove it.")
    print("=" * 86)

    colors = {"NVIDIA": "#2a6f97", "Huawei": "#c1121f", "AMD": "#e09f3e"}

    # --- Figure 1: stranding price per vintage, with US price reference lines ---
    plot = res[res.stranding_price_cents_kwh.notna()].sort_values("year_released")
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    ax.bar(plot["model"].str.replace(" SXM5", "").str.replace(" SXM2", "")
           .str.replace(" SXM 80GB", "").str.replace(" SXM", ""),
           plot["stranding_price_cents_kwh"], color="#8d99ae")
    for lname, mult in PRICE_LINES.items():
        ax.axhline(price * 100 * mult, ls="--", lw=1,
                   color={"current": "#2a9d8f", "+20%": "#e09f3e", "+50%": "#c1121f"}[lname])
        ax.text(len(plot) - 0.5, price * 100 * mult + 1, f"US {lname} ({price*100*mult:.0f}¢)",
                fontsize=7, ha="right")
    ax.set_ylabel("Stranding electricity price P* (¢/kWh)")
    ax.set_title(f"Power price needed to make scrapping-for-{FRONTIER} economic (energy-cost lens)")
    for i, v in enumerate(plot["stranding_price_cents_kwh"]):
        ax.text(i, v + 1, f"{v:.0f}¢", ha="center", fontsize=8)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_stranding_price.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: compute per MW (capacity lens) ---
    d = res.sort_values("year_released")
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.bar(d["model"].str.replace(" SXM5", "").str.replace(" SXM2", "")
           .str.replace(" SXM 80GB", "").str.replace(" SXM", ""),
           d["compute_pflops_per_mw"],
           color=[colors.get(specs.loc[m, "vendor"], "#8d99ae") for m in d["model"]])
    ax.set_ylabel("Compute per MW (PFLOP/s per megawatt, bf16 dense)")
    ax.set_title("Compute per scarce watt multiplies each generation — why old chips get refreshed")
    ax.tick_params(axis="x", rotation=30)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_compute_per_watt.png", dpi=150)
    plt.close(fig)

    # --- Figure 3: scrap frontier — old energy-only vs new all-in at current price ---
    yrs = chain["year_released"].values
    eo = [k_factor(m) * price for m in chain.index]
    ai = [capex_term(m) + k_factor(m) * price for m in chain.index]
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.plot(yrs, eo, marker="o", color="#c1121f", lw=2, label="OLD chip: energy-only $/PFLOP/s-hr")
    ax.plot(yrs, ai, marker="s", color="#2a6f97", lw=2, label="ALL-IN $/PFLOP/s-hr (capex+energy)")
    ax.set_ylabel("$ per PFLOP/s-hour")
    ax.set_xlabel("Year released")
    ax.set_title(f"At US power, even old chips' energy-only cost stays BELOW new chips' all-in cost")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_scrap_frontier.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/economic_obsolescence.csv + 3 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
