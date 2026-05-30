#!/usr/bin/env python3
"""
analyze_equity_concentration.py -- Analysis step.

Answers two halves of "are stocks actually fine, or does it just look that way?":

  1. CONCENTRATION / BREADTH -- the cap-weighted S&P 500 (SPY) vs the EQUAL-weighted
     S&P 500 (RSP). When SPY outruns RSP, the index's gains come from its largest
     names (the AI megacaps), not the median stock -- a narrow, top-heavy market that
     can look healthy at the index level while most stocks lag. Mag-7 combined market
     cap quantifies the top-heaviness.

  2. VALUATION / EQUITY RISK PREMIUM -- the cyclically-adjusted ERP:
        ERP = (1 / CAPE)  -  real 10y (TIPS)
     CAPE's 1/x is a REAL earnings yield, so subtracting the TIPS real 10y is
     apples-to-apples. A near-zero or negative ERP means investors are paid almost
     nothing extra to hold stocks over inflation-protected Treasuries -- a concrete,
     quantified version of "this doesn't seem rational."

Reads   : data/processed/equity_prices.csv, equity_market_caps.csv,
          shiller_cape.csv, treasury_curve.csv
Writes  : output/equity_concentration.csv
          output/fig_capweight_vs_equalweight.png
          output/fig_equity_risk_premium.png

Caveats : Yahoo prices are Tier-2; CAPE is manual/approximate; the Mag-7 S&P index
          WEIGHT is an external flagged reference (float weights are not computed
          here). The cap- vs equal-weight DIVERGENCE and the ERP TREND are the
          robust findings; treat single-decimal levels as indicative.

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
SRC = f"Sources: Yahoo Finance (Tier-2), Shiller CAPE (manual), FRED TIPS. Compiled {RETRIEVED}."

# External, flagged reference: Mag-7 share of S&P 500 by index (float) weight, as
# widely reported in late 2025/early 2026 (~35%). NOT computed here (float weights
# are not in the data); used only for narrative context. Refresh from index docs.
MAG7_SP500_INDEX_WEIGHT_PCT = 35.0

WINDOW_START = "2015-01-01"


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    px = pd.read_csv(PROCESSED / "equity_prices.csv", parse_dates=["date"])
    caps = pd.read_csv(PROCESSED / "equity_market_caps.csv")
    cape = pd.read_csv(PROCESSED / "shiller_cape.csv")
    curve = pd.read_csv(PROCESSED / "treasury_curve.csv")

    # --- 1. Cap-weight vs equal-weight ---
    wide = px.pivot_table(index="date", columns="label", values="close", aggfunc="last")
    pair = wide[["sp500_capweight", "sp500_equalweight"]].dropna()
    pair = pair[pair.index >= WINDOW_START]
    rebased = pair / pair.iloc[0] * 100.0
    ratio = (rebased["sp500_capweight"] / rebased["sp500_equalweight"])
    cap_total_ret = rebased["sp500_capweight"].iloc[-1] / 100 - 1
    ew_total_ret = rebased["sp500_equalweight"].iloc[-1] / 100 - 1

    # trailing ~1y divergence (last 252 trading days)
    last_yr = pair.tail(252)
    cap_1y = last_yr["sp500_capweight"].iloc[-1] / last_yr["sp500_capweight"].iloc[0] - 1
    ew_1y = last_yr["sp500_equalweight"].iloc[-1] / last_yr["sp500_equalweight"].iloc[0] - 1

    mag7_total = caps["market_cap_usd"].dropna().sum() / 1e12

    # --- 2. Equity risk premium (cyclically adjusted) ---
    cape = cape[["year", "cape"]].dropna()
    cape["earnings_yield_pct"] = 100.0 / cape["cape"]
    # year-end real 10y from TIPS (DFII10), by calendar year
    r10 = curve[curve.label == "real_10y"].copy()
    r10["date"] = pd.to_datetime(r10["date"])
    r10["year"] = r10["date"].dt.year
    real_by_year = r10.groupby("year")["value"].last().rename("real_10y_pct")
    erp = cape.merge(real_by_year, left_on="year", right_index=True, how="inner")
    erp["erp_pct"] = erp["earnings_yield_pct"] - erp["real_10y_pct"]

    latest = erp.sort_values("year").iloc[-1]

    # --- Summary table ---
    rows = [
        ("concentration", f"Cap-weight (SPY) total return since {WINDOW_START[:4]}",
         round(cap_total_ret * 100, 1), "%"),
        ("concentration", f"Equal-weight (RSP) total return since {WINDOW_START[:4]}",
         round(ew_total_ret * 100, 1), "%"),
        ("concentration", "Cap/equal-weight outperformance (ratio, end of window)",
         round(ratio.iloc[-1], 3), "x"),
        ("concentration", "Cap-weight trailing ~1y return", round(cap_1y * 100, 1), "%"),
        ("concentration", "Equal-weight trailing ~1y return", round(ew_1y * 100, 1), "%"),
        ("concentration", "Mag-7 combined market cap", round(mag7_total, 2), "USD tn"),
        ("concentration", "Mag-7 share of S&P 500 by index weight (external ref)",
         MAG7_SP500_INDEX_WEIGHT_PCT, "% (flagged)"),
        ("valuation_erp", "Shiller CAPE (latest)", round(latest["cape"], 1), "x"),
        ("valuation_erp", "Cyclically-adj. earnings yield (1/CAPE)",
         round(latest["earnings_yield_pct"], 2), "%"),
        ("valuation_erp", "Real 10y (TIPS, year-end)", round(latest["real_10y_pct"], 2), "%"),
        ("valuation_erp", "Equity risk premium (earnings yield - real 10y)",
         round(latest["erp_pct"], 2), "%"),
    ]
    table = pd.DataFrame(rows, columns=["section", "item", "value", "units"])
    table["retrieved"] = RETRIEVED
    table.to_csv(OUTPUT / "equity_concentration.csv", index=False)

    # --- Console report ---
    print("=" * 72)
    print(f"EQUITY CONCENTRATION (since {WINDOW_START[:4]}) & RISK PREMIUM")
    print("=" * 72)
    print(f"  Cap-weight (SPY)   total return  {cap_total_ret*100:7.1f} %")
    print(f"  Equal-weight (RSP) total return  {ew_total_ret*100:7.1f} %")
    print(f"  -> cap-weight has outperformed equal-weight by {ratio.iloc[-1]:.2f}x")
    print(f"     (gains concentrated in the largest names, not the median stock)")
    print(f"  Trailing ~1y: cap {cap_1y*100:+.1f}%  vs  equal {ew_1y*100:+.1f}%")
    print(f"  Mag-7 combined market cap ~ ${mag7_total:.1f}T "
          f"(~{MAG7_SP500_INDEX_WEIGHT_PCT:.0f}% of S&P 500 by weight, external ref)")
    print(f"\n  Equity risk premium (cyclically adjusted):")
    print(f"    Shiller CAPE                   {latest['cape']:6.1f} x")
    print(f"    earnings yield (1/CAPE)        {latest['earnings_yield_pct']:6.2f} %")
    print(f"    minus real 10y (TIPS)          {latest['real_10y_pct']:6.2f} %")
    print(f"    = equity risk premium          {latest['erp_pct']:6.2f} %  "
          f"<- thin: little extra pay for equity risk")
    print("=" * 72)

    # --- Figure 1: cap-weight vs equal-weight, rebased ---
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.plot(rebased.index, rebased["sp500_capweight"], color="#c1121f", lw=1.6,
            label="Cap-weighted S&P 500 (SPY)")
    ax.plot(rebased.index, rebased["sp500_equalweight"], color="#2a6f97", lw=1.6,
            label="Equal-weighted S&P 500 (RSP)")
    ax.set_title(f"The index vs the median stock (rebased to 100 at {WINDOW_START[:4]})")
    ax.set_ylabel("Total-return index (= 100 at start)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_capweight_vs_equalweight.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: equity risk premium over time ---
    e = erp.sort_values("year")
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.axhline(0, color="grey", lw=0.8)
    ax.bar(e["year"], e["erp_pct"], color="#2a9d8f", alpha=0.8, label="ERP (earnings yield − real 10y)")
    ax.plot(e["year"], e["earnings_yield_pct"], color="#e09f3e", marker="o", lw=1.2,
            label="CAPE earnings yield (1/CAPE)")
    ax.plot(e["year"], e["real_10y_pct"], color="#2a6f97", marker="s", lw=1.2,
            label="Real 10y (TIPS)")
    ax.set_title("Cyclically-adjusted equity risk premium has compressed toward zero")
    ax.set_ylabel("%")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)
    ax.annotate("CAPE manual/approximate — read the TREND, not the decimal",
                xy=(0.02, 0.04), xycoords="axes fraction", fontsize=7, color="grey")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_equity_risk_premium.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/equity_concentration.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
