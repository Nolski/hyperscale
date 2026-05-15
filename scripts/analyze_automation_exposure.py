#!/usr/bin/env python3
"""
analyze_automation_exposure.py -- Analysis step (Question 3c, labor).

Joins BLS OEWS employment to occupation-level AI-exposure scores from TWO
methods, and asks who is exposed and how exposure relates to wages.

  Eloundou (predicted) -- human_rating_beta from "GPTs are GPTs" (2024): share
                          of an occupation's tasks an LLM could materially speed
                          up. A capability ceiling.
  Anthropic (observed) -- observed_exposure from the Anthropic Economic Index:
                          built from actual Claude.ai usage. An adoption floor.

Reporting both brackets the estimate: predicted potential vs. observed take-up.

Reads   : data/processed/{oews_occupations,automation_exposure,anthropic_exposure}.csv
Writes  : output/automation_exposure_summary.csv
          output/fig_exposure_by_wage_decile.png
          output/fig_exposure_method_comparison.png
          output/fig_largest_occupations_exposure.png

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
SRC = (f"Sources: BLS OEWS (May 2024); Eloundou et al. 'GPTs are GPTs' (2024); "
       f"Anthropic Economic Index. Compiled {RETRIEVED}.")

# Display name -> exposure column. Order matters for plotting.
METHODS = {
    "Eloundou (predicted)": "human_rating_beta",
    "Anthropic (observed)": "anthropic_observed_exposure",
}
COLORS = {"Eloundou (predicted)": "#2a6f97", "Anthropic (observed)": "#9d0208"}


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def wmean(frame: pd.DataFrame, value: str, weight: str) -> float:
    return (frame[value] * frame[weight]).sum() / frame[weight].sum()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    oews = pd.read_csv(PROCESSED / "oews_occupations.csv")
    eloundou = pd.read_csv(PROCESSED / "automation_exposure.csv")
    anthropic = pd.read_csv(PROCESSED / "anthropic_exposure.csv")

    # Intersection: occupations covered by OEWS and BOTH exposure methods --
    # the honest common basis for comparing the two.
    merged = (oews.merge(eloundou[["soc_code", "human_rating_beta"]], on="soc_code")
              .merge(anthropic[["soc_code", "anthropic_observed_exposure"]], on="soc_code"))
    match_emp = merged["total_employment"].sum()
    total_emp = oews["total_employment"].sum()

    # --- Per-method headline stats ----------------------------------------
    stats = {}
    for name, col in METHODS.items():
        w = wmean(merged, col, "total_employment")
        hi = merged.loc[merged[col] >= 0.5, "total_employment"].sum() / match_emp * 100
        stats[name] = {"weighted_exposure": w, "high_exposure_emp_pct": hi}

    # --- Exposure by wage decile (employment-weighted), both methods ------
    wage = merged.dropna(subset=["median_annual_wage"]).copy()
    wage["wage_decile"] = pd.qcut(wage["median_annual_wage"], 10, labels=False) + 1
    decile = wage.groupby("wage_decile").apply(
        lambda g: pd.Series({name: wmean(g, col, "total_employment")
                             for name, col in METHODS.items()}),
        include_groups=False)

    corr = merged["human_rating_beta"].corr(merged["anthropic_observed_exposure"])

    # --- Summary table -----------------------------------------------------
    rows = [{"indicator": "Occupations matched (OEWS x both methods)",
             "value": len(merged)},
            {"indicator": "US employment covered (%)",
             "value": round(match_emp / total_emp * 100, 1)},
            {"indicator": "Eloundou-Anthropic rank correlation", "value": round(corr, 3)}]
    for name in METHODS:
        rows.append({"indicator": f"Empl.-weighted exposure -- {name}",
                     "value": round(stats[name]["weighted_exposure"], 3)})
        rows.append({"indicator": f"Empl. in high-exposure occ. (>=0.5) %, {name}",
                     "value": round(stats[name]["high_exposure_emp_pct"], 1)})
    summary = pd.DataFrame(rows)
    summary["retrieved"] = RETRIEVED
    summary.to_csv(OUTPUT / "automation_exposure_summary.csv", index=False)

    # --- Console report ----------------------------------------------------
    print("=" * 74)
    print("QUESTION 3c — LABOR / AUTOMATION EXPOSURE (two methods)")
    print("=" * 74)
    print(f"Matched {len(merged)} occupations covering "
          f"{match_emp / total_emp * 100:.1f}% of US employment.")
    print(f"Eloundou-Anthropic correlation across occupations: {corr:.3f}")
    print(f"\n{'method':24s}{'empl.-wtd exposure':>20s}{'high-exposure empl.':>22s}")
    for name in METHODS:
        s = stats[name]
        print(f"  {name:22s}{s['weighted_exposure']:>18.3f}"
              f"{s['high_exposure_emp_pct']:>20.1f}%")
    print("\nExposure by wage decile (1 = lowest-paid):")
    print(f"  {'decile':8s}{'Eloundou':>12s}{'Anthropic':>12s}")
    for d, r in decile.iterrows():
        print(f"  D{int(d):<7d}{r['Eloundou (predicted)']:>12.3f}"
              f"{r['Anthropic (observed)']:>12.3f}")
    print("\nMost-exposed large occupations (>1M workers):")
    big = merged[merged.total_employment > 1e6].nlargest(6, "anthropic_observed_exposure")
    for _, r in big.iterrows():
        print(f"  Anthropic {r['anthropic_observed_exposure']:.2f} / "
              f"Eloundou {r['human_rating_beta']:.2f}  "
              f"{r['occupation'][:38]:38s} {r['total_employment'] / 1e6:.1f}M")
    print("=" * 74)

    # --- Figure 1: exposure by wage decile, grouped bars -------------------
    fig, ax = plt.subplots(figsize=(9.5, 5))
    x = decile.index.to_numpy()
    width = 0.38
    for i, name in enumerate(METHODS):
        ax.bar(x + (i - 0.5) * width, decile[name], width,
               label=name, color=COLORS[name])
    ax.set_title("Employment-weighted AI exposure by wage decile — two methods")
    ax.set_xlabel("Wage decile (1 = lowest-paid, 10 = highest-paid)")
    ax.set_ylabel("Exposure, employment-weighted")
    ax.set_xticks(x)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_exposure_by_wage_decile.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: method comparison scatter -------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.scatter(merged["human_rating_beta"], merged["anthropic_observed_exposure"],
               s=merged["total_employment"] / 3500, alpha=0.4, color="#2a6f97",
               edgecolors="none")
    ax.plot([0, 1], [0, 1], ls=":", color="grey", lw=1)
    ax.text(0.62, 0.66, "parity (y = x)", fontsize=7, color="grey", rotation=33)
    ax.set_title(f"Predicted vs. observed exposure by occupation (r = {corr:.2f})")
    ax.set_xlabel("Eloundou predicted exposure (beta)")
    ax.set_ylabel("Anthropic observed exposure")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_exposure_method_comparison.png", dpi=150)
    plt.close(fig)

    # --- Figure 3: 15 largest occupations, both methods --------------------
    largest = merged.nlargest(15, "total_employment").sort_values("total_employment")
    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    y = range(len(largest))
    height = 0.4
    ax.barh([i + height / 2 for i in y], largest["human_rating_beta"], height,
            label="Eloundou (predicted)", color=COLORS["Eloundou (predicted)"])
    ax.barh([i - height / 2 for i in y], largest["anthropic_observed_exposure"], height,
            label="Anthropic (observed)", color=COLORS["Anthropic (observed)"])
    ax.set_yticks(list(y))
    ax.set_yticklabels(largest["occupation"].str.slice(0, 38))
    ax.set_title("AI exposure of the 15 largest US occupations — two methods")
    ax.set_xlabel("Exposure")
    ax.tick_params(axis="y", labelsize=8)
    ax.legend(fontsize=8)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_largest_occupations_exposure.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/automation_exposure_summary.csv + 3 figures "
          f"(retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
