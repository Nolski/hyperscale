#!/usr/bin/env python3
"""
analyze_synthesis.py -- Cross-cutting synthesis (Questions 1-3 integrated).

Pulls the headline results of every analysis into one place:
  - output/synthesis_indicators.csv      -- master table of key indicators
  - output/fig_synthesis_dashboard.png   -- 4-panel integrating figure

The four panels track the paper's spine: the AI investment cycle (scale and
forward bet) and the "churn" it displaces onto the energy and labour systems.

Reads   : data/processed/* and output/investment_projection.csv
Writes  : output/synthesis_indicators.csv, output/fig_synthesis_dashboard.png

Re-runnable: reads existing pipeline outputs, overwrites the two synthesis files.
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


def wmean(frame, value, weight):
    return (frame[value] * frame[weight]).sum() / frame[weight].sum()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # ---- Load -------------------------------------------------------------
    capex = pd.read_csv(PROCESSED / "hyperscaler_capex_annual.csv")
    macro = pd.read_csv(PROCESSED / "macro_investment.csv")
    semi = pd.read_csv(PROCESSED / "semiconductor_revenue_annual.csv")
    vc = pd.read_csv(PROCESSED / "vc_ai.csv")
    forecasts = pd.read_csv(PROCESSED / "investment_forecasts.csv")
    dce = pd.read_csv(PROCESSED / "datacenter_energy.csv")
    elec = pd.read_csv(PROCESSED / "us_electricity.csv")
    oews = pd.read_csv(PROCESSED / "oews_occupations.csv")
    exposure = pd.read_csv(PROCESSED / "automation_exposure.csv")
    dc_constr = pd.read_csv(PROCESSED / "datacenter_construction_annual.csv")
    proj = pd.read_csv(OUTPUT / "investment_projection.csv")

    # ---- Q1: scale & macro weight ----------------------------------------
    end_month = pd.to_datetime(capex["period_end"]).dt.month
    capex["chart_year"] = capex["fiscal_year"].where(end_month != 1,
                                                     capex["fiscal_year"] - 1)
    capex_by_year = (capex[capex.chart_year <= 2025]
                     .groupby("chart_year")["total_capacity_investment_usd"].sum() / BN)
    hyper_2025 = capex_by_year.loc[2025]

    macro["year"] = pd.to_datetime(macro["date"]).dt.year
    m25 = lambda lbl: macro[(macro.label == lbl) & (macro.year == 2025)]["value"].mean()
    gdp, pnfi, it_inv = m25("gdp_nominal"), m25("private_nonresidential_fixed_invest"), \
        m25("fixed_invest_it_equip_and_software")
    share_gdp = hyper_2025 / gdp * 100
    share_pnfi = hyper_2025 / pnfi * 100
    share_it = hyper_2025 / it_inv * 100

    vc_world = vc[(vc.year == 2025) & (vc.geography == "World")
                  & (vc.series == "ai_vc")].iloc[0]["value_usd_billion"]
    chip_rev = (semi.sort_values("period_end").groupby("ticker").tail(1)
                ["revenue_usd"].sum() / BN)

    # ---- Q2: projections --------------------------------------------------
    proj_cum = proj.groupby("scenario")["annual_capex_usd_bn"].sum()
    mck_base = forecasts[(forecasts.source == "McKinsey") &
                         (forecasts.scope.str.startswith("Data-center")) &
                         (forecasts.scenario.str.contains("base"))
                         ]["value_usd_billion"].iloc[0]
    gs_cum = forecasts[(forecasts.source == "Goldman Sachs") &
                       (forecasts.metric == "cumulative")]["value_usd_billion"].iloc[0]

    # ---- Q3: energy + labour ---------------------------------------------
    dc_share_2023 = dce[(dce.year == 2023) &
                        (dce.metric == "datacenter_share_of_us")].iloc[0]["value"]
    dc_share_2030 = dce[(dce.year == 2030) &
                        (dce.metric == "datacenter_share_of_us")]["value"].tolist()
    res = elec[elec.sector == "residential"].set_index("year")["price_cents_per_kwh"]
    price_mult = res.loc[res.index.max()] / res.loc[res.index.min()]

    m = oews.merge(exposure[["soc_code", "human_rating_beta"]], on="soc_code")
    exp_w = wmean(m, "human_rating_beta", "total_employment")
    hi_share = (m[m.human_rating_beta >= 0.5]["total_employment"].sum()
                / m["total_employment"].sum() * 100)
    mw = m.dropna(subset=["median_annual_wage"]).copy()
    mw["decile"] = pd.qcut(mw["median_annual_wage"], 10, labels=False) + 1
    decile_exp = mw.groupby("decile").apply(
        lambda g: wmean(g, "human_rating_beta", "total_employment"),
        include_groups=False)

    dc_full = dc_constr[~dc_constr["partial_year"]]
    dc_constr_2025 = dc_full[dc_full.year == 2025]["spending_usd"].iloc[0] / BN

    # ---- Master indicators table -----------------------------------------
    ind = [
        ("Q1 Scale", "Hyperscaler capital investment, 2025", round(hyper_2025), "USD bn"),
        ("Q1 Scale", "  as share of US GDP", round(share_gdp, 1), "%"),
        ("Q1 Scale", "  as share of US private nonres. fixed investment",
         round(share_pnfi, 1), "%"),
        ("Q1 Scale", "  as share of US IT-equipment + software investment",
         round(share_it, 1), "%"),
        ("Q1 Scale", "Global VC into AI, 2025", round(vc_world), "USD bn"),
        ("Q1 Scale", "AI-chip supplier revenue (5 US firms)", round(chip_rev), "USD bn"),
        ("Q2 Forward bet", "Independent estimate, cumulative 2026-2030 (mid)",
         round(proj_cum["mid"]), "USD bn"),
        ("Q2 Forward bet", "Independent estimate, range (low-high)",
         f"{round(proj_cum['low'])}-{round(proj_cum['high'])}", "USD bn"),
        ("Q2 Forward bet", "McKinsey global data-center capex 2025-30 (base)",
         round(mck_base), "USD bn"),
        ("Q2 Forward bet", "Goldman global AI capex 2026-31", round(gs_cum), "USD bn"),
        ("Q3 Energy churn", "Data-center share of US electricity, 2023",
         dc_share_2023, "%"),
        ("Q3 Energy churn", "Data-center share of US electricity, 2030 (proj.)",
         f"{min(dc_share_2030):g}-{max(dc_share_2030):g}", "%"),
        ("Q3 Energy churn", "Residential electricity price multiple, 2001-2025",
         round(price_mult, 2), "x"),
        ("Q3 Labour churn", "Employment-weighted mean LLM exposure",
         round(exp_w, 3), "beta"),
        ("Q3 Labour churn", "US employment in high-exposure occupations",
         round(hi_share, 1), "%"),
        ("Q3 Construction", "Data-center construction, 2025", round(dc_constr_2025, 1),
         "USD bn"),
    ]
    table = pd.DataFrame(ind, columns=["thread", "indicator", "value", "unit"])
    table["retrieved"] = RETRIEVED
    table.to_csv(OUTPUT / "synthesis_indicators.csv", index=False)

    print("=" * 74)
    print("CROSS-CUTTING SYNTHESIS — KEY INDICATORS")
    print("=" * 74)
    thread = None
    for _, r in table.iterrows():
        if r["thread"] != thread:
            thread = r["thread"]
            print(f"\n[{thread}]")
        print(f"  {r['indicator']:52s} {str(r['value']):>12s} {r['unit']}")
    print("=" * 74)

    # ---- 4-panel dashboard ------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle("The AI investment cycle and its churn", fontsize=14, weight="bold")

    # (a) the cycle: actuals + projection band
    ax = axes[0, 0]
    hist = capex_by_year[capex_by_year.index >= 2015]
    ax.plot(hist.index, hist.values, marker="o", color="black", lw=2, label="Actual")
    for sc, col in [("low", "#9dc3d9"), ("mid", "#2a6f97"), ("high", "#013a63")]:
        p = proj[proj.scenario == sc].set_index("year")["annual_capex_usd_bn"]
        ax.plot([2025] + list(p.index), [hist.loc[2025]] + list(p.values),
                ls="--", marker="o", ms=3, color=col, label=f"{sc} proj.")
    ax.set_title("(a) Hyperscaler capital investment ($bn): the cycle", fontsize=10)
    ax.set_ylabel("USD billion")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # (b) macro weight of 2025 hyperscaler capex
    ax = axes[0, 1]
    labels = ["% of\nGDP", "% of all private\nnonres. investment",
              "% of US IT-equip.\n+ software invest."]
    vals = [share_gdp, share_pnfi, share_it]
    ax.bar(labels, vals, color=["#2a6f97", "#5fa8d3", "#013a63"], width=0.6)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.6, f"{v:.1f}%", ha="center", fontsize=10, weight="bold")
    ax.set_title("(b) 2025 hyperscaler capex as a share of US capital formation",
                 fontsize=10)
    ax.set_ylabel("%")
    ax.set_ylim(0, max(vals) * 1.25)

    # (c) energy churn: data-center share of US electricity
    ax = axes[1, 0]
    ax.plot([2023], [dc_share_2023], marker="o", ms=11, color="#013a63",
            label="Actual")
    ax.plot([2030, 2030], [min(dc_share_2030), max(dc_share_2030)],
            color="#e09f3e", lw=9, solid_capstyle="round", label="2030 projected")
    ax.text(2030.25, sum(dc_share_2030) / 2,
            f"{min(dc_share_2030):g}-{max(dc_share_2030):g}%", va="center", fontsize=9)
    ax.set_title("(c) Data-center share of US electricity: the energy churn",
                 fontsize=10)
    ax.set_ylabel("% of US electricity")
    ax.set_xlim(2021, 2032)
    ax.set_ylim(0, 19)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # (d) labour churn: LLM exposure by wage decile
    ax = axes[1, 1]
    ax.bar(decile_exp.index, decile_exp.values, color="#9d0208", width=0.7)
    ax.axhline(exp_w, color="grey", ls="--", lw=1)
    ax.text(1, exp_w + 0.015, "workforce avg", fontsize=7, color="grey")
    ax.set_title("(d) LLM task exposure by wage decile: the labour churn",
                 fontsize=10)
    ax.set_xlabel("Wage decile (1 = lowest-paid)")
    ax.set_ylabel("Exposure (beta), empl.-weighted")
    ax.set_xticks(range(1, 11))
    ax.grid(alpha=0.3, axis="y")

    fig.text(0.5, 0.005,
             f"Sources: SEC EDGAR, FRED, EIA, BLS OEWS, US Census/OWID, OECD, "
             f"McKinsey/Goldman, LBNL/EPRI, Eloundou et al. Compiled {RETRIEVED}.",
             ha="center", fontsize=7.5, color="grey")
    fig.tight_layout(rect=(0, 0.025, 1, 0.97))
    fig.savefig(OUTPUT / "fig_synthesis_dashboard.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/synthesis_indicators.csv + "
          f"output/fig_synthesis_dashboard.png (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
