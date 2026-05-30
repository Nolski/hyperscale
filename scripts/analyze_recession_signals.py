#!/usr/bin/env python3
"""
analyze_recession_signals.py -- Analysis step.

Answers: "Did the bond market's recession signal fire, and is it firing now?"
Two parts:

  1. EVENT STUDY -- locate every yield-curve inversion (T10Y2Y < 0) since 1976,
     match each to the next NBER recession (USREC), and report the LEAD TIME
     (months from first inversion to recession start). This documents both the
     curve's historical track record AND this cycle's anomaly: the deepest, longest
     inversion since the 1980s that (so far) un-inverted WITHOUT a recession.

  2. CURRENT DASHBOARD -- the live readings of the collapse-signal battery:
     curve spreads, smoothed recession probability, real-time Sahm rule, jobless
     claims, unemployment. Shows whether the "collapse" indicators are actually lit.

The point for the wider question: the classic recession signals are benign right
now, so a heavy long end is better explained by term premium (see
analyze_curve_decomposition.py) than by a priced-in growth collapse.

Reads   : data/processed/treasury_curve.csv, data/processed/market_stress.csv
Writes  : output/recession_signals.csv           (inversion episodes + current dashboard)
          output/fig_inversions_vs_recessions.png (curve spread w/ NBER shading)
          output/fig_recession_dashboard.png      (current signal battery)

Caveat  : ~7 post-war recessions -> small N. The curve's record is suggestive,
          not a law; "this time" can differ. See notes/provenance.md.

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
SRC = f"Sources: FRED (T10Y2Y, T10Y3M, USREC, Sahm rule, recession prob). Compiled {RETRIEVED}."


def caption(ax) -> None:
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=7, color="grey")


def series(df: pd.DataFrame, label: str) -> pd.Series:
    s = df[df.label == label].copy()
    s["date"] = pd.to_datetime(s["date"])
    return s.set_index("date")["value"].sort_index()


def recession_episodes(usrec: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Contiguous spans where USREC == 1, as (start, end) timestamps."""
    rec = usrec == 1
    episodes, start = [], None
    for date, flag in rec.items():
        if flag and start is None:
            start = date
        elif not flag and start is not None:
            episodes.append((start, prev))
            start = None
        prev = date
    if start is not None:
        episodes.append((start, prev))
    return episodes


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    curve = pd.read_csv(PROCESSED / "treasury_curve.csv")
    stress = pd.read_csv(PROCESSED / "market_stress.csv")

    t10y2y = series(curve, "spread_10y_2y")
    t10y3m = series(curve, "spread_10y_3mo")
    usrec = series(stress, "nber_recession")
    rec_prob = series(stress, "recession_prob_12m")
    sahm = series(stress, "sahm_realtime")
    claims = series(stress, "initial_claims")
    unrate = series(stress, "unemployment_rate")

    recessions = recession_episodes(usrec)

    # --- Event study: find inversion episodes in T10Y2Y, match to next recession ---
    inverted = t10y2y < 0
    episodes, start = [], None
    prev = t10y2y.index[0]
    for date, flag in inverted.items():
        if flag and start is None:
            start = date
        elif not flag and start is not None:
            episodes.append((start, prev))
            start = None
        prev = date
    ongoing_inversion = start is not None
    if ongoing_inversion:
        episodes.append((start, prev))

    rec_starts = [r[0] for r in recessions]
    ep_rows = []
    for inv_start, inv_end in episodes:
        # Ignore trivially short inversions (< ~10 trading days of noise).
        if (inv_end - inv_start).days < 14:
            continue
        next_rec = next((rs for rs in rec_starts if rs >= inv_start), None)
        lead_months = round((next_rec - inv_start).days / 30.44, 1) if next_rec is not None else None
        ep_rows.append({
            "section": "inversion_episode",
            "inversion_start": inv_start.date().isoformat(),
            "inversion_end": inv_end.date().isoformat(),
            "inversion_days": (inv_end - inv_start).days,
            "min_spread_pct": round(t10y2y.loc[inv_start:inv_end].min(), 2),
            "next_recession_start": next_rec.date().isoformat() if next_rec is not None else "none yet",
            "lead_time_months": lead_months,
        })

    # --- Current dashboard ---
    dash_rows = [
        ("dashboard", "T10Y2Y spread (pp)", round(t10y2y.iloc[-1], 2),
         "inverted (<0) = classic signal" if t10y2y.iloc[-1] < 0 else "positive / un-inverted"),
        ("dashboard", "T10Y3M spread (pp)", round(t10y3m.iloc[-1], 2),
         "inverted (<0)" if t10y3m.iloc[-1] < 0 else "positive / un-inverted"),
        ("dashboard", "Recession prob 12m (%)", round(rec_prob.iloc[-1], 2),
         "elevated (>30%)" if rec_prob.iloc[-1] > 30 else "low"),
        ("dashboard", "Sahm rule (pp)", round(sahm.iloc[-1], 2),
         "TRIGGERED (>=0.50)" if sahm.iloc[-1] >= 0.50 else "below 0.50 trigger"),
        ("dashboard", "Unemployment rate (%)", round(unrate.iloc[-1], 2), "level"),
        ("dashboard", "Initial jobless claims", int(claims.iloc[-1]),
         "elevated (>300k)" if claims.iloc[-1] > 300_000 else "low/normal"),
    ]

    out = pd.DataFrame(ep_rows + [
        {"section": s, "inversion_start": item, "min_spread_pct": val, "next_recession_start": note}
        for s, item, val, note in dash_rows
    ])
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "recession_signals.csv", index=False)

    # --- Console report ---
    print("=" * 72)
    print("YIELD-CURVE INVERSIONS (T10Y2Y < 0) vs NBER RECESSIONS")
    print("=" * 72)
    print(f"  {'inversion start':>16s} {'days':>6s} {'min':>7s} {'next recession':>16s} {'lead mo':>8s}")
    for r in ep_rows:
        lead = f"{r['lead_time_months']}" if r["lead_time_months"] is not None else "—"
        print(f"  {r['inversion_start']:>16s} {r['inversion_days']:6d} "
              f"{r['min_spread_pct']:7.2f} {r['next_recession_start']:>16s} {lead:>8s}")
    leads = [r["lead_time_months"] for r in ep_rows if r["lead_time_months"] is not None]
    if leads:
        print(f"\n  Historical lead time inversion->recession: "
              f"{min(leads):.0f}-{max(leads):.0f} months (median {pd.Series(leads).median():.0f}).")
    if ongoing_inversion:
        print("  NOTE: an inversion is ongoing as of the latest data.")
    else:
        print("  NOTE: the curve is currently UN-INVERTED.")

    print("\n" + "=" * 72)
    print("CURRENT RECESSION-SIGNAL DASHBOARD")
    print("=" * 72)
    for _, item, val, note in dash_rows:
        print(f"  {item:28s} {str(val):>12s}   {note}")
    print("=" * 72)

    # --- Figure 1: curve spread with NBER recession shading ---
    s = t10y2y[t10y2y.index >= "1976-06-01"]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.axhline(0, color="black", lw=0.8)
    ax.plot(s.index, s.values, color="#2a6f97", lw=1.0, label="10y − 2y spread")
    for r_start, r_end in recessions:
        if r_end >= s.index[0]:
            ax.axvspan(max(r_start, s.index[0]), r_end, color="grey", alpha=0.25)
    ax.set_title("Yield-curve inversions precede recessions (grey = NBER recessions)")
    ax.set_ylabel("10y − 2y spread, percentage points")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_inversions_vs_recessions.png", dpi=150)
    plt.close(fig)

    # --- Figure 2: current dashboard, normalized "is it lit?" view ---
    gauges = [
        ("10y−2y spread", t10y2y.iloc[-1], 0.0, "below 0 = signal"),
        ("10y−3mo spread", t10y3m.iloc[-1], 0.0, "below 0 = signal"),
        ("Recession prob 12m (%)", rec_prob.iloc[-1], 30.0, "above 30 = signal"),
        ("Sahm rule", sahm.iloc[-1], 0.50, "above 0.50 = signal"),
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    names = [g[0] for g in gauges]
    vals = [g[1] for g in gauges]
    thresh = [g[2] for g in gauges]
    # color red if the signal is "lit" (spreads below 0; others above threshold)
    lit = [vals[0] < thresh[0], vals[1] < thresh[1], vals[2] > thresh[2], vals[3] > thresh[3]]
    colors = ["#c1121f" if l else "#2a9d8f" for l in lit]
    ax.barh(names, vals, color=colors)
    for i, (v, t) in enumerate(zip(vals, thresh)):
        ax.plot([t, t], [i - 0.4, i + 0.4], color="black", lw=1.5, ls="--")
        ax.text(v, i, f" {v:.2f}", va="center", fontsize=9)
    ax.set_title("Current recession-signal battery (dashed = trigger; green = not lit)")
    ax.set_xlabel("value (units vary by row — see labels)")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_recession_dashboard.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/recession_signals.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
