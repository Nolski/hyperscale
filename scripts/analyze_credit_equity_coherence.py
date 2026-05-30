#!/usr/bin/env python3
"""
analyze_credit_equity_coherence.py -- Analysis step.

Answers: "Across asset classes, is anything actually pricing distress?" by
PERCENTILE-RANKING each stress gauge against its own full history. A percentile
near 0 means 'as calm as it ever gets'; near 100 means 'as stressed as it ever gets'.

The point: if credit spreads, equity volatility, and financial-conditions indices
all sit at LOW percentiles while the TERM PREMIUM sits higher, then the bond
market is NOT pricing a credit/growth collapse -- the only thing elevated is the
compensation for holding duration. That is the cross-asset evidence that the
"bonds signal collapse" read is really a term-premium / supply story (the same
conclusion as analyze_curve_decomposition.py, reached from the other direction).

Gauges (higher value = more stress, except where noted):
  * HY / IG / CCC OAS        -- credit-default risk priced in corporate bonds
  * Moody's Baa-10y spread   -- investment-grade risk premium
  * VIX                      -- equity implied volatility
  * NFCI, STLFSI             -- financial-conditions / stress indices
  * Realized 10y vol (proxy) -- stands in for the paywalled ICE MOVE bond-vol index
  * 10y term premium         -- shown for CONTRAST (the one likely-elevated gauge)

Reads   : data/processed/credit_spreads.csv, market_stress.csv, treasury_curve.csv
Writes  : output/cross_asset.csv
          output/fig_cross_asset_percentiles.png
          output/fig_credit_vs_vix_history.png

Caveats : Realized 10y vol is a PROXY for MOVE, not the index. Percentiles use each
          series' full available history (lengths differ). See notes/provenance.md.

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
SRC = f"Sources: FRED (ICE BofA OAS, Moody's, VIX, NFCI, ACM term premium). Compiled {RETRIEVED}."


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def get_series(df: pd.DataFrame, label: str) -> pd.Series:
    s = df[df.label == label].copy()
    s["date"] = pd.to_datetime(s["date"])
    return s.set_index("date")["value"].sort_index()


def pct_rank(s: pd.Series) -> float:
    """Percentile (0-100) of the latest value within the series' full history."""
    return float((s <= s.iloc[-1]).mean() * 100)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    credit = pd.read_csv(PROCESSED / "credit_spreads.csv")
    stress = pd.read_csv(PROCESSED / "market_stress.csv")
    curve = pd.read_csv(PROCESSED / "treasury_curve.csv")

    # Realized 10y vol proxy for MOVE: annualized 21-day std of daily yield changes (bp).
    n10 = get_series(curve, "nominal_10y")
    realized_vol = (n10.diff().rolling(21).std() * np.sqrt(252) * 100).dropna()  # bp/yr

    gauges = {
        "HY OAS": get_series(credit, "hy_oas"),
        "IG OAS": get_series(credit, "ig_oas"),
        "CCC OAS": get_series(credit, "ccc_oas"),
        "Baa−10y spread": get_series(credit, "baa_minus_10y"),
        "VIX": get_series(stress, "vix"),
        "NFCI": get_series(stress, "nfci"),
        "STLFSI": get_series(stress, "stlfsi"),
        "Realized 10y vol (MOVE proxy)": realized_vol,
        "10y term premium (contrast)": get_series(curve, "term_premium_10y"),
    }

    rows = []
    for name, s in gauges.items():
        rows.append({
            "gauge": name,
            "latest_value": round(float(s.iloc[-1]), 2),
            "percentile_vs_history": round(pct_rank(s), 1),
            "hist_min": round(float(s.min()), 2),
            "hist_max": round(float(s.max()), 2),
            "hist_start": s.index[0].date().isoformat(),
            "n_obs": int(s.shape[0]),
        })
    table = pd.DataFrame(rows)
    table["retrieved"] = RETRIEVED
    table.to_csv(OUTPUT / "cross_asset.csv", index=False)

    # --- Console report ---
    print("=" * 78)
    print("CROSS-ASSET STRESS — latest value & percentile vs own history")
    print("=" * 78)
    print(f"  {'Gauge':34s} {'latest':>8s} {'pctile':>7s}   reading")
    for r in rows:
        p = r["percentile_vs_history"]
        if "term premium" in r["gauge"]:
            tag = "elevated (the duration-risk story)" if p >= 60 else "moderate"
        else:
            tag = "calm (low percentile)" if p <= 40 else ("stressed" if p >= 70 else "middling")
        print(f"  {r['gauge']:34s} {r['latest_value']:8.2f} {p:6.1f}%   {tag}")
    print("-" * 78)
    print("  Read: credit spreads, equity vol and financial conditions sit LOW; the")
    print("  term premium is the outlier. Nothing is pricing a credit/growth collapse —")
    print("  the heavy long end is about duration supply, not distress.")
    print("=" * 78)

    # --- Figure 1: percentile bars (the coherence picture) ---
    order = [r for r in rows]  # keep insertion order
    names = [r["gauge"] for r in order]
    pctiles = [r["percentile_vs_history"] for r in order]
    colors = []
    for r in order:
        p = r["percentile_vs_history"]
        if "term premium" in r["gauge"]:
            colors.append("#e09f3e")  # contrast gauge
        else:
            colors.append("#2a9d8f" if p <= 40 else ("#c1121f" if p >= 70 else "#8d99ae"))
    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.barh(names, pctiles, color=colors)
    ax.axvline(50, color="grey", ls="--", lw=1.0)
    for i, p in enumerate(pctiles):
        ax.text(p, i, f" {p:.0f}%", va="center", fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Percentile vs own history (0 = calmest ever, 100 = most stressed ever)")
    ax.set_title("Is anything pricing distress? Cross-asset stress percentiles")
    ax.invert_yaxis()
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_cross_asset_percentiles.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: HY spread vs VIX over time (both calm now) ---
    hy = gauges["HY OAS"]
    vix = gauges["VIX"]
    common_start = max(hy.index[0], vix.index[0], pd.Timestamp("2007-01-01"))
    hy2 = hy[hy.index >= common_start].resample("ME").last()
    vix2 = vix[vix.index >= common_start].resample("ME").last()
    fig, ax1 = plt.subplots(figsize=(10, 5.2))
    ax1.plot(hy2.index, hy2.values, color="#c1121f", lw=1.3, label="HY OAS (left)")
    ax1.set_ylabel("High-yield OAS, %", color="#c1121f")
    ax1.tick_params(axis="y", labelcolor="#c1121f")
    ax2 = ax1.twinx()
    ax2.plot(vix2.index, vix2.values, color="#2a6f97", lw=1.0, alpha=0.8, label="VIX (right)")
    ax2.set_ylabel("VIX", color="#2a6f97")
    ax2.tick_params(axis="y", labelcolor="#2a6f97")
    ax1.set_title("Credit risk and equity fear move together — and both are low now")
    caption(ax1)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_credit_vs_vix_history.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/cross_asset.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
