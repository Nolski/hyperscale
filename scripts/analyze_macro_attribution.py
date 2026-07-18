#!/usr/bin/env python3
"""
analyze_macro_attribution.py -- Analysis step (the macro layer of the broadened analysis).

Replicates, with BEA PRIMARY data, the finding that AI/IT investment has driven the bulk of
recent US growth (Furman: information-processing equipment + software ~= 92% of H1-2025 real
GDP growth; without it, ~0.1%). Answers "is the whole economy leaning on this?" without any
firm-by-firm AI guessing.

Method (contribution-to-annualized-growth, the BEA convention, approximated from real levels):
  gdp_growth_ann_t   = 400 * (GDP_t - GDP_{t-1}) / GDP_{t-1}
  it_contribution_t  = 400 * (IT_t  - IT_{t-1})  / GDP_{t-1}
  share_t            = it_contribution_t / gdp_growth_ann_t
where IT = "private fixed investment in information processing equipment and software" and GDP
is real GDP, both chained-$ SAAR levels (bea_*.csv). Chained dollars are not perfectly additive,
so this approximates BEA's chain-weighted contributions; cross-checked against the published
aggregate Equipment + IP-products contributions (Table 1.1.2).

Reads : data/processed/bea_fixed_investment.csv, bea_real_gdp.csv, bea_contributions.csv
Writes: output/macro_attribution.csv
        output/fig_gdp_growth_attribution.png
        output/fig_it_investment_share_gdp.png

Caveats: contribution != causation (absent the boom, lower rates/power would have offset some);
BEA data is real (chained) and REVISED, so the exact share moves with vintage; this is the
disciplined macro measure, paired with the firm-level complex (analyze_ai_complex.py).

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
SRC = f"Source: BEA NIPA (real, chained $; revised). Compiled {RETRIEVED}."
NAVY, RED, GREY = "#1a3a5c", "#a4262c", "#8a8a8a"


def caption(ax):
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color=GREY)


def q_index(tp):
    """'2025Q1' -> sortable (year, quarter)."""
    y, q = tp.split("Q")
    return int(y) * 4 + int(q)


def series_by_desc(df, needle):
    s = df[df["description"].str.contains(needle, case=False, na=False)].copy()
    s["qi"] = s["time_period"].map(q_index)
    return s.sort_values("qi").set_index("time_period")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    inv = pd.read_csv(PROCESSED / "bea_fixed_investment.csv")
    gdp = pd.read_csv(PROCESSED / "bea_real_gdp.csv")
    contrib = pd.read_csv(PROCESSED / "bea_contributions.csv")

    it = series_by_desc(inv, "information processing equipment and software")["value"]
    g = series_by_desc(gdp[gdp.line == 1], "gross domestic product")["value"]

    df = pd.DataFrame({"it": it, "gdp": g}).dropna()
    df = df.sort_index(key=lambda idx: idx.map(q_index))
    df["gdp_growth_ann"] = 400 * df["gdp"].diff() / df["gdp"].shift(1)
    df["it_contrib"] = 400 * df["it"].diff() / df["gdp"].shift(1)
    df["it_share_of_growth"] = df["it_contrib"] / df["gdp_growth_ann"]
    df["it_pct_of_gdp"] = df["it"] / df["gdp"] * 100

    # H1-2025 window (the Furman headline)
    h1 = df.loc[[q for q in ["2025Q1", "2025Q2"] if q in df.index]]
    h1_gdp = h1["gdp_growth_ann"].mean()
    h1_it = h1["it_contrib"].mean()
    h1_share = h1_it / h1_gdp if h1_gdp else float("nan")
    ex_it = h1_gdp - h1_it

    # cross-check: aggregate Equipment + IP-products contribution (T10102), H1 2025
    cc = contrib.copy(); cc["qi"] = cc["time_period"].map(q_index)
    def contrib_h1(needle):
        s = cc[cc["description"].str.fullmatch(needle, case=False, na=False)
               & cc["time_period"].isin(["2025Q1", "2025Q2"])]
        return s["value"].mean() if not s.empty else float("nan")
    equip_ip = contrib_h1("Equipment") + contrib_h1("Intellectual property products")

    out = df.reset_index().rename(columns={"index": "time_period"})
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "macro_attribution.csv", index=False)

    print("=" * 78)
    print("AI/IT INVESTMENT AS A DRIVER OF US GROWTH  (BEA primary data)")
    print("=" * 78)
    print(f"  'Information processing equipment + software' investment (real, chained $):")
    print(f"    latest {df.index[-1]}: ${df['it'].iloc[-1]/1000:,.0f}B SAAR, "
          f"{df['it_pct_of_gdp'].iloc[-1]:.1f}% of GDP "
          f"(vs {df['it_pct_of_gdp'].iloc[0]:.1f}% in {df.index[0]})")
    print(f"\n  H1 2025 (the Furman window):")
    print(f"    real GDP growth (annualized, avg)     {h1_gdp:6.1f}%")
    print(f"    of which IT-investment contribution   {h1_it:6.1f}%  "
          f"= {h1_share*100:.0f}% of growth")
    print(f"    GDP growth WITHOUT IT investment      {ex_it:6.1f}%")
    print(f"    [cross-check] BEA Equipment + IP-products contribution: {equip_ip:.1f}pp")
    print(f"\n  Reading: a single investment category -- the data-center / AI build --")
    print(f"  accounts for the large majority of recent measured growth. Contribution, not")
    print(f"  causation: absent the boom, lower rates and power would have offset some.")
    print("=" * 78)

    # --- Fig 1: GDP growth attribution, recent quarters ---
    recent = df[df.index.map(q_index) >= q_index("2023Q1")]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = range(len(recent))
    ax.bar(x, recent["it_contrib"], color=RED, label="IT-investment contribution")
    ax.bar(x, recent["gdp_growth_ann"] - recent["it_contrib"],
           bottom=recent["it_contrib"], color=NAVY, label="rest of the economy")
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set_xticks(list(x)); ax.set_xticklabels(recent.index, rotation=45, fontsize=7)
    ax.set_ylabel("Contribution to real GDP growth (annualized, pp)")
    ax.set_title("AI/IT investment vs the rest of the economy in US GDP growth")
    ax.legend(fontsize=8.5, frameon=False, loc="upper right")
    ax.grid(axis="x", visible=False)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_gdp_growth_attribution.png", dpi=150)
    plt.close(fig)

    # --- Fig 2: IT investment as % of GDP over time ---
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(df.index.map(lambda t: q_index(t) / 4), df["it_pct_of_gdp"], color=NAVY, lw=2.2)
    ax.set_ylabel("% of real GDP")
    ax.set_xlabel("Year")
    ax.set_title("Information-processing equipment + software investment, share of GDP")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_it_investment_share_gdp.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/macro_attribution.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
