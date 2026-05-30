#!/usr/bin/env python3
"""
analyze_curve_decomposition.py -- Analysis step (the core reframe).

Answers: "What is the 10-year Treasury yield actually telling us -- a coming
recession, or a fiscal/term-premium repricing?" by DECOMPOSING the nominal 10y
two complementary ways:

  (a) NOMINAL = REAL (TIPS, DFII10) + BREAKEVEN INFLATION (T10YIE).
      Is the move in real yields (growth/policy) or in inflation compensation?
  (b) NOMINAL ~= EXPECTATIONS component + TERM PREMIUM (THREEFYTP10, ACM model).
      A term-premium-driven rise is a SUPPLY / duration-risk story -- investors
      demanding more to hold long bonds -- NOT the market forecasting Fed cuts.
      (expectations component is derived: nominal_10y - term_premium_10y.)

The headline figure shows the 10y term premium going from mostly NEGATIVE through
the 2010s (QE era) to clearly POSITIVE now -- the single best one-picture answer
to "why are long yields high if no recession is coming."

Reads   : data/processed/treasury_curve.csv
Writes  : output/curve_decomposition.csv  (latest-snapshot + history summary)
          output/fig_curve_decomposition.png   (10y = real + breakeven, over time)
          output/fig_term_premium_regime.png   (term premium regime shift)
          output/fig_yield_curve_snapshot.png  (current curve shape)

Caveat  : THREEFYTP10 is a MODEL ESTIMATE (Adrian-Crump-Moench); other models
          (Kim-Wright) give different levels. Report the level AND the model
          dependence. See notes/provenance.md.

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
SRC = f"Source: FRED (Treasury constant maturity, TIPS, ACM term premium). Compiled {RETRIEVED}."


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def wide(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot the long panel to a date-indexed wide frame keyed by label."""
    w = df.pivot_table(index="date", columns="label", values="value", aggfunc="last")
    w.index = pd.to_datetime(w.index)
    return w.sort_index()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PROCESSED / "treasury_curve.csv")
    w = wide(df)

    # --- Decomposition (a): nominal = real + breakeven (daily, then resampled) ---
    decomp = w[["nominal_10y", "real_10y", "breakeven_10y"]].dropna()
    # Residual is the small basis between CMT nominal and (TIPS real + breakeven);
    # FRED's breakeven IS nominal - real, so this closes to ~0 -- a sanity check.
    decomp = decomp.assign(check_residual=decomp["nominal_10y"]
                           - decomp["real_10y"] - decomp["breakeven_10y"])

    # --- Decomposition (b): expectations vs term premium ---
    tp = w[["nominal_10y", "term_premium_10y"]].dropna()
    tp = tp.assign(expectations_10y=tp["nominal_10y"] - tp["term_premium_10y"])

    # --- Latest snapshot ---
    latest_n = w["nominal_10y"].dropna()
    latest_r = w["real_10y"].dropna()
    latest_b = w["breakeven_10y"].dropna()
    latest_tp = w["term_premium_10y"].dropna()
    snap = {
        "nominal_10y": latest_n.iloc[-1],
        "real_10y": latest_r.iloc[-1],
        "breakeven_10y": latest_b.iloc[-1],
        "term_premium_10y": latest_tp.iloc[-1],
        "expectations_10y": latest_n.iloc[-1] - latest_tp.iloc[-1],
    }

    # Term-premium regime means: 2010-2019 (QE era) vs 2020+ vs last 90 obs.
    tp_series = w["term_premium_10y"].dropna()
    tp_2010s = tp_series[(tp_series.index >= "2010-01-01") & (tp_series.index < "2020-01-01")].mean()
    tp_2020s = tp_series[tp_series.index >= "2020-01-01"].mean()
    tp_recent = tp_series.tail(90).mean()

    # --- Summary table ---
    rows = [
        ("snapshot", "Nominal 10y yield", round(snap["nominal_10y"], 2), "%"),
        ("snapshot", "  = Real (TIPS) 10y", round(snap["real_10y"], 2), "%"),
        ("snapshot", "  + Breakeven inflation 10y", round(snap["breakeven_10y"], 2), "%"),
        ("snapshot", "Term premium 10y (ACM, model est.)", round(snap["term_premium_10y"], 2), "%"),
        ("snapshot", "  Expectations component (nominal - TP)", round(snap["expectations_10y"], 2), "%"),
        ("term_premium_regime", "Mean TP 2010-2019 (QE era)", round(tp_2010s, 2), "%"),
        ("term_premium_regime", "Mean TP 2020-present", round(tp_2020s, 2), "%"),
        ("term_premium_regime", "Mean TP last 90 obs", round(tp_recent, 2), "%"),
    ]
    table = pd.DataFrame(rows, columns=["section", "item", "value", "units"])
    table["retrieved"] = RETRIEVED
    table.to_csv(OUTPUT / "curve_decomposition.csv", index=False)

    # --- Console report ---
    print("=" * 70)
    print("10-YEAR TREASURY DECOMPOSITION — latest snapshot")
    print("=" * 70)
    print(f"  Nominal 10y                         {snap['nominal_10y']:6.2f} %")
    print(f"    = Real (TIPS) 10y                 {snap['real_10y']:6.2f} %")
    print(f"    + Breakeven inflation 10y         {snap['breakeven_10y']:6.2f} %")
    print(f"  (residual nominal-real-breakeven)   {decomp['check_residual'].iloc[-1]:6.2f} %  <- should be ~0")
    print(f"\n  Term premium 10y (ACM model est.)   {snap['term_premium_10y']:6.2f} %")
    print(f"    Expectations component            {snap['expectations_10y']:6.2f} %")
    print(f"\n  Term-premium regime shift (ACM 10y; turned deeply negative 2016-2021):")
    print(f"    2010-2019 (QE era) mean           {tp_2010s:6.2f} %")
    print(f"    2020-present mean                 {tp_2020s:6.2f} %")
    print(f"    last 90 obs mean                  {tp_recent:6.2f} %  <- recent level")
    print("  Reading: a POSITIVE, rising term premium => the long end is heavy for")
    print("  duration/supply reasons, not because the market forecasts a recession.")
    print("=" * 70)

    # --- Figure 1: 10y = real + breakeven, stacked area over time (2015+) ---
    d = decomp[decomp.index >= "2015-01-01"].resample("ME").last().dropna()
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.stackplot(d.index, d["real_10y"], d["breakeven_10y"],
                 labels=["Real (TIPS) 10y", "Breakeven inflation 10y"],
                 colors=["#2a6f97", "#e09f3e"], alpha=0.85)
    ax.plot(d.index, d["nominal_10y"], color="black", lw=1.3, label="Nominal 10y")
    ax.set_title("The 10-year yield, decomposed: real yield + inflation compensation")
    ax.set_ylabel("%")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_curve_decomposition.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: term-premium regime shift (the headline) ---
    t = tp_series[tp_series.index >= "2005-01-01"].resample("ME").last().dropna()
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.axhline(0, color="grey", lw=0.8)
    ax.fill_between(t.index, t.values, 0, where=(t.values >= 0), color="#c1121f", alpha=0.5,
                    label="positive term premium")
    ax.fill_between(t.index, t.values, 0, where=(t.values < 0), color="#2a6f97", alpha=0.5,
                    label="negative term premium")
    ax.plot(t.index, t.values, color="black", lw=1.0)
    ax.set_title("10-year term premium: from negative (QE era) to positive (now)")
    ax.set_ylabel("Term premium, % (ACM model — estimate, not observed)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_term_premium_regime.png", dpi=150)
    plt.close(fig)

    # --- Figure 3: current yield-curve snapshot (the shape) ---
    tenors = [("nominal_3mo", 0.25), ("nominal_2y", 2), ("nominal_5y", 5),
              ("nominal_10y", 10), ("nominal_30y", 30)]
    xs, ys = [], []
    for label, yrs in tenors:
        s = w[label].dropna()
        if not s.empty:
            xs.append(yrs)
            ys.append(s.iloc[-1])
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(xs, ys, marker="o", color="#2a6f97", lw=2)
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:.2f}%", (x, y), textcoords="offset points", xytext=(0, 8),
                    fontsize=8, ha="center")
    ax.set_title(f"US Treasury yield curve — latest ({latest_n.index[-1].date()})")
    ax.set_xlabel("Maturity (years)")
    ax.set_ylabel("Yield, %")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_yield_curve_snapshot.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/curve_decomposition.csv + 3 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
