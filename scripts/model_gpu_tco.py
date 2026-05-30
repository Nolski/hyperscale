#!/usr/bin/env python3
"""
model_gpu_tco.py -- Model step (Threads 1-2 foundation).

Computes the total cost of ownership (TCO) of each AI accelerator vintage and the share
of that cost that is ELECTRICITY (vs upfront silicon), plus an all-in cost per unit of
sustained compute. Answers:
  * What fraction of a GPU's lifetime cost is power?
  * How does that move with electricity price, PUE, and utilization?
  * At what electricity price does cumulative power cost equal the silicon (the "power =
    silicon" milestone)?
  * How fast is the all-in cost per PFLOP/s falling across vintages (the efficiency march)?

Model (see notes/methodology_hardware_economics.md):
  system_power_kW   = (tdp_W/1000) * system_overhead_factor * PUE
  annual_energy_kWh = system_power_kW * hours_per_year * utilization
  annual_energy_$   = annual_energy_kWh * P_elec($/kWh)
  TCO(L)            = msrp + L * annual_energy_$
  energy_share      = (L * annual_energy_$) / TCO(L)
  throughput_PFLOPs = (bf16_tflops/1000) * utilization
  $ per PFLOP/s-hr  = (TCO(L)/L) / (throughput_PFLOPs * hours_per_year)   [all-in]

Reads : data/processed/gpu_specs.csv, data/raw/manual/pue_assumptions.csv,
        data/processed/us_electricity.csv (industrial retail price)
Writes: output/gpu_tco.csv
        output/fig_gpu_energy_share.png
        output/fig_gpu_cost_per_pflop.png
        output/fig_tco_electricity_sensitivity.png

Caveats: bf16 dense FLOPS is a peak (not realized) throughput proxy; per-unit metrics are
indicative and best read across vintages. China rows are Tier-2 estimates. See the note.

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
SRC = f"Sources: vendor specs (Tier-2), EIA industrial electricity price. Compiled {RETRIEVED}."

LIFE_YEARS = 5          # reference accounting-ish life for the TCO snapshot
PUE_SCENARIO = "hyperscaler_modern"


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def industrial_price_usd_per_kwh() -> tuple[float, int]:
    el = pd.read_csv(PROCESSED / "us_electricity.csv")
    ind = el[el["sector"].str.contains("industrial", case=False)].sort_values("year")
    row = ind.iloc[-1]
    return float(row["price_cents_per_kwh"]) / 100.0, int(row["year"])


def tco_table(specs: pd.DataFrame, assum: pd.Series, price: float, life: int) -> pd.DataFrame:
    df = specs.copy()
    df["system_power_kw"] = (df["tdp_watts"] / 1000.0
                             * assum["system_overhead_factor"] * assum["pue"])
    df["annual_energy_kwh"] = df["system_power_kw"] * assum["hours_per_year"] * assum["utilization"]
    df["annual_energy_usd"] = df["annual_energy_kwh"] * price
    df["lifetime_energy_usd"] = df["annual_energy_usd"] * life
    df["tco_usd"] = df["msrp_usd"] + df["lifetime_energy_usd"]
    df["energy_share"] = df["lifetime_energy_usd"] / df["tco_usd"]
    df["throughput_pflops"] = df["flops_dense_bf16_tflops"] / 1000.0 * assum["utilization"]
    df["allin_usd_per_pflops_hour"] = ((df["tco_usd"] / life)
                                       / (df["throughput_pflops"] * assum["hours_per_year"]))
    # Electricity price at which cumulative power cost == silicon (energy share 50%).
    # lifetime_energy == msrp  =>  P* = msrp / (annual_energy_kwh * life)
    df["price_power_equals_silicon"] = df["msrp_usd"] / (df["annual_energy_kwh"] * life)
    return df


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = pd.read_csv(PROCESSED / "gpu_specs.csv")
    assum_all = pd.read_csv(MANUAL / "pue_assumptions.csv", comment="#")
    assum = assum_all[assum_all["scenario"] == PUE_SCENARIO].iloc[0]
    price, price_year = industrial_price_usd_per_kwh()

    df = tco_table(specs, assum, price, LIFE_YEARS)

    keep = ["model", "vendor", "country", "year_released", "tdp_watts", "msrp_usd",
            "annual_energy_usd", "lifetime_energy_usd", "tco_usd", "energy_share",
            "allin_usd_per_pflops_hour", "price_power_equals_silicon"]
    out = df[keep].copy()
    out["life_years"] = LIFE_YEARS
    out["elec_price_usd_kwh"] = round(price, 4)
    out["pue_scenario"] = PUE_SCENARIO
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "gpu_tco.csv", index=False)

    # --- Console report ---
    print("=" * 84)
    print(f"GPU TOTAL COST OF OWNERSHIP — {LIFE_YEARS}-yr life, {PUE_SCENARIO} "
          f"(PUE {assum['pue']}, util {assum['utilization']:.0%}), "
          f"industrial power {price*100:.1f}¢/kWh ({price_year})")
    print("=" * 84)
    print(f"  {'Model':18s} {'MSRP':>8s} {'5y energy':>10s} {'TCO':>9s} {'energy%':>8s} "
          f"{'$/PFs·h':>8s} {'P*=silicon':>11s}")
    for _, r in df.sort_values("year_released").iterrows():
        print(f"  {r['model']:18s} {r['msrp_usd']/1e3:7.0f}k {r['lifetime_energy_usd']/1e3:9.1f}k "
              f"{r['tco_usd']/1e3:8.0f}k {r['energy_share']*100:7.1f}% "
              f"{r['allin_usd_per_pflops_hour']:8.3f} {r['price_power_equals_silicon']*100:9.1f}¢")
    print("-" * 84)
    print(f"  $/PFs·h = all-in $ per PFLOP/s sustained for one hour (lower = cheaper compute).")
    print(f"  P*=silicon = electricity price at which {LIFE_YEARS}y power cost equals the chip price.")
    print(f"  Energy is a modest share at today's ~{price*100:.0f}¢ industrial power, but it is the")
    print(f"  ONLY ongoing cost — so it governs when an old chip is scrapped (see obsolescence model).")
    print("=" * 84)

    colors = {"NVIDIA": "#2a6f97", "AMD": "#e09f3e", "Huawei": "#c1121f"}

    # --- Figure 1: energy share of TCO by vintage ---
    d = df.sort_values("year_released")
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.bar(d["model"], d["energy_share"] * 100,
           color=[colors.get(v, "#8d99ae") for v in d["vendor"]])
    ax.set_ylabel(f"Electricity as % of {LIFE_YEARS}-yr TCO")
    ax.set_title(f"Energy share of GPU total cost of ownership "
                 f"({price*100:.0f}¢/kWh, PUE {assum['pue']}, {assum['utilization']:.0%} util)")
    ax.tick_params(axis="x", rotation=40)
    for i, v in enumerate(d["energy_share"]):
        ax.text(i, v * 100, f"{v*100:.0f}%", ha="center", va="bottom", fontsize=8)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_gpu_energy_share.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: all-in cost per PFLOP/s-hour vs release year (efficiency march) ---
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for vendor, g in df.groupby("vendor"):
        g = g.sort_values("year_released")
        ax.scatter(g["year_released"], g["allin_usd_per_pflops_hour"],
                   color=colors.get(vendor, "#8d99ae"), s=70, label=vendor, zorder=5)
        for _, r in g.iterrows():
            ax.annotate(r["model"].replace(" SXM", "").replace(" superchip", ""),
                        (r["year_released"], r["allin_usd_per_pflops_hour"]),
                        textcoords="offset points", xytext=(5, 4), fontsize=7)
    nv = df[df.vendor == "NVIDIA"].sort_values("year_released")
    ax.plot(nv["year_released"], nv["allin_usd_per_pflops_hour"], color="#2a6f97", lw=1, alpha=0.5)
    ax.set_yscale("log")
    ax.set_ylabel("All-in $ per PFLOP/s-hour (log scale)")
    ax.set_xlabel("Year released")
    ax.set_title("Cost of compute falls fast across vintages — why old chips get stranded")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_gpu_cost_per_pflop.png", dpi=150)
    plt.close(fig)

    # --- Figure 3: energy share vs electricity price, for representative chips ---
    prices = np.linspace(0.04, 0.30, 40)  # 4¢ to 30¢/kWh
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for model in ["A100 SXM 80GB", "H100 SXM5", "B200"]:
        s = specs[specs.model == model].iloc[0]
        spow = s["tdp_watts"] / 1000 * assum["system_overhead_factor"] * assum["pue"]
        akwh = spow * assum["hours_per_year"] * assum["utilization"]
        shares = [(akwh * LIFE_YEARS * p) / (s["msrp_usd"] + akwh * LIFE_YEARS * p) * 100
                  for p in prices]
        ax.plot(prices * 100, shares, lw=2, label=model.replace(" SXM5", "").replace(" SXM 80GB", ""))
    ax.axvline(price * 100, color="grey", ls="--", lw=1)
    ax.text(price * 100, 5, f" today ~{price*100:.0f}¢", fontsize=8, color="grey")
    ax.set_xlabel("Industrial electricity price (¢/kWh)")
    ax.set_ylabel(f"Electricity as % of {LIFE_YEARS}-yr TCO")
    ax.set_title("Higher power prices tilt GPU economics from silicon toward energy")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_tco_electricity_sensitivity.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/gpu_tco.csv + 3 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
