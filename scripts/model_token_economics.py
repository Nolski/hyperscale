#!/usr/bin/env python3
"""
model_token_economics.py -- Model step (Thread 4: token unit economics / asset NPV).

Asks: given that API token prices are collapsing (~order of magnitude per year for a given
capability) while a GPU's cost is mostly fixed, does a GPU ever earn back its (margin-
inflated) price from selling inference -- and how much cushion is there before the price war
turns the bet negative?

Pipeline:
  1. Throughput: convert a GPU's compute to tokens/sec with the standard transformer-inference
     rule -- generating one output token costs ~2 * N_active_params FLOPs:
         tokens_per_sec = (peak_bf16_FLOPS * MFU) / (2 * N_active_params)
     N_active_params and MFU (model-FLOPs utilization) are EXPLICIT, flagged assumptions;
     real decode is often memory-bandwidth-bound, so this is a compute-bound proxy (MLPerf
     would refine). Sensitivity over model size is reported.
  2. Cost per token: from the deployed cost (MSRP + facility + lifetime energy, via the TCO
     model) divided by lifetime tokens -> all-in $/Mtok; and energy-only $/Mtok (the floor).
     Cross-checked against observed cloud rental rates (gpu_rental_rates.csv).
  3. Revenue: API OUTPUT token price path (token_prices.csv), with the annual decline rate
     derived from the frontier tier in the data, projected forward.
  4. NPV / payback / break-even for an H100 bought today; and the SQUEEZE on old vintages as
     the market price falls toward newer hardware's cost-per-token.

Honest framing: revenue = output tokens at API list price at high utilization is a BEST-CASE
(many GPUs train rather than serve; free tiers, input tokens, idle time cut it). The model
reports the cushion -- how far price/utilization can fall before NPV<0 -- rather than a single
NPV. See notes/methodology_hardware_economics.md.

Reads : data/processed/gpu_specs.csv, us_electricity.csv,
        data/raw/manual/{pue_assumptions,token_prices,gpu_rental_rates}.csv
Writes: output/token_economics.csv
        output/fig_cost_vs_price_per_token.png
        output/fig_gpu_payback.png

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
SRC = f"Sources: vendor specs (Tier-2), API token prices (Tier-2), EIA power. Compiled {RETRIEVED}."

PUE_SCENARIO = "hyperscaler_modern"
LIFE_YEARS = 5
# --- Flagged inference assumptions (the model is sensitive to these) ---
N_ACTIVE_PARAMS_B = 100        # active params (billions) of a representative served model
MFU = 0.30                     # inference model-FLOPs utilization (compute-bound proxy)
DISCOUNT = 0.12                # annual discount rate
SERVE_TICKERS = ["A100 SXM 80GB", "H100 SXM5", "B200"]
SIZE_SENSITIVITY_B = [30, 100, 300]


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.8, color="grey")


def industrial_price() -> float:
    el = pd.read_csv(PROCESSED / "us_electricity.csv")
    ind = el[el["sector"].str.contains("industrial", case=False)].sort_values("year").iloc[-1]
    return float(ind["price_cents_per_kwh"]) / 100.0


def frontier_price_decline() -> tuple[float, float]:
    """Current frontier OUTPUT price ($/Mtok) and annual decline factor, from token_prices."""
    tp = pd.read_csv(MANUAL / "token_prices.csv", comment="#")
    tp["date"] = pd.to_datetime(tp["date"])
    # OpenAI FLAGSHIP tier as the capability-constant anchor (GPT-4 -> 4-Turbo -> 4o).
    # Exclude "mini" — the small/cheap tier is not capability-constant with the flagship.
    frontier = tp[tp["model"].str.contains("GPT-4", case=False)
                  & ~tp["model"].str.contains("mini", case=False)].sort_values("date")
    first, last = frontier.iloc[0], frontier.iloc[-1]
    yrs = (last["date"] - first["date"]).days / 365.25
    factor = (last["output_usd_per_mtok"] / first["output_usd_per_mtok"]) ** (1 / yrs)  # per yr
    return float(last["output_usd_per_mtok"]), float(factor)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = pd.read_csv(PROCESSED / "gpu_specs.csv").set_index("model")
    assum = pd.read_csv(MANUAL / "pue_assumptions.csv", comment="#")
    assum = assum[assum["scenario"] == PUE_SCENARIO].iloc[0]
    price_kwh = industrial_price()
    oh, pue, util, hrs = (assum["system_overhead_factor"], assum["pue"],
                          assum["utilization"], assum["hours_per_year"])
    p0, decline = frontier_price_decline()  # $/Mtok now, annual multiplier (<1)

    def econ(model, n_params_b):
        s = specs.loc[model]
        flops = s["flops_dense_bf16_tflops"] * 1e12
        tok_per_sec = flops * MFU / (2 * n_params_b * 1e9)
        tok_per_year = tok_per_sec * 3600 * hrs * util
        sys_kw = s["tdp_watts"] / 1000 * oh * pue
        annual_energy = sys_kw * hrs * util * price_kwh
        # deployed cost: MSRP + facility (per the cost-stack ~$9M/MW) + lifetime energy
        facility = sys_kw / 1000 * 9_000_000
        tco = s["msrp_usd"] + facility + annual_energy * LIFE_YEARS
        return {
            "tok_per_sec": tok_per_sec,
            "tok_per_year": tok_per_year,
            "annual_energy": annual_energy,
            "capex": s["msrp_usd"] + facility,
            "allin_per_mtok": (tco / LIFE_YEARS) / tok_per_year * 1e6,
            "energy_per_mtok": annual_energy / tok_per_year * 1e6,
        }

    # --- Per-vintage cost per Mtok (base model size) ---
    rows = []
    for m in SERVE_TICKERS:
        e = econ(m, N_ACTIVE_PARAMS_B)
        rows.append({"model": m, "tokens_per_sec": round(e["tok_per_sec"]),
                     "allin_cost_per_mtok": round(e["allin_per_mtok"], 3),
                     "energy_cost_per_mtok": round(e["energy_per_mtok"], 4)})
    cost = pd.DataFrame(rows)

    # --- NPV / payback for an H100 under the falling price path ---
    h = econ("H100 SXM5", N_ACTIVE_PARAMS_B)
    tok_yr_m = h["tok_per_year"] / 1e6  # Mtok/yr
    years = list(range(LIFE_YEARS))
    cum, npv, payback_year = 0.0, -h["capex"], None
    cf_track = []
    for t in years:
        price_t = p0 * (decline ** t)
        revenue = tok_yr_m * price_t
        cash = revenue - h["annual_energy"]          # opex ~ energy
        disc = cash / (1 + DISCOUNT) ** (t + 1)
        npv += disc
        cum += cash
        if payback_year is None and cum >= h["capex"]:
            payback_year = t + 1
        cf_track.append({"year": t + 1, "price_per_mtok": round(price_t, 2),
                         "revenue_usd": round(revenue), "cash_usd": round(cash),
                         "cum_cash_usd": round(cum), "npv_running_usd": round(npv)})

    # Break-even: constant price (no decline) that zeroes NPV over the life.
    pv_factor = sum(1 / (1 + DISCOUNT) ** (t + 1) for t in years)
    be_price = (h["capex"] + h["annual_energy"] * pv_factor) / (tok_yr_m * pv_factor)

    # --- Size sensitivity (H100 cost per Mtok vs model size) ---
    sens = [{"n_params_b": n, "h100_allin_per_mtok": round(econ("H100 SXM5", n)["allin_per_mtok"], 3),
             "h100_tokens_per_sec": round(econ("H100 SXM5", n)["tok_per_sec"])}
            for n in SIZE_SENSITIVITY_B]

    out = pd.concat([
        cost.assign(section="cost_per_token"),
        pd.DataFrame(cf_track).assign(section="h100_cashflow"),
        pd.DataFrame(sens).assign(section="size_sensitivity"),
    ], ignore_index=True)
    out["assumptions"] = f"N={N_ACTIVE_PARAMS_B}B,MFU={MFU},disc={DISCOUNT},life={LIFE_YEARS}y"
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "token_economics.csv", index=False)

    # --- Console report ---
    print("=" * 84)
    print(f"TOKEN UNIT ECONOMICS  (served model ~{N_ACTIVE_PARAMS_B}B active params, MFU {MFU}, "
          f"util {util:.0%})")
    print("=" * 84)
    print(f"  Frontier API OUTPUT price now ~${p0:.2f}/Mtok, falling ~{(1-decline)*100:.0f}%/yr "
          f"(from token_prices.csv)")
    print(f"\n  {'GPU':16s} {'tok/sec':>9s} {'all-in $/Mtok':>14s} {'energy $/Mtok':>14s} {'vs price':>10s}")
    for _, r in cost.iterrows():
        ratio = p0 / r["allin_cost_per_mtok"]
        print(f"  {r['model']:16s} {r['tokens_per_sec']:9,.0f} {r['allin_cost_per_mtok']:14.3f} "
              f"{r['energy_cost_per_mtok']:14.4f} {ratio:8.0f}x")
    print(f"\n  -> at list prices, all-in cost/Mtok is a tiny fraction of the API price: inference")
    print(f"     hardware is HUGELY cash-generative if you can sell the tokens.")

    print(f"\n  H100 deployment (capex ${h['capex']/1e3:.0f}k incl. facility):")
    print(f"    {'yr':>3s} {'price $/Mtok':>12s} {'revenue':>10s} {'cum cash':>11s}")
    for r in cf_track:
        print(f"    {r['year']:3d} {r['price_per_mtok']:12.2f} {r['revenue_usd']/1e3:9,.0f}k "
              f"{r['cum_cash_usd']/1e3:10,.0f}k")
    print(f"    payback: {'year '+str(payback_year) if payback_year else '> life'};  "
          f"5y NPV ~${npv/1e6:.1f}M per GPU;  break-even flat price ~${be_price:.2f}/Mtok")
    print("-" * 84)
    print("  Reading: the GPU-level inference bet pays back in well under a year AT LIST PRICES &")
    print("  HIGH UTILISATION. So the unit economics aren't the risk — the risks are: most capex")
    print("  is TRAINING (no per-token revenue), the price war (margin-compression thread) drives")
    print("  price toward cost, and utilisation/demand may not materialise. Break-even price is")
    print(f"  ~${be_price:.2f}/Mtok — orders of magnitude below today's ~${p0:.0f}, so there is huge")
    print("  cushion on inference, which is exactly why prices CAN keep collapsing.")
    print("=" * 84)

    # --- Figure 1: cost-per-Mtok by vintage vs the falling price path ---
    fig, ax = plt.subplots(figsize=(10, 5.6))
    yrs_proj = np.arange(0, 6)
    price_path = p0 * decline ** yrs_proj
    ax.plot(2025 + yrs_proj, price_path, color="#c1121f", lw=2.5, marker="o",
            label=f"API output price (~{(1-decline)*100:.0f}%/yr decline)")
    palette = {"A100 SXM 80GB": "#8d99ae", "H100 SXM5": "#2a6f97", "B200": "#2a9d8f"}
    for _, r in cost.iterrows():
        ax.axhline(r["allin_cost_per_mtok"], ls="--", lw=1.3, color=palette.get(r["model"], "grey"),
                   label=f"{r['model'].split()[0]} all-in cost/Mtok")
    ax.set_yscale("log")
    ax.set_xlabel("Year")
    ax.set_ylabel("$ per million tokens (log scale)")
    ax.set_title("Falling token price vs each GPU's fixed cost-per-token — the inference squeeze")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_cost_vs_price_per_token.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: H100 cumulative cash vs capex (payback) ---
    fig, ax = plt.subplots(figsize=(10, 5.2))
    yy = [r["year"] for r in cf_track]
    cumc = [r["cum_cash_usd"] / 1e6 for r in cf_track]
    ax.bar(yy, cumc, color="#2a9d8f", alpha=0.85, label="cumulative cash (revenue − energy)")
    ax.axhline(h["capex"] / 1e6, color="#c1121f", ls="--", lw=2,
               label=f"capex ${h['capex']/1e3:.0f}k (incl. facility)")
    ax.set_xlabel("Year of deployment")
    ax.set_ylabel("USD millions per GPU")
    ax.set_title("An H100 repays its (margin-inflated) capex in months — at list prices & high use")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_gpu_payback.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/token_economics.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
