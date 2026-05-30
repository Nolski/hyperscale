#!/usr/bin/env python3
"""
analyze_hyperscaler_depreciation.py -- Analysis step (the Burry/Chanos test).

Question: are hyperscalers FLATTERING EARNINGS by stretching the assumed useful life
of servers (longer life -> less annual depreciation -> higher reported profit)?

HONEST FINDING (why this script is structured the way it is): you cannot cleanly
re-derive useful-life gaming from aggregate XBRL, because (a) several firms stop
reporting gross PP&E under a stable tag (Meta after FY2018, Alphabet after FY2024),
and (b) rapid capex growth mechanically lowers any depreciation/PP&E ratio, so the
fastest builders look like they SHORTENED lives even when they disclosed EXTENSIONS.
So the evidence hierarchy is:

  1. PRIMARY -- the firms' OWN DISCLOSED useful-life changes (manual reference). These
     are explicit and material: Microsoft 4->6 yrs (~+$3.7B FY23 operating income),
     Alphabet 4->6 yrs (~+$3.4B 2023), plus Amazon/Meta extensions -- and Amazon then
     SHORTENED some lives in 2024 (counter-move).
  2. CORROBORATION -- the raw DEPRECIATION-EXPENSE series. The fingerprint of an
     extension is depreciation FALLING (or flat) in a year the asset base GREW.
     Alphabet FY2023 is the textbook case: depreciation fell $13.5B->$11.9B.
  3. SUGGESTIVE ONLY -- the implied depreciable life (gross PP&E / depreciation), shown
     for the firms where it is computable, explicitly flagged as growth-confounded.

Reads   : data/processed/hyperscaler_depreciation.csv
          data/raw/manual/server_useful_life_changes.csv
Writes  : output/depreciation_analysis.csv
          output/fig_depreciation_expense.png
          output/fig_implied_useful_life.png

NOTE: a longer useful life is not automatically wrong -- it is only flattering IF the
hardware does not actually last that long. The live controversy is whether 6 yrs is
realistic for AI GPUs run hot 24/7. The data here cannot settle physical longevity.

Re-runnable: reads data/processed/ + manual CSV, overwrites output/. No network.
"""

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "raw" / "manual" / "server_useful_life_changes.csv"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
BN = 1e9
SRC = f"Source: SEC EDGAR XBRL (10-K). Useful-life changes: company disclosures (Tier-2). Compiled {RETRIEVED}."

# Implied-life is only computable (stable gross-PP&E tag, enough history) for these.
CLEAN_LIFE_TICKERS = ["MSFT", "AMZN", "ORCL"]
EXPENSE_TICKERS = ["MSFT", "GOOGL", "AMZN", "META", "ORCL"]


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.5, color="grey")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PROCESSED / "hyperscaler_depreciation.csv")
    changes = pd.read_csv(MANUAL, comment="#")

    df = df.sort_values(["ticker", "period_end"]).copy()
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["year"] = df["period_end"].dt.year
    df["chart_year"] = df["year"].where(df["period_end"].dt.month != 1, df["year"] - 1)

    # YoY changes (within firm) for the fingerprint test.
    df["dep_yoy"] = df.groupby("ticker")["depreciation_amort_usd"].diff()
    df["gross_yoy"] = df.groupby("ticker")["ppe_gross_usd"].diff()
    # Fingerprint: depreciation fell MATERIALLY (> $0.2B) while the gross asset base rose.
    # The $0.2B floor screens out rounding-level wiggles (e.g. NVIDIA's tiny PP&E).
    df["fingerprint"] = (df["dep_yoy"] < -0.2e9) & (df["gross_yoy"] > 0)

    # Implied life (suggestive only).
    df["prev_gross"] = df.groupby("ticker")["ppe_gross_usd"].shift(1)
    df["avg_gross"] = df[["ppe_gross_usd", "prev_gross"]].mean(axis=1)
    df["deprec_rate"] = df["depreciation_amort_usd"] / df["avg_gross"]
    df["implied_life_years"] = 1.0 / df["deprec_rate"]

    # --- PRIMARY evidence: disclosed changes (echo to output) ---
    disclosed = changes.copy()
    disclosed["section"] = "disclosed_useful_life_change"

    # --- CORROBORATION: fingerprint years (depreciation fell as assets grew) ---
    fp = df[df["fingerprint"]].copy()
    fp_rows = [{
        "section": "depreciation_fingerprint",
        "ticker": r["ticker"], "company": r["company"], "fiscal_year": int(r["year"]),
        "depreciation_usd_bn": round(r["depreciation_amort_usd"] / BN, 2),
        "dep_change_usd_bn": round(r["dep_yoy"] / BN, 2),
        "gross_ppe_change_usd_bn": round(r["gross_yoy"] / BN, 2),
        "note": "depreciation FELL while gross PP&E rose — consistent with a life extension",
    } for _, r in fp.iterrows()]

    # --- SUGGESTIVE: implied life early vs latest, computable firms only ---
    life_rows = []
    valid = df[(df["deprec_rate"] > 0) & df["implied_life_years"].notna()
               & df["ppe_gross_usd"].notna()]
    for tkr in CLEAN_LIFE_TICKERS:
        f = valid[(valid.ticker == tkr) & (valid.chart_year >= 2017)].sort_values("chart_year")
        if f.empty:
            continue
        early, late = f.iloc[0], f.iloc[-1]
        life_rows.append({
            "section": "implied_life_suggestive",
            "ticker": tkr, "company": late["company"],
            "early_year": int(early["chart_year"]),
            "early_implied_life_yrs": round(early["implied_life_years"], 1),
            "latest_year": int(late["chart_year"]),
            "latest_implied_life_yrs": round(late["implied_life_years"], 1),
            "change_yrs": round(late["implied_life_years"] - early["implied_life_years"], 1),
        })

    out = pd.concat([
        disclosed, pd.DataFrame(fp_rows), pd.DataFrame(life_rows)
    ], ignore_index=True)
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "depreciation_analysis.csv", index=False)

    # --- Console report ---
    print("=" * 84)
    print("ARE EARNINGS FLATTERED BY LONGER SERVER LIVES?  (evidence hierarchy)")
    print("=" * 84)
    print("\n[1] PRIMARY — disclosed useful-life changes (company 10-Ks; Tier-2, verify text):")
    for _, r in changes.iterrows():
        impact = (f", ~{r['disclosed_income_impact_usd_bn']:+.1f}B op income"
                  if pd.notna(r["disclosed_income_impact_usd_bn"]) else "")
        print(f"  {r['company']:16s} FY{int(r['change_fiscal_year'])}: "
              f"{r['asset_class']} {r['old_years']:g}->{r['new_years']:g}y "
              f"({r['direction']}{impact})")

    print("\n[2] CORROBORATION — years depreciation FELL while gross PP&E rose (fingerprint):")
    if fp_rows:
        for r in fp_rows:
            print(f"  {r['company']:16s} FY{r['fiscal_year']}: depreciation "
                  f"{r['dep_change_usd_bn']:+.1f}B to ${r['depreciation_usd_bn']:.1f}B "
                  f"while gross PP&E {r['gross_ppe_change_usd_bn']:+.1f}B")
    else:
        print("  (none detected)")

    print("\n[3] SUGGESTIVE ONLY — implied life (gross PP&E ÷ deprec.), growth-confounded:")
    for r in life_rows:
        print(f"  {r['company']:16s} {r['early_implied_life_yrs']:.1f}y ({r['early_year']}) "
              f"-> {r['latest_implied_life_yrs']:.1f}y ({r['latest_year']})  "
              f"({r['change_yrs']:+.1f}y)")
    print("  (Meta/Alphabet excluded: gross-PP&E tag gaps + fast capex growth confound the ratio.)")
    print("=" * 84)
    print("Bottom line: the disclosures confirm the buildout's incumbents lengthened server")
    print("lives and booked billions in extra operating income — real and material. The")
    print("aggregate ratios can't independently prove it (growth dominates), and longer life")
    print("is only 'flattering' if AI hardware truly lasts that long — which is contested.")
    print("=" * 84)

    # --- Figure 1: depreciation expense over time (shows the dips/fingerprints) ---
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    colors = {"MSFT": "#2a6f97", "GOOGL": "#c1121f", "AMZN": "#e09f3e",
              "META": "#2a9d8f", "ORCL": "#9d4edd"}
    for tkr in EXPENSE_TICKERS:
        f = df[(df.ticker == tkr) & (df.chart_year >= 2015) & (df.chart_year <= 2025)]
        f = f.dropna(subset=["depreciation_amort_usd"]).sort_values("chart_year")
        if f.empty:
            continue
        ax.plot(f["chart_year"], f["depreciation_amort_usd"] / BN, marker="o", lw=1.8,
                color=colors.get(tkr), label=f["company"].iloc[0])
        # mark fingerprint years
        fpf = f[f["fingerprint"]]
        ax.scatter(fpf["chart_year"], fpf["depreciation_amort_usd"] / BN,
                   s=120, facecolors="none", edgecolors="black", linewidths=1.6, zorder=5)
    ax.set_title("Annual depreciation expense (○ = year it FELL as assets grew — extension fingerprint)")
    ax.set_xlabel("Year (calendar-aligned)")
    ax.set_ylabel("Depreciation / D&A, USD billion")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / "fig_depreciation_expense.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: implied life, computable firms, with caveat ---
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    for tkr in CLEAN_LIFE_TICKERS:
        f = valid[(valid.ticker == tkr) & (valid.chart_year >= 2015) & (valid.chart_year <= 2025)]
        f = f.sort_values("chart_year")
        if f.empty:
            continue
        ax.plot(f["chart_year"], f["implied_life_years"], marker="o", lw=1.8,
                color=colors.get(tkr), label=f["company"].iloc[0])
    ax.set_title("Implied depreciable life (gross PP&E ÷ depreciation) — suggestive, not proof")
    ax.set_xlabel("Year (calendar-aligned)")
    ax.set_ylabel("Implied blended life, years")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax.annotate("Blended (incl. buildings); growth-confounded; Meta/Alphabet omitted for tag gaps.\n"
                "Read alongside the disclosed changes, not on its own.",
                xy=(0.02, 0.04), xycoords="axes fraction", fontsize=7, color="grey")
    caption(ax)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / "fig_implied_useful_life.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/depreciation_analysis.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
